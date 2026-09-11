"""DynamoDB read/write logic for photo metadata records.

Table schema (see scripts/create_dynamodb_table.py):
    Partition key: photo_id (String)

Item shape:
{
    "photo_id": "uuid-1234",
    "s3_key": "photos/uuid-1234.jpg",
    "s3_url": "https://your-bucket.s3.amazonaws.com/photos/uuid-1234.jpg",
    "tags": ["dog", "beach", "sunset"],
    "folders": ["Pets", "Vacations 2026"],
    "ai_suggested_tags": ["dog", "grass", "outdoor"],
    "upload_date": "2026-09-10T14:22:00+00:00"
}

Filtering by tag/folder uses a table Scan with a FilterExpression. That's
fine at personal-library scale (a few hundred/thousand items); if this ever
needed to scale up, the right move would be a Global Secondary Index per
tag/folder instead of scanning the whole table.
"""

import boto3
from boto3.dynamodb.conditions import Attr
from flask import current_app


def _table():
    dynamodb = boto3.resource("dynamodb", region_name=current_app.config["AWS_REGION"])
    return dynamodb.Table(current_app.config["DYNAMODB_TABLE"])


def create_photo(record):
    _table().put_item(Item=record)
    return record


def get_photo(photo_id):
    resp = _table().get_item(Key={"photo_id": photo_id})
    return resp.get("Item")


def update_photo(photo_id, tags=None, folders=None):
    """Partial update: only fields that are not None get overwritten."""
    set_parts = []
    expr_names = {}
    expr_values = {}

    if tags is not None:
        set_parts.append("#t = :t")
        expr_names["#t"] = "tags"
        expr_values[":t"] = tags

    if folders is not None:
        set_parts.append("#f = :f")
        expr_names["#f"] = "folders"
        expr_values[":f"] = folders

    if not set_parts:
        return get_photo(photo_id)

    _table().update_item(
        Key={"photo_id": photo_id},
        UpdateExpression="SET " + ", ".join(set_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )
    return get_photo(photo_id)


def delete_photo(photo_id):
    _table().delete_item(Key={"photo_id": photo_id})


def list_photos(tag=None, folder=None):
    """Scan all photos, optionally filtered by tag and/or folder membership."""
    table = _table()

    filter_expr = None
    if tag:
        filter_expr = Attr("tags").contains(tag)
    if folder:
        folder_expr = Attr("folders").contains(folder)
        filter_expr = folder_expr if filter_expr is None else (filter_expr & folder_expr)

    scan_kwargs = {"FilterExpression": filter_expr} if filter_expr is not None else {}

    items = []
    resp = table.scan(**scan_kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))

    items.sort(key=lambda item: item.get("upload_date", ""), reverse=True)
    return items


def list_folders():
    """Distinct folder names across all photos, for the sidebar/checkboxes."""
    folders = set()
    for item in list_photos():
        folders.update(item.get("folders", []))
    return sorted(folders)
