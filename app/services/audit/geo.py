"""On-site GEO readiness (onsite-geo-v3): 27 uniquely owned checks, six fixed dimensions.

Retains the 4-stage (Retrievable / Understandable / Citable / Recommendable) x 6-dimension
architecture while upgrading P0/P1 technical checks: AI crawler WAF probes, expanded
global+domestic retrieval crawlers, Google-Extended & Content-Signal parsing, anti-CSR
shell detection, Sitemap quality, llms-full.txt & Markdown delivery, Schema.org + sameAs
entity disambiguation, HTML content-to-noise ratio, hreflang, and automated cross-page
fact consistency.
"""
from __future__ import annotations

import asyncio
import json
import math
import re
import time
from collections import Counter
from datetime import date, datetime
from typing import Any
from urllib.parse import parse_qsl, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.models.discovery import DiscoveryResult
from app.models.geo import GEO_SCORING_VERSION, GeoAuditResult, GeoCheckResult, GeoDimensionResult, GeoPageResult
from app.services.audit.scoring import ScoringService
from app.services.crawlers.catalog import GOOGLEBOT_SMARTPHONE_UA, OAI_SEARCH_UA
from app.services.discovery.discovery import DiscoveryService
from app.services.google_crawler.google_render import GoogleRenderService
from app.services.infra.audit_evidence import PageEvidence, collect_page_evidence, sample_candidates
from app.utils.llms_parser import inspect_llms_structure
from app.utils.robots_parser import (
    inspect_google_extended,
    inspect_robot_path,
    inspect_training_crawlers,
    parse_content_signals,
    parse_robots_extras,
    search_crawlers_for_site,
)
from app.utils.schema_extractor import extract_schema_summary
from app.utils.url_utils import detect_explicit_locale, is_internal_url, normalize_url


DIMENSIONS = {
    "access": (20, "可获取：访问与抓取可达性", "Retrievable: Access and crawlability"),
    "discovery": (15, "可获取：页面发现与可索引性", "Retrievable: Discovery and indexability"),
    "extraction": (18, "可理解：正文读取与信息提取", "Understandable: Content extraction"),
    "semantics": (12, "可理解：元数据与实体语义", "Understandable: Metadata and entity semantics"),
    "answers": (20, "可引用：内容价值与答案适配", "Citable: Content and answer readiness"),
    "trust": (15, "可推荐：站内可信度与时效性", "Recommendable: On-site trust and freshness"),
}

# id, dimension, maximum points, Chinese label, English label
RULES = [
    ("GEO-001", "access", 5, "HTTP状态、HTTPS、主域与重定向规范", "HTTP status, HTTPS, canonical host and redirects"),
    ("GEO-002", "access", 6, "Robots.txt与AI检索爬虫精细化放行", "Robots.txt and AI retrieval crawler policy"),
    ("GEO-003", "access", 5, "CDN/WAF放行与AI爬虫访问挑战", "CDN/WAF allowlisting and AI crawler access challenges"),
    ("GEO-005", "discovery", 2, "可抓取导航与语义化内链", "Crawlable navigation and semantic internal links"),
    ("GEO-006", "discovery", 3, "XML Sitemap质量与页面发现覆盖", "XML Sitemap quality and page discovery coverage"),
    ("GEO-007", "discovery", 2, "Canonical规范链接与跳转一致", "Canonical URL and redirect consistency"),
    ("GEO-008", "discovery", 2, "索引与摘要指令（Noindex/Nosnippet）", "Indexing and snippet directives"),
    ("GEO-009", "extraction", 7, "初始HTML核心正文直出与反CSR空壳", "Initial HTML main content and anti-CSR shell"),
    ("GEO-010", "extraction", 5, "关键信息载体与标准HTML语义表格", "Complete information containers and semantic HTML tables"),
    ("GEO-011", "extraction", 4, "原始HTML与渲染后DOM一致性", "Raw HTML and rendered DOM consistency"),
    ("GEO-012", "answers", 5, "Title/H1意图聚焦与正文对应", "Title/H1 intent focus and body alignment"),
    ("GEO-013", "answers", 5, "首段结论前置与问答摘要结构", "Prominent opening answer and Q&A summary structure"),
    ("GEO-014", "answers", 4, "标题层级规范与段落自包含性", "Heading hierarchy and self-contained passages"),
    ("GEO-015", "answers", 4, "页面任务核心信息完备度", "Core task information for this page type"),
    ("GEO-016", "answers", 2, "具象量化表达与低冗余", "Specific quantified expression and low redundancy"),
    ("GEO-017", "trust", 4, "官方发布主体、作者与责任团队", "Official publisher, author or responsible team"),
    ("GEO-018", "trust", 5, "关键主张与数据出处可追溯", "Traceable sources for key claims and data"),
    ("GEO-019", "trust", 4, "机器可读时效性与版本价格明确度", "Machine-readable freshness, version and pricing clarity"),
    ("GEO-020", "trust", 2, "跨页面关键实体与事实一致性", "Cross-page entity and fact consistency"),
    ("GEO-021", "semantics", 2, "页面TDK与语言元数据", "Page title, description and language metadata"),
    ("GEO-022", "semantics", 3, "实体命名、@id与权威关联（sameAs/about/mentions）", "Entity naming, @id and authoritative links"),
    ("GEO-023", "semantics", 5, "适用Schema.org（JSON-LD）与正文一致性", "Relevant Schema.org JSON-LD and visible alignment"),
    ("GEO-024", "discovery", 4, "llms.txt与Markdown纯文本直出", "llms.txt and Markdown plain-text delivery"),
    ("GEO-025", "access", 4, "页面加载速度（TTFB与HTML获取）", "Page loading speed (TTFB and HTML fetch)"),
    ("GEO-026", "discovery", 2, "URL静态化与语义规范", "Static-style URLs and semantic hygiene"),
    ("GEO-027", "extraction", 2, "HTML正文信噪比与响应体量", "HTML content-to-noise ratio and payload size"),
    ("GEO-028", "semantics", 2, "多语言与区域标记（hreflang）", "Multilingual and regional hreflang annotations"),
]
RULE_MAP = {row[0]: row for row in RULES}

AI_WAF_PROBE_AGENTS = (
    ("OAI-SearchBot", OAI_SEARCH_UA + "+https://openai.com/searchbot"),
    ("PerplexityBot", "Mozilla/5.0 (compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)"),
    ("Claude-SearchBot", "Claude-SearchBot"),
    ("Googlebot", GOOGLEBOT_SMARTPHONE_UA),
)

SOFT_404_TITLE_RE = re.compile(
    r"^(?:404\b|page not found\b|not found\b|找不到页面|页面不存在|网页不存在|无法找到该页|404\s*[-–|:：])",
    re.I,
)
CHALLENGE_TITLE_RE = re.compile(
    r"(?:just a moment|attention required|access denied|verify (?:you are|that you are) human|"
    r"enable javascript and cookies|one more step|ddos protection|security check|"
    r"请完成验证|安全验证|访问被拒绝|人机验证|请求被拦截)",
    re.I,
)
CSR_PLACEHOLDER_RE = re.compile(
    r"^(?:loading\.{0,3}|please wait\.{0,3}|initializing\.{0,3}|redirecting\.{0,3}|"
    r"加载中\.{0,3}|正在加载\.{0,3}|请稍候\.{0,3}|enable javascript.*)$",
    re.I,
)
NOSCRIPT_JS_RE = re.compile(
    r"enable javascript|javascript (?:is )?required|you need to enable javascript|"
    r"doesn'?t work properly without javascript|请开启\s*javascript|启用\s*javascript|需要\s*javascript",
    re.I,
)
NON_SOURCE_LINK_RE = re.compile(
    r"/(?:buy|cart|checkout|shop|login|signin|sign-in|signup|sign-up|register|pricing|contact|subscribe)(?:/|$)|"
    r"^(?:mailto:|tel:|javascript:)",
    re.I,
)
SITEMAP_DIRTY_RE = re.compile(r"(?:[?&](?:utm_|sessionid|phpsessid|jsessionid|sid|replytocom)=|;jsessionid=|#)", re.I)
ENGLISH_DATE_RE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+20\d{2}\b|"
    r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+20\d{2}\b",
    re.I,
)
CHINESE_DATE_RE = re.compile(r"20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日")
PRICE_TEXT_RE = re.compile(r"(?:[$€£¥]|USD|EUR|GBP|CNY|RMB)\s*\d[\d,]*(?:\.\d{1,2})?|\d[\d,]*(?:\.\d{1,2})?\s*(?:元|美元|欧元)", re.I)
QUESTION_HEADING_RE = re.compile(
    r"[?？]\s*$|^(?:what|how|why|when|where|which|who|can|does|is|are|should)\b|"
    r"^(?:什么|如何|怎么|为什么|为何|是否|哪些|哪个|怎样)",
    re.I,
)
SPEC_CUE_RE = re.compile(r"规格|参数|配置|对比|选型|价格表|specifications?|specs|comparison|pricing|benchmark", re.I)
REF_HEADING_RE = re.compile(r"参考资料|数据来源|参考文献|来源说明|引用来源|references?|sources?|citations?|methodology", re.I)
CITATION_MARKER_RE = re.compile(r"\[\d+\]|(?:ISO|IEC|RFC|IEEE|GB/T)\s*[-:]?\s*\d+|白皮书|whitepaper|来源[:：]|数据来源|source[:：]", re.I)
VAGUE_COPY_RE = re.compile(
    r"行业领先|全方位赋能|全链路赋能|一站式解决|世界一流|世界领先|颠覆性|"
    r"industry.leading|best.in.class|cutting.edge|next.generation|world.class|revolutionary|all.in.one solution",
    re.I,
)
CONCRETE_FACT_RE = re.compile(
    r"\d+(?:\.\d+)?\s*(?:%|％|ms|s|秒|小时|天|GB|MB|KB|TB|W|kW|Wh|kWh|mAh|V|A|Hz|GHz|mm|cm|m|kg|g|TOPS|元|美元|USD|EUR|倍)|"
    r"\bv\d+\.\d+|\b20\d{2}\b",
    re.I,
)


def main_document(html: str) -> tuple[BeautifulSoup, Any, str]:
    soup = BeautifulSoup(html or "", "lxml")
    for element in soup.select("script:not([type='application/ld+json']), style, template, [hidden], [aria-hidden='true']"):
        element.decompose()
    for element in soup.select("[style]"):
        if element.attrs is not None and re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", element.get("style", ""), re.I):
            element.decompose()
    root = soup.select_one("main, article, [role='main']") or soup.body or soup.new_tag("main")
    # Malformed markup can place the content landmark inside navigation. Keep
    # that landmark while still excluding navigation and other boilerplate.
    protected = {id(root), *(id(parent) for parent in root.parents)}
    for element in soup.select("nav, footer, aside"):
        if id(element) not in protected:
            element.decompose()
    text = root.get_text(" ", strip=True)
    return soup, root, text


