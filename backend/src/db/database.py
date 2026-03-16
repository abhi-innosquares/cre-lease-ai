from functools import lru_cache

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import load_only, sessionmaker
from src.db.models import Base
from src.config.settings import Settings
import urllib.parse
import logging

logger = logging.getLogger(__name__)


def _build_engine():
    """Return a Snowflake engine when credentials are present, SQLite otherwise."""
    sf_account = Settings.SNOWFLAKE_ACCOUNT
    sf_user = Settings.SNOWFLAKE_USER
    sf_password = Settings.SNOWFLAKE_PASSWORD

    if sf_account and sf_user and sf_password:
        encoded_password = urllib.parse.quote(sf_password, safe="")
        url = (
            f"snowflake://{sf_user}:{encoded_password}"
            f"@{sf_account}/{Settings.SNOWFLAKE_DATABASE}/{Settings.SNOWFLAKE_SCHEMA}"
            f"?warehouse={Settings.SNOWFLAKE_WAREHOUSE}"
        )
        if Settings.SNOWFLAKE_ROLE:
            url += f"&role={urllib.parse.quote(Settings.SNOWFLAKE_ROLE, safe='')}"
        logger.info("Connecting to Snowflake: account=%s db=%s", sf_account, Settings.SNOWFLAKE_DATABASE)
        return create_engine(url, pool_pre_ping=True)
    else:
        logger.warning(
            "Snowflake credentials not configured — falling back to local SQLite.\n"
            "Set SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD in your .env to use Snowflake."
        )
        return create_engine(
            "sqlite:///./leases.db",
            connect_args={"check_same_thread": False},
        )


engine = _build_engine()


@lru_cache(maxsize=32)
def get_available_table_columns(table_name: str) -> set[str]:
    inspector = inspect(engine)
    try:
        return {column_info["name"].lower() for column_info in inspector.get_columns(table_name)}
    except Exception as exc:
        logger.warning("Could not inspect columns for table %s: %s", table_name, exc)
        return set()


def has_table_column(table_name: str, column_name: str) -> bool:
    return column_name.lower() in get_available_table_columns(table_name)


def filter_model_kwargs(model, values: dict) -> dict:
    table_name = model.__tablename__
    available_columns = get_available_table_columns(table_name)
    return {
        key: value
        for key, value in values.items()
        if key.lower() in available_columns
    }


def get_load_only_attrs(model, *column_names: str):
    table_name = model.__tablename__
    available_columns = get_available_table_columns(table_name)
    attrs = []
    for column_name in column_names:
        if column_name.lower() in available_columns and hasattr(model, column_name):
            attrs.append(getattr(model, column_name))
    return attrs


def safe_model_value(instance, column_name: str, available_columns: set[str], default=None):
    if column_name.lower() not in available_columns:
        return default
    return getattr(instance, column_name, default)


def _ensure_existing_tables_have_currency_columns():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    dialect = engine.dialect.name

    if dialect == "sqlite":
        text_type = "TEXT"
        float_type = "REAL"
    else:
        text_type = "VARCHAR"
        float_type = "FLOAT"

    expected_columns = {
        "LEASES": {
            "base_rent_currency": text_type,
            "normalized_base_rent": float_type,
            "normalized_currency": text_type,
            "fx_rate_used": float_type,
            "fx_rate_date": text_type,
            "source_filename": text_type,
            "source_s3_key": text_type,
        },
        "LEASE_ANALYTICS": {
            "base_rent": float_type,
            "base_rent_currency": text_type,
            "normalized_base_rent": float_type,
            "normalized_currency": text_type,
            "fx_rate_used": float_type,
            "fx_rate_date": text_type,
            "effective_rent_psf_currency": text_type,
        },
    }

    with engine.begin() as connection:
        for table_name, columns in expected_columns.items():
            if table_name not in table_names:
                continue

            existing_columns = {
                column_info["name"] for column_info in inspector.get_columns(table_name)
            }
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                logger.info("Adding missing column %s.%s", table_name, column_name)
                try:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not add column %s.%s automatically: %s",
                        table_name,
                        column_name,
                        exc,
                    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base.metadata.create_all(bind=engine)
_ensure_existing_tables_have_currency_columns()
get_available_table_columns.cache_clear()
