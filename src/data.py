"""
AI API Scraper - Seed data and discovery sources
"""
from typing import List, Dict, Any

# Known working AI API endpoints (seeded at start)
SEED_ENDPOINTS: List[Dict[str, str]] = [
    # Major providers
    {"id": "openai-gpt35", "modelName": "OpenAI GPT-3.5 Turbo", "endpoint": "https://api.openai.com/v1/chat/completions", "apiKey": "key-required", "source": "openai.com"},
    {"id": "openai-gpt4o", "modelName": "OpenAI GPT-4o", "endpoint": "https://api.openai.com/v1/chat/completions", "apiKey": "key-required", "source": "openai.com"},
    {"id": "mistral", "modelName": "Mistral AI", "endpoint": "https://api.mistral.ai/v1/chat/completions", "apiKey": "key-required", "source": "mistral.ai"},
    # Free tier options
    {"id": "gemini-flash-free", "modelName": "Google Gemini Flash 2.0 (Free)", "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash", "apiKey": "free", "source": "google.com"},
    {"id": "mistral-small-free", "modelName": "Mistral Small 3 (Free)", "endpoint": "https://api.mistral.ai/v1/chat/completions", "apiKey": "free", "source": "mistral.ai"},
]

# Web sources for regex scraping
WEB_SOURCES = [
    "https://huggingface.co/models?pipeline_tag=text-generation&sort=trending",
    "https://github.com/analyticas/ai-api-free",
    "https://github.com/f/awesome-chatgpt-api",
]


def get_seed_endpoints() -> List[Dict[str, str]]:
    return SEED_ENDPOINTS.copy()


def get_web_sources() -> List[str]:
    return WEB_SOURCES.copy()
