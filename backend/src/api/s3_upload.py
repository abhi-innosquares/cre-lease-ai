"""
S3 presigned-upload + async lease processing endpoints.

Flow:
  1. Frontend calls GET /upload/presigned?filename=foo.pdf
     → returns { url (presigned S3 PUT URL), key }
  2. Frontend PUT-uploads the file directly to S3 (progress tracked in browser)
  3. Frontend calls POST /upload/process with list of { filename, s3_key }
     → each file is processed in a background thread
     → returns { jobs: [{ job_id, filename }] }
  4. Frontend polls GET /upload/process/{job_id} to check status

NOTE: Your S3 bucket needs a CORS policy that allows PUT from the frontend origin.
Example CORS rule:
  [{ "AllowedOrigins": ["http://localhost:5173"],
     "AllowedMethods": ["PUT"],
     "AllowedHeaders": ["*"],
     "ExposeHeaders": [] }]
"""

import logging
import threading
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List

from src.config.settings import Settings
from src.graph.controller import graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/upload", tags=["upload"])

# Thread-safe in-memory job registry
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _get_s3_client():
    # Force region-specific S3 endpoint in presigned URLs to avoid browser
    # preflight failures caused by redirects from the global endpoint.
    endpoint_url = f"https://s3.{Settings.AWS_REGION}.amazonaws.com" if Settings.AWS_REGION else None

    return boto3.client(
        "s3",
        region_name=Settings.AWS_REGION,
        endpoint_url=endpoint_url,
        config=Config(signature_version="s3v4"),
        aws_access_key_id=Settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Settings.AWS_SECRET_ACCESS_KEY,
    )


def apply_s3_cors_policy():
    """Idempotently apply a CORS policy to the configured S3 bucket.

    Called once on server startup so the bucket always allows PUT uploads
    from the frontend (localhost dev and any configured origin).
    Safe to call even if the policy already exists.
    """
    if not Settings.AWS_S3_BUCKET:
        logger.warning("AWS_S3_BUCKET not set — skipping CORS policy application.")
        return

    s3 = _get_s3_client()
    cors_config = {
        "CORSRules": [
            {
                "AllowedOrigins": ["*"],
                "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
                "AllowedHeaders": ["*"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }
    try:
        s3.put_bucket_cors(
            Bucket=Settings.AWS_S3_BUCKET,
            CORSConfiguration=cors_config,
        )
        logger.info("S3 CORS policy applied to bucket '%s'.", Settings.AWS_S3_BUCKET)
    except ClientError as exc:
        logger.error("Failed to apply S3 CORS policy: %s", exc)


# ---------------------------------------------------------------------------
# Presigned URL
# ---------------------------------------------------------------------------

@router.get("/presigned")
def get_presigned_url(
    filename: str = Query(..., description="Original filename to store in S3"),
):
    if not Settings.AWS_S3_BUCKET:
        raise HTTPException(
            status_code=500,
            detail="AWS_S3_BUCKET is not configured. Set it in your .env file.",
        )

    s3 = _get_s3_client()
    key = f"leases/{uuid.uuid4().hex}/{filename}"

    try:
        url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": Settings.AWS_S3_BUCKET,
                "Key": key,
                # Do NOT include ContentType here — adding it forces content-type
                # into X-Amz-SignedHeaders which triggers a CORS preflight that
                # S3 rejects unless the bucket has a matching CORS policy.
            },
            ExpiresIn=3600,
        )
    except ClientError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"url": url, "key": key}


# ---------------------------------------------------------------------------
# Trigger background processing
# ---------------------------------------------------------------------------

class ProcessFileItem(BaseModel):
    filename: str
    s3_key: str


class ProcessRequest(BaseModel):
    files: List[ProcessFileItem]


def _run_job(job_id: str, filename: str, s3_key: str):
    local_path = f"temp_{uuid.uuid4().hex}_{filename}"
    try:
        with _jobs_lock:
            _jobs[job_id]["status"] = "processing"

        s3 = _get_s3_client()
        s3.download_file(Settings.AWS_S3_BUCKET, s3_key, local_path)

        result = graph.invoke({
            "file_path": local_path,
            "source_filename": filename,
            "source_s3_key": s3_key,
        })

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["result"] = {
                "filename": filename,
                "source_s3_key": s3_key,
                "lease_id": result.get("lease_id"),
                "structured_data": result.get("structured_data"),
                "analytics_result": result.get("analytics_result"),
                "sanity_flags": result.get("sanity_flags"),
                "raw_text": result.get("raw_text"),
                "execution_log": result.get("execution_log"),
            }
    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = str(exc)
    finally:
        # Clean up temp file if it was created
        import os
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except OSError:
            pass


@router.post("/process")
def trigger_processing(payload: ProcessRequest):
    job_results = []

    for item in payload.files:
        job_id = uuid.uuid4().hex
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "queued",
                "filename": item.filename,
                "result": None,
                "error": None,
            }

        thread = threading.Thread(
            target=_run_job,
            args=(job_id, item.filename, item.s3_key),
            daemon=True,
        )
        thread.start()

        job_results.append({"job_id": job_id, "filename": item.filename})

    return {"jobs": job_results}


# ---------------------------------------------------------------------------
# Poll job status
# ---------------------------------------------------------------------------

@router.get("/process/{job_id}")
def get_job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    return job
