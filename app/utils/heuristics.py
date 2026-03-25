from __future__ import annotations

import re
from typing import Any

from app.models.discovery import BacklinkOverviewResult, KeyPages, LlmsResult, PageProfile, SiteSignals


# 业务类型推断规则：关键词 → 业务类型映射
# 用于从标题、描述和正文文本中自动判断站点所属行业
BUSINESS_TYPE_RULES = {
    "agency": ["agency", "marketing", "seo", "growth"],
    "saas": ["platform", "software", "saas", "automation"],
    "ecommerce": ["shop", "store", "ecommerce", "product"],
    "local_service": ["clinic", "law firm", "dentist", "repair", "consulting"],
    "publisher": ["news", "blog", "media", "insights", "magazine"],
}

# 关键页面类型及其识别关键词
# 用于从 Sitemap URL 列表中定位 About / Service / Contact 等高价值页面
KEY_PAGE_KEYWORDS = {
    "about": ["about", "company", "关于"],
    "service": ["service", "services", "seo", "solution", "产品", "服务"],
    "contact": ["contact", "联系"],
    "article": ["blog", "news", "article", "insights", "posts"],
    "case_study": ["case", "study", "success", "work", "portfolio", "案例"],
}

# 实体信息检测的正则表达式模式
ADDRESS_PATTERN = r"\b\d{1,6}\s+[A-Za-z0-9.\s]+(?:street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln)\b"
PHONE_PATTERN = r"(?:\+?\d[\d\s().-]{7,}\d)"
EMAIL_PATTERN = r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"


def infer_business_type(title: str | None, meta_description: str | None, text: str) -> str:
    """从标题、描述和正文推断站点业务类型

    将各字段拼接成文本片段，按 BUSINESS_TYPE_RULES 规则顺序匹配关键词，
    返回第一个命中的业务类型；无命中时返回 "general_business"。

    Args:
        title: 页面 <title> 文本
        meta_description: meta description 内容
        text: 正文前 1000 字符

    Returns:
        业务类型字符串：agency / saas / ecommerce / local_service / publisher / general_business
    """
    # 合并非空字段后统一小写，取正文前 1000 字符避免性能问题
    haystack = " ".join(filter(None, [title, meta_description, text[:1000]])).lower()
    for business_type, keywords in BUSINESS_TYPE_RULES.items():
        if any(keyword in haystack for keyword in keywords):
            return business_type
    return "general_business"


def select_key_pages(candidate_urls: list[str]) -> KeyPages:
    """从候选 URL 列表中识别关键页面

    按 URL 长度升序（短 URL 更可能是主类目页）遍历候选列表，
    对每种关键页面类型取第一个命中的 URL。

    Args:
        candidate_urls: 来自 Sitemap 的已采样 URL 列表

    Returns:
        KeyPages：包含 about / service / contact / article / case_study 的 URL（未找到时为 None）
    """
    result: dict[str, str | None] = {key: None for key in KEY_PAGE_KEYWORDS}
    # 去重并按 URL 长度排序，短 URL 优先（避免深层子页命中）
    ordered_urls = sorted(dict.fromkeys(candidate_urls), key=lambda item: (len(item), item))

    for page_type, keywords in KEY_PAGE_KEYWORDS.items():
        for url in ordered_urls:
            lowered = url.lower()
            if any(keyword.lower() in lowered for keyword in keywords):
                result[page_type] = url
                break

    return KeyPages(**result)


