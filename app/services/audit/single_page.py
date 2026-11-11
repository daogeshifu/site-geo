from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.exceptions import AppError
from app.services.audit.page_rules import detailed_page_checks
from app.utils.html_parser import parse_html
from app.utils.schema_extractor import extract_schema_summary
from app.utils.url_utils import base_locale, normalize_url


class SinglePageAuditService:
    """Diagnose only the supplied HTML document; never crawl or resolve locale links."""

    def __init__(self, transport=None):
        self.transport = transport

    async def audit(self, url: str, *, country=None, target_locale=None, feedback_lang="zh") -> dict:
        normalized = normalize_url(url)
        parts = urlparse(normalized)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise AppError(400, "Invalid HTTP/HTTPS page URL")
        headers = {"User-Agent": settings.default_user_agent}
        if target_locale:
            language = f"{target_locale}-{country}" if country else target_locale
            headers["Accept-Language"] = f"{language},{target_locale};q=0.9"
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=settings.request_timeout_seconds, follow_redirects=False,
                headers=headers, transport=self.transport,
            ) as client:
                response = await client.get(normalized)
        except httpx.RequestError as exc:
            raise AppError(502, "Failed to fetch requested page", str(exc)) from exc
        elapsed = round((time.perf_counter() - started) * 1000)
        location = response.headers.get("location")
        if response.is_redirect:
            raise AppError(422, "Requested page redirects; destination was not fetched", {
                "requested_url": normalized, "status_code": response.status_code,
                "redirect_url": urljoin(normalized, location) if location else None,
                "audited_urls": [],
            })
        if response.status_code >= 400:
            raise AppError(422, "Requested page returned an HTTP error", {
                "requested_url": normalized, "status_code": response.status_code,
                "audited_urls": [],
            })
        if "html" not in response.headers.get("content-type", "").lower():
            raise AppError(422, "Requested URL did not return an HTML document")
        parsed = parse_html(normalized, response.text, scope_url=normalized)
        schema = extract_schema_summary(parsed["json_ld_blocks"], visible_text=parsed["text_content"])
        soup = BeautifulSoup(response.text, "lxml")
        zh = feedback_lang == "zh"
        checks = []

        def check(key, passed, zh_label, en_label, zh_fix, en_fix):
            checks.append({"key": key, "passed": bool(passed),
                           "label": zh_label if zh else en_label,
                           "severity": "issue", "scope": "response_html",
                           "recommendation": None if passed else (zh_fix if zh else en_fix)})

        check("title", parsed["title"], "页面标题", "Page title", "补充描述当前页面内容的 title。", "Add a descriptive title for this page.")
        check("description", parsed["meta_description"], "页面描述", "Meta description", "补充当前页面的 meta description。", "Add a meta description for this page.")
        check("canonical", parsed["canonical"], "规范链接", "Canonical", "声明当前页面的规范链接。", "Declare the preferred URL for this page.")
        check("language", parsed["lang"], "页面语言声明", "HTML language", "声明 html lang。", "Declare the HTML language.")
        detected = base_locale(parsed["lang"])
        if target_locale:
            check("target_language", detected == base_locale(target_locale), "目标语言匹配", "Target language match", "核对链接与 HTML lang 是否对应目标语言。", "Check that this URL and HTML lang match the requested language.")
        h1s = [h for h in parsed["headings"] if h["level"] == "h1"]
        check("h1", len(h1s) == 1, "唯一主标题", "Single H1", "为页面保留一个描述明确的 H1。", "Use one descriptive H1 on the page.")
        check("headings", any(h["level"] in {"h2", "h3"} for h in parsed["headings"]), "内容分节", "Content sections", "用 H2/H3 组织页面内容。", "Organize the page with H2/H3 sections.")
        check("visible_text", bool(parsed["text_content"].strip()), "可抓取正文", "Crawlable text", "在 HTML 中提供可抓取的正文。", "Provide crawlable text in the HTML.")
        check("viewport", parsed["viewport"], "移动端声明", "Viewport", "补充移动端 viewport。", "Add a mobile viewport declaration.")
        images = parsed["images"]
        if images:
            check("image_alt", all(i.has_attr("alt") for i in soup.find_all("img")), "图片替代文本声明", "Image alt attributes", "为图片声明 alt；信息图片填写描述，装饰图片可用空 alt。", "Declare alt attributes; describe informative images and use empty alt for decorative images.")
        check("structured_data", schema.get("json_ld_present"), "结构化数据", "Structured data", "增加与当前页面类型匹配的 JSON-LD。", "Add JSON-LD relevant to this page type.")
        robots = " ".join((tag.get("content") or "") for tag in soup.find_all("meta", attrs={"name": lambda v: v and v.lower() in {"robots", "googlebot"}}))
        robots += " " + response.headers.get("x-robots-tag", "")
        directives = set(robots.lower().replace(",", " ").split())
        check("indexable", not ({"noindex", "none"} & directives), "页面索引指令", "Indexing directives", "核对 noindex 是否符合该页面的收录意图。", "Review whether noindex matches the intended indexing policy.")
        is_product = bool(schema.get("has_product")) or "/buy/" in parts.path or "-buy" in parts.path
        page_type = "product" if is_product else "article" if schema.get("has_article") else "page"
        if is_product:
            check("product_schema", schema.get("has_product"), "商品结构化数据", "Product schema", "为商品页添加与可见商品信息一致的 Product JSON-LD。", "Add Product JSON-LD aligned with visible product information.")
        elif page_type == "article":
            check("article_date", schema.get("has_date_published"), "文章发布日期", "Article publication date", "为文章声明真实的发布日期。", "Declare the article's actual publication date.")
        checks.extend(detailed_page_checks(soup, parsed, normalized, response, is_product=is_product, zh=zh))
        evidence = {
            "title": parsed["title"], "description": parsed["meta_description"],
            "canonical": parsed["canonical"], "language": parsed["lang"],
            "target_language": {"expected": target_locale, "detected": detected},
            "h1": {"count": len(h1s), "texts": [h["text"] for h in h1s]},
            "headings": parsed["headings"], "visible_text": {"word_count": parsed["word_count"]},
            "viewport": parsed["viewport"],
            "image_alt": {"total":len(soup.find_all('img')), "missing":sum(not i.has_attr('alt') for i in soup.find_all('img'))},
            "structured_data": schema, "product_schema": schema.get("types"),
            "indexable": robots.strip(), "article_date": schema.get("has_date_published"),
        }
        for c in checks:
            c.setdefault("evidence", evidence.get(c["key"]))
        required = [c for c in checks if c["severity"] == "issue"]
        passed = sum(c["passed"] for c in required)
        score = round(100 * passed / len(required))
        issues = [c["label"] for c in required if not c["passed"]]
        advisories = [c["label"] for c in checks if c["severity"] == "advisory" and not c["passed"]]
        recommendations = [c["recommendation"] for c in checks if not c["passed"]]
        page = {
            "url": normalized, "final_url": str(response.url), "page_type": page_type,
            "status_code": response.status_code, "response_time_ms": elapsed,
            "title": parsed["title"], "meta_description": parsed["meta_description"],
            "canonical": parsed["canonical"], "html_lang": parsed["lang"],
            "detected_language": detected, "word_count": parsed["word_count"],
            "headings": parsed["headings"], "schema": schema,
            "checks": checks, "overall_score": score, "issues": issues,
            "advisories": advisories,
            "findings": [c for c in checks if not c["passed"]],
            "recommendations": recommendations,
        }
        return {
            "audit_scope": "page", "url": url, "requested_url": normalized,
            "final_url": str(response.url), "country": country, "target_locale": target_locale,
            "detected_language": detected, "feedback_lang": feedback_lang,
            "audited_urls": [normalized], "audited_page_count": 1,
            "page": page, "page_diagnostics": [page],
            "summary": {"score": score, "scoring_version": "single-page-checks-v2",
                        "score_method": "passed_required_checks / applicable_required_checks * 100; advisory checks excluded",
                        "passed_checks": sum(c["passed"] for c in checks), "total_checks": len(checks),
                        "passed_required_checks": passed, "total_required_checks": len(required),
                        "issue_count": len(issues), "advisory_count": len(advisories),
                        "advisories": advisories,
                        "top_issues": issues, "quick_wins": recommendations,
                        "llm_enhanced": False,
                        "limitations": ["仅检查响应 HTML，不执行 JavaScript，不检查其他页面及站点级信号。" if zh else "Response HTML only; JavaScript, other pages and site-wide signals are not evaluated."]},
        }
