from __future__ import annotations

from urllib.parse import urljoin, urlparse, urlunparse

import tldextract


# 全局 TLD 提取器实例（关闭远程后缀列表更新，加快启动速度）
EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=None)


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


def get_site_root(url: str) -> str:
    """提取站点根 URL（scheme + netloc），如 https://example.com"""
    parsed = urlparse(normalize_url(url))
    return f"{parsed.scheme}://{parsed.netloc}"


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
    """判断 candidate_url 是否与 base_url 属于同一注册域名"""
    return registered_domain(base_url) == registered_domain(candidate_url)