def detect_site_signals(
    text: str,
    schema_summary: dict[str, Any],
    key_pages: KeyPages,
    title: str | None = None,
) -> SiteSignals:
    """检测站点实体信号

    从主页文本、Schema 摘要和关键页面中提取可识别的品牌/实体信号，
    这些信号用于后续的品牌权威评估和 AI 可引用性评分。

    Args:
        text: 主页正文文本（用于正则匹配地址、电话、邮件等）
        schema_summary: 从 JSON-LD 提取的 Schema 摘要（含 sameAs 等）
        key_pages: 已识别的关键页面集合
        title: 页面标题（用于从分隔符后提取公司名称）

    Returns:
        SiteSignals：包含各类实体信号的检测结果
    """
    # 从标题中提取公司名称（取最后一个 | 或 - 之后的部分）
    company_name = None
    if title and ("|" in title or "-" in title):
        company_name = re.split(r"[|-]", title)[-1].strip() or None

    # 检测荣誉/认证关键词
    awards_detected = any(keyword in text.lower() for keyword in ["award", "awards", "certified", "top rated"])
    certifications_detected = any(
        keyword in text.lower()
        for keyword in ["certification", "certified", "iso", "accredited", "google partner"]
    )

    return SiteSignals(
        company_name_detected=bool(company_name),
        address_detected=bool(re.search(ADDRESS_PATTERN, text, re.I)),
        phone_detected=bool(re.search(PHONE_PATTERN, text, re.I)),
        email_detected=bool(re.search(EMAIL_PATTERN, text, re.I)),
        awards_detected=awards_detected,
        certifications_detected=certifications_detected,
        # sameAs 存在说明已建立跨平台实体链接（对 AI 引用非常重要）
        same_as_detected=bool(schema_summary.get("same_as")),
        detected_company_name=company_name,
        # 统计主页正文中品牌名重复出现次数（品牌强化信号）
        homepage_brand_mentions=(len(re.findall(re.escape(company_name), text, re.I)) if company_name else 0),
    )


def assess_llms_effectiveness(
    llms: LlmsResult,
    *,
    company_name: str | None = None,
    business_type: str | None = None,
) -> dict[str, Any]:
    """评估 llms.txt 文件的质量和有效性

    llms.txt 是帮助 AI 系统理解站点内容的机器可读文件。
    从以下维度评分（总分 100）：
    - exists（存在）:              20 分
    - has_meaningful_length（有实质内容，≥250字符）: 20 分
    - mentions_brand（提及品牌名）:  20 分
    - mentions_services（提及服务）: 20 分
    - includes_guidance（包含引导关键词）: 10 分
    - has_structured_sections（有 Markdown 结构）: 10 分

    Args:
        llms: LlmsResult 抓取结果
        company_name: 品牌/公司名称（用于品牌提及检测）
        business_type: 业务类型（用于服务关键词扩展）

    Returns:
        包含 score、signals、reasons 的字典
    """
    # 文件不存在时直接返回零分，所有信号为 False
    if not llms.exists:
        return {
            "score": 0,
            "signals": {
                "exists": False,
                "has_meaningful_length": False,
                "mentions_brand": False,
                "mentions_services": False,
                "includes_guidance": False,
                "has_structured_sections": False,
            },
            "reasons": ["No llms.txt file detected."],
        }

    preview = llms.content_preview.lower()
    company_lower = (company_name or "").lower()
    # 合并业务类型专属关键词和通用服务关键词
    service_keywords = BUSINESS_TYPE_RULES.get(business_type or "", []) + [
        "service",
        "services",
        "solution",
        "solutions",
        "product",
        "products",
    ]
    # 引导关键词：说明内容如何被引用或联系
    guidance_keywords = ["cite", "citation", "canonical", "contact", "support", "policy", "preferred"]
    signals = {
        "exists": True,
        "has_meaningful_length": llms.content_length >= 250,
        "mentions_brand": bool(company_lower and company_lower in preview),
        "mentions_services": any(keyword in preview for keyword in service_keywords),
        "includes_guidance": any(keyword in preview for keyword in guidance_keywords),
        # Markdown 章节结构（## / # / -）说明内容对机器友好
        "has_structured_sections": "##" in llms.content_preview or "# " in llms.content_preview or "- " in llms.content_preview,
    }
    weights = {
        "exists": 20,
        "has_meaningful_length": 20,
        "mentions_brand": 20,
        "mentions_services": 20,
        "includes_guidance": 10,
        "has_structured_sections": 10,
    }
    # 累计命中信号的分数
    score = sum(weights[name] for name, enabled in signals.items() if enabled)
    reasons = []
    if signals["mentions_brand"]:
        reasons.append("llms.txt names the site or brand directly.")
    if signals["mentions_services"]:
        reasons.append("llms.txt describes the site's services or core offering.")
    if signals["includes_guidance"]:
        reasons.append("llms.txt includes machine-facing guidance or citation hints.")
    if signals["has_structured_sections"]:
        reasons.append("llms.txt uses readable sections for machine consumption.")
    return {"score": min(score, 100), "signals": signals, "reasons": reasons}


