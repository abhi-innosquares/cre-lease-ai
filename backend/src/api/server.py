from dotenv import load_dotenv

load_dotenv()
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from src.graph.controller import graph
from src.api.s3_upload import router as s3_router, apply_s3_cors_policy
import shutil


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Apply S3 CORS policy on every server start so bucket is always ready.
    apply_s3_cors_policy()
    yield


app = FastAPI(lifespan=lifespan)

# ---------------------------
# CORS
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Upload Lease
# ---------------------------
@app.post("/upload")
async def upload(
    file: Optional[UploadFile] = File(default=None),
    files: Optional[List[UploadFile]] = File(default=None),
):
    upload_files = files or ([] if file is None else [file])
    if not upload_files:
        raise HTTPException(status_code=400, detail="No files provided")

    lease_results = []

    for uploaded_file in upload_files:
        file_path = f"temp_{uploaded_file.filename}"

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)

        result = graph.invoke({"file_path": file_path, "source_filename": uploaded_file.filename})
        lease_results.append(
            {
                "filename": uploaded_file.filename,
            "source_s3_key": result.get("source_s3_key"),
                "lease_id": result.get("lease_id"),
                "structured_data": result.get("structured_data"),
                "analytics_result": result.get("analytics_result"),
                "sanity_flags": result.get("sanity_flags"),
                "raw_text": result.get("raw_text"),
                "execution_log": result.get("execution_log"),
            }
        )

    first_result = lease_results[0]

    return {
        # Preserve legacy response keys for existing frontend behavior.
        "lease_id": first_result.get("lease_id"),
        "structured_data": first_result.get("structured_data"),
        "analytics_result": first_result.get("analytics_result"),
        "sanity_flags": first_result.get("sanity_flags"),
        "raw_text": first_result.get("raw_text"),
        "execution_log": first_result.get("execution_log"),
        "uploaded_leases": lease_results,
    }


# ---------------------------
# S3 Upload + Async Processing
# ---------------------------
app.include_router(s3_router)

# ---------------------------
# Portfolio Summary
# ---------------------------
from src.api.portfolio import portfolio_summary

@app.get("/portfolio/summary")
def portfolio_summary_route():
    return portfolio_summary()


# ---------------------------
# Chat
# ---------------------------
from src.api.chat import router as chat_router
app.include_router(chat_router)


# ---------------------------
# Analytics
# ---------------------------
from src.api.analytics import router as analytics_router
app.include_router(analytics_router)


# ---------------------------
# Lease Search
# ---------------------------
from src.api.lease_search import router as lease_search_router
app.include_router(lease_search_router)


# ---------------------------
# Report
# ---------------------------
from src.api.report import generate_report_endpoint

@app.post("/report")
def report(payload: dict):
    return generate_report_endpoint(payload)
