"""
Tier Manager for AI Trading Dashboard
======================================
Handles user subscription tiers and feature access control.

Tiers:
- Based (Free): Limited trial with basic features
- Trader ($5/mo): Enhanced features with BYOK
- Pro: Full access including Swarm mode
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple

# Tier data file location
TIER_FILE = Path(__file__).parent.parent / "data" / "user_tiers.json"

# ============================================================================
# TIER DEFINITIONS
# ============================================================================

TIERS = {
    "based": {
        "name": "Based",
        "display_name": "Based (Free Trial)",
        "price": 0,
        "price_display": "Free",
        "description": "Perfect for getting started with AI trading",
        "features": {
            "max_tokens": 5,
            "min_cycle_minutes": 5,
            "min_timeframe": "5m",
            "allowed_timeframes": ["5m", "15m", "30m", "1h", "4h", "1d"],
            "swarm_mode": False,
            "byok": False,
            "max_swarm_models": 0,
            "providers": ["ollama", "ollamafreeapi"],  # Free providers only
        },
        "limits_display": [
            "Up to 5 tokens",
            "5+ minute cycles",
            "Single AI mode only",
            "Free AI models (Ollama)",
        ]
    },
    "trader": {
        "name": "Trader",
        "display_name": "Trader ($5/mo)",
        "price": 5,
        "price_display": "$5/month",
        "description": "For active traders who want more flexibility",
        "features": {
            "max_tokens": 10,
            "min_cycle_minutes": 5,
            "min_timeframe": "5m",
            "allowed_timeframes": ["5m", "15m", "30m", "1h", "4h", "1d"],
            "swarm_mode": False,
            "byok": True,
            "max_swarm_models": 0,
            "providers": "all",  # All providers with BYOK
        },
        "limits_display": [
            "Up to 10 tokens",
            "5+ minute cycles",
            "Single AI mode",
            "Bring Your Own Key (BYOK)",
            "All AI providers",
        ]
    },
    "pro": {
        "name": "Pro",
        "display_name": "Pro",
        "price": 20,
        "price_display": "$20/month",
        "description": "Full power for professional traders",
        "features": {
            "max_tokens": 999,  # Effectively unlimited
            "min_cycle_minutes": 1,
            "min_timeframe": "1m",
            "allowed_timeframes": ["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
            "swarm_mode": True,
            "byok": True,
            "max_swarm_models": 6,
            "providers": "all",
        },
        "limits_display": [
            "Unlimited tokens",
            "Any cycle time",
            "Swarm Mode (multi-AI)",
            "Up to 6 AI models",
            "All AI providers",
            "Priority support",
        ]
    }
}

# Users with special access (for testing/development)
# These users can access all tiers regardless of subscription
ADMIN_USERS = ["KW-Trader", "admin", "moondev"]

# ============================================================================
# TIER MANAGEMENT FUNCTIONS
# ============================================================================

def load_user_tiers() -> Dict:
    """Load user tier data from file"""
    try:
        if TIER_FILE.exists():
            with open(TIER_FILE, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not load tier data: {e}")

    return {"users": {}}


def save_user_tiers(data: Dict) -> bool:
    """Save user tier data to file"""
    try:
        TIER_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TIER_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except IOError as e:
        print(f"Error saving tier data: {e}")
        return False


def get_user_tier(username: str) -> str:
    """Get the tier for a specific user"""
    # Admin users get Pro tier
    if username in ADMIN_USERS:
        return "pro"

    data = load_user_tiers()
    user_data = data.get("users", {}).get(username, {})
    return user_data.get("tier", "based")  # Default to "based" tier


def set_user_tier(username: str, tier: str) -> Tuple[bool, Optional[str]]:
    """Set the tier for a user"""
    if tier not in TIERS:
        return False, f"Invalid tier: {tier}"

    data = load_user_tiers()
    if "users" not in data:
        data["users"] = {}

    data["users"][username] = {
        "tier": tier,
        "updated_at": datetime.now().isoformat()
    }

    if save_user_tiers(data):
        return True, None
    return False, "Failed to save tier data"


def is_admin_user(username: str) -> bool:
    """Check if user is an admin with full access"""
    return username in ADMIN_USERS


def get_tier_info(tier: str) -> Optional[Dict]:
    """Get full information about a tier"""
    return TIERS.get(tier)


def get_all_tiers() -> Dict:
    """Get all tier definitions"""
    return TIERS


def get_tier_features(tier: str) -> Dict:
    """Get features for a specific tier"""
    tier_info = TIERS.get(tier, TIERS["based"])
    return tier_info.get("features", {})


# ============================================================================
# FEATURE ACCESS CHECKS
# ============================================================================

def can_use_swarm_mode(username: str) -> bool:
    """Check if user can use swarm mode"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    return features.get("swarm_mode", False)