def assess_basic_brand_presence(signals: SiteSignals, key_pages: KeyPages) -> dict[str, Any]:
    """评估站点基础品牌展示能力

    评分规则（总分 100，但各项可叠加超出后取 min）：
    - 检测到公司名称:        35 分
    - 检测到电话或邮件:      25 分
    - 存在 About 页面:       20 分
    - 存在 Contact 页面:     20 分

    Args:
        signals: 站点实体信号检测结果
        key_pages: 已识别的关键页面集合

    Returns:
        包含 score 和 reasons 的字典
    """
    score = 0
    reasons: list[str] = []

    if signals.company_name_detected:
        score += 35
        reasons.append("Detected company naming signal.")
    if signals.phone_detected or signals.email_detected:
        score += 25
        reasons.append("Detected direct contact signal.")
    if key_pages.about:
        score += 20
        reasons.append("Site exposes an about/company page.")
    if key_pages.contact:
        score += 20
        reasons.append("Site exposes a contact page.")

    return {"score": min(score, 100), "reasons": reasons}


def assess_brand_mentions(
    signals: SiteSignals,
    *,
    homepage: dict[str, Any],
    llms: LlmsResult,
    key_pages: KeyPages,
) -> dict[str, Any]:
    """评估品牌名称在关键字段中的提及覆盖度

    检查品牌名在 title / meta_description / h1 / llms.txt 预览中的命中数，
    配合主页正文重复次数和关键页面存在情况综合评分。

    评分规则（上限 100）：
    - 关键字段命中：每个 +15 分（上限 45 分）
    - 主页正文 ≥2 次提及：+20 分；1 次：+10 分
    - About 页面：+20 分
    - Contact 页面：+15 分

    Args:
        signals: 站点实体信号（含检测到的公司名和主页提及次数）
        homepage: 主页提取结果字典（含 title / meta_description / h1）
        llms: llms.txt 抓取结果
        key_pages: 已识别的关键页面集合

    Returns:
        包含 score、reasons 和 mention_hits 的字典
    """
    brand_name = (signals.detected_company_name or "").strip()
    brand_lower = brand_name.lower()
    # 检查品牌名在四个关键字段中的出现情况
    text_fields = [
        homepage.get("title") or "",
        homepage.get("meta_description") or "",
        homepage.get("h1") or "",
        llms.content_preview or "",
    ]
    mention_hits = sum(1 for field in text_fields if brand_lower and brand_lower in field.lower())

    score = 0
    reasons: list[str] = []
    if mention_hits:
        score += min(45, mention_hits * 15)
        reasons.append("Brand is repeated across key crawlable fields.")
    if signals.homepage_brand_mentions >= 2:
        score += 20
        reasons.append("Homepage body copy repeats the brand enough to reinforce entity recall.")
    elif signals.homepage_brand_mentions == 1:
        score += 10
        reasons.append("Homepage body copy includes at least one brand mention.")
    if key_pages.about:
        score += 20
        reasons.append("About page supports brand/entity discovery.")
    if key_pages.contact:
        score += 15
        reasons.append("Contact page strengthens branded navigation and entity confirmation.")

    return {"score": min(score, 100), "reasons": reasons, "mention_hits": mention_hits}


