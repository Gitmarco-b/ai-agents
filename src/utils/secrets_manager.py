"""
Secrets Manager for AI Trading Dashboard
=========================================
Handles secure storage and retrieval of API keys for AI providers.

API keys are stored in a separate JSON file (not .env) and loaded into
environment variables when the application starts or when keys are updated.

Security Notes:
- Keys are stored in a JSON file with restricted permissions
- Keys are masked in API responses (only last 4 characters shown)
- Keys are loaded into environment variables for use by model factory
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

# Secrets file location (separate from settings)
SECRETS_FILE = Path(__file__).parent.parent / "data" / "user_secrets.json"

# Supported AI providers and their environment variable names
AI_PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_var": "ANTHROPIC_KEY",
        "placeholder": "sk-ant-...",
        "docs_url": "https://console.anthropic.com/settings/keys"
    },
    "openai": {
        "name": "OpenAI",
        "env_var": "OPENAI_KEY",
        "placeholder": "sk-...",
        "docs_url": "https://platform.openai.com/api-keys"
    },
    "gemini": {
        "name": "Google Gemini",
        "env_var": "GEMINI_KEY",
        "placeholder": "AIza...",
        "docs_url": "https://aistudio.google.com/apikey"
    },
    "deepseek": {
        "name": "DeepSeek",
        "env_var": "DEEPSEEK_KEY",
        "placeholder": "sk-...",
        "docs_url": "https://platform.deepseek.com/api_keys"
    },
    "xai": {
        "name": "xAI (Grok)",
        "env_var": "XAI_KEY",
        "placeholder": "xai-...",
        "docs_url": "https://console.x.ai/"
    },
    "mistral": {
        "name": "Mistral AI",
        "env_var": "MISTRAL_KEY",
        "placeholder": "...",
        "docs_url": "https://console.mistral.ai/api-keys/"
    },
    "cohere": {
        "name": "Cohere",
        "env_var": "COHERE_KEY",
        "placeholder": "...",
        "docs_url": "https://dashboard.cohere.com/api-keys"
    },
    "groq": {
        "name": "Groq",
        "env_var": "GROQ_API_KEY",
        "placeholder": "gsk_...",
        "docs_url": "https://console.groq.com/keys"
    },
    "perplexity": {
        "name": "Perplexity",
        "env_var": "PERPLEXITY_KEY",
        "placeholder": "pplx-...",
        "docs_url": "https://www.perplexity.ai/settings/api"
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_var": "OPENROUTER_API_KEY",
        "placeholder": "sk-or-...",
        "docs_url": "https://openrouter.ai/keys"
    }
}

# Default empty secrets
DEFAULT_SECRETS = {
    "api_keys": {},
    "last_updated": None
}


def load_secrets() -> Dict:
    """Load secrets from file, or return defaults if file doesn't exist"""
    try:
        if SECRETS_FILE.exists():
            with open(SECRETS_FILE, 'r') as f:
                secrets = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged = DEFAULT_SECRETS.copy()
                merged.update(secrets)
                return merged
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load secrets: {e}")

    return DEFAULT_SECRETS.copy()


def save_secrets(secrets: Dict) -> Tuple[bool, Optional[str]]:
    """
    Save secrets to file and update environment variables.

    Returns:
        Tuple of (success, error_message)
    """
    try:
        # Ensure data directory exists
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp
        secrets["last_updated"] = datetime.now().isoformat()

        # Save to file
        with open(SECRETS_FILE, 'w') as f:
            json.dump(secrets, f, indent=2)

        # Set restrictive permissions (owner read/write only)
        try:
            os.chmod(SECRETS_FILE, 0o600)
        except OSError:
            pass  # Windows doesn't support chmod the same way

        # Load keys into environment variables
        load_secrets_to_env()

        return True, None

    except IOError as e:
        return False, f"Failed to save secrets: {str(e)}"


def load_secrets_to_env():
    """Load saved API keys into environment variables"""
    secrets = load_secrets()
    api_keys = secrets.get("api_keys", {})

    for provider, key in api_keys.items():
        if provider in AI_PROVIDERS and key:
            env_var = AI_PROVIDERS[provider]["env_var"]
            os.environ[env_var] = key


def get_api_key(provider: str) -> Optional[str]:
    """Get API key for a provider from secrets or environment"""
    secrets = load_secrets()
    api_keys = secrets.get("api_keys", {})

    # First check our secrets file
    if provider in api_keys and api_keys[provider]:
        return api_keys[provider]

    # Fall back to environment variable
    if provider in AI_PROVIDERS:
        env_var = AI_PROVIDERS[provider]["env_var"]
        return os.getenv(env_var)

    return None


def set_api_key(provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Set API key for a provider.

    Args:
        provider: The provider identifier (e.g., 'anthropic', 'openai')
        api_key: The API key to store

    Returns:
        Tuple of (success, error_message)
    """
    if provider not in AI_PROVIDERS:
        return False, f"Unknown provider: {provider}"

    secrets = load_secrets()
    if "api_keys" not in secrets:
        secrets["api_keys"] = {}

    # Store the key (empty string to remove)
    if api_key:
        secrets["api_keys"][provider] = api_key.strip()
    elif provider in secrets["api_keys"]:
        del secrets["api_keys"][provider]

    return save_secrets(secrets)


def delete_api_key(provider: str) -> Tuple[bool, Optional[str]]:
    """Delete API key for a provider"""
    return set_api_key(provider, "")


def mask_api_key(api_key: str) -> str:
    """Mask an API key, showing only the last 4 characters"""
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return "*" * (len(api_key) - 4) + api_key[-4:]


def get_providers_status() -> Dict:
    """
    Get status of all providers (whether they have API keys configured).

    Returns a dict with provider info and masked keys.
    """
    secrets = load_secrets()
    api_keys = secrets.get("api_keys", {})

    providers_status = {}

    for provider_id, provider_info in AI_PROVIDERS.items():
        # Check secrets file first, then environment
        key = api_keys.get(provider_id)
        if not key:
            env_var = provider_info["env_var"]
            key = os.getenv(env_var)

        providers_status[provider_id] = {
            "name": provider_info["name"],
            "configured": bool(key),
            "masked_key": mask_api_key(key) if key else "",
            "placeholder": provider_info["placeholder"],
            "docs_url": provider_info["docs_url"],
            "source": "secrets" if api_keys.get(provider_id) else ("env" if key else "none")
        }

    return providers_status


def validate_api_key_format(provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
    """
    Basic validation of API key format.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key or not api_key.strip():
        return False, "API key cannot be empty"

    api_key = api_key.strip()

    # Basic length check
    if len(api_key) < 10:
        return False, "API key seems too short"

    # Provider-specific validation
    if provider == "anthropic" and not api_key.startswith("sk-ant-"):
        return False, "Anthropic keys should start with 'sk-ant-'"

    if provider == "openai" and not api_key.startswith("sk-"):
        return False, "OpenAI keys should start with 'sk-'"

    if provider == "gemini" and not api_key.startswith("AIza"):
        return False, "Gemini keys should start with 'AIza'"

    if provider == "groq" and not api_key.startswith("gsk_"):
        return False, "Groq keys should start with 'gsk_'"

    if provider == "openrouter" and not api_key.startswith("sk-or-"):
        return False, "OpenRouter keys should start with 'sk-or-'"

    return True, None


def get_available_providers() -> list:
    """Get list of all available provider IDs"""
    return list(AI_PROVIDERS.keys())


def get_provider_info(provider: str) -> Optional[Dict]:
    """Get info for a specific provider"""
    return AI_PROVIDERS.get(provider)
