"""API Endpoint and route path normalizer."""

import re

LEGACY_ALIASES = {
    "/account": "/users/me",
    "/profile": "/users/me/profile",
    "/status": "/health",
}


def normalize_endpoint(raw_path: str, default_version: str = "v1") -> str:
    """Normalizes an API route path with consistent versioning and formatting.

    Rules:
    - Multiple consecutive slashes are collapsed to single slashes.
    - Leading and trailing slashes are stripped before prefixing.
    - Legacy route aliases are expanded.
    - If no API version (e.g. 'v1', 'v2') is present at start, default_version is prepended.
    - Returns format: '/{version}/{route}'
    """
    if not isinstance(raw_path, str):
        raise TypeError("raw_path must be a string")

    stripped = raw_path.strip()
    if not stripped:
        return f"/{default_version}"

    # BUG / LIMITATION: Current implementation throws on queries and fragments
    if "?" in stripped or "#" in stripped:
        raise ValueError("Invalid character in path: query parameters and fragments are not supported")

    # Replace consecutive slashes
    clean_path = "/" + re.sub(r"/+", "/", stripped).strip("/")

    # Check for legacy aliases
    if clean_path in LEGACY_ALIASES:
        clean_path = LEGACY_ALIASES[clean_path]

    parts = [p for p in clean_path.split("/") if p]
    if not parts:
        return f"/{default_version}"

    # If first part is a version like 'v1', 'v2'
    if re.match(r"^v\d+$", parts[0]):
        return "/" + "/".join(parts)

    return f"/{default_version}/" + "/".join(parts)

