from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from app.models.discovery import LlmsResult
from app.utils.fetcher import fetch_url
from app.utils.heuristics import assess_llms_effectiveness
from app.utils.url_utils import get_site_root


def _is_html_document(text: str, content_type: str = "") -> bool:
    cleaned = (text or "").lstrip("\ufeff")
    return "html" in (content_type or "").lower() or bool(re.search(
        r"<!doctype\s+html|<(?:html|head|body|script|title)(?:\s|>)", cleaned[:2000], re.I,
    ))


def extract_llms_links(text: str, url: str) -> tuple[list[str], list[str]]:
    """Extract internal links and Markdown/plain-text direct links from llms.txt."""
    root_host = urlparse(get_site_root(url)).netloc.lower()
    file_path = urlparse(url).path
    internal_links: list[str] = []
    markdown_links: list[str] = []
    seen: set[str] = set()
    for target in re.findall(r"(?<!!)\[[^\]\n]+\]\(\s*<?([^\s)>]+)", text or ""):
        if target.startswith("#"):
            continue
        try:
            parsed = urlparse(urljoin(url, target))
        except ValueError:
            continue
        if (parsed.scheme in {"http", "https"} and parsed.netloc.lower() == root_host
                and parsed.path != file_path):
            full = parsed.geturl()
            if full not in seen:
                seen.add(full)
                internal_links.append(full)
                if re.search(r"\.(?:md|mdx|markdown|txt)$", parsed.path, re.I):
                    markdown_links.append(full)
    return internal_links, markdown_links


def inspect_llms_structure(text: str, url: str, content_type: str = "") -> dict[str, bool]:
    """Inspect the complete file; HTML fallback pages are not AI navigation files."""
    text = text.lstrip("\ufeff")
    is_html = _is_html_document(text, content_type)
    title = re.search(r"^#[ \t]+\S.*$", text, re.M)
    summary = False
    if title:
        for line in text[title.end():].splitlines():
            line = line.strip()
            if line.startswith("#"):
                break
            if line and not re.match(r"^(?:[-*+]\s|\d+\.\s|```|\[)", line):
                summary = bool(line.lstrip("> ").strip())
                if summary:
                    break
    internal_links, _ = extract_llms_links(text, url)
    return {
        "readable_text": bool(text.strip()) and not is_html,
        "title_and_summary": bool(title and summary),
        "internal_navigation": bool(internal_links),
    }


async def inspect_llms(base_url: str, client: httpx.AsyncClient | None = None) -> LlmsResult:
    """抓取并评估站点的 llms.txt、llms-full.txt 及 Markdown 导航直出能力"""
    site_root = get_site_root(base_url)
    llms_url = f"{site_root}/llms.txt"
    full_url = f"{site_root}/llms-full.txt"
    try:
        response = await fetch_url(llms_url, client=client)
    except Exception as exc:
        return LlmsResult(url=llms_url, exists=False, full_url=full_url, error=str(exc))

    full_exists = False
    full_status_code: int | None = None
    try:
        full_response = await fetch_url(full_url, client=client)
        full_status_code = full_response.status_code
        full_final_path = urlparse(full_response.final_url or "").path.lower()
        if (200 <= full_response.status_code < 300
                and full_final_path.endswith("llms-full.txt")
                and bool((full_response.text or "").strip())
                and not _is_html_document(full_response.text, full_response.headers.get("content-type", ""))):
            full_exists = True
    except Exception:
        full_exists = False

    if response.status_code >= 400:
        return LlmsResult(
            url=llms_url,
            exists=False,
            status_code=response.status_code,
            final_url=response.final_url,
            full_url=full_url,
            full_exists=full_exists,
            full_status_code=full_status_code,
        )

    content_type = response.headers.get("content-type", "")
    structure_checks = inspect_llms_structure(response.text, response.final_url, content_type)
    internal_links, markdown_links = extract_llms_links(response.text, response.final_url)

    sampled_link_checks: list[dict] = []
    if structure_checks.get("readable_text") and internal_links:
        candidates = (markdown_links + [u for u in internal_links if u not in markdown_links])[:3]
        for target in candidates:
            is_md = bool(re.search(r"\.(?:md|mdx|markdown|txt)$", urlparse(target).path, re.I))
            try:
                link_resp = await fetch_url(target, client=client)
                link_ct = link_resp.headers.get("content-type", "")
                ok = 200 <= link_resp.status_code < 300 and (
                    not is_md or (bool((link_resp.text or "").strip()) and not _is_html_document(link_resp.text, link_ct))
                )
                sampled_link_checks.append({
                    "url": target,
                    "status_code": link_resp.status_code,
                    "is_markdown": is_md,
                    "ok": ok,
                })
            except Exception as exc:
                sampled_link_checks.append({
                    "url": target,
                    "status_code": None,
                    "is_markdown": is_md,
                    "ok": False,
                    "error": str(exc)[:120],
                })

    preview = response.text[:500].strip()
    result = LlmsResult(
        url=llms_url,
        exists=True,
        status_code=response.status_code,
        content_preview=preview,
        content_length=len(response.text),
        final_url=response.final_url,
        content_type=content_type,
        structure_checks=structure_checks,
        full_url=full_url,
        full_exists=full_exists,
        full_status_code=full_status_code,
        markdown_links=markdown_links[:20],
        sampled_link_checks=sampled_link_checks,
    )
    quality = assess_llms_effectiveness(result)
    result.effectiveness_score = quality["score"]
    result.signals = quality["signals"]
    return result
