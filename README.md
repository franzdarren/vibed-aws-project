# AI Photo Tagger

just for fun little project that uses MobileNetV2 from [asdasd](https://huggingface.co/google/mobilenet_v2_1.0_224) to suggest tags for uploaded photos. You confirm/edit the tags and file each photo into one or more
overlapping folders. Photos live in S3, metadata (tags/folders) lives in DynamoDB.

everything else below written by AI.

## Project layout

```
ai-photo-tagger/
  run.py                     entrypoint (flask run / python run.py)
  app/
    __init__.py              create_app()
    config.py                env-driven config
    routes.py                all routes (gallery, upload, photo CRUD)
    services/
      classifier.py          MobileNetV2 via Hugging Face transformers
      image_service.py       downscale photos before storage (optional)
      s3_service.py           upload/delete photo files in S3
      dynamo_service.py      read/write photo records in DynamoDB
    templates/                Jinja templates (gallery, upload, detail)
    static/                   CSS + vanilla JS (no frontend framework)
  scripts/
    create_aws_resources.py  one-time S3 bucket + DynamoDB table setup
```

## Setup

1. **Python env**
   ```
   python -m venv venv
   venv\Scripts\activate          # Windows
   pip install -r requirements.txt
   ```
   Note: `torch` + `transformers` is a sizeable install (~1-2GB) — that's
   expected, it's the ML runtime for the classifier.

2. **Configure**
   ```
   copy .env.example .env
   ```
   Fill in `S3_BUCKET_NAME` (must be globally unique) and AWS credentials
   (or leave the key/secret blank if you have `aws configure` set up, or
   this later runs on an EC2 instance with an IAM role attached).

3. **Create the AWS resources** (bucket + table). Either run the helper:
   ```
   python scripts/create_aws_resources.py
   ```
   or create them by hand in the console:
   - **S3**: a bucket named `S3_BUCKET_NAME`, same region as `AWS_REGION`.
   - **DynamoDB**: a table named `DYNAMODB_TABLE_NAME`, partition key
     `photo_id` (type String), on-demand ("Pay per request") capacity.

4. **IAM permissions** — whatever credentials the app runs with need:
   - S3: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on
     `arn:aws:s3:::your-bucket-name/*`
   - DynamoDB: `dynamodb:PutItem`, `dynamodb:GetItem`, `dynamodb:UpdateItem`,
     `dynamodb:DeleteItem`, `dynamodb:Scan` on the table's ARN

5. **Run it**
   ```
   python run.py
   ```
   Visit http://localhost:5000/upload first — that's the core flow
   (upload → classify → S3) everything else depends on. Then confirm tags
   and folders to save the record, and check it shows up on the gallery
   at http://localhost:5000/.

## How the upload flow works

`POST /upload` is a two-step handshake with the frontend, on purpose:

1. `POST /upload` — receives the image, runs it through MobileNetV2, uploads
   the original file to S3, and returns the suggested tags + S3 url/key.
   **Nothing is written to DynamoDB yet.**
2. User reviews/edits tags and picks folders in the browser.
3. `POST /photos` — writes the confirmed record (tags, folders, S3
   pointer) to DynamoDB. This is the point a photo actually "exists" in the
   library.

This split matters: classification and storage are cheap/idempotent, but you
don't want a half-confirmed record (wrong tags, no folder) landing in the
database before the user has actually looked at it.

## Routes

| Route | Method | What it does |
|---|---|---|
| `/` | GET | Gallery grid, folder sidebar, tag search |
| `/photos` | GET | Same gallery, filterable via `?tag=` / `?folder=` |
| `/upload` | GET | Upload page |
| `/upload` | POST | Classify + upload to S3 (not saved to DB) |
| `/uploads/discard` | POST | Delete a classified-but-never-saved S3 object |
| `/photos` | POST | Save confirmed record to DynamoDB |
| `/photos/<id>` | GET | Detail view (edit tags/folders, delete) |
| `/photos/<id>` | PUT | Update tags/folders |
| `/photos/<id>` | DELETE | Delete from both S3 and DynamoDB |

## Notes / gotchas

- **Model loads lazily, once per process.** The first `/upload` call after
  starting the server will be slow (downloading + loading MobileNetV2);
  subsequent calls reuse the cached pipeline. The Hugging Face model itself
  is cached on disk after the first download (`~/.cache/huggingface`).
- **Filtering uses DynamoDB Scan**, not a Query — fine for a personal
  library (hundreds/thousands of photos), since there's no partition key
  to query by tag/folder. If this ever grew into something with real
  traffic, a Global Secondary Index per tag or folder would be the next
  step.
- **EC2 Free Tier RAM (t2.micro/t3.micro = 1GB)** is tight for running
  PyTorch + a loaded model alongside Flask. If you hit OOM issues once
  deployed, consider a slightly larger instance, or swap the classifier to
  a quantized/ONNX MobileNetV2 build later — the `classify_image()`
  interface in `app/services/classifier.py` is the only place that would
  need to change.
- Deleting a photo removes it from S3 first, then DynamoDB; if the S3
  delete fails the DB record is still removed rather than leaving a photo
  the user can't get rid of (it just leaves an orphaned S3 object, which is
  a cheap tradeoff to accept for a personal project).
- **Unsaved uploads are cleaned up automatically.** Since `/upload` puts the
  file in S3 before the user confirms anything, the frontend calls
  `/uploads/discard` to delete it if they hit the Discard button, pick a
  different file without saving, or close/navigate away from the tab
  (via `sendBeacon`). None of this is bulletproof (a crashed browser skips
  it), so an orphaned `photos/*` object once in a while is still possible —
  just not the common case anymore.
- **Photos are downscaled before storage** (`RESIZE_MAX_DIMENSION` in
  `.env`, default 1600px on the longest side) to keep S3 usage down. Set it
  to `0` to store originals untouched — see `app/services/image_service.py`.
