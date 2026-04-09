import { CONTENT_GEO_FACTOR_LABELS } from './task-config.js';
import {
  escapeHtml,
  formatBool,
  formatList,
  formatStatus,
  scoreToStatus,
  statusTone,
  tx
} from './shared.js';

export function renderContentAuditReport({ task, host, lang, setCachedReportHtml }) {
  const result = task?.result || {};
  const summary = result.summary || {};
  const discovery = result.discovery || {};
  const content = result.content || {};
  const target = content.target_page || {};
  const geoFactors = content.geo_factors || {};
  const onPage = content.on_page_checks || {};
  const schema = content.schema_checks || {};
  const coreChecks = Array.isArray(content.core_checks) ? content.core_checks : [];
  const skillLenses = Array.isArray(content.skill_lenses) ? content.skill_lenses : [];
  const topIssues = summary.top_issues || content.issues || [];
  const quickWins = summary.quick_wins || content.recommendations || [];
  const actions = Array.isArray(summary.prioritized_action_plan) ? summary.prioritized_action_plan : [];
  const schemaTypes = Array.isArray(schema.types) ? schema.types : [];
  const scoreBreakdown = summary.score_breakdown || {};
  const labels = {
    overall: tx(lang, '内容总分', 'Content Score'),
    summaryTitle: tx(lang, '内容审计概览', 'Content Audit Overview'),
    topIssuesTitle: tx(lang, '主要问题', 'Top Issues'),
    quickWinsTitle: tx(lang, '优先动作', 'Quick Wins'),
    factorTitle: tx(lang, 'GEO 内容因子', 'GEO Content Factors'),
    factorSubtitle: tx(lang, '对齐 geo-content-optimizer 的主要判断维度', 'Aligned to the geo-content-optimizer skill logic'),
    skillTitle: tx(lang, 'Skill 视角', 'Skill Lenses'),
    skillSubtitle: tx(lang, '按接入的 skill 输出对应得分与建议', 'Scores and guidance grouped by the enabled skills'),
    coreTitle: tx(lang, 'CORE-EEAT 自动检查', 'CORE-EEAT Automated Checks'),
    coreSubtitle: tx(lang, '页面级可自动判断的关键 GEO 检查项', 'Automatically measured page-level GEO checks'),
    evidenceTitle: tx(lang, '页面与结构信号', 'Page and Structure Signals'),
    evidenceSubtitle: tx(lang, '输入页的正文、Schema 和 On-Page 基础信息', 'Signals from the target page content, schema, and on-page basics'),
    actionTitle: tx(lang, '行动计划', 'Action Plan'),
    actionSubtitle: tx(lang, '按优先级整理的落地动作', 'Prioritized fixes based on the page audit'),
    noActions: tx(lang, '暂无行动计划。', 'No action plan available.'),
    noChecks: tx(lang, '暂无检查项。', 'No checks available.'),
    noLenses: tx(lang, '暂无 skill 视角结果。', 'No skill lens results available.'),
    noFactors: tx(lang, '暂无内容因子结果。', 'No content factor results available.'),
    noPageTitle: tx(lang, '未识别标题', 'Untitled page'),
    pageType: tx(lang, '页面类型', 'Page Type'),
    wordCount: tx(lang, '字数', 'Word Count'),
    response: tx(lang, '响应时间', 'Response'),
    pageLang: tx(lang, '页面语言', 'Page Language'),
    schemaTypeCount: tx(lang, 'Schema 类型数', 'Schema Types'),
    llm: tx(lang, 'AI 增强', 'AI Enrichment'),
    yes: tx(lang, '是', 'Yes'),
    no: tx(lang, '否', 'No'),
    passed: tx(lang, '通过', 'Pass'),
    failed: tx(lang, '待补齐', 'Needs work'),
    notes: tx(lang, '说明', 'Notes'),
    priority: tx(lang, '优先级', 'Priority'),
    targetUrl: tx(lang, '目标 URL', 'Target URL'),
    appliedSkills: tx(lang, '已用 skill', 'Applied Skills'),
    pageContentScore: tx(lang, '内容主体', 'Page Content'),
    geoReadinessScore: tx(lang, 'GEO 就绪度', 'GEO Readiness'),
    onPageScore: tx(lang, 'On-Page SEO', 'On-Page SEO'),
    schemaSupportScore: tx(lang, 'Schema 支撑', 'Schema Support'),
    eeat: tx(lang, 'E-E-A-T', 'E-E-A-T'),
    title: 'Title',
    meta: 'Meta',
    canonical: 'Canonical',
    h1: 'H1',
    imagesAlt: tx(lang, '图片 Alt 覆盖率', 'Image Alt Coverage'),
    links: tx(lang, '链接上下文', 'Link Context'),
    citations: tx(lang, '引用/来源', 'Citations / Sources'),
    freshness: tx(lang, '发布日期/更新', 'Publish / Update'),
    byline: tx(lang, '作者署名', 'Author Byline')
  };

  const breakdownCards = [
    [labels.pageContentScore, scoreBreakdown.page_content_score ?? content.page_content_score ?? 0],
    [labels.geoReadinessScore, scoreBreakdown.geo_readiness_score ?? content.geo_readiness_score ?? 0],
    [labels.onPageScore, scoreBreakdown.on_page_seo_score ?? content.on_page_seo_score ?? 0],
    [labels.schemaSupportScore, scoreBreakdown.schema_support_score ?? content.schema_support_score ?? 0],
    [labels.eeat, `${content.experience_score ?? 0} / ${content.expertise_score ?? 0} / ${content.authoritativeness_score ?? 0} / ${content.trustworthiness_score ?? 0}`]
  ].map(([name, value]) => `
    <div class="report-dim-card">
      <div class="report-dim-head">
        <span class="report-dim-name">${escapeHtml(String(name))}</span>
      </div>
      <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(value))}</span></div>
    </div>
  `).join('');

  const factorHtml = Object.entries(geoFactors).length
    ? Object.entries(geoFactors).map(([key, value]) => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(CONTENT_GEO_FACTOR_LABELS[key]?.[lang] || key)}</span>
            <span class="report-dim-pill">${escapeHtml(formatStatus(scoreToStatus(value), lang))}</span>
          </div>
          <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(value))}</span></div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noFactors)}</div>`;

  const skillHtml = skillLenses.length
    ? skillLenses.map(item => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(item.label || item.key)}</span>
            <span class="report-dim-pill">${escapeHtml(formatStatus(item.status, lang))}</span>
          </div>
          <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(item.score ?? 0))}</span></div>
          <div class="report-dim-note">${escapeHtml(item.summary || '')}</div>
          <div class="report-list" style="margin-top:10px">${formatList(item.issues || [], tx(lang, '暂无主要问题。', 'No major issues.'))}</div>
          <div class="report-list" style="margin-top:10px">${formatList(item.recommendations || [], tx(lang, '暂无建议。', 'No recommendations.'))}</div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noLenses)}</div>`;

  const coreHtml = coreChecks.length
    ? coreChecks.map(item => `
        <div class="evidence-card">
          <h5>${escapeHtml(item.label || item.id)}</h5>
          <div class="kv-list">
            <div class="kv-row"><span class="kv-key">${escapeHtml(labels.priority)}</span><span class="kv-val">${escapeHtml(formatStatus(item.priority, lang))}</span></div>
            <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '状态', 'Status'))}</span><span class="kv-val">${item.passed ? escapeHtml(labels.passed) : escapeHtml(labels.failed)}</span></div>
            <div class="kv-row"><span class="kv-key">${escapeHtml(labels.notes)}</span><span class="kv-val">${escapeHtml(item.notes || '-')}</span></div>
          </div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noChecks)}</div>`;

  const actionHtml = actions.length
    ? actions.map(item => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(item.action || '-')}</span>
            <span class="report-dim-pill">${escapeHtml(formatStatus(item.priority, lang))}</span>
          </div>
          <div class="report-dim-note"><strong>${escapeHtml(tx(lang, '模块', 'Module'))}:</strong> ${escapeHtml(item.module || '-')}</div>
          <div class="report-dim-note" style="margin-top:6px">${escapeHtml(item.rationale || '-')}</div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noActions)}</div>`;

  const evidenceHtml = `
    <div class="report-evidence-grid">
      <div class="evidence-card">
        <h5>${escapeHtml(tx(lang, '页面概况', 'Page Overview'))}</h5>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.targetUrl)}</span><span class="kv-val">${escapeHtml(discovery.final_url || task.url || '-')}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.pageType)}</span><span class="kv-val">${escapeHtml(target.page_type || 'article')}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.wordCount)}</span><span class="kv-val">${escapeHtml(String(target.word_count ?? 0))}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.response)}</span><span class="kv-val">${escapeHtml(String(discovery.fetch?.response_time_ms ?? '-'))} ms</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.pageLang)}</span><span class="kv-val">${escapeHtml(discovery.homepage?.lang || '-')}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.schemaTypeCount)}</span><span class="kv-val">${escapeHtml(String(schemaTypes.length))}</span></div>
        </div>
      </div>
      <div class="evidence-card">
        <h5>${escapeHtml(tx(lang, 'GEO 内容信号', 'GEO Content Signals'))}</h5>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">FAQ</span><span class="kv-val">${formatBool(target.has_faq, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.citations)}</span><span class="kv-val">${formatBool(target.has_reference_section || target.has_inline_citations, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.freshness)}</span><span class="kv-val">${formatBool(target.has_publish_date || target.has_update_log, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.byline)}</span><span class="kv-val">${formatBool(target.has_author, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">TL;DR</span><span class="kv-val">${formatBool(target.has_tldr, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">Answer-first</span><span class="kv-val">${formatBool(target.answer_first, labels.yes, labels.no)}</span></div>
        </div>
      </div>
      <div class="evidence-card">
        <h5>${escapeHtml(tx(lang, 'On-Page 基础', 'On-Page Basics'))}</h5>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.title)}</span><span class="kv-val">${formatBool(onPage.title_present, labels.yes, labels.no)} / ${escapeHtml(String(onPage.title_length ?? 0))}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.meta)}</span><span class="kv-val">${formatBool(onPage.meta_description_present, labels.yes, labels.no)} / ${escapeHtml(String(onPage.meta_description_length ?? 0))}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.canonical)}</span><span class="kv-val">${formatBool(onPage.canonical_present, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.h1)}</span><span class="kv-val">${formatBool(onPage.h1_present, labels.yes, labels.no)} / ${escapeHtml(String(onPage.heading_count ?? 0))} headings</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.imagesAlt)}</span><span class="kv-val">${escapeHtml(String(onPage.images_with_alt_ratio ?? 0))}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.links)}</span><span class="kv-val">${escapeHtml(String(onPage.link_context_score ?? 0))}</span></div>
        </div>
      </div>
      <div class="evidence-card">
        <h5>${escapeHtml(tx(lang, 'Schema 支撑', 'Schema Support'))}</h5>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">JSON-LD</span><span class="kv-val">${formatBool(schema.json_ld_present, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">Article / FAQPage</span><span class="kv-val">${formatBool(schema.has_article, labels.yes, labels.no)} / ${formatBool(schema.has_faq_page, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">sameAs</span><span class="kv-val">${escapeHtml(String(schema.same_as_count ?? 0))}</span></div>
          <div class="kv-row"><span class="kv-key">datePublished / dateModified</span><span class="kv-val">${formatBool(schema.has_date_published, labels.yes, labels.no)} / ${formatBool(schema.has_date_modified, labels.yes, labels.no)}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '对齐分', 'Alignment'))}</span><span class="kv-val">${escapeHtml(String(schema.visible_alignment_score ?? 0))}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '@id / 关系数', '@id / Relations'))}</span><span class="kv-val">${escapeHtml(String(schema.entity_id_count ?? 0))} / ${escapeHtml(String(schema.relation_count ?? 0))}</span></div>
        </div>
      </div>
    </div>
  `;

  host.className = 'report-shell';
  const html = `
    <section class="report-hero">
      <div class="report-score-box">
        <div>
          <div class="report-score-label">${escapeHtml(labels.overall)}</div>
          <div class="report-score-value">${escapeHtml(String(summary.overall_score ?? content.score ?? 0))}</div>
          <div class="report-score-sub">${escapeHtml(formatStatus(summary.status || content.status, lang))} · ${escapeHtml(labels.summaryTitle)}</div>
        </div>
        <div class="report-badges">
          <span class="r-badge ${escapeHtml(statusTone(summary.status || content.status))}">${escapeHtml(formatStatus(summary.status || content.status, lang))}</span>
          <span class="r-badge">${task.mode === 'premium' ? tx(lang, '会员版 / AI 增强', 'Premium / AI Enriched') : tx(lang, '普通版 / 规则版', 'Standard / Rule-based')}</span>
          <span class="r-badge ${summary.llm_enhanced ? 'success' : ''}">${summary.llm_enhanced ? escapeHtml(labels.yes) : escapeHtml(labels.no)}</span>
        </div>
      </div>
      <div class="report-hero-main">
        <div class="report-kicker">
          <span>${escapeHtml(discovery.domain || discovery.normalized_url || task.url || '-')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(summary.applied_skills?.join(' / ') || 'geo-content-optimizer / on-page-seo-auditor')}</span>
        </div>
        <h3>${escapeHtml(target.title || discovery.homepage?.title || labels.noPageTitle)}</h3>
        <div class="report-summary">${escapeHtml(summary.summary || '')}</div>
        <div class="report-meta-grid">
          <div class="report-meta-item"><div class="lbl">${escapeHtml(labels.targetUrl)}</div><div class="val">${escapeHtml(discovery.final_url || task.url || '-')}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(labels.appliedSkills)}</div><div class="val">${escapeHtml(summary.applied_skills?.join(', ') || 'geo-content-optimizer, on-page-seo-auditor')}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(labels.pageLang)}</div><div class="val">${escapeHtml(discovery.homepage?.lang || '-')}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(labels.llm)}</div><div class="val">${summary.llm_enhanced ? escapeHtml(labels.yes) : escapeHtml(labels.no)}</div></div>
        </div>
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.summaryTitle)}</h4><span>${escapeHtml(tx(lang, '内容总分、构成分和 E-E-A-T 拆解', 'Overall page content score with component and E-E-A-T breakdowns'))}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${breakdownCards}</div></div>
    </section>

    <div class="report-grid-2">
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(labels.topIssuesTitle)}</h4><span>${escapeHtml(tx(lang, '拖累页面引用与检索表现的主要缺口', 'The biggest gaps hurting retrieval and citation readiness'))}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(topIssues, tx(lang, '暂无主要问题。', 'No major issues.'))}</div></div>
      </section>
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(labels.quickWinsTitle)}</h4><span>${escapeHtml(tx(lang, '优先处理低成本高收益项', 'Prioritize fast, high-leverage fixes'))}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(quickWins, tx(lang, '暂无优先动作。', 'No quick wins available.'))}</div></div>
      </section>
    </div>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.factorTitle)}</h4><span>${escapeHtml(labels.factorSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${factorHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.skillTitle)}</h4><span>${escapeHtml(labels.skillSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${skillHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.coreTitle)}</h4><span>${escapeHtml(labels.coreSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-evidence-grid">${coreHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.evidenceTitle)}</h4><span>${escapeHtml(labels.evidenceSubtitle)}</span></div>
      <div class="report-section-body">${evidenceHtml}</div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.actionTitle)}</h4><span>${escapeHtml(labels.actionSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${actionHtml}</div></div>
    </section>
  `;
  host.innerHTML = html;
  setCachedReportHtml(task, lang, html);
}
