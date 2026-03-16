"""
Application settings and configuration
"""

import os
from pathlib import Path
from typing import Optional
from datetime import date


class Settings:
    """Central configuration for the lease extraction system"""
    
    # Project root
    ROOT_DIR = Path(__file__).parent.parent.parent
    
    # Data directories
    INPUT_DIR = ROOT_DIR / "data" / "input"
    OUTPUT_DIR = ROOT_DIR / "data" / "output"
    LOGS_DIR = ROOT_DIR / "logs"
    
    # API Configuration
    OPENAI_API_KEY: Optional[str] = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL: str = "gpt-4o"
    OPENAI_TEMPERATURE: float = 0.1
    OPENAI_MAX_TOKENS: int = 4000
    AUTO_TRANSLATE_TO_ENGLISH: bool = os.environ.get("AUTO_TRANSLATE_TO_ENGLISH", "true").lower() == "true"

    # Currency normalization configuration
    BASE_CURRENCY: str = os.environ.get("BASE_CURRENCY", "USD")
    FX_RATE_DATE: str = os.environ.get("FX_RATE_DATE", date.today().isoformat())
    FX_RATES_JSON: Optional[str] = os.environ.get("FX_RATES_JSON")
    
    # OCR Configuration
    TESSERACT_PATH: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    OCR_DPI_SCALE: float = 2.5  # For 300 DPI effective resolution
    OCR_LANGUAGE: str = "eng"
    
    # Processing Configuration
    BATCH_SIZE: int = 10
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY: int = 2  # seconds
    
    # Output Configuration
    SAVE_RAW_TEXT: bool = True
    SAVE_JSON: bool = True
    SAVE_CSV_SUMMARY: bool = True
    
    # Snowflake Configuration (set via .env / environment)
    SNOWFLAKE_ACCOUNT: Optional[str] = os.environ.get("SNOWFLAKE_ACCOUNT")
    SNOWFLAKE_USER: Optional[str] = os.environ.get("SNOWFLAKE_USER")
    SNOWFLAKE_PASSWORD: Optional[str] = os.environ.get("SNOWFLAKE_PASSWORD")
    SNOWFLAKE_DATABASE: str = os.environ.get("SNOWFLAKE_DATABASE", "LEASE_DB")
    SNOWFLAKE_SCHEMA: str = os.environ.get("SNOWFLAKE_SCHEMA", "PUBLIC")
    SNOWFLAKE_WAREHOUSE: str = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    SNOWFLAKE_ROLE: Optional[str] = os.environ.get("SNOWFLAKE_ROLE")

    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = os.environ.get("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.environ.get("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.environ.get("AWS_REGION", "us-east-1")
    AWS_S3_BUCKET: str = os.environ.get("AWS_S3_BUCKET", "")

    # Chroma Configuration (local by default; remote when host is provided)
    CHROMA_HOST: Optional[str] = os.environ.get("CHROMA_HOST")
    CHROMA_PORT: int = int(os.environ.get("CHROMA_PORT", "8000"))
    CHROMA_SSL: bool = os.environ.get("CHROMA_SSL", "false").lower() == "true"
    CHROMA_API_KEY: Optional[str] = os.environ.get("CHROMA_API_KEY")
    CHROMA_TENANT: Optional[str] = os.environ.get("CHROMA_TENANT")
    CHROMA_DATABASE: Optional[str] = os.environ.get("CHROMA_DATABASE")
    CHROMA_CLOUD_MODE: bool = os.environ.get("CHROMA_CLOUD_MODE", "false").lower() == "true"
    CHROMA_VECTOR_PATH: str = os.environ.get("CHROMA_VECTOR_PATH", "vectors")

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories if they don't exist"""
        cls.INPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate(cls) -> bool:
        """Validate configuration"""
        issues = []
        
        # Check Tesseract
        if not os.path.exists(cls.TESSERACT_PATH):
            issues.append(f"Tesseract not found at: {cls.TESSERACT_PATH}")
        
        # Check OpenAI key
        if not cls.OPENAI_API_KEY:
            issues.append("OPENAI_API_KEY not set (will use rule-based extraction)")
        
        if issues:
            print("Configuration warnings:")
            for issue in issues:
                print(f"  ⚠ {issue}")
            return False
        
        return True
