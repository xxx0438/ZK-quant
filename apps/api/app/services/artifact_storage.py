"""S3-compatible signed-URL upload for model artifacts.

Works with AWS S3, Cloudflare R2, or any S3-compatible object store.
Quants get a one-shot presigned PUT URL, upload, then call /submit.
"""
import hashlib
import os
from datetime import timedelta
from typing import Optional

import boto3
from botocore.client import Config

_s3 = None

def _client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),  # for R2: https://<acct>.r2.cloudflarestorage.com
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            region_name=os.getenv("S3_REGION", "auto"),
            config=Config(signature_version="s3v4"),
        )
    return _s3

BUCKET = os.getenv("S3_ARTIFACT_BUCKET", "echo-model-artifacts")

def presigned_put_url(key: str, expires_in: int = 600) -> str:
    """Generate a one-shot upload URL valid for `expires_in` seconds."""
    return _client().generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": "application/octet-stream"},
        ExpiresIn=expires_in,
    )

def presigned_get_url(key: str, expires_in: int = 600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires_in,
    )

async def verify_uploaded_sha256(key: str, expected_sha256: str) -> bool:
    """Download object and verify its SHA256 matches what the quant claimed."""
    obj = _client().get_object(Bucket=BUCKET, Key=key)
    h = hashlib.sha256()
    for chunk in obj["Body"].iter_chunks(chunk_size=1024 * 1024):
        h.update(chunk)
    return h.hexdigest() == expected_sha256.lower()
