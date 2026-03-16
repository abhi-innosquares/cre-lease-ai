from src.db.database import SessionLocal, filter_model_kwargs
from src.db.models import Lease, LeaseAnalytics
from src.vector.vector_store import create_vector_store
from src.utils.currency import enrich_structured_data_with_currency, format_currency_amount, parse_numeric
import json
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def _safe_float(value, default=None):
    return parse_numeric(value, default)


def _first_present(*values):
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _parse_iso_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d")
    except ValueError:
        return None


def _coerce_notice_days(value):
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _derive_deadline_date(anchor_date, notice_days):
    parsed_anchor = _parse_iso_date(anchor_date)
    parsed_notice_days = _coerce_notice_days(notice_days)

    if not parsed_anchor or parsed_notice_days is None:
        return None

    return (parsed_anchor - timedelta(days=parsed_notice_days)).strftime("%Y-%m-%d")


def _infer_expense_structure(lease_type, pass_through):
    lt = (lease_type or "").lower()
    pt = (pass_through or "").lower()

    if "absolute" in lt and "nnn" in lt:
        return "Absolute NNN"
    if "triple" in lt or "nnn" in lt or "nnn" in pt:
        return "Triple Net (NNN)"
    if "modified" in lt:
        return "Modified Gross"
    if "full service" in lt or "gross" in pt:
        return "Full Service"
    if "base year" in pt:
        return "Base Year"
    if "expense stop" in pt:
        return "Expense Stop"
    return "Unknown"


def _compute_risk_score(data):
    financial = data.get("financialTerms") or {}
    options = data.get("options") or {}
    risk_flags = data.get("riskFlags") or {}

    score = 0.0

    if not options.get("hasRenewalOption", False):
        score += 0.35
    if options.get("hasTerminationOption", False):
        score += 0.2
    if not financial.get("securityDeposit"):
        score += 0.15
    if not data.get("parties", {}).get("isGuaranteed", False):
        score += 0.1
    if not risk_flags.get("sndaInPlace", False):
        score += 0.1
    if risk_flags.get("coTenancyClause", False):
        score += 0.05
    if risk_flags.get("exclusiveUseClause", False):
        score += 0.05

    return round(min(score, 1.0), 2)


