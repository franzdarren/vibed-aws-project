import io
import re
import uuid
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from werkzeug.utils import secure_filename

from .services.classifier import classify_image
from .services.dynamo_service import (
    create_photo,
    delete_photo as db_delete_photo,
    get_photo,
    list_folders,
    list_photos,
    update_photo,
)
from .services.image_service import resize_image
from .services.s3_service import delete_photo as s3_delete_photo, upload_photo

bp = Blueprint("main", __name__)

# Shape of the keys upload_photo() generates (photos/<uuid4>.<ext>). Used to
# sanity-check keys the client sends back for /uploads/discard, since at that
# point there's no DynamoDB record yet to look the key up against.
_UPLOAD_KEY_RE = re.compile(
    r"^photos/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|jpeg|png)$"
)


def _allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in current_app.config["ALLOWED_EXTENSIONS"]
    )


# ---------------------------------------------------------------------------
# Gallery
# ---------------------------------------------------------------------------

@bp.route("/")
def gallery():
    tag = request.args.get("tag") or None
    folder = request.args.get("folder") or None
    photos = list_photos(tag=tag, folder=folder)
    folders = list_folders()
    return render_template(
        "index.html", photos=photos, folders=folders, active_tag=tag, active_folder=folder
    )


@bp.route("/photos", methods=["GET"])
def photos_filtered():
    # Same view as "/", exposed at /photos?tag=...&folder=... per the spec.
    return gallery()


# ---------------------------------------------------------------------------
# Upload + classify (this is the core flow — everything else builds on it)
# ---------------------------------------------------------------------------

@bp.route("/upload", methods=["GET"])
def upload_form():
    folders = list_folders()
    return render_template("upload.html", folders=folders)


@bp.route("/upload", methods=["POST"])
def upload_and_classify():
    """Classify the image and store it in S3. Does NOT touch DynamoDB yet —
    the user still has to confirm/edit tags and pick folders (POST /photos
    is what actually saves the record).
    """
    if "photo" not in request.files:
        return jsonify({"error": "No file part named 'photo'"}), 400

    file = request.files["photo"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "Only .jpg/.jpeg/.png files are allowed"}), 400

    image_bytes = file.read()
    filename = secure_filename(file.filename)

    image_bytes, content_type = resize_image(
        image_bytes,
        max_dimension=current_app.config["RESIZE_MAX_DIMENSION"],
        content_type=file.mimetype,
    )

    try:
        predictions = classify_image(
            image_bytes,
            model_name=current_app.config["CLASSIFIER_MODEL"],
            top_k=current_app.config["CLASSIFIER_TOP_K"],
            min_score=current_app.config["CLASSIFIER_MIN_SCORE"],
        )
    except Exception as exc:  # noqa: BLE001 - surface classifier errors to the client
        current_app.logger.exception("Classification failed")
        return jsonify({"error": f"Classification failed: {exc}"}), 500

    try:
        s3_result = upload_photo(io.BytesIO(image_bytes), filename=filename, content_type=content_type)
    except Exception as exc:  # noqa: BLE001 - surface S3 errors to the client
        current_app.logger.exception("S3 upload failed")
        return jsonify({"error": f"S3 upload failed: {exc}"}), 500

    return jsonify(
        {
            "s3_key": s3_result["key"],
            "s3_url": s3_result["url"],
            "ai_suggested_tags": [p["label"] for p in predictions],
            "predictions": predictions,
        }
    )


@bp.route("/uploads/discard", methods=["POST"])
def discard_upload():
    """Delete an S3 object from a classify-but-never-saved upload.

    Covers the gap in the two-step handshake: /upload puts the file in S3
    before the user has confirmed anything, so if they change their mind,
    pick a different file, or just close the tab, that object would
    otherwise sit in the bucket forever with no DynamoDB record pointing to
    it. Called from the frontend's Discard button, when a new file replaces
    an unsaved one, and via sendBeacon on page unload.
    """
    data = request.get_json(silent=True) or {}
    key = data.get("s3_key", "")

    if not _UPLOAD_KEY_RE.match(key):
        return jsonify({"error": "Invalid or missing s3_key"}), 400

    try:
        s3_delete_photo(key)
    except Exception:  # noqa: BLE001 - best-effort cleanup, not user-facing critical
        current_app.logger.exception("Failed to discard unsaved upload %s", key)
        return jsonify({"error": "Failed to delete from S3"}), 500

    return jsonify({"discarded": key})


# ---------------------------------------------------------------------------
# Photo records (DynamoDB)
# ---------------------------------------------------------------------------

@bp.route("/photos", methods=["POST"])
def save_photo():
    """Save the user-confirmed tags/folders as a new DynamoDB record."""
    data = request.get_json(silent=True) or {}

    if not data.get("s3_url") or not data.get("s3_key"):
        return jsonify({"error": "s3_url and s3_key are required (upload the photo first)"}), 400

    record = {
        "photo_id": str(uuid.uuid4()),
        "s3_key": data["s3_key"],
        "s3_url": data["s3_url"],
        "tags": data.get("tags", []),
        "folders": data.get("folders", []),
        "ai_suggested_tags": data.get("ai_suggested_tags", []),
        "upload_date": datetime.now(timezone.utc).isoformat(),
    }
    create_photo(record)
    return jsonify(record), 201


@bp.route("/photos/<photo_id>", methods=["GET"])
def photo_detail(photo_id):
    photo = get_photo(photo_id)
    if not photo:
        abort(404)
    folders = list_folders()
    return render_template("detail.html", photo=photo, folders=folders)


@bp.route("/photos/<photo_id>", methods=["PUT"])
def update_photo_route(photo_id):
    if not get_photo(photo_id):
        return jsonify({"error": "Photo not found"}), 404

    data = request.get_json(silent=True) or {}
    updated = update_photo(photo_id, tags=data.get("tags"), folders=data.get("folders"))
    return jsonify(updated)


@bp.route("/photos/<photo_id>", methods=["DELETE"])
def delete_photo_route(photo_id):
    photo = get_photo(photo_id)
    if not photo:
        return jsonify({"error": "Photo not found"}), 404

    try:
        s3_delete_photo(photo["s3_key"])
    except Exception:  # noqa: BLE001 - don't let an S3 hiccup block DB cleanup
        current_app.logger.exception("Failed to delete S3 object; deleting DB record anyway")

    db_delete_photo(photo_id)
    return jsonify({"deleted": photo_id})
