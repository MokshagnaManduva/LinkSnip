"""
utils.py - Utility functions for the URL Shortener
====================================================
Pure helper functions with no side effects or database access.
"""

import re
import secrets
import string
from urllib.parse import urlparse


# Character set for random short IDs: a-z, A-Z, 0-9 (62 chars).
# With length=6 this gives 62^6 ≈ 56.8 billion possible IDs — plenty to
# avoid collisions for any reasonable workload.
_ALPHABET = string.ascii_letters + string.digits

# Pre-compiled regex for validating custom aliases.
# Allowed characters: letters, digits, and hyphens.
_ALIAS_PATTERN = re.compile(r"^[a-zA-Z0-9-]+$")

# Maximum lengths
_MAX_URL_LENGTH = 2048
_MAX_ALIAS_LENGTH = 30


def generate_short_id(length: int = 6) -> str:
    """
    Generate a cryptographically random short ID.

    Args:
        length: Number of characters (default 6).

    Returns:
        A random alphanumeric string, e.g. "aB3xZ9".

    Uses `secrets.choice` for cryptographic randomness — important because
    predictable IDs could let attackers enumerate all stored URLs.
    """
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def validate_url(url: str) -> tuple[bool, str]:
    """
    Validate that a URL is well-formed and safe to store.

    Checks:
      1. Not empty / whitespace-only.
      2. Starts with http:// or https:// (no javascript:, ftp:, etc.).
      3. Has a valid netloc (domain).
      4. Total length ≤ 2048 characters.

    Args:
        url: The URL string to validate.

    Returns:
        (is_valid, error_message) — error_message is empty when valid.
    """
    if not url or not url.strip():
        return False, "URL is required."

    url = url.strip()

    if len(url) > _MAX_URL_LENGTH:
        return False, f"URL must be {_MAX_URL_LENGTH} characters or fewer."

    # Only allow http and https schemes
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False, "URL must start with http:// or https://."

    # Must have a domain (e.g. "example.com")
    if not parsed.netloc or "." not in parsed.netloc:
        return False, "URL must include a valid domain (e.g. example.com)."

    return True, ""


def sanitize_alias(alias: str) -> tuple[bool, str]:
    """
    Validate a user-supplied custom alias.

    Rules:
      - 1–30 characters long.
      - Only letters, digits, and hyphens ([a-zA-Z0-9-]).
      - No leading/trailing hyphens (aesthetic choice).

    Args:
        alias: The custom alias string.

    Returns:
        (is_valid, error_message) — error_message is empty when valid.
    """
    if not alias or not alias.strip():
        return False, "Custom alias cannot be empty."

    alias = alias.strip()

    if len(alias) > _MAX_ALIAS_LENGTH:
        return False, f"Alias must be {_MAX_ALIAS_LENGTH} characters or fewer."

    if len(alias) < 1:
        return False, "Alias must be at least 1 character."

    if not _ALIAS_PATTERN.match(alias):
        return False, "Alias may only contain letters, digits, and hyphens."

    if alias.startswith("-") or alias.endswith("-"):
        return False, "Alias cannot start or end with a hyphen."

    return True, ""


def truncate_url(url: str, max_length: int = 60) -> str:
    """
    Truncate a URL for display purposes, adding an ellipsis if shortened.

    Examples:
        "https://example.com/short"       → "https://example.com/short"
        "https://example.com/very/long..." → "https://example.com/very/lo…"

    Args:
        url:        The URL string to truncate.
        max_length: Maximum display length (default 60).

    Returns:
        The (possibly truncated) URL string.
    """
    if not url:
        return ""
    if len(url) <= max_length:
        return url
    return url[: max_length - 1] + "…"
