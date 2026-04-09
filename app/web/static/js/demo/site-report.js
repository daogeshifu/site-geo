import { PLATFORM_LABELS } from './task-config.js';
import {
  escapeHtml,
  formatBool,
  formatList,
  formatStatus,
  scoreToStatus,
  statusTone,
  tx
} from './shared.js';

function getDimensionMeta(lang) {
  return [
    {
      key: 'AI Citability & Visibility',
      defaultName: tx(lang, 'AI 可见性', 'AI Citability & Visibility'),
      weight: '25%',
      formula: tx(
        lang,
        '0.32 × crawler + 0.40 × snapshot citability + 0.12 × llms 有效性 + 0.16 × 基础实体存在',
        '0.32 × crawler + 0.40 × snapshot citability + 0.12 × llms quality + 0.16 × baseline entity presence'
      ),
      detail: result => {
        const checks = result?.visibility?.checks || {};
        const citability = result?.visibility?.findings?.citability || {};
        const best = citability.best_page_citability || {};
        return tx(
          lang,
          `${checks.allowed_ai_crawlers ?? 0}/${checks.total_ai_crawlers_checked ?? 0} 个 AI crawler 放行 · 最佳页面 ${best.page_key || 'homepage'} ${best.score ?? 0} · 引用概率 ${citability.citation_probability || 'LOW'}`,
          `${checks.allowed_ai_crawlers ?? 0}/${checks.total_ai_crawlers_checked ?? 0} AI crawlers allowed · Best page ${best.page_key || 'homepage'} ${best.score ?? 0} · Citation probability ${citability.citation_probability || 'LOW'}`
        );
      }
    },
    {
      key: 'Brand Authority Signals',
      defaultName: tx(lang, '品牌权威', 'Brand Authority Signals'),
      weight: '20%',
      formula: tx(
        lang,
        '0.25 × 外链质量 + 0.25 × 品牌提及覆盖 + 0.25 × sameAs/Entity 一致性 + 0.25 × 企业信息完整度',
        '0.25 × backlink quality + 0.25 × brand mention coverage + 0.25 × sameAs/entity consistency + 0.25 × business completeness'
      ),
      detail: result => {
        const brand = result?.visibility?.checks?.brand_signals || {};
        const backlinks = result?.visibility?.checks?.backlinks || {};
        const authority = backlinks.authority_score ?? tx(lang, '未接入', 'Unavailable');
        return tx(
          lang,
          `公司名 ${brand.company_name_detected ? '已识别' : '未识别'} · sameAs ${brand.same_as_detected ? '已配置' : '缺失'} · Semrush AS ${authority}`,
          `Company name ${brand.company_name_detected ? 'detected' : 'missing'} · sameAs ${brand.same_as_detected ? 'present' : 'missing'} · Semrush AS ${authority}`
        );
      }
    },
    {
      key: 'Content Quality & E-E-A-T',
      defaultName: tx(lang, '内容与 E-E-A-T', 'Content Quality & E-E-A-T'),
      weight: '20%',
      formula: tx(
        lang,
        '(content + experience + expertise + authority + trust) / 5，内容层同时吸收信息密度、证据引用、链接语义与分块结构',
        '(content + experience + expertise + authority + trust) / 5, with information density, evidence, linking, and chunk structure folded into the content layer'
      ),
      detail: result => {
        const findings = result?.content?.findings || {};
        const sampled = Number(result?.discovery?.profiled_page_count || Object.keys(result?.discovery?.page_profiles || {}).length || 0);
        return tx(
          lang,
          `snapshot 采样 ${sampled} 页 · FAQ ${findings.has_faq_any ? '有' : '无'} · 引用区 ${findings.has_reference_section_any ? '有' : '无'} · 链接语义 ${findings.average_link_context_score ?? 0}`,
          `Snapshot sampled ${sampled} pages · FAQ ${findings.has_faq_any ? 'yes' : 'no'} · References ${findings.has_reference_section_any ? 'yes' : 'no'} · Link context ${findings.average_link_context_score ?? 0}`
        );
      }
    },
    {
      key: 'Technical Foundations',
      defaultName: tx(lang, '技术基础', 'Technical Foundations'),
      weight: '15%',
      formula: tx(
        lang,
        'HTTPS / SSR / Meta / Canonical / unique H1 / Sitemap / 性能 / 安全头 / 图片 / 渲染阻塞 / freshness headers 等加权求和',
        'Weighted sum of HTTPS / SSR / meta / canonical / unique H1 / sitemap / performance / security headers / images / render blocking / freshness headers'
      ),
      detail: result => {
        const tech = result?.technical || {};
        return tx(
          lang,
          `响应 ${tech.findings?.response_time_ms ?? '-'}ms · 性能 ${tech.findings?.performance_classification || '-'} · H1 ${tech.checks?.h1_count ?? 0} · freshness ${tech.findings?.freshness_signal_score ?? 0}`,
          `Response ${tech.findings?.response_time_ms ?? '-'}ms · Performance ${tech.findings?.performance_classification || '-'} · H1 ${tech.checks?.h1_count ?? 0} · Freshness ${tech.findings?.freshness_signal_score ?? 0}`
        );
      }
    },
    {
      key: 'Structured Data',
      defaultName: tx(lang, '结构化数据', 'Structured Data'),
      weight: '10%',
      formula: tx(
        lang,
        'JSON-LD + Organization + WebSite + Service + Article + FAQ + Product + Breadcrumb + machine dates + sameAs + @id + visible-content alignment',
        'JSON-LD + Organization + WebSite + Service + Article + FAQ + Product + Breadcrumb + machine dates + sameAs + @id + visible-content alignment'
      ),
      detail: result => {
        const findings = result?.schema?.findings || {};
        const sampled = Number(result?.discovery?.profiled_page_count || Object.keys(result?.discovery?.page_profiles || {}).length || 0);
        return tx(
          lang,
          `Schema 类型 ${findings.schema_type_count ?? 0} 项 · sameAs ${findings.same_as_count ?? 0} 项 · 对齐 ${findings.visible_alignment_score ?? 0} · 复用 snapshot ${sampled} 页`,
          `Schema types ${findings.schema_type_count ?? 0} · sameAs ${findings.same_as_count ?? 0} · Alignment ${findings.visible_alignment_score ?? 0} · Reused snapshot pages ${sampled}`
        );
      }
    },
    {
      key: 'Platform Optimization',
      defaultName: tx(lang, '平台适配', 'Platform Optimization'),
      weight: '10%',
      formula: 'ChatGPT 22% + Google AI Mode 18% + AI Overviews 18% + Perplexity 16% + Gemini 13% + Grok 13%',
      detail: result => {
        const scores = Object.entries(result?.platform?.platform_scores || {});
        if (!scores.length) return tx(lang, '等待平台结果', 'Waiting for platform scores');
        scores.sort((a, b) => (a[1]?.platform_score || 0) - (b[1]?.platform_score || 0));
        const low = scores[0];
        const high = scores[scores.length - 1];
        return tx(
          lang,
          `最佳 ${PLATFORM_LABELS[high?.[0]] || high?.[0]} ${high?.[1]?.platform_score ?? 0} · 最弱 ${PLATFORM_LABELS[low?.[0]] || low?.[0]} ${low?.[1]?.platform_score ?? 0}`,
          `Best ${PLATFORM_LABELS[high?.[0]] || high?.[0]} ${high?.[1]?.platform_score ?? 0} · Weakest ${PLATFORM_LABELS[low?.[0]] || low?.[0]} ${low?.[1]?.platform_score ?? 0}`
        );
      }
    }
  ];
}

