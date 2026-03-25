from __future__ import annotations

import re
from typing import Any


EXACT_TRANSLATIONS = {
    "robots.txt blocks one or more major AI crawlers.": "robots.txt 阻止了一个或多个主要 AI 爬虫。",
    "Review robots.txt and allow GPTBot, OAI-SearchBot, PerplexityBot, and Google-Extended.": "检查 robots.txt，并放行 GPTBot、OAI-SearchBot、PerplexityBot 和 Google-Extended。",
    "robots.txt appears open to major AI crawlers.": "robots.txt 看起来已对主要 AI 爬虫开放。",
    "Site does not expose llms.txt guidance.": "站点未提供 llms.txt 指引。",
    "Publish a concise llms.txt that describes the site, services, and citation preferences.": "发布简洁的 llms.txt，说明站点、服务和引用偏好。",
    "llms.txt exists but does not yet provide strong machine-facing guidance.": "llms.txt 已存在，但对机器侧的指引仍不够充分。",
    "Expand llms.txt with brand context, services, citation preferences, and structured sections.": "扩充 llms.txt，加入品牌背景、服务说明、引用偏好和结构化章节。",
    "llms.txt exists and can help AI systems understand the site.": "llms.txt 已存在，可帮助 AI 系统理解站点。",
    "Homepage lacks strong citation-friendly structure and content depth.": "首页缺少足够适合引用的结构和内容深度。",
    "Improve homepage metadata, add clearer headings, and strengthen answer-first copy.": "优化首页元数据，增加更清晰的标题结构，并强化先答后述的表达。",
    "Homepage exposes baseline citability signals.": "首页已具备基础的可引用性信号。",
    "Basic entity presence is thin across about/contact and contact signals.": "关于页、联系页和联系信息中的基础实体信号较弱。",
    "Strengthen homepage, about, and contact-page entity signals with brand and contact details.": "通过品牌信息和联系信息强化首页、关于页和联系页的实体信号。",
    "Baseline entity presence is detectable across the site.": "站点已具备可识别的基础实体存在信号。",
    "Brand authority signals are weak on-site.": "站内品牌权威信号偏弱。",
    "Add complete company details, sameAs references, stronger entity consistency, and external authority proof.": "补充完整的公司信息、sameAs 引用、更强的一致性实体信号和外部权威证明。",
    "Brand authority signals show meaningful baseline coverage.": "品牌权威信号已具备一定基础覆盖。",
    "Site resolves over HTTPS.": "站点已通过 HTTPS 访问。",
    "Site does not consistently enforce HTTPS.": "站点未持续强制使用 HTTPS。",
    "Redirect all traffic to HTTPS and preload HSTS once validated.": "将全部流量重定向到 HTTPS，并在验证后启用 HSTS 预加载。",
    "Core security headers are largely in place.": "核心安全响应头基本已到位。",
    "Important security headers are missing.": "缺少重要的安全响应头。",
    "Add HSTS, CSP, X-Frame-Options, X-Content-Type-Options, and Referrer-Policy headers.": "补充 HSTS、CSP、X-Frame-Options、X-Content-Type-Options 和 Referrer-Policy 响应头。",
    "Homepage is missing a meta description.": "首页缺少 meta description。",
    "Add a concise meta description that describes the primary offer and location/entity.": "添加简洁的 meta description，概括核心产品/服务以及地区或实体信息。",
    "Homepage is missing a canonical tag.": "首页缺少 canonical 标签。",
    "Expose self-referencing canonical tags on primary pages.": "在核心页面上添加自引用 canonical 标签。",
    "Homepage has medium or high render-blocking risk.": "首页存在中等或较高的渲染阻塞风险。",
    "Defer non-critical JavaScript and reduce synchronous CSS/JS payloads.": "延迟加载非关键 JavaScript，并减少同步 CSS/JS 体积。",
    "Render-blocking risk looks manageable.": "渲染阻塞风险看起来可控。",
    "Observed response time is slower than ideal for AI retrieval and user experience.": "当前响应时间偏慢，不利于 AI 抓取和用户体验。",
    "Reduce server response latency and optimize page-critical assets.": "降低服务端响应延迟，并优化页面关键资源。",
    "Observed response time is within a healthy baseline.": "当前响应时间处于健康基线范围。",
    "Images are missing lazy loading and/or explicit dimensions.": "图片缺少懒加载和/或显式尺寸声明。",
    "Add lazy loading and width/height attributes to primary images.": "为主要图片增加 lazy loading 以及 width/height 属性。",
    "Image delivery patterns show baseline optimization.": "图片加载模式已具备基础优化。",
    "No clear service page was discovered for content evaluation.": "未识别到明确的服务页，无法充分评估内容质量。",
    "Create a dedicated service page with clear offerings, outcomes, and supporting proof.": "创建独立服务页，明确说明服务内容、结果产出和支撑证明。",
    "Service page copy is thin for AI citation and retrieval.": "服务页内容过薄，不利于 AI 引用和检索。",
    "Expand service pages with problem framing, process details, deliverables, and FAQs.": "扩充服务页，补充问题背景、流程细节、交付内容和 FAQ。",
    "Service page has enough depth for baseline retrieval.": "服务页已具备基础检索所需的内容深度。",
    "No article or news page was discovered.": "未识别到文章页或新闻页。",
    "Publish insight or blog content to increase topical coverage and retrievable expertise.": "发布洞察或博客内容，提升主题覆盖和可检索的专业度。",
    "Article content is too short to establish durable topical authority.": "文章内容过短，难以建立稳定的主题权威。",
    "Publish longer-form articles with original data, examples, and authored bylines.": "发布更长篇的文章，并加入原创数据、案例和作者署名。",
    "Article content demonstrates topical depth.": "文章内容展现出较好的主题深度。",
    "FAQ content is missing.": "缺少 FAQ 内容。",
    "Add FAQ sections to commercial pages and high-intent landing pages.": "在商业页和高意向落地页增加 FAQ 模块。",
    "Author bylines are missing from evaluated content.": "评估页面中缺少作者署名。",
    "Add author profiles and bylines to articles and expert pages.": "为文章页和专家页补充作者简介与署名。",
    "Publication dates are missing from evaluated content.": "评估页面中缺少发布时间信息。",
    "Expose publish/update timestamps on editorial content.": "在内容页中展示发布时间和更新时间。",
    "Some content follows an answer-first structure.": "部分内容已经采用先答后述结构。",
    "Lead pages with direct answers before deeper explanation.": "优先用直接答案开头，再展开更深入的说明。",
    "Pages do not yet surface enough fact density for consistent AI extraction.": "页面事实密度不足，难以支持稳定的 AI 抽取。",
    "Add quantified claims, concrete specifications, and sourceable proof blocks.": "补充量化论断、明确规格信息以及可引用的证据块。",
    "Content chunking is weaker than ideal for answer extraction and citation reuse.": "内容分块结构偏弱，不利于答案抽取和引用复用。",
    "Break long sections into tighter question-led blocks with clearer subheadings.": "将长段内容拆成更紧凑的问题导向模块，并使用更清晰的小标题。",
    "JSON-LD markup is present.": "已存在 JSON-LD 标记。",
    "No JSON-LD structured data detected.": "未检测到 JSON-LD 结构化数据。",
    "Implement baseline JSON-LD on homepage and core landing pages.": "在首页和核心落地页实现基础 JSON-LD。",
    "No sameAs references found in structured data.": "结构化数据中未发现 sameAs 引用。",
    "Add sameAs links for official social, knowledge, and profile URLs.": "为官方社媒、知识库和资料页 URL 添加 sameAs 链接。",
    "Structured data exposes sameAs entity references.": "结构化数据已暴露 sameAs 实体引用。",
    "Structured data lacks stable @id usage across brand and commercial entities.": "结构化数据在品牌和商业实体上缺少稳定的 @id 用法。",
    "Add stable @id identifiers to Organization, WebSite, Product, and other core nodes.": "为 Organization、WebSite、Product 等核心节点补充稳定的 @id 标识。",
    "Structured data uses stable @id values across multiple entities.": "结构化数据已在多个实体上使用稳定的 @id。",
    "Entity relationships are too sparse for strong machine reasoning.": "实体关系过于稀疏，不利于机器推理。",
    "Add richer entity relationships such as brand, manufacturer, hasPart, offers, about, and contactPoint.": "补充更丰富的实体关系，如 brand、manufacturer、hasPart、offers、about 和 contactPoint。",
    "Structured data exposes a usable baseline of entity relationships.": "结构化数据已具备可用的基础实体关系。",
    "Premium mode currently keeps schema audit rule-based for deterministic validation.": "Premium 模式下，Schema 审计仍保持规则驱动，以确保校验结果确定性。",
    "Premium mode currently keeps technical audit rule-based for determinism.": "Premium 模式下，技术审计仍保持规则驱动，以确保结果确定性。",
    "Page is not yet citation-ready enough for consistent AI extraction.": "页面当前还不够适合被稳定抽取和引用。",
    "Restructure the page with answer-first sections, stronger headings, and tighter proof blocks.": "重构页面，加入先答后述模块、更强的标题结构和更紧凑的证据块。",
    "Content depth and fact density are weaker than ideal for GEO reuse.": "内容深度和事实密度偏弱，不利于 GEO 复用。",
    "Add concrete claims, specifications, FAQs, and sourced proof to the page.": "为页面补充明确论断、规格说明、FAQ 和可溯源证据。",
    "Page-level metadata or structure is incomplete.": "页面级元数据或结构不完整。",
    "Improve title, meta description, canonical tags, language declaration, and heading coverage.": "优化 title、meta description、canonical、语言声明和标题覆盖。",
    "Structured data on this page is too thin.": "该页面的结构化数据过薄。",
    "Add page-relevant JSON-LD such as Service, Product, FAQPage, Article, or DefinedTerm.": "为该页面添加相关 JSON-LD，例如 Service、Product、FAQPage、Article 或 DefinedTerm。",
    "Editorial page lacks an author signal.": "内容型页面缺少作者信号。",
    "Expose named authors or reviewers for editorial and knowledge pages.": "为内容页和知识页补充明确的作者或审校者信息。",
    "AI crawlers are not fully allowed by robots.txt.": "robots.txt 尚未完全放行 AI 爬虫。",
    "Publish or expand llms.txt with brand context, services, and citation guidance.": "发布或扩充 llms.txt，加入品牌背景、服务说明和引用指引。",
    "Citation-ready page structure is not yet strong enough for consistent reuse.": "适合引用的页面结构仍不够强，难以支持稳定复用。",
    "Improve answer-first copy, chunk structure, and metadata coverage on key pages.": "优化关键页面的先答后述内容、分块结构和元数据覆盖。",
    "Basic entity presence across homepage, about, and contact experiences is thin.": "首页、关于页和联系页中的基础实体信号偏弱。",
    "Strengthen homepage, about, and contact-page brand and contact signals.": "强化首页、关于页和联系页中的品牌与联系信号。",
    "Brand authority is weak relative to GEO citation needs.": "相对于 GEO 引用需求，品牌权威仍偏弱。",
    "External backlink authority is still light for a strong entity profile.": "对强实体画像来说，外部反链权威仍然不足。",
    "Grow high-quality referring domains and editorial backlinks.": "增加高质量引荐域和编辑型反链。",
    "Entity consistency is weakened by sitemap or domain mismatch.": "Sitemap 或域名不一致削弱了实体一致性。",
    "Align sitemap URLs, canonical signals, and the primary domain.": "对齐 Sitemap URL、canonical 信号和主域名。",
    "Brand entity signals need stronger external and structured support.": "品牌实体信号需要更强的外部与结构化支撑。",
    "Add company details, sameAs references, and stronger entity consistency signals.": "补充公司信息、sameAs 引用和更强的一致性实体信号。",
    "GEO Audit v3 scores only readiness dimensions that can be derived from the site and supplied enrichment sources.": "GEO Audit v3 仅对可从站点和补充数据源中推导出的 readiness 维度进行评分。",
    "Optional observation metrics are displayed separately and never change the composite GEO score.": "可选 observation 指标会单独展示，绝不会改变综合 GEO 分数。",
    "Platform readiness is comparative guidance, not a direct measurement of live mention share or citation rank.": "平台 readiness 仅用于相对指导，不直接代表实时提及份额或引用排名。",
    "Observation data was uploaded and is included as contextual evidence alongside readiness scoring.": "已上传 observation 数据，会作为上下文证据展示，但不参与 readiness 评分。",
    "No major gap detected.": "未发现明显短板。",
}


