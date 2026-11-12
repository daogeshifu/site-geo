"""On-site GEO readiness: 23 uniquely owned checks, six fixed dimensions.

No external authority, social-card, training-policy or platform probability enters
this score. Semantic checks are explicitly structural proxies, not fact checking.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from collections import Counter
from datetime import date
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.core.config import settings
from app.models.discovery import DiscoveryResult
from app.models.geo import GeoAuditResult, GeoCheckResult, GeoDimensionResult, GeoPageResult
from app.services.audit.scoring import ScoringService
from app.services.discovery.discovery import DiscoveryService
from app.services.google_crawler.google_render import GoogleRenderService
from app.services.infra.audit_evidence import PageEvidence, collect_page_evidence, sample_candidates
from app.utils.robots_parser import inspect_robot_path
from app.utils.url_utils import is_internal_url, normalize_url


DIMENSIONS = {
    "access": (20, "访问与抓取可达性", "Access and crawlability"),
    "discovery": (15, "页面发现与可索引性", "Discovery and indexability"),
    "extraction": (20, "正文读取与信息提取", "Content extraction"),
    "answers": (25, "内容价值与答案适配", "Content and answer readiness"),
    "trust": (15, "站内可信度与时效性", "On-site trust and freshness"),
    "semantics": (5, "元数据与实体语义", "Metadata and entity semantics"),
}

# id, dimension, maximum points, Chinese label, English label
RULES = [
    ("GEO-001", "access", 5, "HTTP与HTTPS可用", "HTTP and HTTPS availability"),
    ("GEO-002", "access", 7, "目标路径检索爬虫规则", "Search crawler policy for this path"),
    ("GEO-003", "access", 5, "当前抓取无访问挑战", "No access challenge in this fetch"),
    ("GEO-004", "access", 3, "抓取稳定性", "Repeated-fetch stability"),
    ("GEO-005", "discovery", 5, "可抓取导航与内链", "Crawlable navigation and internal links"),
    ("GEO-006", "discovery", 4, "发现机制有效覆盖", "Discovery mechanism coverage"),
    ("GEO-007", "discovery", 3, "规范网址与跳转一致", "Canonical and redirect consistency"),
    ("GEO-008", "discovery", 3, "索引与摘要指令", "Indexing and snippet directives"),
    ("GEO-009", "extraction", 10, "核心正文可提取", "Extractable main content"),
    ("GEO-010", "extraction", 6, "关键信息载体完整", "Complete information containers"),
    ("GEO-011", "extraction", 4, "原始与渲染正文一致", "Raw and rendered content consistency"),
    ("GEO-012", "answers", 7, "页面主题与正文对应", "Topic and body alignment"),
    ("GEO-013", "answers", 5, "结论或关键信息易定位", "Prominent answer or key information"),
    ("GEO-014", "answers", 5, "段落自包含与组织", "Self-contained content organization"),
    ("GEO-015", "answers", 5, "页面任务所需信息", "Information needed for this page type"),
    ("GEO-016", "answers", 3, "具体表达与低冗余", "Specific and non-repetitive expression"),
    ("GEO-017", "trust", 4, "发布主体或责任团队", "Publisher or responsible team"),
    ("GEO-018", "trust", 6, "关键主张依据可追溯", "Traceable support for key claims"),
    ("GEO-019", "trust", 3, "日期与适用版本", "Dates and applicable versions"),
    ("GEO-020", "trust", 2, "跨页面关键事实一致", "Cross-page fact consistency"),
    ("GEO-021", "semantics", 2, "标题及语言元数据", "Title and language metadata"),
    ("GEO-022", "semantics", 1, "实体命名及标识一致", "Entity naming and identifiers"),
    ("GEO-023", "semantics", 2, "适用Schema及正文一致性", "Relevant schema and visible alignment"),
]
RULE_MAP = {row[0]: row for row in RULES}


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
    parsed, errors = [], []
    for element in soup.select("script[type='application/ld+json']"):
        try:
            parsed.extend(_nodes(json.loads(element.get_text())))
        except (TypeError, ValueError) as exc:
            errors.append(str(exc)[:120])
    return parsed, errors


def _types(node):
    values = node.get("@type", [])
    return {str(value).rsplit("/", 1)[-1].lower() for value in (values if isinstance(values, list) else [values])}


def _canonical(url):
    try:
        return normalize_url(url).rstrip("/")
    except ValueError:
        return url


class GeoAuditService:
    SCORING_VERSION = "onsite-geo-v1"

    def __init__(self, discovery_service=None):
        self.discovery_service = discovery_service or DiscoveryService()
        self.renderer = GoogleRenderService()

    @staticmethod
    def _label(zh, en, lang):
        return zh if lang == "zh" else en

    async def audit(self, url: str, discovery=None, *, max_pages=8, feedback_lang="en", mode="standard", page_evidence=None, **_):
        started = time.perf_counter()
        if isinstance(discovery, dict):
            discovery = DiscoveryResult.model_validate(discovery)
        resolved = discovery or await self.discovery_service.discover(
            url, full_audit=True, max_pages=max_pages, include_backlinks=False,
        )
        evidence = page_evidence if page_evidence is not None else await collect_page_evidence(resolved, max_pages)
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

        await asyncio.gather(*(render(item) for item in evidence))
        discoverable = self._discoverable_urls(resolved, evidence)
        pages = [self._page(item, resolved, feedback_lang, discoverable) for item in evidence]
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
        notes = [
            self._label("这是站内就绪度评分，不代表实际收录、AI引用概率或事实核查结果。", "This is on-site readiness, not verified indexing, citation probability, or fact checking.", feedback_lang),
            self._label("先逐页计分，再对页面类型等权、同类型页面等权汇总；失败页面保留在样本中。", "Pages are scored individually; page types have equal weight, with equal page weights inside each type. Failed fetches remain in the sample.", feedback_lang),
            self._label("待核验项不视为通过；分数按已核验项暂算，同时给出证据覆盖率与上下界。", "Unknown checks are not passes. The estimate uses measured checks, with evidence coverage and lower/upper bounds.", feedback_lang),
            self._label("语义类规则是明确列出的结构代理指标，无法据此确认事实准确或用户意图完全满足。", "Semantic checks are documented structural proxies; they do not establish factual accuracy or full intent satisfaction.", feedback_lang),
            self._label("抓取来自本服务的HTTP请求及可选浏览器模拟，不代表真实AI爬虫或指定地区访问。", "Fetches come from this service and optional browser simulation, not verified AI crawler IPs or a selected geographic region.", feedback_lang),
        ]
        if mode == "premium":
            notes.append(self._label("本版GEO评分保持规则驱动，AI配置不改变分值。", "GEO scoring remains deterministic; LLM configuration does not alter scores.", feedback_lang))
        return GeoAuditResult(
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
                "scored": False, "llms_txt": {"exists": resolved.llms.exists, "url": resolved.llms.url},
                "external_authority": "Excluded from GEO scoring.",
                "social_cards_security_headers": "Auxiliary SEO/technical signals; excluded from GEO scoring.",
                "training_permission": "Separate from search/retrieval permissions; not scored.",
                "actual_indexing": "Not verified by on-site checks.", "actual_ai_citations": "Not measured by this score.",
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

    def _page(self, item: PageEvidence, discovery, lang, discoverable):
        checks: dict[str, GeoCheckResult] = {}

        def put(key, value=None, *, evidence=None, na=False, blocker=False, proxy=False, recommendation=""):
            _, dim, points, zh, en = RULE_MAP[key]
            numeric = None if value is None else max(0., min(1., float(value)))
            state = "na" if na else "unknown" if numeric is None else "pass" if numeric == 1 else "fail" if numeric == 0 else "partial"
            checks[key] = GeoCheckResult(
                id=key, dimension=dim, label=self._label(zh, en, lang), max_points=points,
                value=None if na else numeric, status=state, evidence=evidence or {}, blocker=blocker,
                evidence_type="structural_proxy" if proxy else "observed_html",
                recommendation=recommendation or self._label(f"核对并修复：{zh}。", f"Review and improve: {en}.", lang),
            )

        policies = inspect_robot_path(discovery.robots, item.url)
        known_policy = [value for value in policies.values() if value is not None]
        put("GEO-002", sum(known_policy) / len(known_policy) if len(known_policy) == len(policies) else None,
            evidence={"url": item.url, "policies": policies, "purpose": "search/retrieval, not training"},
            blocker=any(value is False for value in policies.values()))
        reachable = item.error is None and item.status_code is not None and 200 <= item.status_code < 300
        put("GEO-001", (1 if item.final_url.startswith("https://") else .5) if reachable else 0 if item.error or item.status_code is not None else None,
            evidence={"status_code": item.status_code, "final_url": item.final_url, "error": item.error}, blocker=bool(item.error) or item.status_code is not None and not reachable)
        put("GEO-004", evidence={"reason": "A single fetch cannot establish sustained availability.", "fetched_at": item.fetched_at})
        content_type = item.response_headers.get("content-type", "").lower()
        if item.html is None or content_type and "html" not in content_type:
            for key, *_ in RULES:
                if key not in checks:
                    put(key, evidence={"reason": "Raw HTML unavailable or unsupported MIME type; no inferred pass.", "error": item.error, "content_type": content_type})
        else:
            soup, root, text = main_document(item.html)
            raw_soup = BeautifulSoup(item.html, "lxml")
            nodes, schema_errors = _schema(raw_soup)
            # Type inference uses the current page rather than site-wide schema.
            schema_types = set().union(*(_types(node) for node in nodes)) if nodes else set()
            page_type = item.page_type
            if "product" in schema_types and page_type not in {"homepage", "about", "contact"}:
                page_type = "product"
            elif schema_types & {"article", "blogposting", "newsarticle", "techarticle"} and page_type not in {"homepage", "about", "contact"}:
                page_type = "documentation" if "techarticle" in schema_types else "article"
            item.page_type = page_type
            title = raw_soup.title.get_text(" ", strip=True) if raw_soup.title else ""
            h1 = root.find("h1")
            main_title = h1.get_text(" ", strip=True) if h1 else title
            paragraphs = [element.get_text(" ", strip=True) for element in root.find_all(["p", "li", "dd", "td", "pre"])]
            paragraphs = [p for p in paragraphs if p]
            login_form = bool(raw_soup.select("input[type='password']")) and bool(re.search(r"login|log in|sign in|登录|登入", title, re.I))
            challenge = bool(raw_soup.select("#challenge-form, #cf-challenge-running, .g-recaptcha")) or login_form or bool(
                re.search(r"^(?:just a moment|access denied|verify (?:you are|that you are)|请完成验证|访问被拒绝)", title.strip(), re.I))
            put("GEO-003", not challenge if reachable else 0, evidence={"challenge_detected": challenge, "title": title, "request_kind": "service HTTP request"}, blocker=challenge)
            body_links = [urljoin(item.final_url, a.get("href", "")) for a in root.find_all("a", href=True) if a["href"].startswith(("/", "http", "./", "../"))]
            nav_links = [urljoin(item.final_url, a.get("href", "")) for a in raw_soup.find_all("a", href=True) if a["href"].startswith(("/", "http", "./", "../"))]
            internal = [link for link in nav_links if urlparse(link).netloc == urlparse(item.final_url).netloc]
            single = len(sample_candidates(discovery, 2)) <= 1
            put("GEO-005", bool(internal), na=single, evidence={"internal_links": internal[:10], "single_known_page": single})
            found = _canonical(item.url) in discoverable or _canonical(item.final_url) in discoverable
            put("GEO-006", found,
                evidence={"found_via_entry_link_chain_or_sitemap": found, "sitemap_exists": discovery.sitemap.exists})
            canonical = raw_soup.find("link", rel=lambda value: value and "canonical" in value)
            target = urljoin(item.final_url, canonical.get("href", "")) if canonical else None
            # A missing canonical is not an error for a unique page without variants.
            put("GEO-007", _canonical(target) == _canonical(item.final_url) if target else None,
                na=not target and not urlparse(item.url).query and _canonical(item.url) == _canonical(item.final_url),
                evidence={"canonical": target, "requested_url": item.url, "final_url": item.final_url})
            directives = [tag.get("content", "") for tag in raw_soup.find_all("meta", attrs={"name": re.compile(r"^(robots|googlebot|bingbot)$", re.I)})]
            directives.append(item.response_headers.get("x-robots-tag", ""))
            directive_tokens = set(re.findall(r"[a-z-]+", " ".join(directives).lower()))
            noindex = bool(directive_tokens & {"noindex", "none"})
            nosnippet = "nosnippet" in directive_tokens or bool(re.search(r"max-snippet\s*:\s*0\b", " ".join(directives), re.I))
            put("GEO-008", 0 if noindex else .5 if nosnippet else 1,
                evidence={"directives": directives, "actual_indexing": "not_verified", "snippet_restriction": nosnippet}, blocker=noindex)
            main_text = text if not challenge and reachable else ""
            put("GEO-009", bool(main_text), evidence={"main_selector": root.name, "text_characters": len(main_text), "excerpt": main_text[:240], "truncated": item.source_truncated}, blocker=reachable and not main_text)
            containers = root.find_all(["table", "pre", "code", "ul", "ol", "dl"])
            empty_containers = [tag.name for tag in containers if not tag.get_text(" ", strip=True)]
            image_only = [img.get("src", "") for img in root.find_all("img") if not img.get("alt") and not img.get("role") == "presentation"]
            put("GEO-010", None if item.source_truncated else 0 if empty_containers else .5 if image_only else 1,
                evidence={"containers": len(containers), "empty_containers": empty_containers, "images_without_text": image_only[:5], "scope": "Observed DOM containers only; hidden content requires render comparison."})
            if item.rendered_html is not None:
                _, _, rendered_text = main_document(item.rendered_html)
                raw_tokens, rendered_tokens = _tokens(text), _tokens(rendered_text)
                retained = len(raw_tokens & rendered_tokens) / len(rendered_tokens) if rendered_tokens else 0
                put("GEO-011", retained, evidence={"raw_characters": len(text), "rendered_characters": len(rendered_text), "rendered_token_coverage": round(retained, 4), "measurement": "browser_simulation"})
            else:
                put("GEO-011", evidence={"reason": item.render_note or "Browser comparison not measured."})
            title_tokens = _tokens(main_title)
            body_without_heading = " ".join(paragraphs)
            topic_ratio = len(title_tokens & _tokens(body_without_heading)) / len(title_tokens) if title_tokens else 0
            put("GEO-012", topic_ratio, proxy=True, evidence={"page_topic": main_title, "topic_term_coverage": round(topic_ratio, 4), "method": "Topic-term overlap with body blocks; not semantic intent verification."})
            opening = paragraphs[0] if paragraphs else ""
            opening_ratio = len(title_tokens & _tokens(opening)) / len(title_tokens) if title_tokens else 0
            key_block = bool(root.find(["table", "dl", "ol"])) or bool(root.select("[itemprop='price'], [role='search'], form"))
            put("GEO-013", 1 if opening_ratio >= .5 or key_block else .5 if opening else 0, proxy=True,
                evidence={"opening": opening[:240], "key_information_block": key_block, "opening_topic_coverage": round(opening_ratio, 4)})
            headings = root.find_all(re.compile(r"^h[1-6]$"))
            levels = [int(tag.name[1]) for tag in headings]
            jumps = sum(right > left + 1 for left, right in zip(levels, levels[1:]))
            dependent = sum(bool(re.match(r"^(?:this|these|it|they|上述|前述|该功能|它们|因此它)\b", p, re.I)) for p in paragraphs)
            structure = (1 - dependent / len(paragraphs)) if paragraphs else 0
            if jumps:
                structure *= .5
            put("GEO-014", structure, proxy=True, evidence={"paragraph_count": len(paragraphs), "context_dependent_openings": dependent, "heading_jumps": jumps})
            has_description = bool(root.find("p"))
            has_details = bool(root.find(["table", "dl", "ul", "ol", "pre"]))
            has_action = bool(root.find(["form", "button"])) or bool(body_links)
            if page_type == "product":
                requirements = {"name": bool(main_title), "description": has_description, "specification_or_offer": has_details or any(node.get("offers") for node in nodes)}
            elif page_type in {"documentation", "api", "migration", "troubleshooting"}:
                requirements = {"topic": bool(main_title), "instructions_or_reference": has_details, "explanation": has_description}
            elif page_type == "tool":
                requirements = {"purpose": bool(main_title), "labelled_inputs": bool(root.select("label, [aria-label]")), "controls": bool(root.find(["form", "button"]))}
            elif page_type in {"homepage", "service", "contact", "about"}:
                requirements = {"purpose": bool(main_title), "description": has_description, "next_step_or_contact": has_action or bool(re.search(r"@|tel:", item.html))}
            else:
                requirements = {"topic": bool(main_title), "explanation": has_description, "supporting_sections_or_details": len(headings) > 1 or has_details}
            put("GEO-015", sum(requirements.values()) / len(requirements), proxy=True, evidence={"page_type": page_type, "requirements": requirements, "method": "Task-specific structural completeness, not factual verification."})
            unique_ratio = len(set(paragraphs)) / len(paragraphs) if paragraphs else 0
            vague = sum(bool(re.search(r"行业领先|全方位赋能|世界一流|industry.leading|best.in.class|cutting.edge", p, re.I)) for p in paragraphs)
            expression = unique_ratio * (1 - vague / len(paragraphs)) if paragraphs else 0
            put("GEO-016", expression, proxy=True, evidence={"distinct_block_ratio": round(unique_ratio, 4), "vague_blocks": vague})
            publisher = any(node.get("author") or node.get("publisher") or (_types(node) & {"organization", "person"} and node.get("name")) for node in nodes)
            responsibility = raw_soup.select_one("[rel='author'], [itemprop='author'], .author, .byline") or re.search(r"作者|责任团队|技术团队|编辑|author|written by|reviewed by|maintained by|technical team|editorial team", text, re.I)
            publisher_link = any(re.search(r"/(?:about|company|team|contact)(?:/|$)", urlparse(link).path, re.I) for link in internal)
            put("GEO-017", 1 if publisher or responsibility else .5 if publisher_link else 0,
                evidence={"publisher_or_author_markup": bool(publisher), "visible_responsibility": bool(responsibility), "publisher_information_link": publisher_link})
            claim_blocks = [p for p in root.find_all(["p", "li", "td"]) if re.search(r"\d\s*(?:%|％|倍|ms|GB|MB|kg|TOPS)|研究表明|测试结果|according to|benchmark", p.get_text(" ", strip=True), re.I)]
            source_links = [a for a in root.find_all("a", href=True) if a["href"].startswith(("http", "/")) and a.get_text(" ", strip=True)]
            sourced = sum(bool(p.find("a", href=True)) for p in claim_blocks)
            put("GEO-018", sourced / len(claim_blocks) if claim_blocks else None, na=not claim_blocks,
                evidence={"detected_claim_blocks": len(claim_blocks), "claims_with_nearby_source_link": sourced, "source_links": len(source_links), "source_accuracy": "not_verified"})
            dates = [t.get("datetime") or t.get_text(strip=True) for t in raw_soup.find_all("time")]
            dates.extend(str(node[field]) for node in nodes for field in ("datePublished", "dateModified") if node.get(field))
            visible_dates = re.findall(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}\b", text)
            dates.extend(visible_dates)
            valid_dates = []
            for raw in dates:
                try:
                    value = date.fromisoformat(raw[:10].replace("/", "-"))
                    valid_dates.append(value <= date.today())
                except ValueError:
                    valid_dates.append(False)
            versioned = bool(re.search(r"\b(?:version|v)\s*\d+(?:\.\d+)+|版本\s*\d+", text, re.I))
            date_applicable = page_type in {"article", "documentation", "api", "migration", "troubleshooting", "case_study"} or bool(dates)
            put("GEO-019", (sum(valid_dates) / len(valid_dates)) if valid_dates else 1 if versioned else 0, na=not date_applicable,
                evidence={"observed_dates": dates[:10], "valid_non_future_dates": valid_dates, "version_scope_present": versioned, "freshness_not_inferred_from_headers": True})
            # Cross-document fact verification needs an explicit fact inventory;
            # matching brand strings alone does not establish factual agreement.
            put("GEO-020", evidence={"reason": "No reviewed cross-page fact inventory supplied; manual fact verification required."})
            language = raw_soup.html.get("lang", "") if raw_soup.html else ""
            put("GEO-021", (bool(title) + bool(language)) / 2,
                evidence={"title": title, "html_lang": language, "fixed_length_threshold": False})
            names = [str(node.get("name") or node.get("headline")) for node in nodes if node.get("name") or node.get("headline")]
            visible_names = [name for name in names if name.casefold() in text.casefold()]
            identifiers: dict[str, set[str]] = {}
            for node in nodes:
                if node.get("@id"):
                    identifiers.setdefault(urljoin(item.final_url, str(node["@id"])), set()).add(str(node.get("name") or node.get("headline") or "").casefold())
            conflicts = [key for key, values in identifiers.items() if len(values - {""}) > 1]
            consistent_ids = not conflicts and all(urlparse(key).scheme in {"http", "https", "urn"} for key in identifiers)
            name_score = len(visible_names) / len(names) if names else None
            entity_score = ((name_score if name_score is not None else 1) + int(consistent_ids)) / 2 if identifiers else name_score
            put("GEO-022", entity_score, na=not names and not identifiers,
                evidence={"entity_names": names[:10], "visible_names": visible_names[:10], "identifiers": list(identifiers)[:10], "conflicting_identifiers": conflicts, "method": "On-page names and identifiers only; no external mentions."})
            expected = {"product"} if page_type == "product" else {"article", "blogposting", "newsarticle", "techarticle"} if page_type in {"article", "documentation"} else set()
            relevant = bool(schema_types & expected) if expected else True
            claims = [str(node[key]) for node in nodes for key in ("description", "text") if isinstance(node.get(key), str) and node[key].strip()]
            aligns = all(value.casefold() in text.casefold() for value in claims)
            put("GEO-023", 0 if schema_errors or expected and not nodes else 1 if relevant and aligns else .5,
                na=not nodes and not schema_errors and not expected,
                evidence={"types": sorted(schema_types), "expected_types": sorted(expected), "syntax_errors": schema_errors, "visible_text_alignment": aligns, "all_schema_types_required": False})

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
        for key, (points, zh, en) in DIMENSIONS.items():
            combined = []
            for rule_id, _, maximum, label_zh, label_en in (row for row in RULES if row[1] == key):
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
                    recommendation=next((c.recommendation for c, _ in pairs if c.status in {"partial", "fail"}), ""),
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
