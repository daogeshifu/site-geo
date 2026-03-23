from __future__ import annotations

from typing import Any


REQUIRED_SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
]


def evaluate_security_headers(headers: dict[str, str]) -> dict[str, Any]:
    normalized = {key.lower(): value for key, value in headers.items()}
    checks: dict[str, dict[str, str | bool | None]] = {}
    present_count = 0

    for header in REQUIRED_SECURITY_HEADERS:
        value = normalized.get(header)
        is_present = value is not None
        if is_present:
            present_count += 1
        checks[header] = {"present": is_present, "value": value}

    score = int((present_count / len(REQUIRED_SECURITY_HEADERS)) * 100)
    return {"score": score, "checks": checks}