def _tokens(text: str) -> set[str]:
    words = set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", text.lower()))
    for fragment in re.findall(r"[\u4e00-\u9fff]+", text):
        words.update(fragment[i:i + 2] for i in range(max(1, len(fragment) - 1)))
    return words - {"the", "and", "for", "with", "from", "this", "that", "your", "our"}


def _nodes(data: Any):
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from _nodes(value)
    elif isinstance(data, list):
        for value in data:
            yield from _nodes(value)


def _schema(soup):
    parsed, errors, raw_blocks = [], [], []
    for element in soup.select("script[type='application/ld+json']"):
        block = element.get_text()
        if block and block.strip():
            raw_blocks.append(block)
        try:
            parsed.extend(_nodes(json.loads(block)))
        except (TypeError, ValueError) as exc:
            errors.append(str(exc)[:120])
    return parsed, errors, raw_blocks


def _types(node):
    values = node.get("@type", [])
    return {
        str(value).rsplit("/", 1)[-1].rsplit("#", 1)[-1].rsplit(":", 1)[-1].lower()
        for value in (values if isinstance(values, list) else [values])
        if value
    }


def _canonical(url):
    try:
        return normalize_url(url).rstrip("/")
    except ValueError:
        return url


def _parse_date_candidate(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    iso_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if iso_match:
        try:
            return date(int(iso_match[1]), int(iso_match[2]), int(iso_match[3]))
        except ValueError:
            return None
    zh_match = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", text)
    if zh_match:
        try:
            return date(int(zh_match[1]), int(zh_match[2]), int(zh_match[3]))
        except ValueError:
            return None
    cleaned = re.sub(r",", "", text)
    for fmt in ("%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _parse_http_link_header(header_value: str, base_url: str) -> list[dict[str, str]]:
    """Parse HTTP Link header entries such as canonical, alternate hreflang, or markdown."""
    entries: list[dict[str, str]] = []
    if not header_value:
        return entries
    for part in header_value.split(","):
        match = re.search(r"<([^>]+)>", part)
        if not match:
            continue
        href = urljoin(base_url, match.group(1).strip())
        params = dict(re.findall(r';\s*([a-zA-Z0-9_-]+)\s*=\s*"?([^";]+)"?', part))
        entries.append({"href": href, **{k.lower(): v.strip() for k, v in params.items()}})
    return entries


def _detect_challenge_response(status_code: int | None, headers: dict[str, str], html: str | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    lowered_headers = {k.lower(): str(v) for k, v in (headers or {}).items()}
    if lowered_headers.get("cf-mitigated"):
        reasons.append(f"cf-mitigated:{lowered_headers['cf-mitigated']}")
    if status_code in {401, 403, 407, 429, 451, 503}:
        reasons.append(f"http_{status_code}")
    if html:
        soup = BeautifulSoup(html[:120_000], "lxml")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if soup.select("#challenge-form, #cf-challenge-running, .g-recaptcha, .h-captcha, .cf-turnstile"):
            reasons.append("challenge_dom")
        if soup.select("input[type='password']") and re.search(r"login|log in|sign in|登录|登入", title, re.I):
            reasons.append("login_wall")
        if CHALLENGE_TITLE_RE.search(title.strip()):
            reasons.append("challenge_title")
    return bool(reasons), reasons


class GeoAuditService:
    SCORING_VERSION = GEO_SCORING_VERSION
    DIMENSIONS = DIMENSIONS
    RULES = RULES

    def __init__(self, discovery_service=None):
        self.discovery_service = discovery_service or DiscoveryService()
        self.renderer = GoogleRenderService()

    @staticmethod
    def _label(zh, en, lang):
        return zh if lang == "zh" else en

    async def _probe_host_variants(self, final_url: str) -> dict[str, bool | None]:
        """Probe http->https and www/apex unification on the site root."""
        parsed = urlparse(final_url)
        host = parsed.netloc
        scheme = parsed.scheme or "https"
        if not host:
            return {}
        bare_host = host[4:] if host.startswith("www.") else host
        www_host = host if host.startswith("www.") else f"www.{host}"
        preferred = normalize_url(f"{scheme}://{host}/")
        candidates = {
            "http_to_https": f"http://{host}/",
            "non_www_to_preferred": f"{scheme}://{bare_host}/",
            "www_to_preferred": f"{scheme}://{www_host}/",
        }
        results: dict[str, bool | None] = {}
        timeout = httpx.Timeout(min(8.0, float(settings.request_timeout_seconds)))
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": settings.default_user_agent},
        ) as client:
            async def check_one(key: str, target: str):
                try:
                    resp = await client.get(target)
                    results[key] = resp.status_code < 400 and normalize_url(str(resp.url)).startswith(preferred)
                except Exception:
                    results[key] = None

            await asyncio.gather(*(check_one(k, v) for k, v in candidates.items()))
        return results

    async def _probe_ai_crawlers(self, evidence: list[PageEvidence], discovery: DiscoveryResult) -> None:
        """Probe up to 2 representative pages with real AI retrieval UAs to catch WAF/CDN blocks."""
        targets = [
            item for item in evidence
            if item.error is None and item.status_code is not None and 200 <= item.status_code < 300 and not item.crawler_probes
        ]
        if not targets:
            return
        selected: list[PageEvidence] = []
        home = next((item for item in targets if item.page_type == "homepage"), targets[0])
        selected.append(home)
        other = next((item for item in targets if item is not home), None)
        if other is not None:
            selected.append(other)

        timeout = httpx.Timeout(min(8.0, float(settings.request_timeout_seconds)))
        semaphore = asyncio.Semaphore(4)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, max_redirects=5) as client:
            async def probe(item: PageEvidence, token: str, ua: str):
                async with semaphore:
                    try:
                        async with client.stream(
                            "GET",
                            item.final_url,
                            headers={"User-Agent": ua, "Accept": "text/html,*/*;q=0.8"},
                        ) as resp:
                            chunks = bytearray()
                            async for chunk in resp.aiter_bytes(chunk_size=16384):
                                chunks.extend(chunk[: max(0, 65536 - len(chunks))])
                                if len(chunks) >= 65536:
                                    break
                            preview = chunks.decode("utf-8", errors="replace")
                            headers = {k.lower(): v for k, v in resp.headers.items()}
                            blocked, reasons = _detect_challenge_response(resp.status_code, headers, preview)
                            item.crawler_probes[token] = {
                                "status_code": resp.status_code,
                                "blocked": blocked,
                                "reasons": reasons,
                                "cf_mitigated": headers.get("cf-mitigated"),
                            }
                    except Exception as exc:
                        item.crawler_probes[token] = {
                            "status_code": None,
                            "blocked": None,
                            "error": str(exc)[:120],
                        }

            await asyncio.gather(*(
                probe(item, token, ua)
                for item in selected
                for token, ua in AI_WAF_PROBE_AGENTS
            ))

    @staticmethod
    def _analyze_cross_page_facts(evidence: list[PageEvidence]) -> dict[str, Any]:
        """Automatically verify sampled cross-page entity/fact consistency."""
        fetched = [
            item for item in evidence
            if item.html is not None and not item.error and 200 <= (item.status_code or 0) < 300
        ]
        if len(fetched) < 2:
            return {
                "comparable": False,
                "sampled_pages": len(fetched),
                "reason": "Need at least 2 fetched pages to compare cross-page structured facts.",
            }

        org_names: dict[str, set[str]] = {}
        id_names: dict[str, set[str]] = {}
        product_offers: dict[str, set[tuple[str, str]]] = {}

        for item in fetched:
            soup = BeautifulSoup(item.html or "", "lxml")
            nodes, _, _ = _schema(soup)
            for node in nodes:
                types = _types(node)
                name = str(node.get("name") or node.get("headline") or "").strip()
                if node.get("@id") and name:
                    norm_id = urljoin(item.final_url, str(node["@id"]))
                    id_names.setdefault(norm_id, set()).add(name.casefold())
                if types & {"organization", "corporation", "localbusiness", "onlinestore", "store"} and name:
                    org_names.setdefault(name.casefold(), set()).add(item.final_url)
                if types & {"product", "productmodel", "individualproduct"}:
                    key = str(node.get("sku") or node.get("name") or "").strip().casefold()
                    offers = node.get("offers")
                    offer_list = offers if isinstance(offers, list) else [offers] if isinstance(offers, dict) else []
                    for offer in offer_list:
                        if isinstance(offer, dict) and offer.get("price") is not None:
                            price = str(offer.get("price")).strip()
                            currency = str(offer.get("priceCurrency") or "").strip().upper()
                            if key and price:
                                product_offers.setdefault(key, set()).add((price, currency))

        id_conflicts = {k: sorted(v) for k, v in id_names.items() if len(v) > 1}
        price_conflicts = {k: sorted(list(v)) for k, v in product_offers.items() if len(v) > 1}
        distinct_orgs = sorted(org_names)
        org_conflicts: list[str] = []
        if len(distinct_orgs) > 1:
            # Allow harmless short/long brand variants (e.g., "Acme" vs "Acme Inc.")
            for left in distinct_orgs:
                if not any(left != right and (left in right or right in left) for right in distinct_orgs):
                    org_conflicts.append(left)

        multi_page_ids = sum(1 for v in id_names.values() if v)
        comparable_signals = len(org_names) + len(product_offers) + (1 if multi_page_ids >= 1 and len(fetched) >= 2 else 0)
        if comparable_signals == 0:
            return {
                "comparable": False,
                "sampled_pages": len(fetched),
                "reason": "No comparable cross-page structured entities/offers found in sampled pages.",
            }
        return {
            "comparable": True,
            "sampled_pages": len(fetched),
            "organization_names": distinct_orgs[:10],
            "checked_entity_ids": len(id_names),
            "checked_product_offers": len(product_offers),
            "id_conflicts": id_conflicts,
            "price_conflicts": price_conflicts,
            "org_conflicts": org_conflicts,
            "scope": "automated_sampled_facts_only",
        }

    async def audit(
        self,
        url: str,
        discovery=None,
        *,
        max_pages=8,
        feedback_lang="en",
        mode="standard",
        page_evidence=None,
        host_variants: dict[str, bool | None] | None = None,
        run_live_probes: bool | None = None,
        **_,
    ):
        started = time.perf_counter()
        if isinstance(discovery, dict):
            discovery = DiscoveryResult.model_validate(discovery)
        resolved = discovery or await self.discovery_service.discover(
            url, full_audit=True, max_pages=max_pages, include_backlinks=False,
        )
        evidence = page_evidence if page_evidence is not None else await collect_page_evidence(resolved, max_pages)
        live_probes = (page_evidence is None) if run_live_probes is None else bool(run_live_probes)

        # Bounded rendering reuses the existing opt-in renderer. Disabled or failed
        # measurements remain unknown, never fabricated from HTML word counts.
        semaphore = asyncio.Semaphore(2)

        async def render(item):
            if item.html is None or item.rendered_html is not None or item.error or (item.status_code or 0) >= 400:
                return
            if not settings.allow_playwright:
                item.render_note = "Browser comparison is disabled; no inferred render score."
                return
            policies = inspect_robot_path(resolved.robots, item.url)
            if policies.get("Googlebot") is not True:
                item.render_note = "Render comparison not run: Googlebot permission is blocked or unverified."
                return
            async with semaphore:
                try:
                    result = await self.renderer.test(item.final_url, initial_html=item.html, crawl_allowed=True)
                except Exception as exc:
                    item.render_note = f"Browser measurement failed: {exc}"
                    return
            snapshot = result.get("rendered_html", {})
            request = result.get("request", {})
            valid = (request.get("status_code") or 0) in range(200, 300) and not request.get("network_idle_timed_out")
            valid = valid and is_internal_url(resolved.scope_root_url or resolved.final_url, request.get("final_url") or item.final_url)
            if valid and isinstance(snapshot, dict) and snapshot.get("html") and not snapshot.get("truncated"):
                item.rendered_html = snapshot["html"]
            else:
                item.render_note = str(result.get("reason") or result.get("message") or result.get("status") or "Render comparison unavailable.")

        probe_tasks = [render(item) for item in evidence]
        if live_probes:
            probe_tasks.append(self._probe_ai_crawlers(evidence, resolved))
        await asyncio.gather(*probe_tasks)
        if host_variants is None and live_probes:
            host_variants = await self._probe_host_variants(resolved.final_url)

        discoverable = self._discoverable_urls(resolved, evidence)
        cross_page_facts = self._analyze_cross_page_facts(evidence)

        # Track title/description uniqueness across distinct final URLs in sample.
        distinct_meta: dict[str, tuple[str, str]] = {}
        for item in evidence:
            if item.html is None or item.error or not 200 <= (item.status_code or 0) < 300:
                continue
            key = _canonical(item.final_url)
            if key in distinct_meta:
                continue
            soup = BeautifulSoup(item.html, "lxml")
            t = soup.title.get_text(" ", strip=True) if soup.title else ""
            d_tag = soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            d = (d_tag.get("content") or "").strip() if d_tag else ""
            distinct_meta[key] = (t.casefold(), d.casefold())
        title_counts = Counter(t for t, _ in distinct_meta.values() if t)
        desc_counts = Counter(d for _, d in distinct_meta.values() if d)

        pages = [
            self._page(
                item,
                resolved,
                feedback_lang,
                discoverable,
                host_variants=host_variants or {},
                cross_page_facts=cross_page_facts,
                title_counts=title_counts,
                desc_counts=desc_counts,
            )
            for item in evidence
        ]
        counts = Counter(page.page_type for page in pages)
        weights = [1 / (len(counts) * counts[page.page_type]) for page in pages] if counts else []
        dimensions = self._aggregate(pages, weights, feedback_lang)
        score, coverage, bounds = self._scores(dimensions)
        blockers = [item for page in pages for item in page.blockers]
        blocked_urls = {item["url"] for item in blockers}
        missing = sum(check.status == "unknown" for page in pages for dim in page.dimensions.values() for check in dim.checks)
        provisional = missing > 0 or not pages
        status = "blocked" if blockers else "provisional" if provisional else ScoringService().status_from_score(score or 0)
        readiness = "blocked" if blockers else "unverified" if provisional else "ready" if (score or 0) >= 85 else "needs_work"
        issues, recommendations = [], []
        for dimension in dimensions.values():
            for check in dimension.checks:
                if check.status in {"fail", "partial"}:
                    issues.append(check.label)
                    if check.recommendation:
                        recommendations.append(check.recommendation)
        known_candidates = sample_candidates(resolved, 10000)

        google_ext = inspect_google_extended(resolved.robots, resolved.final_url)
        robots_signals, llm_policies = (
            (resolved.robots.content_signals, resolved.robots.llm_policy_urls)
            if (resolved.robots.content_signals or resolved.robots.llm_policy_urls)
            else parse_robots_extras(resolved.robots.raw_text or "")
        )

        notes = [
            self._label("这是站内 GEO 就绪度评分（onsite-geo-v3），不代表实际收录、AI引用概率或人工事实核查结果。", "This is on-site GEO readiness (onsite-geo-v3), not verified indexing, citation probability, or manual fact checking.", feedback_lang),
            self._label("先逐页计分，再对页面类型等权、同类型页面等权汇总；失败页面保留在样本中。", "Pages are scored individually; page types have equal weight, with equal page weights inside each type. Failed fetches remain in the sample.", feedback_lang),
            self._label("待核验项不视为通过；分数按已核验项暂算，同时给出证据覆盖率与上下界。", "Unknown checks are not passes. The estimate uses measured checks, with evidence coverage and lower/upper bounds.", feedback_lang),
            self._label("内容答案类规则（GEO-012至016）为结构代理指标；GEO-020为采样结构化事实自动初筛，不能替代深度人工核验。", "Answer-readiness checks (GEO-012 to 016) are structural proxies; GEO-020 screens structured facts across sampled pages and does not replace manual fact checking.", feedback_lang),
            self._label("持续稳定性监测（原GEO-004）已移入持续观测层，避免单次扫描长期停留在待核验状态。", "Repeated-fetch stability (former GEO-004) has moved to continuous observation so single runs can reach a verified readiness state.", feedback_lang),
        ]
        if google_ext is False:
            notes.append(self._label("风险提示：robots.txt 拦截了 Google-Extended，可能导致失去 Gemini 应用内引用资格。", "Warning: robots.txt blocks Google-Extended, which can remove citation eligibility in Gemini apps.", feedback_lang))
        if mode == "premium":
            notes.append(self._label("本版GEO评分保持规则驱动，AI配置不改变分值。", "GEO scoring remains deterministic; LLM configuration does not alter scores.", feedback_lang))

        return GeoAuditResult(
            scoring_version=self.SCORING_VERSION,
            score_name=self._label("站内 GEO 就绪度", "On-site GEO readiness", feedback_lang),
            score=score, score_range=bounds, status=status, readiness_status=readiness, provisional=provisional,
            dimensions=dimensions, pages=pages, blockers=blockers, issues=list(dict.fromkeys(issues)),
            recommendations=list(dict.fromkeys(recommendations)), audit_mode=mode, processing_notes=notes,
            duration_ms=int((time.perf_counter() - started) * 1000),
            coverage={
                "sampled_pages": len(pages), "fetched_pages": sum(item.html is not None for item in evidence),
                "known_candidate_pages": len(known_candidates), "page_type_counts": dict(counts),
                "sample_coverage": round(len(pages) / len(known_candidates), 4) if known_candidates else 0,
                "evidence_coverage": coverage, "unknown_checks": missing,
                "blocked_pages": len(blocked_urls), "blocked_page_ratio": round(len(blocked_urls) / len(pages), 4) if pages else 0,
                "sample_weights": {page.url: round(weight, 6) for page, weight in zip(pages, weights)},
                "scope": resolved.scope_root_url or resolved.final_url,
                "total_site_pages": None, "population_note": "Candidate coverage is not whole-site coverage.",
            },
            auxiliary={
                "scored": False,
                "continuous_monitoring": "Sustained repeated-fetch stability (former GEO-004) is tracked across repeated runs rather than single-run scoring.",
                "google_extended_allowed": google_ext,
                "content_signals": robots_signals,
                "llm_policy_urls": llm_policies,
                "mobile_viewport": "Evaluated in SGEO (SGEO-027) and SEO (CHK-009); excluded from pure GEO scoring.",
                "external_authority": "Excluded from GEO scoring.",
                "social_cards_security_headers": "Auxiliary SEO/technical signals; excluded from GEO scoring.",
                "training_permission": "Separate from search/retrieval permissions; unscored unless search/ai-input is restricted.",
                "actual_indexing": "Not verified by on-site checks (Google/Bing/Toutiao/Bocha).",
                "actual_ai_citations": "Not measured by this score.",
            },
        )

    @staticmethod
    def _discoverable_urls(discovery, evidence):
        """Follow observed link chains, not only direct links from the homepage."""
        scope = discovery.scope_root_url or discovery.final_url
        reachable = {_canonical(discovery.final_url)}
        reachable.update(_canonical(url) for url in discovery.sitemap.discovered_urls if is_internal_url(scope, url))
        graph = {_canonical(discovery.final_url): {_canonical(link.url) for link in discovery.homepage.internal_links if is_internal_url(scope, link.url)}}
        for item in evidence:
            if item.html is None or item.error or not 200 <= (item.status_code or 0) < 300:
                continue
            soup = BeautifulSoup(item.html, "lxml")
            links = {urljoin(item.final_url, tag["href"]) for tag in soup.find_all("a", href=True)}
            links = {_canonical(url) for url in links if is_internal_url(scope, url)}
            graph.setdefault(_canonical(item.url), set()).update(links)
            graph.setdefault(_canonical(item.final_url), set()).update(links)
            graph[_canonical(item.url)].add(_canonical(item.final_url))
        pending = list(reachable)
        while pending:
            current = pending.pop()
            for target in graph.get(current, ()):
                if target not in reachable:
                    reachable.add(target)
                    pending.append(target)
        return reachable

    def _page(
        self,
        item: PageEvidence,
        discovery: DiscoveryResult,
        lang: str,
        discoverable: set[str],
        *,
        host_variants: dict[str, bool | None] | None = None,
        cross_page_facts: dict[str, Any] | None = None,
        title_counts: Counter | None = None,
        desc_counts: Counter | None = None,
    ):
        checks: dict[str, GeoCheckResult] = {}
        host_variants = host_variants or {}
        cross_page_facts = cross_page_facts or {"comparable": False}
        title_counts = title_counts or Counter()
        desc_counts = desc_counts or Counter()

        def put(key, value=None, *, evidence=None, na=False, blocker=False, proxy=False, recommendation="", evidence_type=None):
            _, dim, points, zh, en = RULE_MAP[key]
            numeric = None if value is None else max(0., min(1., float(value)))
            state = "na" if na else "unknown" if numeric is None else "pass" if numeric == 1 else "fail" if numeric == 0 else "partial"
            checks[key] = GeoCheckResult(
                id=key, dimension=dim, label=self._label(zh, en, lang), max_points=points,
                value=None if na else numeric, status=state, evidence=evidence or {}, blocker=blocker,
                evidence_type=evidence_type or ("structural_proxy" if proxy else "observed_html"),
                recommendation=recommendation or self._label(f"核对并修复：{zh}。", f"Review and improve: {en}.", lang),
            )

        raw_soup = BeautifulSoup(item.html, "lxml") if item.html is not None else None
        html_lang = raw_soup.html.get("lang", "").strip() if (raw_soup and raw_soup.html) else ""
        effective_locale = discovery.resolved_target_locale or discovery.requested_target_locale or html_lang or detect_explicit_locale(item.final_url)

        # --- GEO-002: Robots.txt & AI retrieval crawler policy (+ Content-Signal & Google-Extended) ---
        selected_crawlers = search_crawlers_for_site(item.final_url, locale=effective_locale)
        policies = inspect_robot_path(discovery.robots, item.url, crawlers=selected_crawlers)
        google_ext = inspect_google_extended(discovery.robots, item.url)
        training_policies = inspect_training_crawlers(discovery.robots, item.url)
        robots_signals, llm_policies = (
            (dict(discovery.robots.content_signals), list(discovery.robots.llm_policy_urls))
            if (discovery.robots.content_signals or discovery.robots.llm_policy_urls)
            else parse_robots_extras(discovery.robots.raw_text or "")
        )
        header_signals = parse_content_signals(item.response_headers.get("content-signal", ""))
        merged_signals = {**robots_signals, **header_signals}
        retrieval_signal_blocked = any(merged_signals.get(k) == "no" for k in ("search", "ai-input", "input"))

        known_policy = [value for value in policies.values() if value is not None]
        robots_value = (sum(known_policy) / len(known_policy)) if len(known_policy) == len(policies) else None
        if robots_value is not None and retrieval_signal_blocked:
            blocked_sig_count = sum(merged_signals.get(k) == "no" for k in ("search", "ai-input", "input"))
            robots_value = max(0.0, robots_value - 0.25 * blocked_sig_count)
        warnings = []
        if google_ext is False:
            warnings.append("Google-Extended is disallowed, which may disable Gemini app citations.")
        if retrieval_signal_blocked:
            warnings.append("Content-Signal restricts search or ai-input usage.")
        robots_rec = self._label(
            "按目标路径放行主流搜索与 AI 检索爬虫（可将训练爬虫单独管控）；" + ("注意误屏蔽 Google-Extended 会影响 Gemini 应用内引用。" if google_ext is False else "核对 Content-Signal 不误禁 search / ai-input。"),
            "Allow search and AI retrieval crawlers on public paths (separately from training bots); " + ("avoid blocking Google-Extended if Gemini app citations are desired." if google_ext is False else "ensure Content-Signal does not disable search or ai-input."),
            lang,
        )
        put(
            "GEO-002",
            robots_value,
            evidence={
                "url": item.url,
                "locale_scope": effective_locale or "global",
                "policies": policies,
                "google_extended_allowed": google_ext,
                "training_policies_unscored": training_policies,
                "robots_has_sitemap": discovery.robots.has_sitemap_directive,
                "content_signals": merged_signals,
                "llm_policy_urls": llm_policies,
                "warnings": warnings,
                "purpose": "search/retrieval, separate from training",
            },
            blocker=any(value is False for value in policies.values()) or retrieval_signal_blocked,
            recommendation=robots_rec,
        )

        # --- GEO-001: HTTP status, soft-404, HTTPS, redirect chain & canonical host ---
        reachable = item.error is None and item.status_code is not None and 200 <= item.status_code < 300
        soft_404 = False
        if reachable and raw_soup is not None:
            raw_title = raw_soup.title.get_text(" ", strip=True) if raw_soup.title else ""
            raw_h1 = raw_soup.find("h1").get_text(" ", strip=True) if raw_soup.find("h1") else ""
            _, _, preview_text = main_document(item.html)
            path_lower = (urlparse(item.final_url).path or "").lower()
            if "/404" not in path_lower and (
                (SOFT_404_TITLE_RE.search(raw_title) and len(preview_text) < 800)
                or (SOFT_404_TITLE_RE.search(raw_h1) and len(preview_text) < 400)
            ):
                soft_404 = True

        redirect_count = item.redirect_count if item.redirect_count is not None else (len(item.redirect_chain) if item.redirect_chain else None)
        if not reachable or soft_404:
            http_value = 0.0 if (item.error or item.status_code is not None or soft_404) else None
        else:
            http_value = 1.0 if item.final_url.startswith("https://") else 0.5
            if redirect_count is not None:
                if redirect_count > 3:
                    http_value = max(0.25, http_value - 0.5)
                elif redirect_count > 1:
                    http_value = max(0.5, http_value - 0.25)
            failed_variants = [k for k, v in host_variants.items() if v is False]
            if failed_variants:
                http_value = max(0.25, http_value - 0.15 * len(failed_variants))
        put(
            "GEO-001",
            http_value,
            evidence={
                "status_code": item.status_code,
                "final_url": item.final_url,
                "soft_404": soft_404,
                "redirect_count": redirect_count,
                "redirect_chain": item.redirect_chain[:5],
                "host_variants": host_variants,
                "error": item.error,
            },
            blocker=bool(item.error) or (item.status_code is not None and not reachable) or soft_404,
            recommendation=self._label(
                "确保核心页面稳定返回 200 OK 且无软 404，将 HTTP 与 www/非www 统一 301 至首选 HTTPS 主域，并把重定向链控制在 1 跳以内。",
                "Serve core pages with stable 200 OK (no soft 404), unify HTTP and www/apex variants via 301 to the preferred HTTPS host, and keep redirects to <= 1 hop.",
                lang,
            ),
        )

        # --- GEO-024: llms.txt & Markdown plain-text delivery ---
        llms = discovery.llms
        structure = llms.structure_checks
        if not structure and llms.content_preview and llms.content_length == len(llms.content_preview):
            structure = inspect_llms_structure(llms.content_preview, llms.final_url or llms.url, llms.content_type or "")
        link_header_entries = _parse_http_link_header(item.response_headers.get("link", ""), item.final_url)
        page_md_alt = any(
            entry.get("rel") == "alternate" and "markdown" in entry.get("type", "").lower()
            for entry in link_header_entries
        )
        if raw_soup is not None and not page_md_alt:
            page_md_alt = bool(raw_soup.find("link", attrs={"rel": lambda v: v and "alternate" in v, "type": re.compile(r"markdown", re.I)}))

        llms_value = None
        if llms.status_code is not None and 400 <= llms.status_code < 500 and llms.status_code != 429:
            llms_value = 0.0
            if llms.full_exists or page_md_alt:
                llms_value = 0.25
        elif llms.exists and llms.status_code is not None and 200 <= llms.status_code < 300:
            if structure.get("readable_text") is False:
                llms_value = 0.0
            elif all(key in structure for key in ("readable_text", "title_and_summary", "internal_navigation")):
                base = 0.0
                if structure["readable_text"]:
                    base += 0.20
                if structure["title_and_summary"]:
                    base += 0.20
                if structure["internal_navigation"]:
                    if llms.sampled_link_checks:
                        ok_ratio = sum(1 for c in llms.sampled_link_checks if c.get("ok")) / len(llms.sampled_link_checks)
                        base += 0.225 * ok_ratio
                    else:
                        base += 0.225
                advanced = 0.0
                if llms.full_exists:
                    advanced += 0.20
                has_healthy_md = bool(llms.markdown_links) and (
                    not any(c.get("is_markdown") for c in llms.sampled_link_checks)
                    or any(c.get("is_markdown") and c.get("ok") for c in llms.sampled_link_checks)
                )
                if has_healthy_md or page_md_alt:
                    advanced += 0.175
                llms_value = round(min(1.0, base + advanced), 4)
        put(
            "GEO-024",
            llms_value,
            evidence_type="observed_file",
            evidence={
                "url": llms.url,
                "final_url": llms.final_url,
                "status_code": llms.status_code,
                "structure_checks": structure,
                "full_url": llms.full_url,
                "full_exists": llms.full_exists,
                "markdown_links": llms.markdown_links[:10],
                "page_markdown_alternate": page_md_alt,
                "sampled_link_checks": llms.sampled_link_checks,
                "error": llms.error,
                "scope": "Complete-file structure + llms-full.txt & Markdown delivery; does not replace P0 crawl readiness.",
            },
            recommendation=self._label(
                "在根目录提供规范纯文本 /llms.txt（含标题、简介与可达站内链接），并按需补充 /llms-full.txt 或 .md 纯文本直出版本。",
                "Provide a readable /llms.txt (title, summary, working internal links) and add /llms-full.txt or .md plain-text versions for key pages.",
                lang,
            ),
        )

        # --- GEO-025: Page loading speed (TTFB & HTML fetch) ---
        elapsed = item.response_time_ms
        valid_time = (
            reachable and isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool)
            and math.isfinite(elapsed) and elapsed >= 0
        )
        speed = next((value for limit, value in ((800, 1), (1500, .75), (3000, .5), (5000, .25)) if elapsed <= limit), 0) if valid_time else None
        put(
            "GEO-025",
            speed,
            evidence_type="http_timing",
            evidence={
                "response_time_ms": elapsed,
                "ttfb_ms": item.ttfb_ms,
                "measurement": "HTML fetch duration (and TTFB when available), including redirects and response body",
                "thresholds_ms": {"full": 800, "three_quarters": 1500, "half": 3000, "quarter": 5000},
                "browser_load_and_core_web_vitals_measured": False,
            },
            recommendation=self._label(
                "优化 TTFB 与 HTML 响应耗时（≤800ms 最佳），启用服务端缓存与 CDN 边缘加速并减少重定向。",
                "Reduce TTFB and HTML fetch latency (<=800ms ideal) with caching, CDN edge delivery, and fewer redirects.",
                lang,
            ),
        )

        # --- GEO-026: Static-style URLs and semantic hygiene ---
        parsed_url = urlparse(item.final_url)
        query_keys = [key.lower() for key, _ in parse_qsl(parsed_url.query, keep_blank_values=True)]
        tracking = {"gclid", "dclid", "fbclid", "msclkid", "yclid", "_ga", "_gl"}
        content_keys = sorted({key for key in query_keys if not key.startswith("utm_") and key not in tracking})
        session_keys = {"sid", "session", "sessionid", "session_id", "phpsessid", "jsessionid"}
        session = bool(session_keys & set(content_keys)) or bool(re.search(
            r";jsessionid=", unquote(parsed_url.path + ";" + parsed_url.params), re.I,
        ))
        route_links = []
        if raw_soup is not None:
            for link in raw_soup.find_all("a", href=True):
                target = urljoin(item.final_url, link["href"])
                if urlparse(target).fragment.startswith(("/", "!/")) and _canonical(target) == _canonical(item.final_url):
                    route_links.append(target)
        hash_route = bool(route_links) or any(urlparse(url).fragment.startswith(("/", "!/")) for url in (item.url, item.final_url))
        dynamic_entry = bool(re.search(r"\.(?:php\d?|asp|aspx|jsp|cgi)(?:/|$)", parsed_url.path, re.I))
        uppercase_path = any(ch.isupper() for ch in parsed_url.path)
        opaque_slug = bool(re.search(r"/[0-9a-f]{24,}(?:/|$)", parsed_url.path, re.I))
        if session or hash_route:
            static_value = 0.0
        elif content_keys or dynamic_entry:
            static_value = 0.5
        elif uppercase_path or opaque_slug:
            static_value = 0.75
        else:
            static_value = 1.0
        put(
            "GEO-026",
            static_value,
            evidence_type="observed_url",
            evidence={
                "final_url": item.final_url,
                "content_parameter_keys": content_keys,
                "ignored_tracking_keys": sorted(set(query_keys) - set(content_keys)),
                "dynamic_entry": dynamic_entry,
                "session_identifier": session,
                "hash_route": hash_route,
                "uppercase_path": uppercase_path,
                "opaque_path_segment": opaque_slug,
                "hash_route_links": route_links[:5],
                "method": "URL-shape check only; clean paths need no .html suffix and do not establish SSR.",
            },
            recommendation=self._label(
                "为公开内容使用简短、小写、语义化的静态路径，减少动态参数，移除会话标识与哈希路由。",
                "Use clean, lowercase, semantic path URLs without session IDs, hash routes, or redundant query parameters.",
                lang,
            ),
        )

        # --- GEO-003: CDN/WAF allowlisting & AI crawler access challenge ---
        base_challenge, base_reasons = _detect_challenge_response(item.status_code, item.response_headers, item.html)
        probed_results = item.crawler_probes or {}
        measured_probes = {k: v for k, v in probed_results.items() if v.get("blocked") is not None}
        blocked_crawlers = [k for k, v in measured_probes.items() if v.get("blocked") is True]
        if not reachable:
            waf_value = 0.0 if (item.error or item.status_code is not None) else None
            waf_blocker = bool(base_challenge or blocked_crawlers)
        elif base_challenge:
            waf_value = 0.0
            waf_blocker = True
        elif blocked_crawlers:
            waf_value = round(1.0 - len(blocked_crawlers) / len(measured_probes), 4)
            waf_blocker = True
        else:
            waf_value = 1.0
            waf_blocker = False

        if item.html is not None or base_challenge or blocked_crawlers or not reachable:
            put(
                "GEO-003",
                waf_value,
                evidence={
                    "challenge_detected": base_challenge,
                    "challenge_reasons": base_reasons,
                    "ai_crawler_probes": probed_results,
                    "blocked_ai_crawlers": blocked_crawlers,
                    "request_kind": "service HTTP + AI retrieval UA probe" if probed_results else "service HTTP request",
                },
                blocker=waf_blocker,
                recommendation=self._label(
                    "在 CDN/WAF（如 Cloudflare）白名单中放行主流 AI 检索爬虫 UA，移除公开页面的 403/429、人机验证与登录墙。",
                    "Allowlist AI retrieval crawler UAs in CDN/WAF (e.g. Cloudflare) and remove 403/429, CAPTCHA, or login walls from public content.",
                    lang,
                ),
            )

        content_type = item.response_headers.get("content-type", "").lower()
        if item.html is None or content_type and "html" not in content_type:
            for key, *_ in RULES:
                if key not in checks:
                    put(key, evidence={"reason": "Raw HTML unavailable or unsupported MIME type; no inferred pass.", "error": item.error, "content_type": content_type})
        else:
            soup, root, text = main_document(item.html)
            nodes, schema_errors, raw_ld_blocks = _schema(raw_soup)
            schema_summary = extract_schema_summary(raw_ld_blocks, visible_text=text)
            schema_types = set().union(*(_types(node) for node in nodes)) if nodes else set()
            page_type = item.page_type
            title = raw_soup.title.get_text(" ", strip=True) if raw_soup.title else ""
            if "product" in schema_types and page_type not in {"homepage", "about", "contact"}:
                page_type = "product"
            elif schema_types & {"article", "blogposting", "newsarticle", "techarticle"} and page_type not in {"homepage", "about", "contact"}:
                page_type = "documentation" if "techarticle" in schema_types else "article"
            elif page_type not in {"homepage", "about", "contact"} and re.search(r"/(?:compare|comparison|vs)(?:/|$)|\bvs\.?\b|对比|选型", f"{item.final_url} {title}", re.I):
                page_type = "comparison"
            item.page_type = page_type

            h1_tags = root.find_all("h1")
            h1 = h1_tags[0] if h1_tags else None
            main_title = h1.get_text(" ", strip=True) if h1 else title
            paragraphs = [element.get_text(" ", strip=True) for element in root.find_all(["p", "li", "dd", "td", "pre"])]
            paragraphs = [p for p in paragraphs if p]
            prose_paragraphs = [element.get_text(" ", strip=True) for element in root.find_all("p") if element.get_text(" ", strip=True)]

            # --- GEO-005: Crawlable navigation & semantic internal links ---
            all_anchors = raw_soup.find_all("a", href=True)
            js_pseudo_links = sum(1 for a in all_anchors if re.match(r"^\s*(?:javascript:|#?\s*$)", a.get("href", ""), re.I))
            nav_anchors = [a for a in all_anchors if a["href"].startswith(("/", "http", "./", "../"))]
            internal_anchors = [
                a for a in nav_anchors
                if urlparse(urljoin(item.final_url, a["href"])).netloc == urlparse(item.final_url).netloc
            ]
            internal = [urljoin(item.final_url, a["href"]) for a in internal_anchors]
            body_links = [urljoin(item.final_url, a.get("href", "")) for a in root.find_all("a", href=True) if a["href"].startswith(("/", "http", "./", "../"))]
            named_internal = sum(
                1 for a in internal_anchors
                if (a.get_text(" ", strip=True) or a.get("aria-label") or a.get("title") or (a.find("img") and (a.find("img").get("alt") or "").strip()))
            )
            named_ratio = (named_internal / len(internal_anchors)) if internal_anchors else 0.0
            single = len(sample_candidates(discovery, 2)) <= 1
            nav_value = 0.0 if not internal else (1.0 if named_ratio >= 0.7 else 0.75 if named_ratio >= 0.5 else 0.5)
            put(
                "GEO-005",
                nav_value,
                na=single,
                evidence={
                    "internal_links": internal[:10],
                    "internal_link_count": len(internal),
                    "named_anchor_ratio": round(named_ratio, 4),
                    "js_pseudo_links": js_pseudo_links,
                    "single_known_page": single,
                },
            )

            # --- GEO-006: XML Sitemap quality & page discovery coverage ---
            found = _canonical(item.url) in discoverable or _canonical(item.final_url) in discoverable
            sm = discovery.sitemap
            sm_urls = sm.discovered_urls or []
            non_https = sm.non_https_urls or [u for u in sm_urls if urlparse(u).scheme.lower() == "http"]
            dirty = sm.dirty_urls or [u for u in sm_urls if SITEMAP_DIRTY_RE.search(u)]
            sm_declared = bool(discovery.robots.has_sitemap_directive or discovery.robots.sitemaps)
            if sm.exists and not sm.invalid_xml and sm_urls:
                sm_quality = (
                    0.25
                    + (0.25 if sm_declared else 0.0)
                    + (0.25 if (not non_https and not dirty) else 0.0)
                    + (0.25 if sm.lastmod_count > 0 else 0.125)
                )
            else:
                sm_quality = 0.0
            disc_value = round(0.5 * (1.0 if found else 0.0) + 0.5 * sm_quality, 4)
            put(
                "GEO-006",
                disc_value,
                evidence={
                    "found_via_entry_link_chain_or_sitemap": found,
                    "sitemap_exists": sm.exists,
                    "sitemap_invalid_xml": sm.invalid_xml,
                    "sitemap_declared_in_robots": sm_declared,
                    "sitemap_non_https_count": len(non_https),
                    "sitemap_dirty_url_count": len(dirty),
                    "sitemap_lastmod_count": sm.lastmod_count,
                    "sitemap_lastmod_ratio": sm.lastmod_ratio,
                    "sitemap_quality_score": round(sm_quality, 4),
                },
                recommendation=self._label(
                    "提供合法、全 HTTPS、无脏链且含 <lastmod> 的 sitemap.xml 并在 robots.txt 中声明，同时将目标页面接入导航链或 Sitemap。",
                    "Serve a valid HTTPS sitemap.xml with <lastmod> timestamps, declare it in robots.txt, and connect all core pages via navigation or Sitemap.",
                    lang,
                ),
            )

            # --- GEO-007: Canonical URL & redirect consistency ---
            canonical = raw_soup.find("link", rel=lambda value: value and "canonical" in value)
            target = urljoin(item.final_url, canonical.get("href", "")) if canonical and canonical.get("href") else None
            if not target:
                header_canon = next((e["href"] for e in link_header_entries if e.get("rel") == "canonical"), None)
                target = header_canon
            has_variant = bool(urlparse(item.url).query) or _canonical(item.url) != _canonical(item.final_url)
            if target:
                canon_value = 1.0 if _canonical(target) == _canonical(item.final_url) else 0.0
            else:
                canon_value = 0.0 if has_variant else 0.5
            put(
                "GEO-007",
                canon_value,
                evidence={"canonical": target, "requested_url": item.url, "final_url": item.final_url, "missing_self_canonical": not target},
                recommendation=self._label(
                    "为页面配置指向最终规范网址的自引用 rel=\"canonical\"（或 HTTP Link Canonical），避免带参或重复链接分散 AI 引用归因。",
                    "Add a self-referencing rel=\"canonical\" (or HTTP Link canonical) matching the final preferred URL to prevent attribution split.",
                    lang,
                ),
            )

            # --- GEO-008: Indexing & snippet directives ---
            directives = [
                tag.get("content", "")
                for tag in raw_soup.find_all(
                    "meta",
                    attrs={"name": re.compile(r"^(?:robots|googlebot|googlebot-news|bingbot|oai-searchbot|chatgpt-user|perplexitybot|claudebot|claude-searchbot|baiduspider|bytespider|kimi-searchbot)$", re.I)},
                )
            ]
            x_robots = item.response_headers.get("x-robots-tag", "")
            directives.append(x_robots)
            joined_directives = " ".join(directives)
            directive_tokens = set(re.findall(r"[a-z-]+", joined_directives.lower()))
            noindex = bool(directive_tokens & {"noindex", "none"})
            snippet_match = re.search(r"max-snippet\s*:\s*(-?\d+)", joined_directives, re.I)
            tiny_snippet = snippet_match is not None and 0 <= int(snippet_match.group(1)) < 50
            nosnippet = bool(directive_tokens & {"nosnippet", "noai", "noimageai"}) or tiny_snippet
            put(
                "GEO-008",
                0.0 if noindex else 0.5 if nosnippet else 1.0,
                evidence={
                    "directives": directives,
                    "actual_indexing": "not_verified",
                    "snippet_restriction": nosnippet,
                    "noindex_detected": noindex,
                },
                blocker=noindex,
            )

            # --- GEO-009: Initial HTML main content & anti-CSR shell ---
            main_text = text if not base_challenge and reachable else ""
            script_count = len(raw_soup.find_all("script"))
            noscript_text = " ".join(tag.get_text(" ", strip=True) for tag in raw_soup.find_all("noscript"))
            noscript_js_warning = bool(NOSCRIPT_JS_RE.search(noscript_text))
            spa_mounts = raw_soup.select("#root, #app, #__next, #__nuxt, app-root")
            empty_spa_mount = bool(spa_mounts) and all(not m.get_text(" ", strip=True) for m in spa_mounts)
            placeholder_only = bool(main_text) and bool(CSR_PLACEHOLDER_RE.match(main_text.strip()))
            csr_shell = bool(
                not main_text
                or placeholder_only
                or (empty_spa_mount and len(main_text) < 40)
                or (noscript_js_warning and len(main_text) < 80)
                or (len(main_text) < 30 and script_count >= 5 and bool(spa_mounts))
            )
            extract_ok = bool(main_text) and not csr_shell
            put(
                "GEO-009",
                1.0 if extract_ok else 0.0,
                evidence={
                    "main_selector": root.name,
                    "text_characters": len(main_text),
                    "csr_shell_detected": csr_shell,
                    "empty_spa_mount": empty_spa_mount,
                    "noscript_js_warning": noscript_js_warning,
                    "placeholder_only": placeholder_only,
                    "script_count": script_count,
                    "excerpt": main_text[:240],
                    "truncated": item.source_truncated,
                },
                blocker=reachable and not extract_ok,
                recommendation=self._label(
                    "通过 SSR/SSG 在初始 HTML 中完整直出核心标题、正文与参数内容，消除 CSR 空壳与 Loading 占位页。",
                    "Render core headings, body text, and specifications in initial HTML via SSR/SSG rather than serving an empty CSR shell.",
                    lang,
                ),
            )

            # --- GEO-010: Complete information containers & semantic HTML tables ---
            containers = root.find_all(["table", "pre", "code", "ul", "ol", "dl"])
            empty_containers = [tag.name for tag in containers if not tag.get_text(" ", strip=True)]
            tables = root.find_all("table")
            tables_without_headers = sum(1 for t in tables if not t.find(["thead", "th", "caption"]))
            image_only = [img.get("src", "") for img in root.find_all("img") if not img.get("alt") and not img.get("role") == "presentation"]
            missing_semantic_table = bool(
                page_type in {"product", "comparison"}
                and not tables
                and SPEC_CUE_RE.search(text)
                and (len(root.find_all("img")) >= 3 or len(root.find_all("div")) >= 20)
            )
            if item.source_truncated:
                container_value = None
            elif empty_containers:
                container_value = 0.0
            else:
                container_value = 1.0
                if tables_without_headers:
                    container_value -= 0.25
                if image_only:
                    container_value -= 0.25
                if missing_semantic_table:
                    container_value -= 0.25
                container_value = max(0.25, container_value)
            put(
                "GEO-010",
                container_value,
                evidence={
                    "containers": len(containers),
                    "empty_containers": empty_containers,
                    "table_count": len(tables),
                    "tables_without_headers": tables_without_headers,
                    "missing_semantic_table_for_specs": missing_semantic_table,
                    "images_without_text": image_only[:5],
                    "scope": "Observed DOM containers and semantic HTML table structure.",
                },
                recommendation=self._label(
                    "使用标准 HTML <table>（含 <thead>/<th>）承载规格与对比参数，禁用纯图片或空容器，并为信息图片补齐描述性 Alt。",
                    "Use semantic HTML <table> with <thead>/<th> for specs and comparisons, remove empty containers, and provide descriptive image alt text.",
                    lang,
                ),
            )

            # --- GEO-011: Raw HTML vs rendered DOM consistency ---
            if item.rendered_html is not None:
                _, rendered_root, rendered_text = main_document(item.rendered_html)
                raw_tokens, rendered_tokens = _tokens(text), _tokens(rendered_text)
                text_retained = len(raw_tokens & rendered_tokens) / len(rendered_tokens) if rendered_tokens else 0.0
                raw_h = {tag.get_text(" ", strip=True).casefold() for tag in root.find_all(["h1", "h2"]) if tag.get_text(" ", strip=True)}
                ren_h = {tag.get_text(" ", strip=True).casefold() for tag in rendered_root.find_all(["h1", "h2"]) if tag.get_text(" ", strip=True)}
                heading_retained = (len(raw_h & ren_h) / len(ren_h)) if ren_h else 1.0
                ren_tables = len(rendered_root.find_all("table"))
                table_retained = min(1.0, len(tables) / ren_tables) if ren_tables else 1.0
                ren_links = {
                    _canonical(urljoin(item.final_url, a["href"]))
                    for a in rendered_root.find_all("a", href=True)
                    if a["href"].startswith(("/", "http", "./", "../"))
                }
                raw_links = {_canonical(u) for u in body_links}
                link_retained = (len(raw_links & ren_links) / len(ren_links)) if ren_links else 1.0
                structure_retained = (table_retained + link_retained) / 2
                retained = round(0.5 * text_retained + 0.25 * heading_retained + 0.25 * structure_retained, 4)
                put(
                    "GEO-011",
                    retained,
                    evidence={
                        "raw_characters": len(text),
                        "rendered_characters": len(rendered_text),
                        "rendered_token_coverage": round(text_retained, 4),
                        "heading_retention": round(heading_retained, 4),
                        "table_retention": round(table_retained, 4),
                        "internal_link_retention": round(link_retained, 4),
                        "measurement": "browser_simulation",
                    },
                )
            else:
                put("GEO-011", evidence={"reason": item.render_note or "Browser comparison not measured.", "csr_shell_hint": csr_shell})

            # --- GEO-027: HTML content-to-noise ratio & payload size ---
            html_bytes = len((item.html or "").encode("utf-8"))
            text_bytes = len(main_text.encode("utf-8"))
            signal_ratio = (text_bytes / html_bytes) if html_bytes else 0.0
            if item.source_truncated:
                payload_score = 0.0
            elif html_bytes <= 250_000:
                payload_score = 1.0
            elif html_bytes <= 500_000:
                payload_score = 0.75
            elif html_bytes <= 1_000_000:
                payload_score = 0.5
            else:
                payload_score = 0.0
            if signal_ratio >= 0.05:
                ratio_score = 1.0
            elif signal_ratio >= 0.02:
                ratio_score = 0.75
            elif signal_ratio >= 0.008:
                ratio_score = 0.5
            else:
                ratio_score = 0.0
            put(
                "GEO-027",
                round((payload_score + ratio_score) / 2, 4),
                proxy=True,
                evidence={
                    "html_bytes": html_bytes,
                    "main_text_bytes": text_bytes,
                    "text_to_html_ratio": round(signal_ratio, 4),
                    "source_truncated": item.source_truncated,
                    "payload_budgets_bytes": [250_000, 500_000, 1_000_000],
                },
                recommendation=self._label(
                    "精简超大内联脚本、重复 DOM 与冗余状态数据，控制 HTML 体量并提升有效正文信噪比，降低 AI 抓取截断与 Token 噪音。",
                    "Trim oversized inline scripts, state blobs, and redundant markup to keep HTML compact and improve text-to-HTML signal ratio.",
                    lang,
                ),
            )

            # --- GEO-012: Title / H1 intent focus & body alignment ---
            title_tokens = _tokens(main_title)
            body_without_heading = " ".join(paragraphs)
            topic_ratio = len(title_tokens & _tokens(body_without_heading)) / len(title_tokens) if title_tokens else 0.0
            h1_count = len(h1_tags)
            h1_score = 1.0 if h1_count == 1 else 0.5 if h1_count > 1 else 0.0
            put(
                "GEO-012",
                round(0.75 * topic_ratio + 0.25 * h1_score, 4),
                proxy=True,
                evidence={
                    "page_topic": main_title,
                    "h1_count": h1_count,
                    "topic_term_coverage": round(topic_ratio, 4),
                    "method": "Topic-term overlap + single-H1 check; not semantic intent verification.",
                },
            )

            # --- GEO-013: Prominent opening answer & Q&A / summary structure ---
            opening = paragraphs[0] if paragraphs else ""
            opening_ratio = len(title_tokens & _tokens(opening)) / len(title_tokens) if title_tokens else 0.0
            key_block = bool(root.find(["table", "dl", "ol"])) or bool(root.select("[itemprop='price'], [role='search'], form"))
            headings = root.find_all(re.compile(r"^h[1-6]$"))
            has_tldr = bool(re.search(r"\btl;?dr\b|核心结论|摘要|要点总结|key takeaways|executive summary", text[:1500], re.I))
            qa_headings = [
                tag.get_text(" ", strip=True)
                for tag in headings
                if tag.name in {"h2", "h3"} and QUESTION_HEADING_RE.search(tag.get_text(" ", strip=True))
            ]
            put(
                "GEO-013",
                1.0 if (opening_ratio >= 0.5 or key_block or has_tldr or bool(qa_headings)) else 0.5 if opening else 0.0,
                proxy=True,
                evidence={
                    "opening": opening[:240],
                    "key_information_block": key_block,
                    "has_summary_or_tldr": has_tldr,
                    "qa_headings_detected": qa_headings[:5],
                    "opening_topic_coverage": round(opening_ratio, 4),
                },
            )

            # --- GEO-014: Heading hierarchy & self-contained passages ---
            levels = [int(tag.name[1]) for tag in headings]
            jumps = sum(right > left + 1 for left, right in zip(levels, levels[1:]))
            checked_blocks = prose_paragraphs or paragraphs
            dependent = sum(
                bool(re.match(r"^(?:this|these|it|they|that|such|above|below|上述|前述|以上|该功能|该产品|它们|因此它|如下所示)(?:\b|[\s，。：:])", p, re.I))
                for p in checked_blocks
            )
            structure_score = (1.0 - dependent / len(checked_blocks)) if checked_blocks else 0.0
            if jumps:
                structure_score *= 0.5
            put(
                "GEO-014",
                round(structure_score, 4),
                proxy=True,
                evidence={
                    "paragraph_count": len(checked_blocks),
                    "context_dependent_openings": dependent,
                    "heading_jumps": jumps,
                    "note": "Promotes clear natural hierarchy without fragmenting long-form content.",
                },
            )

            # --- GEO-015: Core task information for this page type ---
            has_description = bool(root.find("p"))
            has_details = bool(root.find(["table", "dl", "ul", "ol", "pre"]))
            has_action = bool(root.find(["form", "button"])) or bool(body_links)
            if page_type == "product":
                requirements = {
                    "name": bool(main_title),
                    "description": has_description,
                    "specification_or_offer": has_details or any(node.get("offers") for node in nodes) or bool(PRICE_TEXT_RE.search(text)),
                }
            elif page_type == "comparison":
                requirements = {
                    "topic": bool(main_title),
                    "comparison_structure": bool(tables) or has_details,
                    "selection_guidance": has_description and (bool(re.search(r"推荐|建议|适合|结论|best for|recommended|choose", text, re.I)) or len(headings) > 1),
                }
            elif page_type in {"documentation", "api", "migration", "troubleshooting"}:
                requirements = {"topic": bool(main_title), "instructions_or_reference": has_details, "explanation": has_description}
            elif page_type == "tool":
                requirements = {"purpose": bool(main_title), "labelled_inputs": bool(root.select("label, [aria-label]")), "controls": bool(root.find(["form", "button"]))}
            elif page_type in {"homepage", "service", "contact", "about"}:
                requirements = {"purpose": bool(main_title), "description": has_description, "next_step_or_contact": has_action or bool(re.search(r"@|tel:", item.html))}
            else:
                requirements = {"topic": bool(main_title), "explanation": has_description, "supporting_sections_or_details": len(headings) > 1 or has_details}
            put(
                "GEO-015",
                sum(requirements.values()) / len(requirements),
                proxy=True,
                evidence={"page_type": page_type, "requirements": requirements, "method": "Task-specific structural completeness, not factual verification."},
            )

            # --- GEO-016: Specific quantified expression & low redundancy ---
            unique_ratio = len(set(paragraphs)) / len(paragraphs) if paragraphs else 0.0
            vague = sum(bool(VAGUE_COPY_RE.search(p)) for p in paragraphs)
            has_concrete = bool(CONCRETE_FACT_RE.search(text))
            expression = unique_ratio * (1.0 - vague / len(paragraphs)) if paragraphs else 0.0
            if not has_concrete and len(paragraphs) >= 3:
                expression = min(expression, 0.85)
            put(
                "GEO-016",
                round(expression, 4),
                proxy=True,
                evidence={
                    "distinct_block_ratio": round(unique_ratio, 4),
                    "vague_blocks": vague,
                    "has_concrete_metrics": has_concrete,
                },
            )

            # --- GEO-017: Official publisher, author or responsible team ---
            publisher = any(node.get("author") or node.get("publisher") or (_types(node) & {"organization", "person"} and node.get("name")) for node in nodes)
            responsibility = bool(
                raw_soup.select_one("[rel='author'], [itemprop='author'], .author, .byline")
                or re.search(r"作者|责任团队|技术团队|官方团队|编辑|author|written by|reviewed by|maintained by|published by|technical team|editorial team", text, re.I)
            )
            publisher_link = any(re.search(r"/(?:about|company|team|contact)(?:/|$)", urlparse(link).path, re.I) for link in internal)
            if publisher and responsibility:
                identity_score = 1.0
            elif publisher or responsibility:
                identity_score = 0.75
            elif publisher_link:
                identity_score = 0.5
            else:
                identity_score = 0.0
            put(
                "GEO-017",
                identity_score,
                evidence={
                    "publisher_or_author_markup": publisher,
                    "visible_responsibility": responsibility,
                    "publisher_information_link": publisher_link,
                },
            )

            # --- GEO-018: Traceable sources for key claims & data ---
            claim_blocks = [
                p for p in root.find_all(["p", "li", "td"])
                if re.search(r"\d\s*(?:%|％|倍|ms|GB|MB|kg|TOPS)|研究表明|测试结果|according to|benchmark", p.get_text(" ", strip=True), re.I)
            ]
            has_ref_section = any(REF_HEADING_RE.search(tag.get_text(" ", strip=True)) for tag in headings)
            valid_source_links = [
                a for a in root.find_all("a", href=True)
                if a["href"].startswith(("http", "/")) and a.get_text(" ", strip=True) and not NON_SOURCE_LINK_RE.search(a["href"])
            ]
            sourced_score = 0.0
            sourced_direct = 0
            for block in claim_blocks:
                block_text = block.get_text(" ", strip=True)
                block_links = [
                    a for a in block.find_all("a", href=True)
                    if a["href"].startswith(("http", "/")) and not NON_SOURCE_LINK_RE.search(a["href"])
                ]
                if block_links or CITATION_MARKER_RE.search(block_text):
                    sourced_direct += 1
                    sourced_score += 1.0
                elif has_ref_section and valid_source_links:
                    sourced_score += 0.75
            put(
                "GEO-018",
                (sourced_score / len(claim_blocks)) if claim_blocks else None,
                na=not claim_blocks,
                evidence={
                    "detected_claim_blocks": len(claim_blocks),
                    "claims_with_direct_source_or_citation": sourced_direct,
                    "has_reference_section": has_ref_section,
                    "valid_source_links": len(valid_source_links),
                    "source_accuracy": "not_verified",
                },
            )

            # --- GEO-019: Machine-readable freshness, version & pricing clarity ---
            machine_dates = [t.get("datetime") for t in raw_soup.find_all("time") if t.get("datetime")]
            machine_dates.extend(str(node[field]) for node in nodes for field in ("datePublished", "dateModified") if node.get(field))
            for meta in raw_soup.find_all("meta", attrs={"property": re.compile(r"^article:(?:published|modified)_time$", re.I)}):
                if meta.get("content"):
                    machine_dates.append(meta["content"])
            visible_dates = re.findall(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text)
            visible_dates.extend(CHINESE_DATE_RE.findall(text))
            visible_dates.extend(ENGLISH_DATE_RE.findall(text))

            parsed_machine = [_parse_date_candidate(raw) for raw in machine_dates]
            valid_machine = [d is not None and d <= date.today() for d in parsed_machine]
            parsed_visible = [_parse_date_candidate(raw) for raw in visible_dates]
            valid_visible = [d is not None and d <= date.today() for d in parsed_visible]
            all_valid = valid_machine + valid_visible
            has_date_modified = any(node.get("dateModified") for node in nodes) or bool(
                raw_soup.find("meta", attrs={"property": re.compile(r"^article:modified_time$", re.I)})
            )
            versioned = bool(re.search(r"\b(?:version|v)\s*\d+(?:\.\d+)+|版本\s*\d+", text, re.I))
            has_machine_offer = any(
                isinstance(node.get("offers"), dict) and node["offers"].get("price") is not None
                or isinstance(node.get("offers"), list) and any(isinstance(o, dict) and o.get("price") is not None for o in node["offers"])
                for node in nodes
            )
            has_visible_price = bool(PRICE_TEXT_RE.search(text))
            date_applicable = (
                page_type in {"article", "documentation", "api", "migration", "troubleshooting", "case_study", "product"}
                or bool(machine_dates or visible_dates)
            )
            if page_type == "product" and not (machine_dates or visible_dates):
                if has_machine_offer and has_visible_price:
                    fresh_value = 1.0
                elif has_machine_offer or has_visible_price or versioned:
                    fresh_value = 0.75
                else:
                    fresh_value = 0.0
            elif valid_machine:
                fresh_value = sum(valid_machine) / len(valid_machine)
            elif valid_visible:
                fresh_value = round(0.75 * (sum(valid_visible) / len(valid_visible)), 4)
            elif versioned:
                fresh_value = 1.0
            else:
                fresh_value = 0.0
            put(
                "GEO-019",
                fresh_value,
                na=not date_applicable,
                evidence={
                    "machine_dates": machine_dates[:10],
                    "visible_dates": visible_dates[:10],
                    "has_date_modified": has_date_modified,
                    "valid_non_future_dates": all_valid[:10],
                    "version_scope_present": versioned,
                    "machine_offer_price": has_machine_offer,
                    "visible_price": has_visible_price,
                    "freshness_not_inferred_from_headers": True,
                },
            )

            # --- GEO-020: Cross-page entity & fact consistency ---
            if not cross_page_facts.get("comparable"):
                put("GEO-020", na=True, evidence=cross_page_facts)
            else:
                has_hard_conflict = bool(cross_page_facts.get("id_conflicts") or cross_page_facts.get("price_conflicts"))
                has_org_conflict = bool(cross_page_facts.get("org_conflicts"))
                put(
                    "GEO-020",
                    0.0 if has_hard_conflict else 0.5 if has_org_conflict else 1.0,
                    evidence=cross_page_facts,
                )

            # --- GEO-021: Page TDK & language metadata ---
            meta_desc_tag = raw_soup.find("meta", attrs={"name": re.compile(r"^description$", re.I)})
            meta_desc = (meta_desc_tag.get("content") or "").strip() if meta_desc_tag else ""
            dup_title = bool(title) and title_counts[title.casefold()] > 1
            dup_desc = bool(meta_desc) and desc_counts[meta_desc.casefold()] > 1
            lang_valid = bool(re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", html_lang, re.I))
            tdk_score = (int(bool(title) and not dup_title) + int(bool(meta_desc) and not dup_desc) + int(lang_valid)) / 3
            put(
                "GEO-021",
                round(tdk_score, 4),
                evidence={
                    "title": title,
                    "meta_description": meta_desc,
                    "html_lang": html_lang,
                    "duplicate_title": dup_title,
                    "duplicate_description": dup_desc,
                    "fixed_length_threshold": False,
                },
            )

            # --- GEO-022: Entity naming, @id & authoritative links (sameAs / about / mentions) ---
            names = [str(node.get("name") or node.get("headline")) for node in nodes if node.get("name") or node.get("headline")]
            visible_names = [name for name in names if name.casefold() in text.casefold()]
            identifiers: dict[str, set[str]] = {}
            for node in nodes:
                if node.get("@id"):
                    identifiers.setdefault(urljoin(item.final_url, str(node["@id"])), set()).add(
                        str(node.get("name") or node.get("headline") or "").casefold()
                    )
            conflicts = [key for key, values in identifiers.items() if len(values - {""}) > 1]
            consistent_ids = bool(identifiers) and not conflicts and all(urlparse(key).scheme in {"http", "https", "urn"} for key in identifiers)
            valid_same_as = [u for u in schema_summary.get("same_as", []) if urlparse(u).scheme in {"http", "https"}]
            relation_count = int(schema_summary.get("relation_count", 0))
            key_entity_page = page_type in {"homepage", "about", "product", "service", "article", "documentation"}
            if not names and not identifiers and not valid_same_as and relation_count == 0:
                entity_score = 0.0 if key_entity_page else None
                entity_na = not key_entity_page
            else:
                name_part = (len(visible_names) / len(names)) if names else 0.5
                id_part = 1.0 if consistent_ids else (0.0 if conflicts else 0.5)
                rel_part = 1.0 if (valid_same_as and relation_count >= 2) else (0.75 if (valid_same_as or relation_count >= 2) else 0.35 if relation_count >= 1 else 0.0)
                entity_score = round(0.4 * name_part + 0.25 * id_part + 0.35 * rel_part, 4)
                entity_na = False
            put(
                "GEO-022",
                entity_score,
                na=entity_na,
                evidence={
                    "entity_names": names[:10],
                    "visible_names": visible_names[:10],
                    "identifiers": list(identifiers)[:10],
                    "conflicting_identifiers": conflicts,
                    "same_as": valid_same_as[:10],
                    "relation_count": relation_count,
                    "method": "On-page entity names, @id stability, and Schema.org sameAs/about/mentions links.",
                },
                recommendation=self._label(
                    "在 JSON-LD 中为品牌/产品/文章配置稳定的 @id，并通过 sameAs、about、mentions 等标准字段关联官网与外部权威实体。",
                    "Add stable @id values and standard sameAs, about, and mentions links in JSON-LD to strengthen entity disambiguation.",
                    lang,
                ),
            )

            # --- GEO-023: Relevant Schema.org (JSON-LD) & visible alignment ---
            expected_map = {
                "homepage": {"organization", "website", "localbusiness", "corporation", "onlinestore", "store"},
                "about": {"organization", "aboutpage", "localbusiness", "corporation"},
                "contact": {"organization", "contactpage", "localbusiness"},
                "product": {"product", "productmodel", "individualproduct"},
                "service": {"service", "organization", "offer", "softwareapplication", "localbusiness"},
                "article": {"article", "blogposting", "newsarticle", "report", "scholarlyarticle"},
                "case_study": {"article", "blogposting", "report", "casestudy"},
                "documentation": {"techarticle", "article", "howto", "faqpage", "softwareapplication", "webapi"},
                "api": {"techarticle", "webapi", "softwareapplication", "article"},
                "troubleshooting": {"techarticle", "howto", "faqpage", "article"},
                "comparison": {"article", "itemlist", "product", "faqpage", "webpage"},
            }
            expected = expected_map.get(page_type, set())
            if not nodes and not schema_errors and not expected:
                put(
                    "GEO-023",
                    na=True,
                    evidence={"types": [], "expected_types": [], "syntax_errors": [], "all_schema_types_required": False},
                )
            elif schema_errors or (expected and not nodes):
                put(
                    "GEO-023",
                    0.0,
                    evidence={
                        "types": sorted(schema_types),
                        "expected_types": sorted(expected),
                        "syntax_errors": schema_errors,
                        "visible_text_alignment": False,
                        "all_schema_types_required": False,
                    },
                    recommendation=self._label(
                        "按页面类型部署标准 Schema.org JSON-LD（如 Organization/WebSite、Product/Offer、TechArticle、FAQPage），修复语法并保持与正文一致。",
                        "Deploy standard page-appropriate Schema.org JSON-LD (Organization/WebSite, Product/Offer, TechArticle, FAQPage), fix syntax, and align with visible copy.",
                        lang,
                    ),
                )
            else:
                relevant = bool(schema_types & expected) if expected else True
                type_score = 1.0 if relevant else 0.4
                claims = [
                    str(node[key]).strip()
                    for node in nodes
                    for key in ("description", "text", "name", "headline")
                    if isinstance(node.get(key), str) and len(node[key].strip()) >= 4
                ]
                body_tokens = _tokens(text)
                if claims and body_tokens:
                    overlaps = []
                    for claim in claims:
                        if claim.casefold() in text.casefold():
                            overlaps.append(1.0)
                        else:
                            c_tokens = _tokens(claim)
                            overlaps.append((len(c_tokens & body_tokens) / len(c_tokens)) if c_tokens else 1.0)
                    avg_overlap = sum(overlaps) / len(overlaps)
                    align_score = 1.0 if avg_overlap >= 0.6 else 0.6 if avg_overlap >= 0.3 else 0.2
                else:
                    avg_overlap = 1.0
                    align_score = 1.0
                put(
                    "GEO-023",
                    round(0.6 * type_score + 0.4 * align_score, 4),
                    evidence={
                        "types": sorted(schema_types),
                        "expected_types": sorted(expected),
                        "syntax_errors": schema_errors,
                        "visible_text_alignment": align_score >= 0.6,
                        "alignment_overlap": round(avg_overlap, 4),
                        "all_schema_types_required": False,
                    },
                )

            # --- GEO-028: Multilingual & regional hreflang annotations (conditional) ---
            alternates = [
                {"lang": (tag.get("hreflang") or "").strip(), "url": urljoin(item.final_url, tag["href"]) if tag.get("href") else ""}
                for tag in raw_soup.select("link[hreflang]")
            ]
            for entry in link_header_entries:
                if entry.get("rel") == "alternate" and entry.get("hreflang"):
                    alternates.append({"lang": entry["hreflang"], "url": entry["href"]})
            explicit_locale_path = bool(detect_explicit_locale(item.final_url))
            if item.source_truncated and not alternates:
                put("GEO-028", evidence={"reason": "HTML truncated before alternates could be verified."})
            elif not alternates and not explicit_locale_path:
                put("GEO-028", na=True, evidence={"alternates": [], "multilingual_path_detected": False})
            elif not alternates and explicit_locale_path:
                put(
                    "GEO-028",
                    0.0,
                    evidence={"alternates": [], "multilingual_path_detected": True, "html_lang": html_lang},
                    recommendation=self._label(
                        "多语言站点应为各语言版本页面补齐规范的 hreflang（含自引用与 x-default），防止跨语种错配引用。",
                        "Add valid hreflang alternate links (including self-reference and x-default) on multilingual pages to avoid cross-language citation mismatches.",
                        lang,
                    ),
                )
            else:
                valid_count = sum(
                    bool(re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*|x-default", a["lang"], re.I))
                    and urlparse(a["url"]).scheme in {"http", "https"}
                    for a in alternates
                )
                valid_ratio = valid_count / len(alternates)
                self_match = any(_canonical(a["url"]) == _canonical(item.final_url) for a in alternates if a["url"])
                lang_prefix = (html_lang.split("-")[0].lower()) if html_lang else ""
                lang_consistent = (not lang_prefix) or any(
                    a["lang"].lower().split("-")[0] == lang_prefix for a in alternates if a["lang"].lower() != "x-default"
                )
                has_x_default = any(a["lang"].lower() == "x-default" for a in alternates)
                hreflang_score = round(
                    0.5 * valid_ratio
                    + 0.35 * (1.0 if (self_match and lang_consistent) else 0.5 if (self_match or lang_consistent) else 0.0)
                    + 0.15 * (1.0 if has_x_default else 0.0),
                    4,
                )
                put(
                    "GEO-028",
                    hreflang_score,
                    evidence={
                        "alternates": alternates[:15],
                        "valid_ratio": round(valid_ratio, 4),
                        "self_reference_present": self_match,
                        "matches_html_lang": lang_consistent,
                        "has_x_default": has_x_default,
                        "reciprocal_links_verified": False,
                    },
                )

        dimensions = {}
        for key, (points, zh, en) in DIMENSIONS.items():
            owned = [checks[row[0]] for row in RULES if row[1] == key]
            applicable = sum(c.max_points for c in owned if c.status != "na")
            measured = sum(c.max_points for c in owned if c.status not in {"na", "unknown"})
            earned = sum(c.max_points * (c.value or 0) for c in owned if c.status not in {"na", "unknown"})
            dimensions[key] = GeoDimensionResult(key=key, label=self._label(zh, en, lang), weight=points / 100,
                score=round(100 * earned / measured, 2) if measured else None,
                earned_points=round(earned, 4), applicable_points=applicable, measured_points=measured,
                evidence_coverage=round(measured / applicable, 4) if applicable else 1, checks=owned)
        blockers = [{"url": item.url, "check_id": c.id, "reason": c.label, "evidence": c.evidence} for c in checks.values() if c.blocker]
        score, coverage, _ = self._scores(dimensions)
        status = "blocked" if blockers else "provisional" if any(c.status == "unknown" for c in checks.values()) else ScoringService().status_from_score(score or 0)
        return GeoPageResult(url=item.url, final_url=item.final_url, page_type=item.page_type, score=score, status=status,
            evidence_coverage=coverage, **item.metadata(), dimensions=dimensions, blockers=blockers)

    def _aggregate(self, pages, page_weights, lang):
        output = {}
        for key, (points, zh, en) in self.DIMENSIONS.items():
            combined = []
            for rule_id, _, maximum, label_zh, label_en in (row for row in self.RULES if row[1] == key):
                pairs = [(next(c for c in page.dimensions[key].checks if c.id == rule_id), weight) for page, weight in zip(pages, page_weights)]
                applicable = [(c, w) for c, w in pairs if c.status != "na"]
                denominator = sum(w for _, w in applicable)
                measured = [(c, w) for c, w in applicable if c.status != "unknown"]
                measured_weight = sum(w for _, w in measured)
                value = sum((c.value or 0) * w for c, w in measured) / measured_weight if measured_weight else None
                known_fraction = measured_weight / denominator if denominator else 0
                counts = Counter(c.status for c, _ in pairs)
                state = "na" if not applicable else "unknown" if value is None else "partial" if known_fraction < 1 or 0 < value < 1 else "pass" if value == 1 else "fail"
                combined.append(GeoCheckResult(id=rule_id, dimension=key, label=self._label(label_zh, label_en, lang), max_points=maximum,
                    status=state, value=value, evidence={"page_status_counts": dict(counts), "measured_fraction": round(known_fraction, 6)},
                    recommendation=next((c.recommendation for c, _ in pairs if c.status in {"partial", "fail"}),
                        next((c.recommendation for c, _ in pairs if c.recommendation), "")),
                    impact=next((c.impact for c, _ in pairs if c.impact), ""),
                    acceptance_criteria=next((c.acceptance_criteria for c, _ in pairs if c.acceptance_criteria), ""),
                    evidence_type=next((c.evidence_type for c, _ in pairs), "observed_html"), blocker=any(c.blocker for c, _ in pairs)))
            applicable_points = sum(c.max_points for c in combined if c.status != "na")
            measured_points = sum(c.max_points * c.evidence["measured_fraction"] for c in combined if c.status != "na")
            earned = sum(c.max_points * c.evidence["measured_fraction"] * (c.value or 0) for c in combined if c.status != "na")
            output[key] = GeoDimensionResult(key=key, label=self._label(zh, en, lang), weight=points / 100,
                score=round(100 * earned / measured_points, 2) if measured_points else None,
                earned_points=round(earned, 4), applicable_points=applicable_points, measured_points=round(measured_points, 4),
                evidence_coverage=round(measured_points / applicable_points, 4) if applicable_points else 1, checks=combined)
        return output

    @staticmethod
    def _scores(dimensions):
        applicable = [d for d in dimensions.values() if d.applicable_points]
        total_weight = sum(d.weight for d in applicable)
        measured = [d for d in applicable if d.measured_points]
        measured_weight = sum(d.weight for d in measured)
        score = round(sum((d.earned_points / d.measured_points) * d.weight for d in measured) / measured_weight * 100, 2) if measured_weight else None
        if not total_weight:
            return score, 0, [0, 100]
        coverage = sum(d.weight * d.measured_points / d.applicable_points for d in applicable) / total_weight
        lower = sum(d.weight * d.earned_points / d.applicable_points for d in applicable) / total_weight * 100
        upper = sum(d.weight * (d.earned_points + d.applicable_points - d.measured_points) / d.applicable_points for d in applicable) / total_weight * 100
        return score, round(coverage, 4), [round(lower, 2), round(upper, 2)]

    def summarize(self, result: GeoAuditResult, *, seo=None, feedback_lang="en") -> dict:
        geo_score = result.score
        title = self._label("站内 GEO 就绪度", "On-site GEO readiness", feedback_lang)
        seo_score = seo.overall_score if seo is not None else None
        return {
            "scoring_version": self.SCORING_VERSION, "score_name": title,
            "geo_score": geo_score, "composite_geo_score": geo_score,
            "seo_score": seo_score, "combined_score": None,
            "score_policy": "Independent SEO and GEO scores; never averaged.",
            "status": result.status, "readiness_status": result.readiness_status,
            "provisional": result.provisional, "score_range": result.score_range,
            "summary": self._label(f"{title}：{geo_score if geo_score is not None else '待核验'}；阻断页面 {result.coverage.get('blocked_pages', 0)} 个。", f"{title}: {geo_score if geo_score is not None else 'unverified'}; {result.coverage.get('blocked_pages', 0)} blocked pages.", feedback_lang),
            "dimensions": {key: value.model_dump() for key, value in result.dimensions.items()},
            "top_issues": result.issues[:8], "quick_wins": result.recommendations[:8],
            "notices": result.processing_notes, "coverage": result.coverage,
            "audit_mode": result.audit_mode, "llm_enhanced": False,
        }