function formatDetailMap(detailMap, fallback) {
  const entries = Object.entries(detailMap || {}).filter(([, items]) => Array.isArray(items) && items.length);
  if (!entries.length) {
    return `<div class="detail-group"><div class="detail-group-item">${escapeHtml(fallback)}</div></div>`;
  }
  return entries.map(([category, items]) => `
    <div class="detail-group">
      <div class="detail-group-title">${escapeHtml(category)}</div>
      ${items.map((item, idx) => `<div class="detail-group-item">${idx + 1}. ${escapeHtml(item)}</div>`).join('')}
    </div>
  `).join('');
}

function normalizeActions(result, lang = 'zh') {
  const llmPlan = result?.summary?.llm_insights?.prioritized_action_plan;
  if (Array.isArray(llmPlan) && llmPlan.length) {
    return llmPlan.map(item => ({
      priority: (item.priority || 'medium').toLowerCase(),
      action: item.action || tx(lang, '待补充', 'TBD'),
      description: item.description || item.rationale || '',
      impact: item.expected_impact || 'High'
    }));
  }
  return (result?.summary?.prioritized_action_plan || []).map(item => ({
    priority: (item.priority || 'medium').toLowerCase(),
    action: item.action || tx(lang, '待补充', 'TBD'),
    description: item.rationale || tx(lang, `${item.module || '该模块'} 需要优先优化。`, `${item.module || 'This module'} needs priority optimization.`),
    impact: item.priority === 'high' ? 'High' : item.priority === 'low' ? 'Medium' : 'High'
  }));
}

function formatKeyPages(keyPages, lang = 'zh') {
  return Object.entries({
    About: keyPages?.about,
    Service: keyPages?.service,
    Contact: keyPages?.contact,
    Article: keyPages?.article,
    'Case Study': keyPages?.case_study
  }).map(([name, value]) => `
    <div class="kv-row">
      <span class="kv-key">${escapeHtml(name)}</span>
      <span class="kv-val">${value ? tx(lang, '已识别', 'Detected') : tx(lang, '缺失', 'Missing')}</span>
    </div>
  `).join('');
}

