import json
import re
from typing import Any, Optional

from src.config.settings import Settings


DEFAULT_FX_RATES_TO_USD = {
    "USD": 1.0,
    "INR": 0.012,
    "CNY": 0.14,
    "JPY": 0.0067,
    "EUR": 1.09,
    "GBP": 1.28,
    "AUD": 0.66,
    "CAD": 0.74,
    "SGD": 0.74,
    "HKD": 0.13,
}

_ALIAS_TO_CODE = {
    "$": "USD",
    "US$": "USD",
    "USD": "USD",
    "DOLLAR": "USD",
    "DOLLARS": "USD",
    "UNITED STATES DOLLAR": "USD",
    "UNITED STATES DOLLARS": "USD",
    "₹": "INR",
    "RS": "INR",
    "RS.": "INR",
    "INR": "INR",
    "RUPEE": "INR",
    "RUPEES": "INR",
    "INDIAN RUPEE": "INR",
    "INDIAN RUPEES": "INR",
    "¥": "CNY",
    "CNY": "CNY",
    "CNY": "CNY",
    "RMB": "CNY",
    "YUAN": "CNY",
    "RENMINBI": "CNY",
    "CHINESE YUAN": "CNY",
    "JPY": "JPY",
    "YEN": "JPY",
    "EUR": "EUR",
    "EURO": "EUR",
    "EUROS": "EUR",
    "GBP": "GBP",
    "POUND": "GBP",
    "POUNDS": "GBP",
    "STERLING": "GBP",
    "AUD": "AUD",
    "AU$": "AUD",
    "CAD": "CAD",
    "CA$": "CAD",
    "SGD": "SGD",
    "S$": "SGD",
    "HKD": "HKD",
    "HK$": "HKD",
}

_CONTEXT_HINTS = {
    "INDIA": "INR",
    "MUMBAI": "INR",
    "DELHI": "INR",
    "BENGALURU": "INR",
    "BANGALORE": "INR",
    "CHENNAI": "INR",
    "HYDERABAD": "INR",
    "CHINA": "CNY",
    "BEIJING": "CNY",
    "SHANGHAI": "CNY",
    "SHENZHEN": "CNY",
    "GUANGZHOU": "CNY",
    "HONG KONG": "HKD",
    "JAPAN": "JPY",
    "TOKYO": "JPY",
    "UNITED STATES": "USD",
    "USA": "USD",
    "SAN FRANCISCO": "USD",
    "NEW YORK": "USD",
    "CHICAGO": "USD",
    "CANADA": "CAD",
    "TORONTO": "CAD",
    "AUSTRALIA": "AUD",
    "SYDNEY": "AUD",
    "SINGAPORE": "SGD",
    "UNITED KINGDOM": "GBP",
    "LONDON": "GBP",
    "EUROPE": "EUR",
    "GERMANY": "EUR",
    "FRANCE": "EUR",
}


def _text_contains_alias(text: str, alias: str) -> bool:
    if not text or not alias:
        return False
    if any(char in alias for char in "$¥₹"):
        return alias in text
    return re.search(rf"(?<![A-Z]){re.escape(alias)}(?![A-Z])", text) is not None