def assess_entity_consistency(
    signals: SiteSignals,
    *,
    schema_summary: dict[str, Any],
    homepage: dict[str, Any],
    llms: LlmsResult,
    key_pages: KeyPages,
    primary_domain: str,
    sitemap_urls: list[str],
) -> dict[str, Any]:
    """评估品牌/实体在各渠道间的一致性

    AI 系统通过跨信源一致性判断实体真实性。
    评分规则（上限 100）：
    - Schema sameAs 存在：         +35 分（跨平台实体链接）
    - Organization Schema：        +20 分
    - 品牌名在标题/H1/llms.txt 一致：+20 分
    - About + Contact 双页面：      +15 分
    - Sitemap URL 域名一致：        +10 分

    Args:
        signals: 站点实体信号
        schema_summary: Schema 摘要（含 sameAs 和 has_organization）
        homepage: 主页提取结果（含 title / h1）
        llms: llms.txt 抓取结果
        key_pages: 已识别的关键页面
        primary_domain: 站点主域名
        sitemap_urls: Sitemap 中采样的 URL 列表

    Returns:
        包含 score、reasons、same_as_count 和 same_domain_sitemap 的字典
    """
    company_lower = (signals.detected_company_name or "").lower()
    title = (homepage.get("title") or "").lower()
    h1 = (homepage.get("h1") or "").lower()
    llms_preview = llms.content_preview.lower()
    same_as_count = len(schema_summary.get("same_as", []))
    # 取前 10 个 Sitemap URL 检查域名一致性
    sitemap_domains = {url.lower() for url in sitemap_urls[:10]}
    same_domain_sitemap = all(primary_domain in url for url in sitemap_domains) if sitemap_domains else True

    score = 0
    reasons: list[str] = []
    if same_as_count > 0:
        score += 35
        reasons.append("Schema exposes sameAs references.")
    if schema_summary.get("has_organization"):
        score += 20
        reasons.append("Organization schema is present.")
    # 品牌名在标题/H1/llms.txt 中任意一处出现则视为跨渠道一致
    if company_lower and any(company_lower in field for field in [title, h1, llms_preview]):
        score += 20
        reasons.append("Brand naming is consistent across page metadata and machine-readable copy.")
    if key_pages.about and key_pages.contact:
        score += 15
        reasons.append("About and contact pages reinforce entity continuity.")
    if same_domain_sitemap:
        score += 10
        reasons.append("Sitemap URLs align with the primary domain.")
    else:
        reasons.append("Sitemap URLs do not align with the primary domain.")

    return {
        "score": min(score, 100),
        "reasons": reasons,
        "same_as_count": same_as_count,
        "same_domain_sitemap": same_domain_sitemap,
    }


def assess_business_completeness(signals: SiteSignals, key_pages: KeyPages) -> dict[str, Any]:
    """评估企业信息完整度

    AI 系统更倾向于引用信息完备的实体。
    评分规则（上限 100）：
    - 公司名称：    +20 分
    - 实体地址：    +15 分
    - 电话号码：    +15 分
    - 公开邮件：    +15 分
    - About 页面：  +10 分
    - Contact 页面：+10 分
    - 奖项荣誉：    +10 分
    - 认证资质：    +5 分

    Args:
        signals: 站点实体信号检测结果
        key_pages: 已识别的关键页面集合

    Returns:
        包含 score 和 reasons 的字典
    """
    score = 0
    reasons: list[str] = []

    if signals.company_name_detected:
        score += 20
        reasons.append("Detected company naming signal.")
    if signals.address_detected:
        score += 15
        reasons.append("Detected business address.")
    if signals.phone_detected:
        score += 15
        reasons.append("Detected phone number.")
    if signals.email_detected:
        score += 15
        reasons.append("Detected public email address.")
    if key_pages.about:
        score += 10
        reasons.append("Site exposes an about/company page.")
    if key_pages.contact:
        score += 10
        reasons.append("Site exposes a contact page.")
    if signals.awards_detected:
        score += 10
        reasons.append("Detected awards or recognitions.")
    if signals.certifications_detected:
        score += 5
        reasons.append("Detected certifications or accreditation.")

    return {"score": min(score, 100), "reasons": reasons}


def assess_backlink_quality(backlinks: BacklinkOverviewResult) -> dict[str, Any]:
    """评估外链质量（基于 Semrush 数据）

    当 Semrush 数据不可用时返回 score=None（调用方处理跳过加权）。
    评分公式：authority_score * 0.4 + referring_domains_score * 0.25
              + ip_diversity_score * 0.15 + follow_ratio_score * 0.2

    各分项标准化方法：
    - authority_score: Semrush 原始值（0-100），直接使用
    - referring_domains → /5 标准化（≥500域名得满分）
    - referring_ip_classes → /3 标准化（≥300 IP C类段得满分）
    - follow_ratio → *100（100% follow 得满分）

    Args:
        backlinks: Semrush 外链概览数据

    Returns:
        包含 score（可能为 None）、available 和 reasons 的字典
    """
    if not backlinks.available:
        return {
            "score": None,
            "available": False,
            "reasons": [backlinks.error or "Backlink provider unavailable."],
        }

    authority = min(backlinks.authority_score or 0, 100)
    # 将 referring_domains 标准化到 0-100（500+ 个引用域名视为满分）
    domains = min(100, int(min((backlinks.referring_domains or 0) / 5, 100)))
    # IP C类段多样性（300+ 个 IP 段视为满分，防止同一主机大量低质外链）
    diversity = min(100, int(min((backlinks.referring_ip_classes or 0) / 3, 100)))
    follow_ratio_score = int((backlinks.follow_ratio or 0) * 100)
    # 加权组合：权威度占比最高（40%），follow 比率次之（20%）
    score = int(round(authority * 0.4 + domains * 0.25 + diversity * 0.15 + follow_ratio_score * 0.2))

    reasons = [f"Semrush authority score: {backlinks.authority_score or 0}."]
    if backlinks.referring_domains is not None:
        reasons.append(f"Referring domains: {backlinks.referring_domains}.")
    if backlinks.follow_ratio is not None:
        reasons.append(f"Follow backlink ratio: {int(backlinks.follow_ratio * 100)}%.")
    return {"score": min(score, 100), "available": True, "reasons": reasons}


