"""
Settings Manager for AI Trading Dashboard
==========================================
Handles user-configurable settings storage and retrieval
"""

import json
import os
from pathlib import Path
from datetime import datetime

# Settings file location
SETTINGS_FILE = Path(__file__).parent.parent / "data" / "user_settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "timeframe": "30m",           # Default: 30 minutes
    "days_back": 2,               # Default: 2 days
    "sleep_minutes": 30,          # Default: 30 minutes between cycles
    "last_updated": None
}


def load_settings():
    """Load user settings from file, or return defaults if file doesn't exist"""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r') as f:
                settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged = DEFAULT_SETTINGS.copy()
                merged.update(settings)
                return merged
        else:
            # Create default settings file
            save_settings(DEFAULT_SETTINGS)
            return DEFAULT_SETTINGS.copy()
    except Exception as e:
        print(f"⚠️ Error loading settings: {e}")
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    """Save user settings to file"""
    try:
        # Ensure data directory exists
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Add timestamp
        settings["last_updated"] = datetime.now().isoformat()

        # Write to file
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)

        return True
    except Exception as e:
        print(f"❌ Error saving settings: {e}")
        return False


def update_setting(key, value):
    """Update a single setting"""
    try:
        settings = load_settings()
        settings[key] = value
        return save_settings(settings)
    except Exception as e:
        print(f"❌ Error updating setting {key}: {e}")
        return False


def validate_timeframe(timeframe):
    """Validate timeframe string"""
    valid_timeframes = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
    return timeframe in valid_timeframes


def validate_settings(settings):
    """Validate settings dictionary"""
    errors = []

    # Validate timeframe
    if "timeframe" in settings and not validate_timeframe(settings["timeframe"]):
        errors.append(f"Invalid timeframe: {settings['timeframe']}")

    # Validate days_back (1-30 days)
    if "days_back" in settings:
        try:
            days = int(settings["days_back"])
            if days < 1 or days > 30:
                errors.append("days_back must be between 1 and 30")
        except (ValueError, TypeError):
            errors.append("days_back must be a number")

    # Validate sleep_minutes (1-1440 minutes = 1 day max)
    if "sleep_minutes" in settings:
        try:
            minutes = int(settings["sleep_minutes"])
            if minutes < 1 or minutes > 1440:
                errors.append("sleep_minutes must be between 1 and 1440")
        except (ValueError, TypeError):
            errors.append("sleep_minutes must be a number")

    return len(errors) == 0, errors