def analytics_agent(state: dict):

    data = enrich_structured_data_with_currency(state.get("structured_data", {}) or {}, state.get("raw_text", ""))
    raw_text = state.get("raw_text", "")

    # ---------------------------
    # Safe extraction
    # ---------------------------

    lease_identification = data.get("leaseIdentification") or {}
    parties = data.get("parties") or {}
    premises = data.get("premises") or {}
    lease_term = data.get("leaseTerm") or {}
    financial = data.get("financialTerms") or {}
    options = data.get("options") or {}
    currency_analysis = data.get("currencyAnalysis") or {}

    base_schedule = financial.get("baseRentSchedule") or []

    first_year_rent = _safe_float(currency_analysis.get("original_annual_base_rent"), None)
    if isinstance(base_schedule, list) and len(base_schedule) > 0:
        first_year_rent = _first_present(
            first_year_rent,
            _safe_float(
                _first_present(
                    base_schedule[0].get("annualBaseRent"),
                    base_schedule[0].get("annualRent"),
                ),
                None,
            ),
        )

    if first_year_rent is None:
        first_year_rent = _safe_float(
            _first_present(financial.get("annualBaseRent"), financial.get("annualRent")),
            None,
        )

    original_currency = _first_present(
        currency_analysis.get("original_currency"),
        financial.get("currency"),
        data.get("currency"),
    )
    normalized_base_rent = _safe_float(currency_analysis.get("normalized_annual_base_rent"), None)
    normalized_currency = _first_present(
        currency_analysis.get("normalized_currency"),
        data.get("normalized_currency"),
        original_currency,
    )
    fx_rate_used = _safe_float(currency_analysis.get("fx_rate_used"), None)
    fx_rate_date = _first_present(currency_analysis.get("fx_rate_date"), None)

    rentable_sf = _safe_float(premises.get("rentableSquareFeet"), None)

    effective_rent_psf = None
    if normalized_base_rent and rentable_sf and rentable_sf > 0:
        effective_rent_psf = round(normalized_base_rent / rentable_sf, 2)

    expiration_date = _first_present(
        lease_term.get("expirationDate"),
        data.get("expirationDate"),
        data.get("lease_end_date"),
        (data.get("leaseDates") or {}).get("expirationDate"),
    )

    renewal_option_deadline_date = _derive_deadline_date(
        expiration_date,
        _first_present(options.get("renewalNoticePeriodDays"), options.get("renewalNoticeDays")),
    )
    termination_option_deadline_date = _derive_deadline_date(
        expiration_date,
        _first_present(options.get("terminationNoticePeriodDays"), options.get("terminationNoticeDays")),
    )

    expense_recovery_structure = _infer_expense_structure(
        lease_identification.get("leaseType"),
        financial.get("operatingExpensePassThrough"),
    )

    # ---------------------------
    # Renewal Risk Calculation
    # ---------------------------

    renewal_risk_score = _compute_risk_score(data)

    state["analytics_result"] = {
        "lease_id": state.get("lease_id"),
        "base_rent": first_year_rent,
        "base_rent_currency": original_currency,
        "base_rent_display": format_currency_amount(first_year_rent, original_currency),
        "normalized_base_rent": normalized_base_rent,
        "normalized_currency": normalized_currency,
        "normalized_base_rent_display": format_currency_amount(normalized_base_rent, normalized_currency),
        "fx_rate_used": fx_rate_used,
        "fx_rate_date": fx_rate_date,
        "effective_rent_psf": effective_rent_psf,
        "effective_rent_psf_currency": normalized_currency,
        "effective_rent_psf_display": f"{format_currency_amount(effective_rent_psf, normalized_currency)} / SF" if effective_rent_psf is not None else "Unknown",
        "expense_recovery_structure": expense_recovery_structure,
        "tenant_pro_rata_share": _safe_float(financial.get("proRataShare"), None),
        "renewal_option_deadline_date": renewal_option_deadline_date,
        "termination_option_deadline_date": termination_option_deadline_date,
        "has_renewal_option": options.get("hasRenewalOption", False),
        "has_termination_option": options.get("hasTerminationOption", False),
        "renewal_option_rent_basis": _first_present(options.get("renewalRentBasis"), options.get("renewalOptionRentBasis")),
        "renewal_risk_score": renewal_risk_score,
    }

    # Keep derived KPI payload attached to structured data for downstream APIs and reporting.
    data["derivedAnalytics"] = state["analytics_result"]

    # ---------------------------
    # Save to Database
    # ---------------------------

    db = SessionLocal()

    lease_payload = dict(
        tenant_name=parties.get("tenantName"),
        region=premises.get("propertyAddress"),
        base_rent=first_year_rent,
        base_rent_currency=original_currency,
        normalized_base_rent=normalized_base_rent,
        normalized_currency=normalized_currency,
        fx_rate_used=fx_rate_used,
        fx_rate_date=fx_rate_date,
        escalation_percent=_safe_float(financial.get("rentEscalationPercent"), None),
        renewal_years=_safe_float(options.get("renewalTermYears"), None),
        deviation_score=0.0,
        renewal_risk_score=renewal_risk_score,
        source_filename=state.get("source_filename"),
        source_s3_key=state.get("source_s3_key"),
        structured_data=json.dumps(data),
        raw_text=raw_text
    )

    lease = Lease(**filter_model_kwargs(Lease, lease_payload))

    db.add(lease)
    db.commit()
    db.refresh(lease)

    lease_id_value = int(lease.id)
    state["lease_id"] = lease_id_value

    # Persist warehouse-style analytics record for portfolio-level reporting.
    analytics_payload = dict(
        lease_id=lease_id_value,
        property_id=_first_present(premises.get("propertyId"), data.get("propertyId")),
        lease_uid=_first_present(lease_identification.get("leaseId"), data.get("leaseId"), data.get("lease_uid")),
        parent_tenant_id=_first_present(parties.get("parentTenantId"), data.get("parentTenantId")),
        market=_first_present(premises.get("market"), data.get("market"), data.get("region")),
        base_rent=first_year_rent,
        base_rent_currency=original_currency,
        normalized_base_rent=normalized_base_rent,
        normalized_currency=normalized_currency,
        fx_rate_used=fx_rate_used,
        fx_rate_date=fx_rate_date,
        effective_rent_psf=effective_rent_psf,
        effective_rent_psf_currency=normalized_currency,
        tenant_improvement_allowance=_safe_float(
            _first_present(financial.get("tenantImprovementAllowance"), financial.get("tiAllowance")),
            None,
        ),
        expense_recovery_structure=expense_recovery_structure,
        tenant_pro_rata_share=_safe_float(financial.get("proRataShare"), None),
        expiration_date=expiration_date,
        renewal_option_deadline_date=renewal_option_deadline_date,
        termination_option_deadline_date=termination_option_deadline_date,
        has_renewal_option=str(bool(options.get("hasRenewalOption", False))).lower(),
        renewal_option_rent_basis=_first_present(options.get("renewalRentBasis"), options.get("renewalOptionRentBasis")),
        has_termination_option=str(bool(options.get("hasTerminationOption", False))).lower(),
        co_tenancy_clause=str(bool((data.get("riskFlags") or {}).get("coTenancyClause", False))).lower(),
        exclusive_use_clause=str(bool((data.get("riskFlags") or {}).get("exclusiveUseClause", False))).lower(),
        snda_in_place=str(bool((data.get("riskFlags") or {}).get("sndaInPlace", False))).lower(),
        renewal_risk_score=renewal_risk_score,
    )

    analytics_row = LeaseAnalytics(**filter_model_kwargs(LeaseAnalytics, analytics_payload))

    db.add(analytics_row)
    db.commit()

    db.close()

    state["analytics_result"]["lease_id"] = lease_id_value

    # ---------------------------
    # Create Vector Store
    # ---------------------------
    try:
        create_vector_store(lease_id_value, raw_text)
        state.setdefault("execution_log", []).append(f"Vector store created for lease {lease_id_value}")
    except Exception as exc:
        # provide extra diagnostic information; the raw_text is often large so only
        # log a snippet and its type/length to help diagnose unexpected values
        snippet = repr(raw_text[:200]) if isinstance(raw_text, str) else repr(raw_text)
        logger.error(
            "Vector store creation failed for lease %s: %s; raw_text snippet=%s; raw_text_type=%s",
            lease_id_value,
            exc,
            snippet,
            type(raw_text),
        )
        state.setdefault("execution_log", []).append(f"Vector store creation failed: {exc}")

    state.setdefault("execution_log", []).append("Analytics agent completed")

    return state
