import os
from dataclasses import dataclass, field
from pathlib import Path


def _f(name: str, default: str) -> float:
    return float(os.getenv(name, default).replace(",", "."))


@dataclass(frozen=True)
class Settings:
    secret_key: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/crm.db"))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", "./data/files")))
    https_only: bool = field(default_factory=lambda: os.getenv("HTTPS_ONLY", "1") == "1")
    lead_api_token: str = field(default_factory=lambda: os.getenv("LEAD_API_TOKEN", ""))
    events_api_token: str = field(default_factory=lambda: os.getenv("EVENTS_API_TOKEN", ""))
    public_leads_enabled: bool = field(default_factory=lambda: os.getenv("PUBLIC_LEADS_ENABLED", "0") == "1")
    public_site_origins: str = field(default_factory=lambda: os.getenv("PUBLIC_SITE_ORIGINS", ""))
    public_rate_limit: int = field(default_factory=lambda: int(os.getenv("PUBLIC_RATE_LIMIT_PER_HOUR", "10")))
    consent_version: str = field(default_factory=lambda: os.getenv("CONSENT_VERSION", "draft"))
    max_upload_mb: int = field(default_factory=lambda: int(os.getenv("MAX_UPLOAD_MB", "25")))
    k_mtr: float = field(default_factory=lambda: _f("DEFAULT_K_MTR", "1.20"))
    k_smr: float = field(default_factory=lambda: _f("DEFAULT_K_SMR", "1.356"))
    vat: float = field(default_factory=lambda: _f("DEFAULT_VAT", "0.22"))
    company_phone: str = field(default_factory=lambda: os.getenv("COMPANY_PHONE", ""))
    company_email: str = field(default_factory=lambda: os.getenv("COMPANY_EMAIL", ""))
    legal_name: str = field(default_factory=lambda: os.getenv("COMPANY_LEGAL_NAME", ""))
    requisites: str = field(default_factory=lambda: os.getenv("COMPANY_REQUISITES", ""))
    request_contact: str = field(
        default_factory=lambda: os.getenv(
            "REQUEST_CONTACT_TEXT",
            "По техническим вопросам свяжитесь, пожалуйста, с нашим ответственным специалистом.",
        )
    )


def get_settings() -> Settings:
    s = Settings()
    if len(s.secret_key) < 32:
        raise RuntimeError("SECRET_KEY must be set and at least 32 characters long")
    return s