def calculate_brand_authority(
    *,
    signals: SiteSignals,
    homepage: dict[str, Any],
    llms: LlmsResult,
    key_pages: KeyPages,
    schema_summary: dict[str, Any],
    primary_domain: str,
    sitemap_urls: list[str],
    backlinks: BacklinkOverviewResult,
) -> dict[str, Any]:
    """计算综合品牌权威度分数

    将四个维度的评估结果按等权重（各 25%）加权合并：
    - backlink_quality:       外链质量（Semrush 数据，不可用时跳过）
    - brand_mentions:         品牌提及覆盖度
    - entity_consistency:     跨渠道实体一致性
    - business_completeness:  企业信息完整度

    注意：当 backlink_quality 不可用时，剩余三个维度按实际权重比例归一化。

    Args:
        signals: 站点实体信号
        homepage: 主页提取结果
        llms: llms.txt 结果
        key_pages: 关键页面集合
        schema_summary: Schema 摘要
        primary_domain: 主域名
        sitemap_urls: Sitemap URL 样本
        backlinks: Semrush 外链概览数据

    Returns:
        包含 score、reasons 和 components（各维度详情）的字典
    """
    components = {
        "backlink_quality": assess_backlink_quality(backlinks),
        "brand_mentions": assess_brand_mentions(signals, homepage=homepage, llms=llms, key_pages=key_pages),
        "entity_consistency": assess_entity_consistency(
            signals,
            schema_summary=schema_summary,
            homepage=homepage,
            llms=llms,
            key_pages=key_pages,
            primary_domain=primary_domain,
            sitemap_urls=sitemap_urls,
        ),
        "business_completeness": assess_business_completeness(signals, key_pages),
    }
    # 各维度等权重 25%
    weights = {
        "backlink_quality": 0.25,
        "brand_mentions": 0.25,
        "entity_consistency": 0.25,
        "business_completeness": 0.25,
    }

    weighted_total = 0.0
    weight_total = 0.0
    reasons: list[str] = []
    for name, component in components.items():
        score = component.get("score")
        if score is None:
            # score=None 表示该维度数据不可用，跳过不计入加权
            continue
        weighted_total += score * weights[name]
        weight_total += weights[name]
        # 每个维度最多取前 2 条原因，避免 reasons 过长
        reasons.extend(component.get("reasons", [])[:2])

    # weight_total 可能小于 1.0（backlinks 不可用时），需归一化
    score = int(round(weighted_total / weight_total)) if weight_total else 0
    return {"score": min(score, 100), "reasons": reasons[:8], "components": components}


def _normalize_page_profile(page: PageProfile | dict[str, Any]) -> dict[str, Any]:
    """将 PageProfile 模型或字典统一转换为字典格式

    支持两种输入类型，确保后续处理逻辑统一。
    """
    if isinstance(page, PageProfile):
        return page.model_dump()
    return page