PATTERN_TRANSLATIONS: list[tuple[re.Pattern[str], str | Any]] = [
    (re.compile(r"^([A-Za-z][A-Za-z0-9\s/-]+) schema detected\.$"), lambda m: f"已检测到 {m.group(1)} Schema。"),
    (re.compile(r"^([A-Za-z][A-Za-z0-9\s/-]+) schema is missing\.$"), lambda m: f"缺少 {m.group(1)} Schema。"),
    (re.compile(r"^(.+?) readiness is acceptable\.$"), lambda m: f"{m.group(1)} 的 readiness 表现尚可。"),
    (re.compile(r"^(.+?) currently scores (\d+)/100 for GEO readiness\. The biggest gaps are in (.+?) and (.+?)\.$"), lambda m: f"{m.group(1)} 当前 GEO readiness 得分为 {m.group(2)}/100，最大的短板在 {m.group(3)} 和 {m.group(4)}。"),
    (re.compile(r"^Non-homepage input detected: (.+)$"), lambda m: f"检测到非首页输入：{m.group(1)}"),
    (re.compile(r"^Full audit mode sampled (\d+) pages and produced page-level diagnostics without changing the site-level scoring weights\.$"), lambda m: f"Full audit 模式共采样 {m.group(1)} 个页面，并返回逐页诊断结果，但不会改变站点级评分权重。"),
    (re.compile(r"^Input URL does not look like a homepage\. GEO site-level scores may be directionally useful but can be biased because homepage-derived signals are being evaluated from a deeper page\.$"), "输入 URL 看起来不是首页。GEO 站点级分数仍可作为方向性参考，但由于首页信号来自更深层页面，结果可能存在偏差。"),
]


def localize_text(text: str, lang: str = "en") -> str:
    if lang != "zh" or not text:
        return text
    if text in EXACT_TRANSLATIONS:
        return EXACT_TRANSLATIONS[text]
    for pattern, replacement in PATTERN_TRANSLATIONS:
        match = pattern.match(text)
        if not match:
            continue
        if callable(replacement):
            return replacement(match)
        return replacement
    return text


def localize_payload(value: Any, lang: str = "en") -> Any:
    if lang != "zh":
        return value
    if isinstance(value, str):
        return localize_text(value, lang)
    if isinstance(value, list):
        return [localize_payload(item, lang) for item in value]
    if isinstance(value, dict):
        return {key: localize_payload(item, lang) for key, item in value.items()}
    return value
