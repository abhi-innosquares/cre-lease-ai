from sqlalchemy import Column, Integer, String, Float, Text, Sequence
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Lease(Base):
    __tablename__ = "LEASES"  # uppercase — Snowflake stores unquoted identifiers in uppercase

    id = Column(Integer, Sequence("LEASES_ID_SEQ"), primary_key=True)

    tenant_name = Column(String)
    region = Column(String)
    base_rent = Column(Float)
    base_rent_currency = Column(String, nullable=True)
    normalized_base_rent = Column(Float, nullable=True)
    normalized_currency = Column(String, nullable=True)
    fx_rate_used = Column(Float, nullable=True)
    fx_rate_date = Column(String, nullable=True)

    escalation_percent = Column(Float, nullable=True)
    renewal_years = Column(Float, nullable=True)
    deviation_score = Column(Float, nullable=True)

    renewal_risk_score = Column(Float)
    source_filename = Column(String, nullable=True)
    source_s3_key = Column(String, nullable=True)

    # 🔥 Add these
    structured_data = Column(Text)   # store JSON as string
    raw_text = Column(Text)


class LeaseAnalytics(Base):
    __tablename__ = "LEASE_ANALYTICS"

    id = Column(Integer, Sequence("LEASE_ANALYTICS_ID_SEQ"), primary_key=True)
    # Avoid unique/index constraints here because standard Snowflake tables
    # do not support SQLAlchemy index DDL in this setup.
    lease_id = Column(Integer)

    # Portfolio and lease identifiers
    property_id = Column(String, nullable=True)
    lease_uid = Column(String, nullable=True)
    parent_tenant_id = Column(String, nullable=True)
    market = Column(String, nullable=True)

    # Core economics
    base_rent = Column(Float, nullable=True)
    base_rent_currency = Column(String, nullable=True)
    normalized_base_rent = Column(Float, nullable=True)
    normalized_currency = Column(String, nullable=True)
    fx_rate_used = Column(Float, nullable=True)
    fx_rate_date = Column(String, nullable=True)
    effective_rent_psf = Column(Float, nullable=True)
    effective_rent_psf_currency = Column(String, nullable=True)
    tenant_improvement_allowance = Column(Float, nullable=True)
    expense_recovery_structure = Column(String, nullable=True)
    tenant_pro_rata_share = Column(Float, nullable=True)

    # Term and option deadlines
    expiration_date = Column(String, nullable=True)
    renewal_option_deadline_date = Column(String, nullable=True)
    termination_option_deadline_date = Column(String, nullable=True)

    # Optionality and risk
    has_renewal_option = Column(String, nullable=True)
    renewal_option_rent_basis = Column(String, nullable=True)
    has_termination_option = Column(String, nullable=True)
    co_tenancy_clause = Column(String, nullable=True)
    exclusive_use_clause = Column(String, nullable=True)
    snda_in_place = Column(String, nullable=True)
    renewal_risk_score = Column(Float, nullable=True)