export function renderSiteAuditReport({ task, host, lang, setCachedReportHtml }) {
  const result = task?.result || {};
  const summary = result.summary || {};
  const discovery = result.discovery || {};
  const homepage = discovery.homepage || {};
  const visibility = result.visibility || {};
  const technical = result.technical || {};
  const content = result.content || {};
  const schema = result.schema || {};
  const platform = result.platform || {};
  const labels = {
    noSummary: tx(lang, '暂无摘要。', 'No summary available.'),
    noPageSamples: tx(lang, '暂无可展示的页面采样。', 'No sampled pages available.'),
    contribution: tx(lang, '综合贡献', 'Weighted contribution'),
    rawWeight: tx(lang, '原始权重', 'Weight'),
    formula: tx(lang, '公式', 'Formula'),
    currentSignals: tx(lang, '当前信号', 'Current signals'),
    noPlatformData: tx(lang, '暂无平台数据。', 'No platform data available.'),
    noMetricDefinitions: tx(lang, '暂无指标说明。', 'No metric definitions available.'),
    observationStatus: tx(lang, 'Observation 状态', 'Observation Status'),
    observationSummaryTitle: tx(lang, 'Observation 摘要', 'Observation Summary'),
    provided: tx(lang, '已提供', 'Provided'),
    notProvided: tx(lang, '未提供', 'Not provided'),
    scored: tx(lang, '是', 'Yes'),
    unscored: tx(lang, '否', 'No'),
    maturity: tx(lang, '成熟度', 'Maturity'),
    note: tx(lang, '说明', 'Note'),
    observationNote: tx(lang, 'Observation 仅做展示，不改写综合分', 'Observation is shown for context only and never changes the composite score'),
    noObservationSummary: tx(lang, '未上传 observation 数据，系统仅基于 URL 做 readiness 评分。', 'No observation data was uploaded. Readiness is scored from the URL alone.'),
    noHighlights: tx(lang, '暂无 highlights。', 'No highlights available.'),
    noDataGaps: tx(lang, '暂无数据缺口。', 'No data gaps available.'),
    noNotices: tx(lang, '暂无提示。', 'No notices.'),
    fullAuditMissing: tx(lang, '当前未启用 full audit，未返回逐页诊断。', 'Full audit is not enabled, so no page diagnostics were returned.'),
    noActionPlan: tx(lang, '暂无行动计划。', 'No action plan available.'),
    reportBasis: tx(lang, '报告口径', 'Report basis'),
    compositeGeoScore: 'Composite GEO Score',
    premiumBadge: tx(lang, '会员版 / AI 增强', 'Premium / AI Enriched'),
    standardBadge: tx(lang, '普通版 / 规则版', 'Standard / Rule-based'),
    enhanced: tx(lang, '报告已增强', 'Report Enhanced'),
    ruleSummary: tx(lang, '规则汇总', 'Rule Summary'),
    siteGeoReport: tx(lang, '站点 GEO 报告', 'Site GEO Report'),
    responsePrefix: tx(lang, '响应', 'Response'),
    snapshotLabel: 'Snapshot',
    scopeRootLabel: 'Scope Root',
    aiCrawlLlms: tx(lang, 'AI 抓取 / llms', 'AI Crawl / llms'),
    citationProbability: tx(lang, '引用概率', 'Citation Probability'),
    bestWeakestPlatform: tx(lang, '最佳 / 最弱平台', 'Best / Weakest Platform'),
    observationLabel: 'Observation',
    inputScope: 'Input Scope',
    fullAudit: 'Full Audit',
    aiPerceptionTitle: tx(lang, 'AI 认知快照', 'AI Perception Snapshot'),
    aiPerceptionSubtitle: tx(lang, '根据站点信号估算 AI 对该站点的认知倾向，不参与评分', 'Estimated AI-side perception based on site signals. This does not affect scoring.'),
    positiveLabel: tx(lang, '正面', 'Positive'),
    neutralLabel: tx(lang, '中性', 'Neutral'),
    controversialLabel: tx(lang, '争议', 'Controversial'),
    cognitionKeywordsLabel: tx(lang, '认知标签', 'Perception Keywords'),
    scoredDimensionsTitle: tx(lang, '6 个汇总维度评估', '6 Scored Dimensions'),
    scoredDimensionsSubtitle: tx(lang, '原始分满分 100，按权重折算进入综合分', 'Raw scores are out of 100 and are weighted into the composite score'),
    keyIssuesTitle: tx(lang, '关键问题', 'Key Issues'),
    keyIssuesSubtitle: tx(lang, '优先处理最拖分的约束项', 'Prioritize the constraints hurting the score most'),
    quickWinsTitle: tx(lang, '快速收益项', 'Quick Wins'),
    quickWinsSubtitle: tx(lang, '优先处理投入低、收益快的动作', 'Prioritize low-effort, fast-return actions'),
    actionPlanTitle: tx(lang, '优先行动计划', 'Prioritized Action Plan'),
    actionPlanSubtitle: tx(lang, '结合规则结果与 AI 增强建议生成', 'Generated from rule-based outputs and AI enrichment'),
    platformOverviewTitle: tx(lang, '平台适配概览', 'Platform Readiness Overview'),
    platformOverviewSubtitle: tx(lang, '展示 6 个目标平台的 readiness、优化焦点、主缺口与首要建议', 'Shows readiness, optimization focus, primary gap, and top recommendation across 6 platforms'),
    metricsTitle: tx(lang, '指标说明', 'Metric Definitions'),
    metricsSubtitle: tx(lang, '区分计分维度与 Observation Layer', 'Separates scored dimensions from the Observation Layer'),
    observationTitle: 'Observation Layer',
    observationSubtitle: tx(lang, '可选上传的外部观测数据，仅展示，不计分', 'Optional uploaded observation data, displayed only and not scored'),
    pageDiagnosticsTitle: 'Page Diagnostics',
    pageDiagnosticsSubtitle: tx(lang, '仅 full audit 模式返回，逐页展示可引用性与结构质量', 'Returned only in full audit mode, with page-level extraction and structure diagnostics'),
    snapshotTitle: tx(lang, 'Snapshot 与原始发现', 'Snapshot and Raw Findings'),
    snapshotSubtitle: tx(lang, '基于 discovery snapshot 与各模块 checks / findings 的事实层展示', 'Fact-layer view based on the discovery snapshot and module checks/findings'),
    notesTitle: tx(lang, '说明与备注', 'Notes and Context'),
    notesSubtitle: tx(lang, '发现层版本、处理注释与模式说明', 'Discovery version, processing notes, and mode context'),
    impact: tx(lang, '预计影响', 'Expected impact'),
    pageWordCountSuffix: tx(lang, '词', 'words'),
    pageFaqYes: tx(lang, '有', 'Yes'),
    pageFaqNo: tx(lang, '无', 'No'),
    pageDetailEmpty: tx(lang, '暂无明细', 'No details'),
    unavailable: tx(lang, '暂无', 'N/A'),
    missingGap: tx(lang, '暂无缺口描述', 'No gap description'),
    preferredSourcesFallback: tx(lang, '暂无偏好信源', 'No preferred sources'),
    recommendationFallback: tx(lang, '暂无建议', 'No recommendation'),
    observationProvidedLine: observation => observation.provided
      ? tx(lang, `已提供 · ${observation.measurement_maturity || 'basic'}`, `Provided · ${observation.measurement_maturity || 'basic'}`)
      : tx(lang, '未提供 · 不计分', 'Not provided · Unscored')
  };
  const executive = summary?.llm_insights?.executive_summary || summary.summary || labels.noSummary;
  const topIssues = summary?.llm_insights?.top_issues || summary.top_issues || [];
  const quickWins = summary?.llm_insights?.quick_wins || summary.quick_wins || [];
  const actions = normalizeActions(result, lang).slice(0, 5);
  const weighted = summary.weighted_scores || {};
  const aiPerception = summary.ai_perception || {};
  const platformScores = platform.platform_scores || {};
  const observation = result.observation || summary.observation || {};
  const metricDefinitions = summary.metric_definitions || [];
  const notices = summary.notices || [];
  const pageDiagnostics = Array.isArray(result.page_diagnostics) ? result.page_diagnostics : [];
  const citability = visibility.findings?.citability || {};
  const homepageCitability = citability.homepage_citability || {};
  const bestPageCitability = citability.best_page_citability || {};
  const citationProbability = citability.citation_probability || 'LOW';
  const citationLabelMap = lang === 'zh'
    ? { LOW: '低', MEDIUM: '中', HIGH: '高' }
    : { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High' };
  const pageProfiles = Object.entries(discovery.page_profiles || {});
  const additionalProfiles = Array.isArray(discovery.additional_page_profiles) ? discovery.additional_page_profiles : [];
  const fallbackPages = Object.values(content.page_analyses || {});
  const dimensionMeta = getDimensionMeta(lang);
  const pageSamples = pageProfiles.length
    ? [
        ...pageProfiles.map(([key, page]) => ({ key, source: 'core', ...page })),
        ...additionalProfiles.map((page, index) => ({ key: `additional_${index + 1}`, source: 'extended', ...page }))
      ]
    : fallbackPages;
  const pageSampleHtml = pageSamples.length
    ? pageSamples.slice(0, 5).map(page => {
        const schemaTypes = Array.isArray(page.json_ld_summary?.types) ? page.json_ld_summary.types.length : 0;
        return `
          <div class="page-sample">
            <div class="top">
              <span class="name">${escapeHtml(page.page_type || page.key || 'page')}</span>
              <span class="name">${escapeHtml(String(page.word_count || 0))} ${escapeHtml(labels.pageWordCountSuffix)}</span>
            </div>
            <div class="meta">${escapeHtml(tx(lang, '标题质量', 'Heading quality'))} ${escapeHtml(String(page.heading_quality_score || 0))} · ${escapeHtml(tx(lang, '信息密度', 'Information density'))} ${escapeHtml(String(page.information_density_score || 0))} · ${escapeHtml(tx(lang, '分块结构', 'Chunk structure'))} ${escapeHtml(String(page.chunk_structure_score || 0))}</div>
            <div class="meta">FAQ ${page.has_faq ? labels.pageFaqYes : labels.pageFaqNo} · ${escapeHtml(tx(lang, '作者', 'Author'))} ${page.has_author ? labels.pageFaqYes : labels.pageFaqNo} · ${escapeHtml(tx(lang, '日期', 'Date'))} ${page.has_publish_date ? labels.pageFaqYes : labels.pageFaqNo} · answer-first ${page.answer_first ? labels.pageFaqYes : labels.pageFaqNo} · Schema ${schemaTypes}</div>
          </div>
        `;
      }).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noPageSamples)}</div>`;

  const dimensionHtml = dimensionMeta.map(meta => {
    const item = weighted[meta.key] || {};
    const rawScore = Number(item.raw_score ?? 0);
    const status = scoreToStatus(rawScore);
    const displayName = summary.dimensions?.[meta.key]?.display_name || meta.defaultName;
    return `
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(displayName)}</span>
          <span class="report-dim-pill">${escapeHtml(meta.weight)}</span>
        </div>
        <div class="report-dim-scoreline">
          <span class="score">${escapeHtml(String(rawScore))}</span>
          <span class="status">${escapeHtml(formatStatus(status, lang))}</span>
        </div>
        <div class="report-dim-kpis">
          <div class="report-dim-kpi">
            <div class="lbl">${escapeHtml(labels.contribution)}</div>
            <div class="val">${escapeHtml(String(item.weighted_value ?? 0))}</div>
          </div>
          <div class="report-dim-kpi">
            <div class="lbl">${escapeHtml(labels.rawWeight)}</div>
            <div class="val">${escapeHtml(meta.weight)}</div>
          </div>
        </div>
        <div class="report-dim-note"><strong>${escapeHtml(labels.formula)}:</strong> ${escapeHtml(meta.formula)}</div>
        <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(labels.currentSignals)}:</strong> ${escapeHtml(meta.detail(result))}</div>
      </div>
    `;
  }).join('');

  const platformHtml = Object.entries(platformScores).map(([key, item]) => `
    <div class="platform-card">
      <div class="hd">
        <span class="name">${escapeHtml(PLATFORM_LABELS[key] || key)}</span>
        <span class="score">${escapeHtml(String(item.platform_score ?? 0))}</span>
      </div>
      <div class="gap"><strong>${escapeHtml(tx(lang, '优化焦点', 'Optimization Focus'))}:</strong> ${escapeHtml(item.optimization_focus || labels.unavailable)}</div>
      <div class="gap">${escapeHtml(item.primary_gap || labels.missingGap)}</div>
      <div class="reco">${escapeHtml((item.preferred_sources || []).join(' / ') || labels.preferredSourcesFallback)}</div>
      <div class="reco">${escapeHtml((item.key_recommendations || [])[0] || labels.recommendationFallback)}</div>
    </div>
  `).join('');

  const metricHtml = metricDefinitions.length
    ? metricDefinitions.map(item => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(item.name || '-')}</span>
            <span class="report-dim-pill">${escapeHtml(item.scoring === 'unscored' ? tx(lang, '不计分', 'Unscored') : tx(lang, '计分', 'Scored'))}</span>
          </div>
          <div class="report-dim-note"><strong>${escapeHtml(labels.formula)}:</strong> ${escapeHtml(item.formula || '-')}</div>
          <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(tx(lang, '数据来源', 'Data Source'))}:</strong> ${escapeHtml(item.data_source || '-')}</div>
          <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(tx(lang, '业务意义', 'Why It Matters'))}:</strong> ${escapeHtml(item.why_it_matters || '-')}</div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noMetricDefinitions)}</div>`;

  const observationBreakdown = Array.isArray(observation.platform_breakdown) ? observation.platform_breakdown : [];
  const observationHighlights = Array.isArray(observation.highlights) ? observation.highlights : [];
  const observationGaps = Array.isArray(observation.data_gaps) ? observation.data_gaps : [];
  const observationHtml = `
    <div class="report-grid-2">
      <div class="evidence-card">
        <h5>${escapeHtml(labels.observationStatus)}</h5>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '是否提供', 'Provided'))}</span><span class="kv-val">${observation.provided ? labels.provided : labels.notProvided}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '是否计分', 'Scored'))}</span><span class="kv-val">${observation.scored ? labels.scored : labels.unscored}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.maturity)}</span><span class="kv-val">${escapeHtml(observation.measurement_maturity || 'none')}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.note)}</span><span class="kv-val">${escapeHtml(labels.observationNote)}</span></div>
        </div>
      </div>
      <div class="evidence-card">
        <h5>${escapeHtml(labels.observationSummaryTitle)}</h5>
        <div class="report-note-box">${escapeHtml(observation.summary || labels.noObservationSummary)}</div>
      </div>
    </div>
    ${observationHighlights.length ? `<div class="report-list" style="margin-top:12px">${formatList(observationHighlights, labels.noHighlights)}</div>` : ''}
    ${observationBreakdown.length ? `
      <div class="report-note-box" style="margin-top:12px">
        ${observationBreakdown.map(item => `${escapeHtml(item.platform)}: ${escapeHtml(String(item.sessions ?? '-'))} sessions / ${escapeHtml(String(item.conversions ?? '-'))} conversions / CR ${escapeHtml(String(item.conversion_rate ?? '-'))}`).join('<br />')}
      </div>
    ` : ''}
    ${observationGaps.length ? `<div class="report-list" style="margin-top:12px">${formatList(observationGaps, labels.noDataGaps)}</div>` : ''}
  `;

  const aiPerceptionHtml = `
    <div class="report-grid-2">
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.positiveLabel)}</span>
          <span class="report-dim-pill">%</span>
        </div>
        <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(aiPerception.positive_percentage ?? 0))}</span></div>
      </div>
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.neutralLabel)}</span>
          <span class="report-dim-pill">%</span>
        </div>
        <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(aiPerception.neutral_percentage ?? 0))}</span></div>
      </div>
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.controversialLabel)}</span>
          <span class="report-dim-pill">%</span>
        </div>
        <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(aiPerception.controversial_percentage ?? 0))}</span></div>
      </div>
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.cognitionKeywordsLabel)}</span>
          <span class="report-dim-pill">${escapeHtml(String((aiPerception.cognition_keywords || []).length || 0))}</span>
        </div>
        <div class="report-list">${formatList(aiPerception.cognition_keywords || [], tx(lang, '暂无认知标签。', 'No perception keywords.'))}</div>
      </div>
    </div>
  `;

  const noticesHtml = notices.length
    ? `<div class="report-list" style="margin-top:14px">${formatList(notices, labels.noNotices, 8)}</div>`
    : '';

  const pageDiagnosticsHtml = pageDiagnostics.length
    ? `<div class="report-list">${pageDiagnostics.slice(0, 12).map((item, index) => `
        <div class="page-diagnostic-card">
          <div class="page-diagnostic-head">
            <div style="min-width:0; flex:1;">
              <div class="page-diagnostic-title">
                <strong>${index + 1}. ${escapeHtml(item.page_type || 'page')}</strong>
                <span class="page-diagnostic-badge">${escapeHtml(item.source || 'core')}</span>
                <span class="page-diagnostic-badge score">${escapeHtml(tx(lang, '总分', 'Overall'))} ${escapeHtml(String(item.overall_score ?? 0))}</span>
                <span class="page-diagnostic-badge">${escapeHtml(tx(lang, '问题数', 'Issue count'))} ${escapeHtml(String(item.issue_count ?? ((item.issues || []).length || 0)))}</span>
              </div>
              <div class="page-diagnostic-url-label">${escapeHtml(tx(lang, '页面 URL', 'Page URL'))}</div>
              <div class="page-diagnostic-url">${escapeHtml(item.url || '-')}</div>
            </div>
            <div class="page-diagnostic-metrics">
              <div class="page-diagnostic-metric"><span class="label">Citability</span><span class="value">${escapeHtml(String(item.citability_score ?? 0))}</span></div>
              <div class="page-diagnostic-metric"><span class="label">Content</span><span class="value">${escapeHtml(String(item.content_score ?? 0))}</span></div>
              <div class="page-diagnostic-metric"><span class="label">Technical</span><span class="value">${escapeHtml(String(item.technical_score ?? 0))}</span></div>
              <div class="page-diagnostic-metric"><span class="label">Schema</span><span class="value">${escapeHtml(String(item.schema_score ?? 0))}</span></div>
              <div class="page-diagnostic-metric"><span class="label">${escapeHtml(tx(lang, '状态', 'Status'))}</span><span class="value">${escapeHtml(formatStatus(item.status, lang))}</span></div>
            </div>
          </div>
          <div class="page-diagnostic-panels">
            <div class="page-diagnostic-panel">
              <h6>${escapeHtml(tx(lang, '问题清单', 'Issue List'))}</h6>
              ${formatDetailMap(item.issue_details, labels.pageDetailEmpty)}
            </div>
            <div class="page-diagnostic-panel">
              <h6>${escapeHtml(tx(lang, '修复建议', 'Recommendations'))}</h6>
              ${formatDetailMap(item.recommendation_details, labels.pageDetailEmpty)}
            </div>
          </div>
        </div>
      `).join('')}</div>`
    : `<div class="report-list-item">${escapeHtml(labels.fullAuditMissing)}</div>`;

  const actionHtml = actions.length
    ? actions.map(item => `
        <div class="report-action">
          <div class="report-action-priority ${escapeHtml(item.priority)}">${escapeHtml(formatStatus(item.priority, lang))}</div>
          <div class="report-action-main">
            <h5>${escapeHtml(item.action)}</h5>
            <p>${escapeHtml(item.description || tx(lang, '暂无说明', 'No description'))}</p>
          </div>
          <div class="report-action-impact">
            <div class="report-action-impact-label">${escapeHtml(labels.impact)}</div>
            <span>${escapeHtml(item.impact || 'High')}</span>
          </div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noActionPlan)}</div>`;

  const strongestPlatform = Object.entries(platformScores).sort((a, b) => (b[1]?.platform_score || 0) - (a[1]?.platform_score || 0))[0];
  const weakestPlatform = Object.entries(platformScores).sort((a, b) => (a[1]?.platform_score || 0) - (b[1]?.platform_score || 0))[0];
  const noteText = [
    discovery.site_snapshot_version ? tx(lang, `发现层版本：${discovery.site_snapshot_version}，当前 audit_full 支持复用传入 discovery，避免重复抓取。`, `Discovery version: ${discovery.site_snapshot_version}. Current audit_full can reuse a supplied discovery payload to avoid duplicate crawling.`) : '',
    discovery.scope_root_url ? tx(lang, `抓取作用域：${discovery.scope_root_url}`, `Crawl scope: ${discovery.scope_root_url}`) : '',
    discovery.input_scope_warning ? tx(lang, `输入范围提示：${discovery.input_scope_warning}`, `Input scope note: ${discovery.input_scope_warning}`) : '',
    discovery.full_audit_enabled ? tx(lang, `full audit：已启用，累计建模 ${discovery.profiled_page_count || 0} 页，requested max_pages=${discovery.requested_max_pages || 12}。`, `Full audit enabled: profiled ${discovery.profiled_page_count || 0} pages, requested max_pages=${discovery.requested_max_pages || 12}.`) : tx(lang, 'full audit：未启用，默认只输出站点级结果。', 'Full audit disabled: only site-level results are returned by default.'),
    tx(lang, '品牌权威当前仍通过 visibility 输出，但代码层已预留 BrandAuthorityService 边界，便于后续独立服务化。', 'Brand authority is still emitted from visibility for now, but a BrandAuthorityService boundary is reserved for future service separation.'),
    summary.summary ? tx(lang, `报告摘要：${summary.summary}`, `Report summary: ${summary.summary}`) : '',
    summary.score_interpretation?.length ? tx(lang, `评分说明：${summary.score_interpretation.join(' | ')}`, `Score interpretation: ${summary.score_interpretation.join(' | ')}`) : '',
    summary.processing_notes?.length ? tx(lang, `汇总注释：${summary.processing_notes.join(' | ')}`, `Summary notes: ${summary.processing_notes.join(' | ')}`) : '',
    technical.processing_notes?.length ? tx(lang, `技术模块：${technical.processing_notes.join(' | ')}`, `Technical module: ${technical.processing_notes.join(' | ')}`) : '',
    schema.processing_notes?.length ? tx(lang, `结构化数据模块：${schema.processing_notes.join(' | ')}`, `Structured data module: ${schema.processing_notes.join(' | ')}`) : ''
  ].filter(Boolean).join('\n\n') || tx(lang, '当前无额外备注。', 'No extra notes.');

  host.className = 'report-shell';
  const html = `
    <section class="report-hero">
      <div class="report-score-box">
        <div>
          <div class="report-score-label">${escapeHtml(labels.compositeGeoScore)}</div>
          <div class="report-score-value">${escapeHtml(String(summary.composite_geo_score ?? 0))}</div>
          <div class="report-score-sub">${escapeHtml(formatStatus(summary.status, lang))} · ${escapeHtml(labels.reportBasis)}</div>
        </div>
        <div class="report-badges">
          <span class="r-badge ${escapeHtml(statusTone(summary.status))}">${escapeHtml(formatStatus(summary.status, lang))}</span>
          <span class="r-badge">${task.mode === 'premium' ? labels.premiumBadge : labels.standardBadge}</span>
          <span class="r-badge ${summary.llm_enhanced ? 'success' : ''}">${summary.llm_enhanced ? labels.enhanced : labels.ruleSummary}</span>
          <span class="r-badge">${escapeHtml(summary.scoring_version || 'geo-audit-v3')}</span>
        </div>
      </div>
      <div class="report-hero-main">
        <div class="report-kicker">
          <span>${escapeHtml(discovery.domain || discovery.normalized_url || task.url || '-')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(discovery.business_type || 'unknown')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(labels.responsePrefix)} ${escapeHtml(String(discovery.fetch?.response_time_ms ?? '-'))} ms</span>
        </div>
        <h3>${escapeHtml(labels.siteGeoReport)}</h3>
        <div class="report-summary">${escapeHtml(executive)}</div>
        <div class="report-meta-grid">
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.snapshotLabel)}</div>
            <div class="val">${escapeHtml(discovery.site_snapshot_version || 'snapshot-v1')} · ${escapeHtml(String(discovery.profiled_page_count || pageSamples.length || 1))} ${escapeHtml(tx(lang, '页画像', 'page profiles'))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.scopeRootLabel)}</div>
            <div class="val">${escapeHtml(discovery.scope_root_url || discovery.site_root_url || '-')}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.aiCrawlLlms)}</div>
            <div class="val">${escapeHtml(String(visibility.checks?.allowed_ai_crawlers ?? 0))} / ${escapeHtml(String(visibility.checks?.total_ai_crawlers_checked ?? 0))} ${escapeHtml(tx(lang, '放行', 'allowed'))} · llms ${escapeHtml(String(visibility.findings?.llms_quality?.score ?? 0))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.citationProbability)}</div>
            <div class="val">${escapeHtml(citationLabelMap[citationProbability] || citationProbability)} · ${escapeHtml(tx(lang, '首页', 'Homepage'))} ${escapeHtml(String(homepageCitability.score ?? 0))} / ${escapeHtml(tx(lang, '最佳页', 'Best page'))} ${escapeHtml(String(bestPageCitability.score ?? 0))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.bestWeakestPlatform)}</div>
            <div class="val">${escapeHtml(PLATFORM_LABELS[strongestPlatform?.[0]] || '-')} ${escapeHtml(String(strongestPlatform?.[1]?.platform_score ?? '-'))} / ${escapeHtml(PLATFORM_LABELS[weakestPlatform?.[0]] || '-')} ${escapeHtml(String(weakestPlatform?.[1]?.platform_score ?? '-'))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.observationLabel)}</div>
            <div class="val">${escapeHtml(labels.observationProvidedLine(observation))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.inputScope)}</div>
            <div class="val">${discovery.input_is_likely_homepage === false ? escapeHtml(tx(lang, '非首页输入 · 结果可能偏差', 'Non-homepage input · results may be biased')) : escapeHtml(tx(lang, '首页 / 语言首页输入', 'Homepage / locale-homepage input'))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.fullAudit)}</div>
            <div class="val">${discovery.full_audit_enabled ? `${escapeHtml(tx(lang, '已启用', 'Enabled'))} · ${escapeHtml(String(discovery.profiled_page_count || 0))} ${escapeHtml(tx(lang, '页', 'pages'))}` : escapeHtml(tx(lang, '未启用', 'Disabled'))}</div>
          </div>
        </div>
        ${noticesHtml}
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr">
        <h4>${escapeHtml(labels.scoredDimensionsTitle)}</h4>
        <span>${escapeHtml(labels.scoredDimensionsSubtitle)}</span>
      </div>
      <div class="report-section-body">
        <div class="report-dim-grid">${dimensionHtml}</div>
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr">
        <h4>${escapeHtml(labels.aiPerceptionTitle)}</h4>
        <span>${escapeHtml(labels.aiPerceptionSubtitle)}</span>
      </div>
      <div class="report-section-body">${aiPerceptionHtml}</div>
    </section>

    <div class="report-grid-2">
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(labels.keyIssuesTitle)}</h4><span>${escapeHtml(labels.keyIssuesSubtitle)}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(topIssues, tx(lang, '暂无关键问题。', 'No key issues.'))}</div></div>
      </section>
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(labels.quickWinsTitle)}</h4><span>${escapeHtml(labels.quickWinsSubtitle)}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(quickWins, tx(lang, '暂无快速收益建议。', 'No quick wins available.'))}</div></div>
      </section>
    </div>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.actionPlanTitle)}</h4><span>${escapeHtml(labels.actionPlanSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-action-list">${actionHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.platformOverviewTitle)}</h4><span>${escapeHtml(labels.platformOverviewSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-platform-grid">${platformHtml || `<div class="report-list-item">${escapeHtml(labels.noPlatformData)}</div>`}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.metricsTitle)}</h4><span>${escapeHtml(labels.metricsSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${metricHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.observationTitle)}</h4><span>${escapeHtml(labels.observationSubtitle)}</span></div>
      <div class="report-section-body">${observationHtml}</div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.pageDiagnosticsTitle)}</h4><span>${escapeHtml(labels.pageDiagnosticsSubtitle)}</span></div>
      <div class="report-section-body">${pageDiagnosticsHtml}</div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.snapshotTitle)}</h4><span>${escapeHtml(labels.snapshotSubtitle)}</span></div>
      <div class="report-section-body">
        <div class="report-evidence-grid">
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '站点概况', 'Site Overview'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '规范化 URL', 'Normalized URL'))}</span><span class="kv-val">${escapeHtml(discovery.normalized_url || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页标题', 'Homepage Title'))}</span><span class="kv-val">${escapeHtml(homepage.title || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页 H1', 'Homepage H1'))}</span><span class="kv-val">${escapeHtml(homepage.h1 || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '字数 / 标题数', 'Words / Headings'))}</span><span class="kv-val">${escapeHtml(String(homepage.word_count ?? 0))} / ${escapeHtml(String((homepage.headings || []).length))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '语言 / hreflang', 'Language / hreflang'))}</span><span class="kv-val">${escapeHtml(homepage.lang || '-')} / ${escapeHtml(String((homepage.hreflang || []).length))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '发现层快照', 'Discovery Snapshot'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, 'snapshot 版本', 'Snapshot version'))}</span><span class="kv-val">${escapeHtml(discovery.site_snapshot_version || 'snapshot-v1')}</span></div><div class="kv-row"><span class="kv-key">scope root</span><span class="kv-val">${escapeHtml(discovery.scope_root_url || discovery.site_root_url || '-')}</span></div><div class="kv-row"><span class="kv-key">profiled pages</span><span class="kv-val">${escapeHtml(String(discovery.profiled_page_count || pageSamples.length || 1))} ${escapeHtml(tx(lang, '页', 'pages'))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '关键页面识别', 'Key pages identified'))}</span><span class="kv-val">${escapeHtml(String(Object.values(discovery.key_pages || {}).filter(Boolean).length))} ${escapeHtml(tx(lang, '页', 'pages'))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页引用得分', 'Homepage citability'))}</span><span class="kv-val">${escapeHtml(String(homepageCitability.score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '最佳引用页', 'Best citation page'))}</span><span class="kv-val">${escapeHtml(bestPageCitability.page_key || 'homepage')} / ${escapeHtml(String(bestPageCitability.score ?? 0))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '抓取与实体信号', 'Crawl and Entity Signals'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">robots.txt</span><span class="kv-val">${formatBool(discovery.robots?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))}</span></div><div class="kv-row"><span class="kv-key">llms.txt / ${escapeHtml(tx(lang, '有效性', 'Quality'))}</span><span class="kv-val">${formatBool(discovery.llms?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))} / ${escapeHtml(String(visibility.findings?.llms_quality?.score ?? discovery.llms?.effectiveness_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">Sitemap / Semrush AS</span><span class="kv-val">${formatBool(discovery.sitemap?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))} / ${escapeHtml(String(discovery.backlinks?.authority_score ?? tx(lang, '未接入', 'Unavailable')))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '公司名 / 电话', 'Company / Phone'))}</span><span class="kv-val">${formatBool(discovery.site_signals?.company_name_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.phone_detected, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '地址 / 邮箱 / sameAs', 'Address / Email / sameAs'))}</span><span class="kv-val">${formatBool(discovery.site_signals?.address_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.email_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.same_as_detected, labels.pageFaqYes, labels.pageFaqNo)}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '技术与结构化快照', 'Technical and Structured Snapshot'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '安全头得分', 'Security headers score'))}</span><span class="kv-val">${escapeHtml(String(technical.findings?.security_headers_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">SSR / ${escapeHtml(tx(lang, '性能', 'Performance'))}</span><span class="kv-val">${escapeHtml(technical.findings?.ssr_classification || '-')} / ${escapeHtml(technical.findings?.performance_classification || technical.checks?.performance?.classification || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '唯一 H1 / freshness', 'Unique H1 / freshness'))}</span><span class="kv-val">${formatBool(technical.checks?.unique_h1, labels.pageFaqYes, labels.pageFaqNo)} / ${escapeHtml(String(technical.findings?.freshness_signal_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">ETag / Last-Modified</span><span class="kv-val">${formatBool(technical.checks?.revalidation_headers?.etag, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(technical.checks?.revalidation_headers?.last_modified, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '图片 lazyload / 尺寸', 'Image lazyload / dimensions'))}</span><span class="kv-val">${escapeHtml(String(technical.checks?.image_optimization?.lazyload_ratio ?? 0))} / ${escapeHtml(String(technical.checks?.image_optimization?.dimension_ratio ?? 0))}</span></div><div class="kv-row"><span class="kv-key">Schema / sameAs / ${escapeHtml(tx(lang, '对齐', 'Alignment'))}</span><span class="kv-val">${escapeHtml(String(schema.findings?.schema_type_count ?? 0))} / ${escapeHtml(String(schema.findings?.same_as_count ?? 0))} / ${escapeHtml(String(schema.findings?.visible_alignment_score ?? 0))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '证据与链接上下文', 'Evidence and Link Context'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '参考资料区', 'References section'))}</span><span class="kv-val">${formatBool(content.findings?.has_reference_section_any, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '内联引用', 'Inline citations'))}</span><span class="kv-val">${formatBool(content.findings?.has_inline_citations_any, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">TL;DR / ${escapeHtml(tx(lang, '更新记录', 'Update log'))}</span><span class="kv-val">${formatBool(content.findings?.has_tldr_any, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(content.findings?.has_update_log_any, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '链接语义得分', 'Link context score'))}</span><span class="kv-val">${escapeHtml(String(content.findings?.average_link_context_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '机器日期', 'Machine dates'))}</span><span class="kv-val">${formatBool(schema.checks?.has_date_published, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(schema.checks?.has_date_modified, labels.pageFaqYes, labels.pageFaqNo)}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '引用与平台证据', 'Citation and Platform Evidence'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(labels.citationProbability)}</span><span class="kv-val">${escapeHtml(citationLabelMap[citationProbability] || citationProbability)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '最佳页类型', 'Best page type'))}</span><span class="kv-val">${escapeHtml(bestPageCitability.page_type || bestPageCitability.page_key || 'homepage')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(labels.bestWeakestPlatform)}</span><span class="kv-val">${escapeHtml(PLATFORM_LABELS[strongestPlatform?.[0]] || '-')} / ${escapeHtml(PLATFORM_LABELS[weakestPlatform?.[0]] || '-')}</span></div><div class="kv-row"><span class="kv-key">Observation</span><span class="kv-val">${observation.provided ? tx(lang, '已上传，不计分', 'Uploaded, unscored') : tx(lang, '未上传', 'Not uploaded')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '输入范围', 'Input Scope'))}</span><span class="kv-val">${discovery.input_is_likely_homepage === false ? tx(lang, '非首页，可能偏差', 'Non-homepage, may be biased') : tx(lang, '首页/语言首页', 'Homepage/locale homepage')}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '关键页面与内容采样', 'Key Pages and Content Samples'))}</h5><div class="kv-list" style="margin-bottom:10px">${formatKeyPages(discovery.key_pages || {}, lang)}</div><div class="page-samples">${pageSampleHtml}</div></div>
        </div>
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.notesTitle)}</h4><span>${escapeHtml(labels.notesSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-note-box">${escapeHtml(noteText)}</div></div>
    </section>
  `;
  host.innerHTML = html;
  setCachedReportHtml(task, lang, html);
}
