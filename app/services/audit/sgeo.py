"""One SGEO rubric over page observations; SEO/GEO totals never enter scoring."""
from __future__ import annotations

import re
from collections import Counter
from time import perf_counter
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.models.discovery import DiscoveryResult
from app.models.geo import GeoAuditResult, GeoCheckResult, GeoDimensionResult
from app.models.sgeo import SGEO_SCORING_VERSION, SgeoAuditResult, SgeoPageResult
from app.services.audit.geo import GeoAuditService, RULES as GEO_RULES
from app.services.audit.scoring import ScoringService
from app.services.infra.audit_evidence import collect_page_evidence
from app.utils.html_parser import parse_html


DIMENSIONS = {
    "access": (20, "可获取：访问、抓取与性能", "Retrievable: Access, crawling and performance"),
    "discovery": (15, "可发现：页面发现与索引", "Discoverable: Discovery and indexing"),
    "extraction": (15, "可理解：正文读取与信息提取", "Understandable: Content extraction"),
    "answers": (25, "可引用：内容价值与答案适配", "Citable: Content and answer readiness"),
    "trust": (15, "可信赖：主体、依据与时效", "Trustworthy: Identity, evidence and freshness"),
    "semantics": (10, "可识别：元数据与实体语义", "Recognizable: Metadata and entity semantics"),
}
POINTS = [4, 5, 3, 1, 3, 3, 3, 3, 7, 4, 4, 6, 5, 5, 5, 4, 4, 6, 3, 2, 3, 2, 4, 1, 3, 2]
RULES = [(rule.replace("GEO-", "SGEO-"), dimension, POINTS[index],
          "标题、描述与语言元数据" if rule == "GEO-021" else zh,
          "Title, description and language metadata" if rule == "GEO-021" else en)
         for index, (rule, dimension, _, zh, en) in enumerate(GEO_RULES)] + [
    ("SGEO-027", "access", 2, "移动端视口声明", "Mobile viewport declaration"),
    ("SGEO-028", "access", 1, "HTML 页面体量", "HTML payload size"),
    ("SGEO-029", "access", 1, "图片资源与加载策略", "Image resources and loading policy"),
    ("SGEO-030", "semantics", 1, "多语言版本声明", "Language alternate declarations"),
]
RULE_MAP = {row[0]: row for row in RULES}

