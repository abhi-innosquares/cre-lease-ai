import json
from datetime import datetime

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Query

from src.config.settings import Settings
from src.db.database import SessionLocal
from src.db.models import Lease, LeaseAnalytics
from src.utils.currency import enrich_structured_data_with_currency, format_currency_amount


router = APIRouter(prefix="/leases", tags=["leases"])


def _get_s3_client():
    endpoint_url = f"https://s3.{Settings.AWS_REGION}.amazonaws.com" if Settings.AWS_REGION else None
    return boto3.client(
        "s3",
        region_name=Settings.AWS_REGION,
        endpoint_url=endpoint_url,
        config=Config(signature_version="s3v4"),
        aws_access_key_id=Settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Settings.AWS_SECRET_ACCESS_KEY,
    )


def _extract_tenant_name(lease: Lease, structured_data: dict):
    return (
        structured_data.get("tenant_name")
        or (structured_data.get("parties") or {}).get("tenantName")
        or structured_data.get("tenantName")
        or lease.tenant_name
        or "Unknown tenant"
    )


def _extract_expiration_date(structured_data: dict):
    return (
        structured_data.get("lease_end_date")
        or structured_data.get("expirationDate")
        or (structured_data.get("leaseDates") or {}).get("expirationDate")
        or (structured_data.get("leaseTerm") or {}).get("expirationDate")
    )


@router.get("/search")
def search_leases(
    lease_id: int | None = Query(default=None),
    tenant_name: str | None = Query(default=None),
):
    db = SessionLocal()
    try:
        query = db.query(Lease)
        if lease_id is not None:
            query = query.filter(Lease.id == lease_id)
        if tenant_name:
            query = query.filter(Lease.tenant_name.ilike(f"%{tenant_name.strip()}%"))

        leases = query.order_by(Lease.id.desc()).limit(100).all()
        analytics_rows = db.query(LeaseAnalytics).all()
        analytics_by_lease = {row.lease_id: row for row in analytics_rows}

        rows = []
        tenant_filter = (tenant_name or "").strip().lower()

        for lease in leases:
            try:
                structured_data = json.loads(lease.structured_data) if lease.structured_data else {}
            except Exception:
                structured_data = {}

            structured_data = enrich_structured_data_with_currency(structured_data, lease.raw_text or "")
            derived_tenant_name = _extract_tenant_name(lease, structured_data)
            if tenant_filter and tenant_filter not in str(derived_tenant_name).lower():
                continue

            analytics = analytics_by_lease.get(lease.id)
            expiration = (analytics.expiration_date if analytics else None) or _extract_expiration_date(structured_data)
            normalized_currency = lease.normalized_currency or structured_data.get("normalized_currency")

            rows.append(
                {
                    "lease_id": lease.id,
                    "tenant_name": derived_tenant_name,
                    "region": lease.region,
                    "source_filename": lease.source_filename,
                    "has_document": bool(lease.source_s3_key),
                    "base_rent": lease.base_rent,
                    "base_rent_display": structured_data.get("base_rent_display") or format_currency_amount(lease.base_rent, lease.base_rent_currency),
                    "normalized_base_rent": lease.normalized_base_rent,
                    "normalized_base_rent_display": structured_data.get("normalized_base_rent_display") or format_currency_amount(lease.normalized_base_rent, normalized_currency),
                    "normalized_currency": normalized_currency,
                    "renewal_risk_score": lease.renewal_risk_score,
                    "expiration_date": expiration,
                }
            )

        rows.sort(key=lambda item: item.get("lease_id") or 0, reverse=True)
        return {"leases": rows, "count": len(rows)}
    finally:
        db.close()


@router.get("/{lease_id}/document-link")
def get_document_link(lease_id: int):
    db = SessionLocal()
    try:
        lease = db.query(Lease).filter(Lease.id == lease_id).first()
    finally:
        db.close()

    if not lease:
        raise HTTPException(status_code=404, detail="Lease not found")

    if not lease.source_s3_key:
        raise HTTPException(status_code=404, detail="No source document is linked for this lease")

    if not Settings.AWS_S3_BUCKET:
        raise HTTPException(status_code=500, detail="AWS_S3_BUCKET is not configured")

    s3 = _get_s3_client()
    try:
        url = s3.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": Settings.AWS_S3_BUCKET,
                "Key": lease.source_s3_key,
            },
            ExpiresIn=900,
        )
    except ClientError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "lease_id": lease.id,
        "filename": lease.source_filename,
        "s3_key": lease.source_s3_key,
        "url": url,
        "expires_at": datetime.utcnow().isoformat() + "Z",
    }
