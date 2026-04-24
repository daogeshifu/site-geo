from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

import tldextract


# 全局 TLD 提取器实例（关闭远程后缀列表更新，加快启动速度）
EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=None)
SUPPORTED_LOCALES = {"en", "de", "nl", "fr", "zh"}


def _normalize_embedded_absolute(href: str) -> str:
    """处理特殊格式的链接：/http://... 形式（某些 CMS 的 bug）"""
    candidate = href.strip()
    if candidate.startswith("/http://") or candidate.startswith("/https://"):
        return candidate.lstrip("/")
    if candidate.startswith("http://") or candidate.startswith("https://"):
        return candidate
    return candidate


def normalize_url(url: str) -> str:
    """规范化 URL：
    - 去除首尾空格
    - 无协议头时添加 https://
    - 统一小写 scheme 和 netloc
    - 去除 fragment（#...）
    - 确保 path 不为空（补充 /）
    """
    raw = url.strip()
    if not raw:
        raise ValueError("URL is required")
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"

    parsed = urlparse(raw)
    path = parsed.path or "/"
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        fragment="",   # 去除 fragment，避免缓存键差异
        path=path,
    )
    return urlunparse(normalized)


def entry_url_candidates(url: str) -> list[str]:
    """为站点入口抓取生成候选 URL 列表

    目标是尽量贴近浏览器常见行为：
    - 先尝试用户原始输入归一化后的地址
    - 再尝试同 scheme 的 `www.` 变体
    - 若仍失败，再尝试切换到另一种 scheme（http/https）
    - 最后尝试另一种 scheme 下的 `www.` 变体

    示例：
    - `idtcpack.com` ->
      `https://idtcpack.com/`, `https://www.idtcpack.com/`, `http://idtcpack.com/`, `http://www.idtcpack.com/`
    """
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    alternate_scheme = "http" if parsed.scheme == "https" else "https"
    hosts = [parsed.netloc.lower()]
    if parsed.netloc and not parsed.netloc.lower().startswith("www."):
        hosts.append(f"www.{parsed.netloc.lower()}")

    candidates: list[str] = []
    for scheme in (parsed.scheme.lower(), alternate_scheme):
        for host in hosts:
            candidate = parsed._replace(scheme=scheme, netloc=host, fragment="")
            candidates.append(urlunparse(candidate))

    ordered: list[str] = []
    seen: set[str] = set()
    preferred_order = [
        (parsed.scheme.lower(), hosts[0]),
        *((parsed.scheme.lower(), host) for host in hosts[1:]),
        (alternate_scheme, hosts[0]),
        *((alternate_scheme, host) for host in hosts[1:]),
    ]
    for scheme, host in preferred_order:
        candidate = urlunparse(parsed._replace(scheme=scheme, netloc=host, fragment=""))
        if candidate not in seen:
            ordered.append(candidate)
            seen.add(candidate)
    return ordered


def get_site_root(url: str) -> str:
    """提取站点根 URL（scheme + netloc），如 https://example.com"""
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


def _is_locale_segment(segment: str) -> bool:
    lowered = segment.lower()
    if len(lowered) == 2 and lowered.isalpha():
        return True
    return len(lowered) == 5 and lowered[2] in {"-", "_"} and lowered.replace("-", "").replace("_", "").isalpha()


def normalize_locale(locale: str | None) -> str | None:
    if not locale:
        return None
    normalized = locale.strip().lower().replace("_", "-")
    return normalized or None


def base_locale(locale: str | None) -> str | None:
    normalized = normalize_locale(locale)
    if not normalized:
        return None
    return normalized.split("-", 1)[0]


def locales_match(left: str | None, right: str | None) -> bool:
    left_base = base_locale(left)
    right_base = base_locale(right)
    if not left_base or not right_base:
        return False
    return left_base == right_base


def detect_path_locale(url: str) -> str | None:
    parsed = urlparse(normalize_url(url))
    segments = [segment for segment in parsed.path.split("/") if segment]
    if segments and _is_locale_segment(segments[0]):
        return normalize_locale(segments[0])
    return None


def detect_subdomain_locale(url: str) -> str | None:
    parsed = urlparse(normalize_url(url))
    host = parsed.netloc.lower()
    labels = [label for label in host.split(".") if label]
    if len(labels) >= 3 and _is_locale_segment(labels[0]):
        return normalize_locale(labels[0])
    return None


