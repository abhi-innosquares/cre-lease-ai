from fastapi import APIRouter
from sqlalchemy import func
from datetime import datetime
import json

from src.db.database import SessionLocal
from src.db.models import Lease, LeaseAnalytics
from src.utils.currency import enrich_structured_data_with_currency, format_currency_amount

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/portfolio")
def portfolio_analytics_summary():
    db = SessionLocal()
    try:
        total_leases = db.query(LeaseAnalytics).count()

        avg_effective_rent_psf = db.query(func.avg(LeaseAnalytics.effective_rent_psf)).scalar()
        avg_renewal_risk_score = db.query(func.avg(LeaseAnalytics.renewal_risk_score)).scalar()

        high_risk_count = (
            db.query(LeaseAnalytics)
            .filter(LeaseAnalytics.renewal_risk_score > 0.5)
            .count()
        )

        renewal_option_count = (
            db.query(LeaseAnalytics)
            .filter(LeaseAnalytics.has_renewal_option == "true")
            .count()
        )

        termination_option_count = (
            db.query(LeaseAnalytics)
            .filter(LeaseAnalytics.has_termination_option == "true")
            .count()
        )

        return {
            "total_leases": total_leases,
            "avg_effective_rent_psf": round(float(avg_effective_rent_psf), 2) if avg_effective_rent_psf is not None else None,
            "avg_renewal_risk_score": round(float(avg_renewal_risk_score), 2) if avg_renewal_risk_score is not None else None,
            "high_risk_leases": high_risk_count,
            "leases_with_renewal_option": renewal_option_count,
            "leases_with_termination_option": termination_option_count,
        }
    finally:
        db.close()


def _extract_expiration_date(structured_data: dict):
    return (
        structured_data.get("lease_end_date")
        or structured_data.get("expirationDate")
        or (structured_data.get("leaseDates") or {}).get("expirationDate")
        or (structured_data.get("leaseTerm") or {}).get("expirationDate")
    )


def _extract_tenant_name(lease: Lease, structured_data: dict):
    return (
        structured_data.get("tenant_name")
        or (structured_data.get("parties") or {}).get("tenantName")
        or structured_data.get("tenantName")
        or lease.tenant_name
        or "Unknown tenant"
    )


@router.get("/leases")
def portfolio_analytics_leases():
    db = SessionLocal()
    try:
        lease_rows = db.query(Lease).all()
        analytics_rows = db.query(LeaseAnalytics).all()

        analytics_by_lease_id = {a.lease_id: a for a in analytics_rows}
        lease_table = []
        month_buckets = {}

        for lease in lease_rows:
            try:
                structured_data = json.loads(lease.structured_data) if lease.structured_data else {}
            except Exception:
                structured_data = {}

            structured_data = enrich_structured_data_with_currency(structured_data, lease.raw_text or "")
            currency_analysis = structured_data.get("currencyAnalysis") or {}

            analytics = analytics_by_lease_id.get(lease.id)
            expiration_date = (analytics.expiration_date if analytics else None) or _extract_expiration_date(structured_data)
            tenant_name = _extract_tenant_name(lease, structured_data)

            if expiration_date:
                try:
                    parsed = datetime.strptime(str(expiration_date), "%Y-%m-%d")
                    month_key = parsed.strftime("%Y-%m")
                    month_buckets[month_key] = month_buckets.get(month_key, 0) + 1
                except ValueError:
                    pass

            lease_table.append(
                {
                    "lease_id": lease.id,
                    "tenant_name": tenant_name,
                    "region": lease.region,
                    "base_rent": lease.base_rent,
                    "base_rent_currency": lease.base_rent_currency or currency_analysis.get("original_currency"),
                    "base_rent_display": structured_data.get("base_rent_display") or format_currency_amount(lease.base_rent, lease.base_rent_currency),
                    "normalized_base_rent": lease.normalized_base_rent if lease.normalized_base_rent is not None else currency_analysis.get("normalized_annual_base_rent"),
                    "normalized_currency": lease.normalized_currency or currency_analysis.get("normalized_currency"),
                    "normalized_base_rent_display": structured_data.get("normalized_base_rent_display") or format_currency_amount(lease.normalized_base_rent, lease.normalized_currency),
                    "expiration_date": expiration_date,
                    "effective_rent_psf": analytics.effective_rent_psf if analytics else None,
                    "effective_rent_psf_currency": (analytics.effective_rent_psf_currency if analytics else None) or lease.normalized_currency or currency_analysis.get("normalized_currency"),
                    "renewal_risk_score": lease.renewal_risk_score,
                    "has_renewal_option": analytics.has_renewal_option if analytics else None,
                    "has_termination_option": analytics.has_termination_option if analytics else None,
                    "expense_recovery_structure": analytics.expense_recovery_structure if analytics else None,
                }
            )

        lease_table.sort(key=lambda item: item.get("lease_id") or 0, reverse=True)
        expirations_by_month = [
            {"month": month, "count": count}
            for month, count in sorted(month_buckets.items())
        ]

        high = len([l for l in lease_table if (l.get("renewal_risk_score") or 0) > 0.7])
        medium = len([l for l in lease_table if 0.4 <= (l.get("renewal_risk_score") or 0) <= 0.7])
        low = len([l for l in lease_table if (l.get("renewal_risk_score") or 0) < 0.4])

        return {
            "total_leases": len(lease_table),
            "risk_distribution": {
                "low": low,
                "medium": medium,
                "high": high,
            },
            "expirations_by_month": expirations_by_month,
            "leases": lease_table,
        }
    finally:
        db.close()
