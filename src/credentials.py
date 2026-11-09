"""
AI API Scraper - Credentials manager
Loads provider credentials from .env for authenticated scraping.
"""
import os
from typing import Optional, Dict, Any

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")

_credentials: Dict[str, str] = {}


def load_credentials() -> Dict[str, str]:
    """Load credentials from .env file."""
    global _credentials
    if _credentials:
        return _credentials.copy()
    _credentials = {}
    if not os.path.exists(ENV_PATH):
        return _credentials
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                _credentials[key.strip()] = value.strip()
    return _credentials.copy()


def get(key: str) -> Optional[str]:
    creds = load_credentials()
    return creds.get(key)


def set_credential(key: str, value: str) -> bool:
    """Save a credential to .env file."""
    existing = load_credentials()
    existing[key] = value
    with open(ENV_PATH, "w") as f:
        f.write("# AI API Scanner - Credentials\n")
        f.write(f"# Akun provider untuk scraping auth-required endpoints\n")
        for k, v in existing.items():
            masked = v[:3] + "***" + v[-4:] if len(v) > 8 else "***"
            f.write(f"{k}={v}\n")
    global _credentials
    _credentials = existing
    return True


def get_headers_for_provider(provider: str) -> Dict[str, str]:
    """Get headers for a specific provider based on stored credentials."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*",
    }
    creds = load_credentials()
    # Use Google account credentials for authentication
    if creds.get("GMAIL_ACCOUNT"):
        headers["X-Authenticated-User"] = creds["GMAIL_ACCOUNT"]
    if provider == "openrouter" and creds.get("OPENROUTER_API_KEY"):
        headers["Authorization"] = f"Bearer {creds['OPENROUTER_API_KEY']}"
    elif provider == "anthropic" and creds.get("ANTHROPIC_API_KEY"):
        headers["x-api-key"] = creds["ANTHROPIC_API_KEY"]
        headers["anthropic-version"] = "2023-06-01"
    return headers


def has_google_account() -> bool:
    creds = load_credentials()
    return bool(creds.get("GMAIL_ACCOUNT"))


def get_email() -> Optional[str]:
    return load_credentials().get("GMAIL_ACCOUNT")