def detect_explicit_locale(url: str) -> str | None:
    return detect_path_locale(url) or detect_subdomain_locale(url)


def build_locale_path_url(url: str, locale: str) -> str:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    path_locale = detect_path_locale(normalized)
    locale_value = base_locale(locale) or normalize_locale(locale) or locale
    if path_locale and locales_match(path_locale, locale_value):
        return normalized
    path = parsed.path or "/"
    segments = [segment for segment in path.split("/") if segment]
    if segments and _is_locale_segment(segments[0]):
        segments[0] = locale_value
    elif not segments:
        segments = [locale_value]
    else:
        segments.insert(0, locale_value)
    updated_path = "/" + "/".join(segments)
    if not updated_path.endswith("/"):
        updated_path += "/"
    return urlunparse(parsed._replace(path=updated_path, fragment=""))


def build_locale_subdomain_url(url: str, locale: str) -> str:
    normalized = normalize_url(url)
    parsed = urlparse(normalized)
    locale_value = base_locale(locale) or normalize_locale(locale) or locale
    labels = [label for label in parsed.netloc.split(".") if label]
    if labels:
        if _is_locale_segment(labels[0]):
            labels[0] = locale_value
        else:
            labels.insert(0, locale_value)
    netloc = ".".join(labels)
    return urlunparse(parsed._replace(netloc=netloc, fragment=""))


def get_scope_prefix(url: str) -> str:
    """返回 URL 的抓取作用域前缀

    规则：
    - 默认作用域为 `/`
    - 若首段是语言段（如 /de、/en-us），则作用域为 `/<locale>/`
    """
    parsed = urlparse(normalize_url(url))
    segments = [segment for segment in parsed.path.split("/") if segment]
    if segments and _is_locale_segment(segments[0]):
        return f"/{segments[0].lower()}/"
    return "/"


def get_scope_root(url: str) -> str:
    """返回带路径作用域的站点根，如 https://example.com/de/ 或 https://de.example.com/"""
    site_root = get_site_root(url)
    scope_prefix = get_scope_prefix(url)
    if scope_prefix == "/":
        return f"{site_root}/"
    return f"{site_root}{scope_prefix}"


def scope_identifier(url: str) -> str:
    """返回用于缓存和边界判定的作用域标识：host + scope_prefix"""
    parsed = urlparse(normalize_url(url))
    return f"{parsed.netloc.lower()}|{get_scope_prefix(url)}"


def ensure_absolute_url(base_url: str, href: str) -> str:
    """将相对 URL 解析为绝对 URL，处理嵌入式绝对 URL 的特殊情况"""
    normalized_href = _normalize_embedded_absolute(href)
    return urljoin(base_url, normalized_href)


def registered_domain(url: str) -> str:
    """提取注册域名（domain.tld），如 example.com、example.co.uk

    使用 tldextract 正确处理多级后缀（.co.uk、.com.cn 等）
    """
    extracted = EXTRACTOR(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}"
    return extracted.domain or ""


def is_internal_url(base_url: str, candidate_url: str) -> bool:
    """判断 candidate_url 是否与 base_url 属于同一抓取作用域

    作用域规则：
    - 必须精确 host 相同
    - 若 base_url 属于语言路径站点（如 /de/），candidate_url 必须也在该前缀下
    """
    base = urlparse(normalize_url(base_url))
    candidate = urlparse(normalize_url(candidate_url))
    if base.netloc.lower() != candidate.netloc.lower():
        return False
    scope_prefix = get_scope_prefix(base_url)
    if scope_prefix == "/":
        return True
    candidate_path = candidate.path or "/"
    normalized_path = candidate_path if candidate_path.endswith("/") else f"{candidate_path}/"
    return normalized_path.startswith(scope_prefix)


def is_likely_homepage_url(url: str) -> bool:
    """判断 URL 是否像首页或语言首页

    允许：
    - /
    - /en
    - /en/
    - /en-us
    - /zh-cn/
    """
    parsed = urlparse(normalize_url(url))
    path = (parsed.path or "/").strip("/")
    if not path:
        return True
    segments = [segment for segment in path.split("/") if segment]
    if len(segments) != 1:
        return False
    return _is_locale_segment(segments[0])
