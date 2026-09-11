"""S3 storage for photo files.

DynamoDB items are capped at 400KB, so the actual image bytes live in S3;
DynamoDB only stores the resulting URL/key alongside tags and folders.
"""

import uuid

import boto3
from flask import current_app


def _client():
    return boto3.client("s3", region_name=current_app.config["AWS_REGION"])


def upload_photo(file_obj, filename, content_type=None):
    """Upload a file-like object to S3 and return its key + public URL."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    key = f"photos/{uuid.uuid4()}.{ext}"

    extra_args = {"ContentType": content_type} if content_type else {}
    _client().upload_fileobj(
        file_obj,
        current_app.config["S3_BUCKET"],
        key,
        ExtraArgs=extra_args,
    )

    url = (
        f"https://{current_app.config['S3_BUCKET']}.s3."
        f"{current_app.config['AWS_REGION']}.amazonaws.com/{key}"
    )
    return {"key": key, "url": url}


def delete_photo(key):
    _client().delete_object(Bucket=current_app.config["S3_BUCKET"], Key=key)
