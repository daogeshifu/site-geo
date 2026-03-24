from __future__ import annotations

from typing import Any


# 需要检查的安全响应头（每个存在加 20 分）
REQUIRED_SECURITY_HEADERS = [
    "strict-transport-security",   # HSTS：强制 HTTPS 连接
    "content-security-policy",     # CSP：防止 XSS 攻击
    "x-frame-options",             # 防止点击劫持（Clickjacking）
    "x-content-type-options",      # 防止 MIME 类型嗅探
    "referrer-policy",             # 控制 Referer 信息泄露
]


def evaluate_security_headers(headers: dict[str, str]) -> dict[str, Any]:
    """评估 HTTP 响应中的安全头覆盖情况

    Args:
        headers: HTTP 响应头字典

    Returns:
        {
            "score": 0-100（存在率 * 100，每个头 20 分）,
            "checks": {header_name: {"present": bool, "value": str|None}, ...}
        }
    """
    # 统一小写处理响应头名称（HTTP 头不区分大小写）
    normalized = {key.lower(): value for key, value in headers.items()}
    checks: dict[str, dict[str, str | bool | None]] = {}
    present_count = 0

    for header in REQUIRED_SECURITY_HEADERS:
        value = normalized.get(header)
        is_present = value is not None
        if is_present:
            present_count += 1
        checks[header] = {"present": is_present, "value": value}

    # 评分 = 存在的安全头数量 / 总检查数量 * 100
    score = int((present_count / len(REQUIRED_SECURITY_HEADERS)) * 100)
    return {"score": score, "checks": checks}
