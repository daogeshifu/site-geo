"""One SGEO rubric (onsite-sgeo-v2) over page observations; SEO/GEO totals never enter scoring."""
from __future__ import annotations

import re
from collections import Counter
from time import perf_counter
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.models.discovery import DiscoveryResult
from app.models.geo import GeoAuditResult, GeoCheckResult, GeoDimensionResult
from app.models.sgeo import SGEO_SCORING_VERSION, SgeoAuditResult, SgeoPageResult
from app.services.audit.geo import GeoAuditService, _canonical, main_document
from app.services.audit.scoring import ScoringService
from app.services.infra.audit_evidence import collect_page_evidence
from app.utils.html_parser import parse_html
from app.utils.url_utils import detect_explicit_locale


DIMENSIONS = {
    "access": (20, "可获取：访问、抓取与性能", "Retrievable: Access, crawling and performance"),
    "discovery": (15, "可发现：页面发现与索引", "Discoverable: Discovery and indexing"),
    "extraction": (18, "可理解：正文读取与信息提取", "Understandable: Content extraction"),
    "semantics": (12, "可识别：元数据与实体语义", "Recognizable: Metadata and entity semantics"),
    "answers": (20, "可引用：内容价值与答案适配", "Citable: Content and answer readiness"),
    "trust": (15, "可信赖：主体、依据与时效", "Trustworthy: Identity, evidence and freshness"),
}

RULES = [
    ("SGEO-001", "access", 4, "HTTP状态、HTTPS、主域与重定向规范", "HTTP status, HTTPS, canonical host and redirects"),
    ("SGEO-002", "access", 5, "Robots.txt与AI检索爬虫精细化放行", "Robots.txt and AI retrieval crawler policy"),
    ("SGEO-003", "access", 4, "CDN/WAF放行与AI爬虫访问挑战", "CDN/WAF allowlisting and AI crawler access challenges"),
    ("SGEO-025", "access", 3, "页面加载速度（TTFB与HTML获取）", "Page loading speed (TTFB and HTML fetch)"),
    ("SGEO-027", "access", 2, "移动端视口声明", "Mobile viewport declaration"),
    ("SGEO-028", "access", 1, "HTML响应体量与正文信噪比", "HTML payload size and content-to-noise ratio"),
    ("SGEO-029", "access", 1, "图片资源与加载策略", "Image resources and loading policy"),
    ("SGEO-005", "discovery", 2, "可抓取导航与语义化内链", "Crawlable navigation and semantic internal links"),
    ("SGEO-006", "discovery", 3, "XML Sitemap质量与页面发现覆盖", "XML Sitemap quality and page discovery coverage"),
    ("SGEO-007", "discovery", 3, "Canonical规范链接与跳转一致", "Canonical URL and redirect consistency"),
    ("SGEO-008", "discovery", 3, "索引与摘要指令（Noindex/Nosnippet）", "Indexing and snippet directives"),
    ("SGEO-024", "discovery", 2, "llms.txt与Markdown纯文本直出", "llms.txt and Markdown plain-text delivery"),
    ("SGEO-026", "discovery", 2, "URL静态化与语义规范", "Static-style URLs and semantic hygiene"),
    ("SGEO-009", "extraction", 8, "初始HTML核心正文直出与反CSR空壳", "Initial HTML main content and anti-CSR shell"),
    ("SGEO-010", "extraction", 6, "关键信息载体与标准HTML语义表格", "Complete information containers and semantic HTML tables"),
    ("SGEO-011", "extraction", 4, "原始HTML与渲染后DOM一致性", "Raw HTML and rendered DOM consistency"),
    ("SGEO-021", "semantics", 2, "页面TDK与语言元数据", "Page title, description and language metadata"),
    ("SGEO-022", "semantics", 3, "实体命名、@id与权威关联（sameAs/about/mentions）", "Entity naming, @id and authoritative links"),
    ("SGEO-023", "semantics", 5, "适用Schema.org（JSON-LD）与正文一致性", "Relevant Schema.org JSON-LD and visible alignment"),
    ("SGEO-030", "semantics", 2, "多语言与区域标记（hreflang）", "Multilingual and regional hreflang annotations"),
    ("SGEO-012", "answers", 5, "Title/H1意图聚焦与正文对应", "Title/H1 intent focus and body alignment"),
    ("SGEO-013", "answers", 5, "首段结论前置与问答摘要结构", "Prominent opening answer and Q&A summary structure"),
    ("SGEO-014", "answers", 4, "标题层级规范与段落自包含性", "Heading hierarchy and self-contained passages"),
    ("SGEO-015", "answers", 4, "页面任务核心信息完备度", "Core task information for this page type"),
    ("SGEO-016", "answers", 2, "具象量化表达与低冗余", "Specific quantified expression and low redundancy"),
    ("SGEO-017", "trust", 4, "官方发布主体、作者与责任团队", "Official publisher, author or responsible team"),
    ("SGEO-018", "trust", 5, "关键主张与数据出处可追溯", "Traceable sources for key claims and data"),
    ("SGEO-019", "trust", 4, "机器可读时效性与版本价格明确度", "Machine-readable freshness, version and pricing clarity"),
    ("SGEO-020", "trust", 2, "跨页面关键实体与事实一致性", "Cross-page entity and fact consistency"),
]
RULE_MAP = {row[0]: row for row in RULES}

