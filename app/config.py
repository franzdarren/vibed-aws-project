import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")

    # AWS
    AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
    S3_BUCKET = os.environ.get("S3_BUCKET_NAME")
    DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "photos")

    # Uploads
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB cap per upload
    ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}
    # Longest side (px) a photo is downscaled to before storage. Set to 0 to
    # store originals untouched.
    RESIZE_MAX_DIMENSION = int(os.environ.get("RESIZE_MAX_DIMENSION", 1600))

    # Classifier
    CLASSIFIER_MODEL = os.environ.get("CLASSIFIER_MODEL", "google/mobilenet_v2_1.0_224")
    CLASSIFIER_TOP_K = int(os.environ.get("CLASSIFIER_TOP_K", 5))
    CLASSIFIER_MIN_SCORE = float(os.environ.get("CLASSIFIER_MIN_SCORE", 0.15))