def _citation_probability(score: int, page: dict[str, Any]) -> str:
    """根据可引用性分数和辅助信号判定引用概率等级

    分级标准：
    - HIGH:   score ≥ 75 且辅助信号 ≥ 2 个
    - MEDIUM: score ≥ 55
    - LOW:    其余

    辅助信号包括：answer_first / has_quantified_data / has_faq / has_author / has_publish_date

    Args:
        score: 页面可引用性评分（0-100）
        page: 页面属性字典

    Returns:
        引用概率等级字符串：HIGH / MEDIUM / LOW
    """
    # 统计命中的辅助信号数量
    support_signals = sum(
        1
        for present in [
            page.get("answer_first"),
            page.get("has_quantified_data"),
            page.get("has_faq"),
            page.get("has_author"),
            page.get("has_publish_date"),
        ]
        if present
    )
    if score >= 75 and support_signals >= 2:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def _score_page_citability(page: dict[str, Any]) -> dict[str, Any]:
    """对单个页面计算 AI 可引用性分数

    评分由两部分组成：
    1. 信号加权分（最高 90 分）
       - has_title / has_meta_description / has_h1_or_headings / has_canonical: 各 8 分
       - has_multiple_headings（≥3个）: 10 分
       - has_substantial_copy（≥250字）: 10 分
       - answer_first（答案前置）:  15 分（最高权重：AI 优先引用直接回答）
       - has_data_points（量化数据）: 8 分
       - has_faq:       5 分
       - has_author:    5 分
       - has_publish_date: 5 分
    2. 密度/结构补充分（各最高 10 分）
       - information_density_score * 0.1
       - chunk_structure_score * 0.1

    Args:
        page: 包含页面属性和评分字段的字典

    Returns:
        包含 score、signals、information_density_score、chunk_structure_score、citation_probability 的字典
    """
    signals: dict[str, bool] = {
        "has_title": bool(page.get("title")),
        "has_meta_description": bool(page.get("meta_description")),
        "has_h1_or_headings": bool(page.get("h1")) or len(page.get("headings", [])) >= 1,
        "has_canonical": bool(page.get("canonical")),
        "has_multiple_headings": len(page.get("headings", [])) >= 3,
        "has_substantial_copy": page.get("word_count", 0) >= 250,
        "answer_first": bool(page.get("answer_first")),
        "has_data_points": bool(page.get("has_quantified_data")),
        "has_faq": bool(page.get("has_faq")),
        "has_author": bool(page.get("has_author")),
        "has_publish_date": bool(page.get("has_publish_date")),
    }
    information_density_score = int(page.get("information_density_score", 0))
    chunk_structure_score = int(page.get("chunk_structure_score", 0))
    score = 0.0
    weights = {
        "has_title": 8,
        "has_meta_description": 8,
        "has_h1_or_headings": 8,
        "has_canonical": 8,
        "has_multiple_headings": 10,
        "has_substantial_copy": 10,
        "answer_first": 15,   # 最高权重信号：AI 系统偏好答案前置的内容
        "has_data_points": 8,
        "has_faq": 5,
        "has_author": 5,
        "has_publish_date": 5,
    }
    for name, present in signals.items():
        if present:
            score += weights[name]
    # 内容密度和段落结构各贡献最多 10 分
    score += information_density_score * 0.1
    score += chunk_structure_score * 0.1
    normalized_score = min(int(round(score)), 100)
    return {
        "score": normalized_score,
        "signals": signals,
        "information_density_score": information_density_score,
        "chunk_structure_score": chunk_structure_score,
        "citation_probability": _citation_probability(normalized_score, page),
    }


def assess_page_citability(page: PageProfile | dict[str, Any]) -> dict[str, Any]:
    """对单个页面直接计算 citability，供逐页诊断复用"""
    return _score_page_citability(_normalize_page_profile(page))