def can_use_byok(username: str) -> bool:
    """Check if user can use BYOK (Bring Your Own Key)"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    return features.get("byok", False)


def get_max_tokens(username: str) -> int:
    """Get maximum tokens allowed for user"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    return features.get("max_tokens", 5)


def get_min_cycle_minutes(username: str) -> int:
    """Get minimum cycle time in minutes for user"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    return features.get("min_cycle_minutes", 5)


def get_allowed_timeframes(username: str) -> list:
    """Get allowed timeframes for user"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    return features.get("allowed_timeframes", ["5m", "15m", "30m", "1h", "4h", "1d"])


def get_allowed_providers(username: str) -> list:
    """Get allowed AI providers for user"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    providers = features.get("providers", ["ollama", "ollamafreeapi"])

    if providers == "all":
        return ["anthropic", "openai", "gemini", "deepseek", "xai",
                "mistral", "cohere", "perplexity", "groq", "ollama",
                "ollamafreeapi", "openrouter"]
    return providers


def get_max_swarm_models(username: str) -> int:
    """Get maximum swarm models allowed for user"""
    tier = get_user_tier(username)
    features = get_tier_features(tier)
    return features.get("max_swarm_models", 0)


def validate_settings_for_tier(username: str, settings: Dict) -> Tuple[bool, list]:
    """
    Validate settings against user's tier limits.
    Returns (is_valid, list of error messages)
    """
    errors = []
    tier = get_user_tier(username)
    features = get_tier_features(tier)

    # Check token count
    tokens = settings.get("monitored_tokens", [])
    max_tokens = features.get("max_tokens", 5)
    if len(tokens) > max_tokens:
        errors.append(f"Your tier allows up to {max_tokens} tokens. Please upgrade to monitor more.")

    # Check cycle time
    cycle_minutes = settings.get("sleep_minutes", 30)
    min_cycle = features.get("min_cycle_minutes", 5)
    if cycle_minutes < min_cycle:
        errors.append(f"Your tier requires {min_cycle}+ minute cycles. Please upgrade for faster cycles.")

    # Check timeframe
    timeframe = settings.get("timeframe", "30m")
    allowed_timeframes = features.get("allowed_timeframes", [])
    if timeframe not in allowed_timeframes:
        errors.append(f"Timeframe '{timeframe}' not available on your tier.")

    # Check swarm mode
    swarm_mode = settings.get("swarm_mode", "single")
    if swarm_mode == "swarm" and not features.get("swarm_mode", False):
        errors.append("Swarm mode requires Pro tier. Please upgrade to use multiple AI models.")

    # Check swarm models count
    swarm_models = settings.get("swarm_models", [])
    max_swarm = features.get("max_swarm_models", 0)
    if len(swarm_models) > max_swarm:
        errors.append(f"Your tier allows up to {max_swarm} swarm models.")

    # Check provider access
    provider = settings.get("ai_provider", "ollama")
    allowed_providers = features.get("providers", [])
    if allowed_providers != "all" and provider not in allowed_providers:
        errors.append(f"Provider '{provider}' requires Trader tier or higher. Please upgrade or use Ollama.")

    return len(errors) == 0, errors


def get_tier_comparison() -> list:
    """Get tier comparison data for UI display"""
    comparison = []
    for tier_id, tier_info in TIERS.items():
        comparison.append({
            "id": tier_id,
            "name": tier_info["name"],
            "display_name": tier_info["display_name"],
            "price": tier_info["price"],
            "price_display": tier_info["price_display"],
            "description": tier_info["description"],
            "limits": tier_info["limits_display"],
            "features": tier_info["features"]
        })
    return comparison