def normalize_currency_code(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None

    direct = _ALIAS_TO_CODE.get(text.upper())
    if direct:
        return direct

    collapsed = re.sub(r"\s+", " ", text.upper())
    for alias, code in _ALIAS_TO_CODE.items():
        if _text_contains_alias(collapsed, alias):
            return code

    return None


def parse_numeric(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return default

    cleaned = text.replace(",", "")
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if cleaned.count(".") > 1:
        first, *rest = cleaned.split(".")
        cleaned = first + "." + "".join(rest)

    try:
        return float(cleaned)
    except ValueError:
        return default


def format_currency_amount(amount: Any, currency: Optional[str], fallback: str = "Unknown") -> str:
    numeric = parse_numeric(amount, None)
    code = normalize_currency_code(currency)
    if numeric is None:
        return fallback

    if numeric.is_integer():
        rendered = f"{int(numeric):,}"
    else:
        rendered = f"{numeric:,.2f}"

    return f"{code or ''} {rendered}".strip()


def _configured_fx_rates_to_usd() -> dict[str, float]:
    configured = getattr(Settings, "FX_RATES_JSON", None)
    if not configured:
        return dict(DEFAULT_FX_RATES_TO_USD)

    try:
        parsed = json.loads(configured)
    except json.JSONDecodeError:
        return dict(DEFAULT_FX_RATES_TO_USD)

    merged = dict(DEFAULT_FX_RATES_TO_USD)
    for code, rate in parsed.items():
        normalized = normalize_currency_code(code)
        numeric = parse_numeric(rate, None)
        if normalized and numeric and numeric > 0:
            merged[normalized] = numeric
    return merged


def get_fx_rate(from_currency: Optional[str], to_currency: Optional[str] = None) -> Optional[float]:
    source = normalize_currency_code(from_currency)
    target = normalize_currency_code(to_currency or Settings.BASE_CURRENCY)
    if not source or not target:
        return None

    rates_to_usd = _configured_fx_rates_to_usd()
    source_to_usd = rates_to_usd.get(source)
    target_to_usd = rates_to_usd.get(target)
    if source_to_usd is None or target_to_usd is None:
        return None

    return round(source_to_usd / target_to_usd, 6)


def _context_currency(structured_data: dict[str, Any], raw_text: str) -> Optional[str]:
    context_parts = [
        str(structured_data.get("region") or ""),
        str(structured_data.get("property_address") or ""),
        str((structured_data.get("premises") or {}).get("market") or ""),
        str((structured_data.get("premises") or {}).get("propertyAddress") or ""),
        raw_text[:2000] if raw_text else "",
    ]
    context = " ".join(context_parts).upper()
    for hint, code in _CONTEXT_HINTS.items():
        if hint in context:
            return code
    return None


def infer_currency(structured_data: dict[str, Any], raw_text: str = "") -> tuple[Optional[str], str, str]:
    financial = structured_data.get("financialTerms") or {}
    schedule = financial.get("baseRentSchedule") or []

    explicit_sources = [
        structured_data.get("currency"),
        financial.get("currency"),
    ]
    if isinstance(schedule, list):
        explicit_sources.extend(entry.get("currency") for entry in schedule if isinstance(entry, dict))

    for value in explicit_sources:
        normalized = normalize_currency_code(value)
        if normalized:
            return normalized, "high", "explicit_field"

    context_code = _context_currency(structured_data, raw_text)

    searchable_values = [raw_text]
    for entry in schedule:
        if not isinstance(entry, dict):
            continue
        searchable_values.extend(
            [
                str(entry.get("annualBaseRent") or ""),
                str(entry.get("annualRent") or ""),
                str(entry.get("monthlyRent") or ""),
            ]
        )
    searchable_values.extend(
        [
            str(financial.get("annualBaseRent") or ""),
            str(financial.get("annualRent") or ""),
            str(structured_data.get("base_rent") or ""),
        ]
    )
    combined = " ".join(searchable_values).upper()

    for alias, code in _ALIAS_TO_CODE.items():
        if alias in {"$", "¥"}:
            continue
        if _text_contains_alias(combined, alias):
            return code, "medium", "text_match"

    if "₹" in combined:
        return "INR", "medium", "symbol_match"

    if "¥" in combined:
        if context_code in {"JPY", "CNY", "HKD"}:
            return context_code, "medium", "symbol_with_context"
        return "CNY", "low", "symbol_default"

    if "$" in combined:
        if context_code in {"USD", "AUD", "CAD", "SGD", "HKD"}:
            return context_code, "medium", "symbol_with_context"
        return "USD", "low", "symbol_default"

    if context_code:
        return context_code, "low", "context_hint"

    return None, "low", "unresolved"


def enrich_structured_data_with_currency(structured_data: dict[str, Any], raw_text: str = "") -> dict[str, Any]:
    if not isinstance(structured_data, dict):
        return structured_data

    financial = structured_data.setdefault("financialTerms", {})
    schedule = financial.get("baseRentSchedule") or []

    original_amount = None
    if isinstance(schedule, list) and schedule:
        first_entry = schedule[0] if isinstance(schedule[0], dict) else {}
        original_amount = parse_numeric(
            first_entry.get("annualBaseRent") if isinstance(first_entry, dict) else None,
            None,
        )
        if original_amount is None and isinstance(first_entry, dict):
            original_amount = parse_numeric(first_entry.get("annualRent"), None)

    if original_amount is None:
        original_amount = parse_numeric(financial.get("annualBaseRent"), None)
    if original_amount is None:
        original_amount = parse_numeric(financial.get("annualRent"), None)
    if original_amount is None:
        original_amount = parse_numeric(structured_data.get("base_rent"), None)

    original_currency, confidence, source = infer_currency(structured_data, raw_text)
    normalized_currency = normalize_currency_code(Settings.BASE_CURRENCY) or "USD"
    fx_rate_used = get_fx_rate(original_currency, normalized_currency) if original_currency else None
    normalized_amount = round(original_amount * fx_rate_used, 2) if original_amount is not None and fx_rate_used is not None else None

    if original_currency and not financial.get("currency"):
        financial["currency"] = original_currency

    if isinstance(schedule, list):
        for entry in schedule:
            if isinstance(entry, dict) and original_currency and not entry.get("currency"):
                entry["currency"] = original_currency

    financial["normalizedCurrency"] = normalized_currency
    if normalized_amount is not None:
        financial["normalizedAnnualBaseRent"] = normalized_amount

    structured_data["base_rent"] = original_amount
    structured_data["currency"] = original_currency
    structured_data["base_rent_display"] = format_currency_amount(original_amount, original_currency)
    structured_data["normalized_base_rent"] = normalized_amount
    structured_data["normalized_currency"] = normalized_currency
    structured_data["normalized_base_rent_display"] = format_currency_amount(normalized_amount, normalized_currency)
    structured_data["currencyAnalysis"] = {
        "original_currency": original_currency,
        "original_annual_base_rent": original_amount,
        "normalized_currency": normalized_currency,
        "normalized_annual_base_rent": normalized_amount,
        "fx_rate_used": fx_rate_used,
        "fx_rate_date": Settings.FX_RATE_DATE,
        "confidence": confidence,
        "source": source,
    }

    return structured_data