def assess_citability(
    homepage: dict[str, Any],
    page_profiles: dict[str, PageProfile | dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """评估站点整体 AI 可引用性

    策略：
    - 主页默认填充缺失的辅助评分字段（information_density_score / chunk_structure_score 等）
    - 对所有页面（主页 + 关键页）独立评分
    - 如存在比主页更高分的关键页，以 45% 主页 + 55% 最佳页面 加权合并总分
    - 仅主页时，总分直接等于主页评分

    Args:
        homepage: 主页提取结果字典
        page_profiles: 关键页面评分字典（key 为页面类型）

    Returns:
        包含 score、signals、homepage_citability、best_page_citability、
        citation_probability 和 page_scores 的字典
    """
    # 为主页填充缺失字段的默认估算值（避免因 KeyError 导致计算失败）
    homepage_payload = dict(homepage)
    homepage_payload.setdefault("information_density_score", 40 if homepage.get("word_count", 0) >= 250 else 20)
    homepage_payload.setdefault("chunk_structure_score", 50 if len(homepage.get("headings", [])) >= 3 else 25)
    homepage_payload.setdefault("answer_first", False)
    homepage_payload.setdefault("has_quantified_data", False)
    homepage_payload.setdefault("has_faq", False)
    homepage_payload.setdefault("has_author", False)
    homepage_payload.setdefault("has_publish_date", False)

    homepage_citability = _score_page_citability(homepage_payload)
    scored_pages: dict[str, Any] = {"homepage": homepage_citability}

    # 对每个关键页面单独评分
    for key, profile in (page_profiles or {}).items():
        normalized = _normalize_page_profile(profile)
        scored_pages[key] = _score_page_citability(normalized)

    # 找出所有页面中评分最高的页面
    best_page_key, best_page = max(scored_pages.items(), key=lambda item: item[1]["score"])
    overall_score = homepage_citability["score"]
    if best_page_key != "homepage":
        # 最佳关键页比主页更优时，给予深度页更高权重，更符合 GEO 的引用现实
        overall_score = int(round(homepage_citability["score"] * 0.45 + best_page["score"] * 0.55))

    return {
        "score": min(overall_score, 100),
        "signals": homepage_citability["signals"],
        "homepage_citability": homepage_citability,
        "best_page_citability": {"page_key": best_page_key, **best_page},
        "citation_probability": best_page["citation_probability"],
        "page_scores": scored_pages,
    }


def assess_ssr_signal(html_length: int, word_count: int) -> dict[str, Any]:
    """评估服务端渲染（SSR）信号强度

    通过 HTML 体积和可见文字数量推断内容是否为 SSR 渲染。
    SSR 对 AI 爬虫非常重要，因为大多数 AI 抓取不执行 JavaScript。

    分级标准：
    - strong（100 分）：html_length ≥ 5000 且 word_count ≥ 300
    - moderate（70 分）：html_length ≥ 2500 且 word_count ≥ 120
    - weak（45 分）：   html_length ≥ 1200 且 word_count ≥ 60
    - poor（20 分）：   其余（极可能为纯客户端渲染）

    Args:
        html_length: HTML 响应体字节数
        word_count: 页面可见文字词数

    Returns:
        包含 score 和 classification 的字典
    """
    if html_length >= 5000 and word_count >= 300:
        return {"score": 100, "classification": "strong"}
    if html_length >= 2500 and word_count >= 120:
        return {"score": 70, "classification": "moderate"}
    if html_length >= 1200 and word_count >= 60:
        return {"score": 45, "classification": "weak"}
    return {"score": 20, "classification": "poor"}


def assess_render_blocking(scripts: list[dict[str, Any]], stylesheets: list[dict[str, Any]]) -> dict[str, Any]:
    """评估渲染阻塞资源对页面性能的影响

    渲染阻塞资源会延迟首次内容渲染（FCP），影响 Core Web Vitals。
    风险计算：同步脚本每个 +20 分风险，CSS 样式表每个 +10 分风险，风险上限 100。
    最终评分 = 100 - risk_score（分数越高越好）。

    风险等级：
    - high:   risk_score ≥ 70
    - medium: risk_score ≥ 35
    - low:    risk_score < 35

    同步脚本判定：有 src 属性且未设置 async 或 defer 的外部脚本。

    Args:
        scripts: 页面脚本列表（每项含 src / async_attr / defer_attr）
        stylesheets: 页面样式表列表

    Returns:
        包含 score、sync_script_count、stylesheet_count 和 risk_level 的字典
    """
    # 同步阻塞脚本：有外部 src 且没有 async/defer 属性
    sync_scripts = [
        item for item in scripts if item.get("src") and not item.get("async_attr") and not item.get("defer_attr")
    ]
    stylesheet_count = len(stylesheets)
    # 风险分：同步脚本权重更高（每个 20 分 vs 样式表 10 分）
    risk_score = min(100, len(sync_scripts) * 20 + stylesheet_count * 10)
    return {
        "score": max(0, 100 - risk_score),
        "sync_script_count": len(sync_scripts),
        "stylesheet_count": stylesheet_count,
        "risk_level": "high" if risk_score >= 70 else "medium" if risk_score >= 35 else "low",
    }
