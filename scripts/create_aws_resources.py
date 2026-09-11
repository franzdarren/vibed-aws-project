"""One-time setup helper: creates the S3 bucket and DynamoDB table this app
needs, using the same env vars as the Flask app (see .env.example).

Usage:
    python scripts/create_aws_resources.py

Requires AWS credentials to be available (env vars, ~/.aws/credentials, or an
IAM role) with permission to create S3 buckets and DynamoDB tables.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()

REGION = os.environ.get("AWS_REGION", "us-east-1")
BUCKET = os.environ.get("S3_BUCKET_NAME")
TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "photos")


def create_bucket():
    if not BUCKET:
        print("S3_BUCKET_NAME is not set in .env — skipping bucket creation.")
        return

    s3 = boto3.client("s3", region_name=REGION)
    try:
        if REGION == "us-east-1":
            s3.create_bucket(Bucket=BUCKET)
        else:
            s3.create_bucket(
                Bucket=BUCKET,
                CreateBucketConfiguration={"LocationConstraint": REGION},
            )
        print(f"Created S3 bucket: {BUCKET}")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"S3 bucket already exists: {BUCKET}")
        else:
            raise


def create_table():
    dynamodb = boto3.client("dynamodb", region_name=REGION)
    try:
        dynamodb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "photo_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "photo_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",  # free-tier friendly, no capacity planning
        )
        print(f"Creating DynamoDB table: {TABLE} (waiting for it to become active)…")
        dynamodb.get_waiter("table_exists").wait(TableName=TABLE)
        print(f"Table active: {TABLE}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceInUseException":
            print(f"DynamoDB table already exists: {TABLE}")
        else:
            raise


if __name__ == "__main__":
    if not BUCKET:
        print("Warning: S3_BUCKET_NAME is not set — copy .env.example to .env and fill it in.")
    create_bucket()
    create_table()
    print("Done.")
    sys.exit(0)