# A shared check owns one remedy, regardless of which search surface it helps.
REMEDIES = {
    "SGEO-001": ("确保核心页面稳定返回 200 OK 且无软 404，将 HTTP 与 www/非www 统一 301 至首选 HTTPS 主域，并将重定向链控制在 1 跳以内。", "Serve core pages with stable 200 OK (no soft 404), unify HTTP and www/apex variants to the preferred HTTPS host, and keep redirects to <= 1 hop."),
    "SGEO-002": ("按目标路径放行主流搜索与 AI 检索爬虫（中文站同步覆盖国内引擎），核对 Content-Signal 不误禁 search/ai-input，并警惕误屏蔽 Google-Extended。", "Allow search and AI retrieval crawlers on target paths, ensure Content-Signal allows search/ai-input, and avoid unintended Google-Extended blocks."),
    "SGEO-003": ("在 CDN/WAF（如 Cloudflare）放行主流 AI 检索爬虫 UA，移除公开页面的 403/429、人机验证与登录挑战并复测。", "Allowlist AI retrieval crawler UAs in CDN/WAF and remove 403/429, CAPTCHA, or login walls from public content."),
    "SGEO-005": ("用可抓取的标准 HTML 链接连接核心页面，减少伪链接并提供清晰语义锚文本。", "Connect core pages with crawlable HTML links and descriptive anchor text rather than JS pseudo-links."),
    "SGEO-006": ("提供合法、全 HTTPS、无脏链且含 <lastmod> 的 sitemap.xml 并在 robots.txt 声明，同时将目标页面接入导航链或 Sitemap。", "Serve a valid HTTPS sitemap.xml with <lastmod> declared in robots.txt and ensure target pages are reachable via navigation or Sitemap."),
    "SGEO-007": ("配置自引用 rel=\"canonical\"（或 HTTP Link Canonical），统一规范网址、最终跳转地址与 Sitemap 首选地址。", "Set self-referencing canonical URLs (HTML or HTTP Link header) aligned with redirect destinations and Sitemap URLs."),
    "SGEO-008": ("移除公开页面误设的 noindex，并核对 Meta Robots 与 X-Robots-Tag 摘要限制是否符合检索目标。", "Remove unintended noindex directives and review Meta Robots and X-Robots-Tag snippet limits."),
    "SGEO-009": ("通过 SSR/SSG 在初始 HTML 中完整直出核心正文，消除 CSR 空壳与 Loading 占位页。", "Expose complete main content in initial HTML via SSR/SSG and eliminate CSR placeholder shells."),
    "SGEO-010": ("使用标准 HTML <table>（含 <thead>/<th>）承载规格与对比参数，补齐列表、代码及信息图片的描述性 Alt。", "Use semantic HTML <table> with <thead>/<th> for specs and comparisons, complete lists/code, and add descriptive image alt text."),
    "SGEO-011": ("补充浏览器渲染对照，确保核心正文、H1/H2 标题、表格与关键内链在原始与渲染 DOM 中保持一致。", "Compare rendered and raw DOM to retain core body text, headings, tables, and key internal links."),
    "SGEO-012": ("保持每页唯一 H1，使页面标题、主标题与正文核心主题聚焦对应。", "Keep a single clear H1 and align page title, main heading, and body topic."),
    "SGEO-013": ("在首段或清晰信息区直给结论、产品要点、TL;DR 摘要或问答式标题块。", "Place key conclusions, product highlights, TL;DR summaries, or Q&A heading blocks prominently."),
    "SGEO-014": ("整理 H1–H6 标题层级和段落指代，使关键段落自然清晰且脱离上下文仍可理解。", "Maintain clean heading hierarchy and self-contained passages without artificially fragmenting long-form content."),
    "SGEO-015": ("按产品、对比选型、文档、服务等页面任务补齐参数规格、操作步骤、选型建议或适用条件。", "Add the specifications, comparison details, steps, or service scope needed for the page's task."),
    "SGEO-016": ("删去重复和空泛营销段落，用具体量化数据、规格范围与实证案例表达信息。", "Remove repetitive or vague copy and provide concrete quantified metrics, ranges, and examples."),
    "SGEO-017": ("在页面可见区与结构化数据中同时标明官方发布主体、作者或责任团队，并提供主体信息入口。", "Identify the official publisher, author, or responsible team in both visible copy and structured data."),
    "SGEO-018": ("为关键数据与主张补充出处链接、标准/报告编号或文末参考来源区，避免仅放购买/登录链接。", "Support key claims with source links, standard/report citations, or a reference section."),
    "SGEO-019": ("展示并同步机器可读的 datePublished/dateModified、产品版本号或明确报价/币种信息。", "Expose visible and machine-readable dates, applicable versions, or clear product pricing/currency."),
    "SGEO-020": ("统一跨采样页的组织名称、实体 @id 与同产品报价/版本事实，避免跨页自相矛盾。", "Keep organization names, entity @id values, and product offers consistent across pages."),
    "SGEO-021": ("补齐准确且跨页唯一的 Title、Meta Description 与合法 HTML lang 声明，不套用死板字符数。", "Provide accurate, distinct titles, descriptions, and valid HTML lang declarations without rigid length thresholds."),
    "SGEO-022": ("在 JSON-LD 中统一实体命名与稳定 @id，并通过 sameAs、about、mentions 等标准字段关联权威实体。", "Use consistent entity names and stable @id values with standard sameAs, about, and mentions links."),
    "SGEO-023": ("按全页面类型部署标准 Schema.org（Organization/WebSite/Product/TechArticle/FAQPage），修复语法并与正文对齐。", "Deploy standard page-appropriate Schema.org JSON-LD, fix syntax errors, and align with visible copy."),
    "SGEO-024": ("提供规范可读的 /llms.txt（含标题、简介与可达站内链接），并按需补充 /llms-full.txt 或 .md 纯文本直出。", "Provide a readable /llms.txt with working links, and add /llms-full.txt or .md plain-text delivery where appropriate."),
    "SGEO-025": ("优化服务端 TTFB、缓存与跳转链，缩短 HTML 获取耗时（≤800ms 最佳）。", "Optimize TTFB, caching, and redirects to reduce HTML fetch time (<=800ms ideal)."),
    "SGEO-026": ("使用简洁小写、语义化的静态路径，减少动态参数，清理会话标识与哈希路由。", "Use clean, lowercase, semantic paths and remove session parameters and hash routes."),
    "SGEO-027": ("声明 width=device-width 的 viewport，并另行验证实际移动端布局。", "Declare a width=device-width viewport and separately verify the mobile layout."),
    "SGEO-028": ("精简超大内联脚本、状态 JSON 与重复标记，控制 HTML 体积并提升正文信噪比。", "Reduce oversized inline scripts, state blobs, and redundant HTML to improve payload size and content-to-noise ratio."),
    "SGEO-029": ("为图片提供可发现的资源地址，避免高优先级图片同时延迟加载。", "Expose discoverable image URLs and avoid lazy-loading explicitly high-priority images."),
    "SGEO-030": ("为多语言站点补齐合法的 hreflang、自引用与 x-default，确保与 HTML lang 一致并另行核验互返。", "Provide valid hreflang, self-reference, and x-default aligned with HTML lang for multilingual pages, and separately verify reciprocity."),
}

