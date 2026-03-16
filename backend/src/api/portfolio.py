from fastapi import APIRouter
import json

from src.db.database import SessionLocal
from src.db.models import Lease
from src.utils.currency import enrich_structured_data_with_currency, format_currency_amount

router = APIRouter()

@router.get("/portfolio/summary")
def portfolio_summary():

    db = SessionLocal()

    leases = db.query(Lease).all()
    total_leases = len(leases)
    normalized_values = []
    currencies_present = set()
    average_currency = "USD"

    for lease in leases:
        try:
            structured_data = json.loads(lease.structured_data) if lease.structured_data else {}
        except Exception:
            structured_data = {}

        structured_data = enrich_structured_data_with_currency(structured_data, lease.raw_text or "")
        currency_analysis = structured_data.get("currencyAnalysis") or {}

        normalized_rent = (
            lease.normalized_base_rent
            if lease.normalized_base_rent is not None
            else currency_analysis.get("normalized_annual_base_rent")
        )
        if normalized_rent is None:
            normalized_rent = lease.base_rent

        if normalized_rent is not None:
            normalized_values.append(normalized_rent)

        original_currency = lease.base_rent_currency or currency_analysis.get("original_currency")
        if original_currency:
            currencies_present.add(original_currency)

        average_currency = lease.normalized_currency or currency_analysis.get("normalized_currency") or average_currency

    avg_rent = sum(normalized_values) / len(normalized_values) if normalized_values else None
    high_risk = len([lease for lease in leases if (lease.renewal_risk_score or 0) > 0.5])

    db.close()

    return {
        "total_leases": total_leases,
        "average_rent": avg_rent,
        "average_rent_display": format_currency_amount(avg_rent, average_currency),
        "average_rent_currency": average_currency,
        "source_currencies": sorted(currencies_present),
        "high_risk_leases": high_risk
    }