# A shared check owns one remedy, regardless of which search surface it helps.
REMEDIES = [
    ("修复失败响应，并将公开页面统一到可访问的 HTTPS 地址。", "Fix failed responses and serve public pages over accessible HTTPS URLs."),
    ("按目标路径核对 robots.txt，允许期望服务的搜索与 AI 检索爬虫。", "Review robots.txt for each path and allow the intended search and AI retrieval crawlers."),
    ("为公开正文移除登录、验证码和访问挑战，并复测抓取响应。", "Remove login or access challenges from public content and retest the response."),
    ("补充不同时段的重复抓取记录，确认响应与正文持续可用。", "Collect repeated fetches over time to verify stable responses and content."),
    ("用可抓取的 HTML 链接连接核心页面，并提供清晰的链接文字。", "Connect core pages with crawlable HTML links and descriptive anchor text."),
    ("将目标页面接入导航链或有效 Sitemap，修复孤立页面。", "Include target pages in navigation chains or a valid sitemap and repair orphan pages."),
    ("统一 canonical、最终跳转地址与 Sitemap 中的首选网址。", "Align canonical URLs, redirect destinations and preferred sitemap URLs."),
    ("移除公开页面误设的 noindex，并核对摘要限制是否符合检索目标。", "Remove unintended noindex directives and review snippet restrictions."),
    ("让核心正文在可获取的 HTML 中完整呈现，减少对交互和脚本的依赖。", "Expose complete main content in retrievable HTML without requiring interaction."),
    ("补齐表格、列表和代码内容，为信息图片提供可读替代文本。", "Complete tables, lists and code blocks and provide text alternatives for informative images."),
    ("补充浏览器渲染对照，确保关键正文在原始与渲染 HTML 中一致。", "Compare browser-rendered and raw HTML and retain the key content in both."),
    ("使页面标题、主标题与正文主题对应，并补齐相关说明。", "Align the title, main heading and body topic and add the relevant explanation."),
    ("在开头或清晰的信息区直接给出结论、产品要点或操作入口。", "Place the answer, product details or task entry in a prominent opening or information block."),
    ("整理标题层级和段落指代，使关键段落脱离上下文仍可理解。", "Organize headings and paragraph references so key passages can stand alone."),
    ("按页面任务补齐操作步骤、产品参数、服务范围或适用条件。", "Add the steps, product details, service scope or conditions needed for the page's task."),
    ("删去重复和空泛段落，用具体事实、范围与示例表达信息。", "Remove repetitive or vague copy and use specific facts, scope and examples."),
    ("标明作者、发布主体或责任团队，并提供可访问的主体信息。", "Identify the author, publisher or responsible team with accessible identity information."),
    ("为关键主张补充来源、原始资料或可核验的方法说明。", "Support key claims with sources, original material or a verifiable method."),
    ("展示适用的发布日期、更新日期或版本，并与正文保持一致。", "Show applicable publication dates, updates or versions consistent with the content."),
    ("补充跨页面核验，统一价格、产品规格、主体与其他关键事实。", "Verify key facts across pages and align prices, specifications and identity information."),
    ("补齐准确且可区分的标题、描述与语言声明，不套用固定字符数。", "Provide accurate, distinct titles, descriptions and language declarations without a fixed character-count rule."),
    ("统一页面、可见正文与结构化数据中的实体名称和标识。", "Use consistent entity names and identifiers across visible content and structured data."),
    ("使用适合页面任务的 Schema，修复语法并与可见正文保持一致。", "Use page-appropriate schema, fix syntax errors and align it with visible content."),
    ("提供含站点简介与内容导航的可读 llms.txt，作为辅助发现入口。", "Provide a readable llms.txt with a site summary and content navigation as an auxiliary discovery aid."),
    ("优化服务端响应、缓存与跳转链，缩短 HTML 获取耗时。", "Improve server responses, caching and redirect chains to reduce HTML fetch time."),
    ("提供稳定的内容路径，清理会话参数与哈希路由，统一规范网址。", "Use stable content paths, remove session parameters and hash routes and align canonical URLs."),
    ("声明 width=device-width 的 viewport，并另行验证实际移动端布局。", "Declare a width=device-width viewport and separately verify the mobile layout."),
    ("减少内联脚本、重复标记与无效 HTML，并复测正文响应体积。", "Reduce inline scripts, duplicate markup and unnecessary HTML and remeasure the payload."),
    ("为图片提供可发现的资源地址，避免高优先级图片同时延迟加载。", "Expose image resource URLs and avoid lazy-loading explicitly high-priority images."),
    ("补齐有效的 hreflang 与版本链接，另行验证语言版本互返关系。", "Provide valid hreflang and alternate URLs and separately verify reciprocal links."),
]
IMPACTS = {
    "access": ("影响搜索与 AI 检索获取页面的能力及读取效率。", "Affects search and AI retrieval access and reading efficiency."),
    "discovery": ("影响页面发现、规范化和进入检索候选的条件。", "Affects discovery, canonicalization and eligibility for retrieval."),
    "extraction": ("影响搜索与 AI 对核心正文的读取完整性。", "Affects complete extraction of the main content by search and AI systems."),
    "answers": ("影响主题理解、答案定位和内容片段的可引用性。", "Affects topic understanding, answer discovery and reusable passages."),
    "trust": ("影响内容依据、责任主体和适用时效的可核验性。", "Affects verification of supporting evidence, responsibility and freshness."),
    "semantics": ("影响搜索摘要、语言识别与实体关系理解。", "Affects snippets, language recognition and entity understanding."),
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
        geo = await GeoAuditService(self.discovery_service).audit(url, resolved, max_pages=max_pages,
            feedback_lang=feedback_lang, mode=mode, page_evidence=evidence)
        signals = {}
        for item in evidence:
            content_type = item.response_headers.get("content-type", "").lower()
            if item.html is None or item.error or not 200 <= (item.status_code or 0) < 300 or content_type and "html" not in content_type:
                continue
            parsed = parse_html(item.final_url, item.html, scope_url=resolved.scope_root_url)
            soup = BeautifulSoup(item.html, "lxml")
            parsed.update(html_bytes=len(item.html.encode("utf-8")), source_truncated=item.source_truncated,
                alternates=[{"lang": tag.get("hreflang", ""), "url": urljoin(item.final_url, tag["href"]) if tag.get("href") else ""}
                    for tag in soup.select("link[hreflang]")],
                image_policies=[{"src": (image.get("src") or image.get("srcset") or "").strip(),
                    "loading": (image.get("loading") or "").strip().lower(),
                    "priority": (image.get("fetchpriority") or "").strip().lower()} for image in soup.find_all("img")])
            signals[item.url] = parsed
        result = self.build(geo, signals=signals, feedback_lang=feedback_lang)
        result.duration_ms = int((perf_counter() - started) * 1000)
        return result

    def build(self, geo, *, signals=None, feedback_lang="en"):
        """Re-score primitive evidence under the SGEO rubric, including old captures."""
        geo = GeoAuditResult.model_validate(geo) if isinstance(geo, dict) else geo
        lang = feedback_lang
        documents = {page.final_url: (signals or {}).get(page.url, {}) for page in geo.pages}
        duplicates = {key: Counter(str(s[key]).strip().casefold() for s in documents.values() if s.get(key))
            for key in ("title", "meta_description")}
        pages = []
        for page in geo.pages:
            source = {c.id: c for d in page.dimensions.values() for c in d.checks}
            signal = (signals or {}).get(page.url)
            if signal:
                signal = {**signal, **{f"duplicate_{key}": duplicates[key][str(signal.get(key) or "").strip().casefold()] > 1
                    for key in duplicates}}
            checks = []
            for rule_id, dimension, points, zh, en in RULES:
                original = source.get(rule_id.replace("SGEO-", "GEO-"))
                check = original.model_copy(deep=True) if original else GeoCheckResult(
                    id=rule_id, dimension=dimension, label="", max_points=points, status="unknown",
                    evidence={"reason": "This measurement is absent from the saved page evidence."})
                check.id, check.dimension, check.max_points = rule_id, dimension, points
                check.label = self._label(zh, en, lang)
                check.recommendation = self._label(*REMEDIES[int(rule_id[-3:]) - 1], lang)
                check.impact = self._label(*IMPACTS[dimension], lang)
                check.acceptance_criteria = self._label(f"重新检测「{zh}」，适用采样页面均通过并留存证据。", f"Recheck {en}; all applicable sampled pages pass with recorded evidence.", lang)
                if rule_id == "SGEO-021":
                    # GEO's title/lang observation cannot verify a description.
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
                dimensions[key] = GeoDimensionResult(key=key, label=self._label(zh, en, lang), weight=points / 100,
                    applicable_points=applicable, measured_points=measured, earned_points=earned,
                    score=round(100 * earned / measured, 2) if measured else None,
                    evidence_coverage=measured / applicable if applicable else 1, checks=owned)
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
            pages.append(SgeoPageResult.model_validate({**page.model_dump(), **page_fields,
                "dimensions": dimensions, "score": score, "evidence_coverage": coverage, "status": status, "blockers": blockers}))
        counts = Counter(page.page_type for page in pages)
        weights = [1 / (len(counts) * counts[page.page_type]) for page in pages] if counts else []
        dimensions = self._aggregate(pages, weights, lang)
        score, coverage, bounds = self._scores(dimensions)
        blockers = [b for p in pages for b in p.blockers]
        unknown = sum(c.status == "unknown" for p in pages for d in p.dimensions.values() for c in d.checks)
        provisional = unknown > 0 or not pages
        status = "blocked" if blockers else "provisional" if provisional else ScoringService().status_from_score(score or 0)
        failed = sorted((c for d in dimensions.values() for c in d.checks if c.status in {"partial", "fail"}
            and any(p.status in {"fail", "partial"} for page in pages for p in page.dimensions[c.dimension].checks if p.id == c.id)),
            key=lambda c: (not c.blocker, c.dimension not in {"access", "discovery", "extraction"}, -(c.max_points * (1 - (c.value or 0)))))
        return SgeoAuditResult(score_name=self._label("SGEO 搜索与生成式引擎就绪度", "SGEO search and generative-engine readiness", lang),
            score=score, status=status, readiness_status="blocked" if blockers else "unverified" if provisional else "ready" if (score or 0) >= 85 else "needs_work",
            provisional=provisional, score_range=bounds, dimensions=dimensions, pages=pages, blockers=blockers,
            coverage={**geo.coverage, "sampled_pages": len(pages), "page_type_counts": dict(counts),
                "sample_weights": {page.url: round(weight, 6) for page, weight in zip(pages, weights)},
                "blocked_pages": len({b["url"] for b in blockers}),
                "blocked_page_ratio": len({b["url"] for b in blockers}) / len(pages) if pages else 0,
                "evidence_coverage": coverage, "unknown_checks": unknown, "total_checks": len(RULES)},
            issues=[c.label for c in failed], recommendations=list(dict.fromkeys(c.recommendation for c in failed)),
            audit_mode=geo.audit_mode, processing_notes=[
                self._label("SGEO 将搜索与生成式检索的共用能力合并为六个维度、30项唯一检查，总权重100%；同一检查只计分一次。", "SGEO unifies search and generative retrieval into six dimensions and 30 unique checks, weighted to 100%; each check is scored once.", lang),
                self._label("总分直接由逐项证据计算，不使用 SEO 或 GEO 总分、维度分做平均。", "The total is calculated from check evidence, without averaging SEO or GEO totals or dimension scores.", lang),
                self._label("先逐页计分，再按页面类型等权、同类型页面等权汇总；失败页保留在样本中。", "Score pages individually, then weight page types equally and pages equally within each type; failed pages remain in the sample.", lang),
                self._label("待核验不视为通过；暂定分按已测项计算，同时显示覆盖率和分数上下界。不适用项在维度内归一。", "Unknowns are not passes; estimates use measured checks with coverage and score bounds. Inapplicable checks are normalized within dimensions.", lang),
                self._label("HTML耗时、体量、viewport与图片策略属于站内观测或结构代理，不能代替 Core Web Vitals、实际移动布局和事实核查。", "HTML timing, payload, viewport and image policies are on-site observations or structural proxies, not Core Web Vitals, mobile-layout measurements or fact checking.", lang),
                self._label("llms.txt仅占1分，属于辅助发现入口；训练授权、社交卡片、安全头、分析代码及站外权威不参与 SGEO 计分。", "llms.txt is a one-point auxiliary discovery aid; training permissions, social cards, security headers, analytics and external authority are unscored.", lang),
                self._label("评分不代表实际收录、排名或 AI 引用概率；AI配置不改变规则分。", "This score does not establish indexing, rankings or AI citation probability; LLM settings do not change rule scores.", lang),
            ], auxiliary={"scored": False, "actual_indexing": "not_verified", "actual_ai_citations": "not_measured"})

    @staticmethod
    def _page_signals(check, signal, lang):
        value, na = None, False
        if check.id == "SGEO-021":
            parts = {key: signal.get(key) for key in ("title", "meta_description", "lang")}
            value = (int(bool(parts["title"]) and not signal.get("duplicate_title"))
                + int(bool(parts["meta_description"]) and not signal.get("duplicate_meta_description"))
                + int(bool(parts["lang"]))) / 3 if all(key in signal for key in parts) else None
            if signal.get("source_truncated") and not all(parts.values()):
                value = None
            check.evidence = {**parts, "duplicate_title": signal.get("duplicate_title", False),
                "duplicate_description": signal.get("duplicate_meta_description", False)}
        elif check.id == "SGEO-027":
            viewport = signal.get("viewport")
            if "viewport" in signal:
                value = bool(re.search(r"(?:^|[,;])\s*width\s*=\s*device-width\s*(?:[,;]|$)", viewport or "", re.I))
            elif signal.get("viewport_present") is False:
                value = False
            if signal.get("source_truncated") and not viewport:
                value = None
            check.evidence = {"viewport": viewport, "viewport_present": bool(viewport) if "viewport" in signal else signal.get("viewport_present"),
                "device_width_declared": value, "actual_mobile_layout_measured": False}
            check.evidence_type = "structural_proxy"
        elif check.id == "SGEO-028":
            size = signal.get("html_bytes")
            value = (1 if size <= 250000 else .5 if size <= 1000000 else 0) if size is not None and not signal.get("source_truncated") else None
            check.evidence = {"html_bytes": size, "source_truncated": signal.get("source_truncated"), "heuristic_budgets_bytes": [250000, 1000000], "core_web_vitals_measured": False}
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
            na = alternates == [] and not signal.get("source_truncated")
            if alternates and not signal.get("source_truncated"):
                value = sum(bool(re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*|x-default", a["lang"], re.I))
                    and urlparse(a["url"]).scheme in {"http", "https"} for a in alternates) / len(alternates)
            check.evidence = {"alternates": alternates, "reciprocal_links_verified": False}
        else:
            return
        check.value = None if na or value is None else float(value)
        check.status = "na" if na else "unknown" if value is None else "pass" if value == 1 else "fail" if value == 0 else "partial"

    def summarize(self, result, *, feedback_lang="en", **_):
        summary = super().summarize(result, feedback_lang=feedback_lang)
        summary.pop("geo_score", None)
        summary.pop("composite_geo_score", None)
        summary.pop("seo_score", None)
        summary.update(sgeo_score=result.score, overall_score=result.score, combined_score=result.score,
            score_name=result.score_name, score_policy="Unified SGEO checks; each observation scored once.",
            summary=self._label(f"SGEO 就绪度：{result.score if result.score is not None else '待核验'}/100；{len(result.issues)} 项待优化，{result.coverage.get('blocked_pages', 0)} 个阻断页面。",
                f"SGEO readiness: {result.score if result.score is not None else 'unverified'}/100; {len(result.issues)} improvements and {result.coverage.get('blocked_pages', 0)} blocked pages.", feedback_lang))
        return summary

    def upgrade_legacy_payload(self, payload, *, feedback_lang="en"):
        """Derive a view of old combined reports without rewriting saved scores."""
        if payload.get("sgeo") or not payload.get("geo") or not payload.get("seo"):
            return payload
        # Only preserve positive measurements from successful saved fetches.
        signals = {page["url"]: page for page in payload["seo"].get("sampled_pages", [])
            if page.get("url") and 200 <= (page.get("status_code") or 0) < 300}
        result = self.build(payload["geo"], signals=signals, feedback_lang=feedback_lang)
        result.processing_notes.append(self._label("此报告由历史页面证据重新归并；未保存的新增检查保持待核验，重新诊断可补齐。", "This report is regrouped from saved page evidence. New checks without saved measurements remain unverified; rerun the audit to collect them.", feedback_lang))
        return {**payload, "sgeo": result.model_dump(mode="json"),
            "summary": self.summarize(result, feedback_lang=feedback_lang),
            "page_diagnostics": [page.model_dump(mode="json") for page in result.pages]}