IMPACTS = {
    "access": ("影响搜索与 AI 检索获取页面的能力、WAF 放行及读取效率。", "Affects search and AI retrieval access, WAF allowlisting, and reading efficiency."),
    "discovery": ("影响页面在 Sitemap、llms.txt 与索引指令下的发现及规范化条件。", "Affects discovery via Sitemap/llms.txt, canonicalization, and indexing eligibility."),
    "extraction": ("影响搜索与 AI 对初始 HTML 核心正文及表格载体的读取完整性。", "Affects complete extraction of initial HTML main content and semantic tables."),
    "semantics": ("影响搜索摘要、实体消歧（sameAs）、Schema 语义与多语言区域识别。", "Affects snippets, entity disambiguation (sameAs), Schema semantics, and multilingual targeting."),
    "answers": ("影响主题理解、答案定位、问答摘要和内容片段的可引用性。", "Affects topic understanding, answer prominence, Q&A summaries, and reusable passages."),
    "trust": ("影响责任主体、数据出处、适用时效/报价与跨页事实的可核验性。", "Affects verification of publisher identity, claim sources, freshness/pricing, and cross-page consistency."),
}


class SgeoAuditService(GeoAuditService):
    SCORING_VERSION = SGEO_SCORING_VERSION
    DIMENSIONS = DIMENSIONS
    RULES = RULES

    async def audit(self, url, discovery=None, *, max_pages=8, feedback_lang="en", mode="standard", page_evidence=None, **_):
        started = perf_counter()
        if isinstance(discovery, dict):
            discovery = DiscoveryResult.model_validate(discovery)
        resolved = discovery or await self.discovery_service.discover(url, full_audit=True, max_pages=max_pages, include_backlinks=False)
        evidence = page_evidence if page_evidence is not None else await collect_page_evidence(resolved, max_pages)
        # Reuse observed primitive checks, rather than SEO or GEO dimension scores.
        geo = await GeoAuditService(self.discovery_service).audit(
            url, resolved, max_pages=max_pages, feedback_lang=feedback_lang, mode=mode, page_evidence=evidence,
        )
        signals = {}
        for item in evidence:
            content_type = item.response_headers.get("content-type", "").lower()
            if item.html is None or item.error or not 200 <= (item.status_code or 0) < 300 or content_type and "html" not in content_type:
                continue
            parsed = parse_html(item.final_url, item.html, scope_url=resolved.scope_root_url)
            soup = BeautifulSoup(item.html, "lxml")
            _, _, main_text = main_document(item.html)
            parsed.update(
                final_url=item.final_url,
                html_bytes=len(item.html.encode("utf-8")),
                main_text_bytes=len(main_text.encode("utf-8")),
                source_truncated=item.source_truncated,
                alternates=[
                    {"lang": (tag.get("hreflang") or "").strip(), "url": urljoin(item.final_url, tag["href"]) if tag.get("href") else ""}
                    for tag in soup.select("link[hreflang]")
                ],
                image_policies=[
                    {
                        "src": (image.get("src") or image.get("srcset") or "").strip(),
                        "loading": (image.get("loading") or "").strip().lower(),
                        "priority": (image.get("fetchpriority") or "").strip().lower(),
                    }
                    for image in soup.find_all("img")
                ],
            )
            signals[item.url] = parsed
        result = self.build(geo, signals=signals, feedback_lang=feedback_lang)
        result.duration_ms = int((perf_counter() - started) * 1000)
        return result

    def build(self, geo, *, signals=None, feedback_lang="en"):
        """Re-score primitive evidence under the SGEO v2 rubric, including old captures."""
        geo = GeoAuditResult.model_validate(geo) if isinstance(geo, dict) else geo
        lang = feedback_lang
        documents = {page.final_url: (signals or {}).get(page.url, {}) for page in geo.pages}
        duplicates = {
            key: Counter(str(s[key]).strip().casefold() for s in documents.values() if s.get(key))
            for key in ("title", "meta_description")
        }
        pages = []
        for page in geo.pages:
            source = {c.id: c for d in page.dimensions.values() for c in d.checks}
            signal = (signals or {}).get(page.url)
            if signal:
                signal = {
                    **signal,
                    "final_url": signal.get("final_url") or page.final_url,
                    **{
                        f"duplicate_{key}": duplicates[key][str(signal.get(key) or "").strip().casefold()] > 1
                        for key in duplicates
                    },
                }
            checks = []
            for rule_id, dimension, points, zh, en in RULES:
                rule_num = int(rule_id[-3:])
                original = source.get(rule_id.replace("SGEO-", "GEO-")) if rule_num <= 26 else None
                check = original.model_copy(deep=True) if original else GeoCheckResult(
                    id=rule_id, dimension=dimension, label="", max_points=points, status="unknown",
                    evidence={"reason": "This measurement is absent from the saved page evidence."},
                )
                check.id, check.dimension, check.max_points = rule_id, dimension, points
                check.label = self._label(zh, en, lang)
                check.recommendation = self._label(*REMEDIES[rule_id], lang)
                check.impact = self._label(*IMPACTS[dimension], lang)
                check.acceptance_criteria = self._label(
                    f"重新检测「{zh}」，适用采样页面均通过并留存证据。",
                    f"Recheck {en}; all applicable sampled pages pass with recorded evidence.",
                    lang,
                )
                if rule_id == "SGEO-021" and not signal:
                    # Legacy payloads without fresh page signals cannot confirm description uniqueness.
                    check.status, check.value = "unknown", None
                if signal and not any(c.blocker for key, c in source.items() if key in {"GEO-001", "GEO-003"}):
                    self._page_signals(check, signal, lang)
                checks.append(check)
            dimensions = {}
            for key, (points, zh, en) in DIMENSIONS.items():
                owned = [c for c in checks if c.dimension == key]
                applicable = sum(c.max_points for c in owned if c.status != "na")
                measured = sum(c.max_points for c in owned if c.status not in {"na", "unknown"})
                earned = sum(c.max_points * (c.value or 0) for c in owned if c.status not in {"na", "unknown"})
                dimensions[key] = GeoDimensionResult(
                    key=key, label=self._label(zh, en, lang), weight=points / 100,
                    applicable_points=applicable, measured_points=measured, earned_points=earned,
                    score=round(100 * earned / measured, 2) if measured else None,
                    evidence_coverage=measured / applicable if applicable else 1, checks=owned,
                )
            blockers = [{"url": page.url, "check_id": c.id, "reason": c.label, "evidence": c.evidence} for c in checks if c.blocker]
            score, coverage, _ = self._scores(dimensions)
            status = "blocked" if blockers else "provisional" if any(c.status == "unknown" for c in checks) else ScoringService().status_from_score(score or 0)
            page_fields = {key: signal[key] for key in ("title", "meta_description", "canonical", "lang", "word_count", "html_length") if signal and key in signal}
            if signal:
                if "h1_count" in signal or "headings" in signal:
                    page_fields["h1_count"] = signal.get("h1_count", sum(h["level"] == "h1" for h in signal.get("headings", [])))
                if "image_count" in signal or "images" in signal:
                    page_fields["image_count"] = signal.get("image_count", len(signal.get("images", [])))
            index_check = source.get("GEO-008")
            if index_check and index_check.status not in {"unknown", "na"}:
                page_fields["noindex_detected"] = index_check.value == 0
            pages.append(SgeoPageResult.model_validate({
                **page.model_dump(), **page_fields,
                "dimensions": dimensions, "score": score, "evidence_coverage": coverage, "status": status, "blockers": blockers,
            }))
        counts = Counter(page.page_type for page in pages)
        weights = [1 / (len(counts) * counts[page.page_type]) for page in pages] if counts else []
        dimensions = self._aggregate(pages, weights, lang)
        score, coverage, bounds = self._scores(dimensions)
        blockers = [b for p in pages for b in p.blockers]
        unknown = sum(c.status == "unknown" for p in pages for d in p.dimensions.values() for c in d.checks)
        provisional = unknown > 0 or not pages
        status = "blocked" if blockers else "provisional" if provisional else ScoringService().status_from_score(score or 0)
        failed = sorted(
            (c for d in dimensions.values() for c in d.checks if c.status in {"partial", "fail"}
             and any(p.status in {"fail", "partial"} for page in pages for p in page.dimensions[c.dimension].checks if p.id == c.id)),
            key=lambda c: (not c.blocker, c.dimension not in {"access", "discovery", "extraction"}, -(c.max_points * (1 - (c.value or 0)))),
        )
        geo_aux = geo.auxiliary or {}
        return SgeoAuditResult(
            score_name=self._label("SGEO 搜索与生成式引擎就绪度", "SGEO search and generative-engine readiness", lang),
            score=score, status=status,
            readiness_status="blocked" if blockers else "unverified" if provisional else "ready" if (score or 0) >= 85 else "needs_work",
            provisional=provisional, score_range=bounds, dimensions=dimensions, pages=pages, blockers=blockers,
            coverage={
                **geo.coverage, "sampled_pages": len(pages), "page_type_counts": dict(counts),
                "sample_weights": {page.url: round(weight, 6) for page, weight in zip(pages, weights)},
                "blocked_pages": len({b["url"] for b in blockers}),
                "blocked_page_ratio": len({b["url"] for b in blockers}) / len(pages) if pages else 0,
                "evidence_coverage": coverage, "unknown_checks": unknown, "total_checks": len(RULES),
            },
            issues=[c.label for c in failed], recommendations=list(dict.fromkeys(c.recommendation for c in failed)),
            audit_mode=geo.audit_mode,
            processing_notes=[
                self._label("SGEO（onsite-sgeo-v2）将搜索与生成式检索的共用能力合并为六个维度、29项唯一检查，总权重100%；同一检查只计分一次。", "SGEO (onsite-sgeo-v2) unifies search and generative retrieval into six dimensions and 29 unique checks, weighted to 100%; each check is scored once.", lang),
                self._label("总分直接由逐项证据计算，不使用 SEO 或 GEO 总分、维度分做平均。", "The total is calculated from check evidence, without averaging SEO or GEO totals or dimension scores.", lang),
                self._label("先逐页计分，再按页面类型等权、同类型页面等权汇总；失败页保留在样本中。", "Score pages individually, then weight page types equally and pages equally within each type; failed pages remain in the sample.", lang),
                self._label("待核验不视为通过；原 SGEO-004 持续稳定性移入持续观测层，避免单次扫描长期停留在待核验状态。", "Unknowns are not passes; repeated-fetch stability (former SGEO-004) moved to continuous observation so single runs can reach ready.", lang),
                self._label("HTML耗时、体量信噪比、viewport与图片策略属于站内观测或结构代理，不能代替 Core Web Vitals、实际移动布局和人工事实核查。", "HTML timing, payload ratio, viewport and image policies are on-site observations or structural proxies, not Core Web Vitals, mobile-layout measurements or manual fact checking.", lang),
                self._label("llms.txt与Markdown直出占2分，训练授权、社交卡片、一般安全头、分析代码及站外权威不参与 SGEO 计分。", "llms.txt and Markdown delivery carry 2 points; training permissions, social cards, general security headers, analytics and external authority are unscored.", lang),
                self._label("评分不代表实际收录、排名或 AI 引用概率；AI配置不改变规则分。", "This score does not establish indexing, rankings or AI citation probability; LLM settings do not change rule scores.", lang),
            ],
            auxiliary={
                "scored": False,
                "continuous_monitoring": geo_aux.get("continuous_monitoring", "Repeated-fetch stability (former SGEO-004) is tracked via continuous observation."),
                "google_extended_allowed": geo_aux.get("google_extended_allowed"),
                "content_signals": geo_aux.get("content_signals", {}),
                "llm_policy_urls": geo_aux.get("llm_policy_urls", []),
                "actual_indexing": "not_verified",
                "actual_ai_citations": "not_measured",
            },
        )

    @staticmethod
    def _page_signals(check, signal, lang):
        value, na = None, False
        if check.id == "SGEO-021":
            parts = {key: signal.get(key) for key in ("title", "meta_description", "lang")}
            value = (
                int(bool(parts["title"]) and not signal.get("duplicate_title"))
                + int(bool(parts["meta_description"]) and not signal.get("duplicate_meta_description"))
                + int(bool(parts["lang"]))
            ) / 3 if all(key in signal for key in parts) else None
            if signal.get("source_truncated") and not all(parts.values()):
                value = None
            check.evidence = {
                **parts,
                "duplicate_title": signal.get("duplicate_title", False),
                "duplicate_description": signal.get("duplicate_meta_description", False),
            }
        elif check.id == "SGEO-027":
            viewport = signal.get("viewport")
            if "viewport" in signal:
                value = bool(re.search(r"(?:^|[,;])\s*width\s*=\s*device-width\s*(?:[,;]|$)", viewport or "", re.I))
            elif signal.get("viewport_present") is False:
                value = False
            if signal.get("source_truncated") and not viewport:
                value = None
            check.evidence = {
                "viewport": viewport,
                "viewport_present": bool(viewport) if "viewport" in signal else signal.get("viewport_present"),
                "device_width_declared": value,
                "actual_mobile_layout_measured": False,
            }
            check.evidence_type = "structural_proxy"
        elif check.id == "SGEO-028":
            size = signal.get("html_bytes")
            text_bytes = signal.get("main_text_bytes")
            if size is not None and not signal.get("source_truncated"):
                payload_score = 1.0 if size <= 250_000 else 0.75 if size <= 500_000 else 0.5 if size <= 1_000_000 else 0.0
                if text_bytes is not None and size > 0:
                    ratio = text_bytes / size
                    ratio_score = 1.0 if ratio >= 0.05 else 0.75 if ratio >= 0.02 else 0.5 if ratio >= 0.008 else 0.0
                    value = round((payload_score + ratio_score) / 2, 4)
                else:
                    ratio = None
                    value = payload_score
            else:
                ratio = None
            check.evidence = {
                "html_bytes": size,
                "main_text_bytes": text_bytes,
                "text_to_html_ratio": round(ratio, 4) if ratio is not None else None,
                "source_truncated": signal.get("source_truncated"),
                "heuristic_budgets_bytes": [250_000, 500_000, 1_000_000],
                "core_web_vitals_measured": False,
            }
            check.evidence_type = "structural_proxy"
        elif check.id == "SGEO-029":
            images = signal.get("image_policies")
            na = images == [] and not signal.get("source_truncated")
            if images and not signal.get("source_truncated"):
                value = sum(bool(i["src"]) and not (i["loading"] == "lazy" and i["priority"] == "high") for i in images) / len(images)
            check.evidence = {"images": images, "viewport_positions_measured": False, "all_images_required_lazy": False}
            check.evidence_type = "structural_proxy"
        elif check.id == "SGEO-030":
            alternates = signal.get("alternates")
            final_url = signal.get("final_url") or ""
            html_lang = (signal.get("lang") or "").strip()
            explicit_locale_path = bool(detect_explicit_locale(final_url)) if final_url else False
            if signal.get("source_truncated") and not alternates:
                value = None
            elif alternates == []:
                if explicit_locale_path:
                    value = 0.0
                else:
                    na = True
            elif alternates:
                valid_count = sum(
                    bool(re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*|x-default", a["lang"], re.I))
                    and urlparse(a["url"]).scheme in {"http", "https"}
                    for a in alternates
                )
                valid_ratio = valid_count / len(alternates)
                self_match = bool(final_url) and any(_canonical(a["url"]) == _canonical(final_url) for a in alternates if a["url"])
                lang_prefix = html_lang.split("-")[0].lower() if html_lang else ""
                lang_consistent = (not lang_prefix) or any(
                    a["lang"].lower().split("-")[0] == lang_prefix for a in alternates if a["lang"].lower() != "x-default"
                )
                has_x_default = any(a["lang"].lower() == "x-default" for a in alternates)
                if valid_ratio == 0:
                    value = 0.0
                else:
                    value = round(
                        0.5 * valid_ratio
                        + 0.35 * (1.0 if (self_match and lang_consistent) else 0.5 if (self_match or lang_consistent) else 0.0)
                        + 0.15 * (1.0 if has_x_default else 0.0),
                        4,
                    )
            check.evidence = {
                "alternates": alternates,
                "multilingual_path_detected": explicit_locale_path,
                "reciprocal_links_verified": False,
            }
        else:
            return
        check.value = None if na or value is None else float(value)
        check.status = "na" if na else "unknown" if value is None else "pass" if value == 1 else "fail" if value == 0 else "partial"

    def summarize(self, result, *, feedback_lang="en", **_):
        summary = super().summarize(result, feedback_lang=feedback_lang)
        summary.pop("geo_score", None)
        summary.pop("composite_geo_score", None)
        summary.pop("seo_score", None)
        summary.update(
            sgeo_score=result.score, overall_score=result.score, combined_score=result.score,
            score_name=result.score_name, score_policy="Unified SGEO checks; each observation scored once.",
            summary=self._label(
                f"SGEO 就绪度：{result.score if result.score is not None else '待核验'}/100；{len(result.issues)} 项待优化，{result.coverage.get('blocked_pages', 0)} 个阻断页面。",
                f"SGEO readiness: {result.score if result.score is not None else 'unverified'}/100; {len(result.issues)} improvements and {result.coverage.get('blocked_pages', 0)} blocked pages.",
                feedback_lang,
            ),
        )
        return summary

    def upgrade_legacy_payload(self, payload, *, feedback_lang="en"):
        """Derive a view of old combined reports without rewriting saved scores."""
        if payload.get("sgeo") or not payload.get("geo") or not payload.get("seo"):
            return payload
        # Only preserve positive measurements from successful saved fetches.
        signals = {
            page["url"]: page for page in payload["seo"].get("sampled_pages", [])
            if page.get("url") and 200 <= (page.get("status_code") or 0) < 300
        }
        result = self.build(payload["geo"], signals=signals, feedback_lang=feedback_lang)
        result.processing_notes.append(self._label(
            "此报告由历史页面证据重新归并；未保存的新增检查保持待核验，重新诊断可补齐。",
            "This report is regrouped from saved page evidence. New checks without saved measurements remain unverified; rerun the audit to collect them.",
            feedback_lang,
        ))
        return {
            **payload,
            "sgeo": result.model_dump(mode="json"),
            "summary": self.summarize(result, feedback_lang=feedback_lang),
            "page_diagnostics": [page.model_dump(mode="json") for page in result.pages],
        }
