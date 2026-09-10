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

function polarPoint(cx, cy, radius, angleDeg) {
  const rad = (Math.PI / 180) * angleDeg;
  return {
    x: cx + radius * Math.cos(rad),
    y: cy + radius * Math.sin(rad)
  };
}

function buildRadarChartHtml({ dimensionMeta, weighted, summary, lang = 'zh' }) {
  const size = 252;
  const cx = size / 2;
  const cy = size / 2;
  const maxRadius = 72;
  const baseAngle = -90;
  const labelRadius = maxRadius + 29;
  const levels = 5;
  const labelMap = lang === 'zh'
    ? {
        'AI Citability & Visibility': '可见',
        'Brand Authority Signals': '权威',
        'Content Quality & E-E-A-T': '内容',
        'Technical Foundations': '技术',
        'Structured Data': '结构',
        'Platform Optimization': '平台'
      }
    : {
        'AI Citability & Visibility': 'Cite',
        'Brand Authority Signals': 'Auth',
        'Content Quality & E-E-A-T': 'E-E-A-T',
        'Technical Foundations': 'Tech',
        'Structured Data': 'Schema',
        'Platform Optimization': 'Platform'
      };

  const axes = dimensionMeta.map((meta, index) => {
    const score = Math.max(0, Math.min(100, Number(weighted?.[meta.key]?.raw_score ?? 0)));
    const angle = baseAngle + index * (360 / dimensionMeta.length);
    const outer = polarPoint(cx, cy, maxRadius, angle);
    const value = polarPoint(cx, cy, (maxRadius * score) / 100, angle);
    const label = polarPoint(cx, cy, labelRadius, angle);
    const displayName = summary?.dimensions?.[meta.key]?.display_name || meta.defaultName;
    return {
      key: meta.key,
      displayName,
      shortLabel: labelMap[meta.key] || displayName.slice(0, 8),
      score,
      outer,
      value,
      label
    };
  });

  const gridPolygons = Array.from({ length: levels }, (_, i) => {
    const ratio = (i + 1) / levels;
    const points = axes.map((_, axisIndex) => {
      const p = polarPoint(cx, cy, maxRadius * ratio, baseAngle + axisIndex * (360 / axes.length));
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }).join(' ');
    return `<polygon points="${points}" class="report-radar-grid" />`;
  }).join('');

  const axisLines = axes.map(axis => `
    <line x1="${cx}" y1="${cy}" x2="${axis.outer.x.toFixed(1)}" y2="${axis.outer.y.toFixed(1)}" class="report-radar-axis" />
  `).join('');

  const valuePoints = axes.map(axis => `${axis.value.x.toFixed(1)},${axis.value.y.toFixed(1)}`).join(' ');

  const valueDots = axes.map(axis => `
    <circle cx="${axis.value.x.toFixed(1)}" cy="${axis.value.y.toFixed(1)}" r="2.8" class="report-radar-dot">
      <title>${escapeHtml(axis.displayName)}: ${escapeHtml(String(axis.score))}</title>
    </circle>
  `).join('');

  const labels = axes.map(axis => `
    <text x="${axis.label.x.toFixed(1)}" y="${axis.label.y.toFixed(1)}" text-anchor="middle" dominant-baseline="middle" class="report-radar-label">
      <tspan x="${axis.label.x.toFixed(1)}" dy="-4">${escapeHtml(axis.shortLabel)}</tspan>
      <tspan x="${axis.label.x.toFixed(1)}" dy="13" class="report-radar-score">${escapeHtml(String(axis.score))}</tspan>
    </text>
  `).join('');

  return `
    <aside class="combined-radar-panel">
      <div class="combined-radar-heading">
        <div><span>${escapeHtml(tx(lang, '6 DIMENSION RADAR', '6 DIMENSION RADAR'))}</span><h4>${escapeHtml(tx(lang, '六维评分雷达图', '6-Dimension Radar'))}</h4></div>
        <b>0 — 100</b>
      </div>
      <svg viewBox="0 0 ${size} ${size}" class="report-radar-svg" aria-label="radar chart">
        ${gridPolygons}
        ${axisLines}
        <polygon points="${valuePoints}" class="report-radar-value" />
        ${valueDots}
        ${labels}
      </svg>
    </aside>
  `;
}

function localizeCombinedCategory(value, lang = 'zh') {
  if (lang !== 'zh') return value || '';
  return String(value || '')
    .replaceAll('Technical SEO', '技术 SEO')
    .replaceAll('International SEO', '国际 SEO')
    .replaceAll('On-Page SEO', '页面 SEO')
    .replaceAll('Image SEO', '图片 SEO')
    .replaceAll('Content Quality', '内容质量')
    .replaceAll('Schema', '结构化数据')
    .replaceAll('Performance', '性能体验')
    .replaceAll('AI Search / GEO', 'AI 搜索 / GEO');
}

function priorityFromScore(score) {
  const value = Number(score) || 0;
  if (value < 25) return { priority: 'P0', severity: 'critical' };
  if (value < 45) return { priority: 'P1', severity: 'high' };
  if (value < 70) return { priority: 'P2', severity: 'medium' };
  return { priority: 'P3', severity: 'low' };
}

function buildAiIssues({ visibility, content, schema, platform, lang = 'zh' }) {
  const sources = [
    {
      key: 'visibility', module: visibility,
      check: tx(lang, 'AI 可见性与品牌权威', 'AI Visibility & Brand Authority'),
      category: tx(lang, 'AI 发现', 'AI Discovery'),
      impact: tx(lang, '影响 AI 爬虫发现、品牌实体确认及内容进入候选引用集。', 'Reduces AI crawler discovery, entity confidence, and citation eligibility.')
    },
    {
      key: 'content', module: content,
      check: tx(lang, 'AI 可引用内容', 'AI-Citable Content'),
      category: tx(lang, '内容 GEO', 'Content GEO'),
      impact: tx(lang, '降低答案抽取、事实核验与生成式搜索引用概率。', 'Reduces answer extraction, fact verification, and generative-search citation likelihood.')
    },
    {
      key: 'schema', module: schema,
      check: tx(lang, '实体与结构化数据', 'Entity & Structured Data'),
      category: tx(lang, '机器理解', 'Machine Understanding'),
      impact: tx(lang, '削弱 AI 对页面类型、品牌实体、作者与内容关系的理解。', 'Weakens AI understanding of page types, entities, authors, and content relationships.')
    },
    {
      key: 'platform', module: platform,
      check: tx(lang, 'AI 平台适配', 'AI Platform Readiness'),
      category: tx(lang, '平台适配', 'Platform Readiness'),
      impact: tx(lang, '影响 ChatGPT、Perplexity、AI Overviews、Gemini 等平台的读取与引用准备度。', 'Affects readiness across ChatGPT, Perplexity, AI Overviews, Gemini, and similar platforms.')
    }
  ];
  const rows = [];
  const seen = new Set();
  sources.forEach(source => {
    if (!source.module || !Object.keys(source.module).length) return;
    const issues = Array.isArray(source.module?.issues) ? source.module.issues : [];
    const recommendations = Array.isArray(source.module?.recommendations) ? source.module.recommendations : [];
    const score = Number(source.module?.score ?? 0);
    const severity = priorityFromScore(score);
    const normalizedIssues = issues.length
      ? issues.slice(0, 5)
      : score < 70
        ? [tx(lang, `${source.check}得分为 ${score}/100，仍存在明显提升空间。`, `${source.check} scores ${score}/100 and needs improvement.`)]
        : [];
    normalizedIssues.forEach((description, index) => {
      const fingerprint = `${source.key}:${String(description).trim()}`;
      if (!description || seen.has(fingerprint)) return;
      seen.add(fingerprint);
      rows.push({
        issue_id: `AI-${String(rows.length + 1).padStart(3, '0')}`,
        check_item: source.check,
        category: source.category,
        priority: severity.priority,
        severity: severity.severity,
        description,
        evidence: tx(lang, `${source.check} ${score}/100`, `${source.check}: ${score}/100`),
        impact: source.impact,
        recommendation: recommendations[index] || recommendations[0] || tx(lang, '针对该信号补充可抓取、可验证且结构清晰的页面内容。', 'Add crawlable, verifiable, well-structured page content for this signal.')
      });
    });
  });
  const rank = { P0: 0, P1: 1, P2: 2, P3: 3 };
  return rows.sort((a, b) => (rank[a.priority] ?? 4) - (rank[b.priority] ?? 4));
}

function renderIssueRows(issues, lang = 'zh', emptyMessage = '') {
  if (!issues.length) return `<tr><td colspan="5" class="audit-table-empty">${escapeHtml(emptyMessage)}</td></tr>`;
  const severityLabels = lang === 'zh'
    ? { critical: '紧急', high: '高', medium: '常规', low: '低' }
    : { critical: 'Critical', high: 'High', medium: 'Medium', low: 'Low' };
  return issues.map(item => `
    <tr>
      <td><strong class="issue-check-title">${escapeHtml(item.check_item || tx(lang, '站点检查', 'Site Check'))}</strong><span class="issue-meta"><span>${escapeHtml(localizeCombinedCategory(item.category || '-', lang))}</span><code>${escapeHtml(item.issue_id || '-')}</code></span></td>
      <td><span class="priority-chip ${escapeHtml(String(item.priority || '').toLowerCase())}">${escapeHtml(item.priority || '-')}</span><span class="issue-severity">${escapeHtml(tx(lang, '重要程度：', 'Severity: '))}${escapeHtml(severityLabels[item.severity] || item.severity || '-')}</span></td>
      <td class="audit-table-main audit-cell-copy">${escapeHtml(item.description || '-')}<small class="issue-evidence-line">${escapeHtml(item.evidence || '')}</small></td>
      <td class="audit-cell-copy">${escapeHtml(item.seo_impact || item.impact || '-')}</td>
      <td class="audit-cell-copy recommendation">${escapeHtml(item.recommendation || '-')}</td>
    </tr>
  `).join('');
}

function renderPrioritySummary(issues) {
  return ['P0', 'P1', 'P2', 'P3'].map(priority => {
    const count = issues.filter(item => item.priority === priority).length;
    return count ? `<span class="issue-count"><i class="priority-dot ${priority.toLowerCase()}"></i>${priority}<strong>${count}</strong></span>` : '';
  }).join('');
}

function buildPerceptionWords({ aiPerception, dimensionMeta, weighted, summary, lang = 'zh' }) {
  const negativePattern = lang === 'zh'
    ? /弱|不足|受限|缺失|风险|争议|低|薄弱|阻止|不可|欠缺/
    : /weak|missing|limited|risk|controvers|low|block|insufficient|poor/i;
  const keywords = Array.isArray(aiPerception?.cognition_keywords)
    ? aiPerception.cognition_keywords.map(item => String(item || '').trim()).filter(Boolean)
    : [];
  const positive = keywords.filter(item => !negativePattern.test(item));
  const limited = keywords.filter(item => negativePattern.test(item));
  const perceptionLabels = lang === 'zh'
    ? {
        'AI Citability & Visibility': ['AI 可见性强', 'AI 抓取受限'],
        'Brand Authority Signals': ['品牌可信', '品牌权威偏弱'],
        'Content Quality & E-E-A-T': ['内容可信', '内容证据不足'],
        'Technical Foundations': ['技术可读', '技术读取受限'],
        'Structured Data': ['实体清晰', '结构化数据不足'],
        'Platform Optimization': ['平台适配良好', '平台适配受限']
      }
    : {
        'AI Citability & Visibility': ['AI-visible', 'AI crawl limited'],
        'Brand Authority Signals': ['Trusted brand', 'Weak brand authority'],
        'Content Quality & E-E-A-T': ['Credible content', 'Insufficient evidence'],
        'Technical Foundations': ['Machine readable', 'Technical access limited'],
        'Structured Data': ['Clear entities', 'Insufficient structured data'],
        'Platform Optimization': ['Platform ready', 'Platform readiness limited']
      };

  dimensionMeta.forEach(meta => {
    const score = Math.max(0, Math.min(100, Number(weighted?.[meta.key]?.raw_score ?? 0)));
    const fallbackName = summary?.dimensions?.[meta.key]?.display_name || meta.defaultName;
    const [positiveWord, limitedWord] = perceptionLabels[meta.key] || [fallbackName, fallbackName];
    if (score >= 70) positive.push(positiveWord);
    if (score < 60) limited.push(limitedWord);
  });

  const unique = items => [...new Set(items)].slice(0, 8);
  return {
    positive: unique(positive.length ? positive : [tx(lang, '待建立正面认知', 'Positive perception pending')]),
    limited: unique(limited.length ? limited : [tx(lang, '暂无明显受限认知', 'No strong limiting perception')])
  };
}

function renderWordCloud(words, tone) {
  return words.map((word, index) => `
    <span class="ai-word ai-word-${tone} size-${(index % 4) + 1}">${escapeHtml(word)}</span>
  `).join('');
}

export function renderSiteAuditReport({ task, host, lang, setCachedReportHtml }) {
  const result = task?.result || {};
  const summary = result.summary || {};
  const discovery = result.discovery || {};
  const seo = result.seo || {};
  const assetSummary = discovery.asset_summary || {};
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
    compositeGeoScore: tx(lang, 'SEO + GEO 综合得分', 'SEO + GEO Composite Score'),
    premiumBadge: tx(lang, '会员版 / AI 增强', 'Premium / AI Enriched'),
    standardBadge: tx(lang, '普通版 / 规则版', 'Standard / Rule-based'),
    enhanced: tx(lang, '报告已增强', 'Report Enhanced'),
    ruleSummary: tx(lang, '规则汇总', 'Rule Summary'),
    siteGeoReport: tx(lang, '网站 SEO+GEO 审计报告', 'Website SEO + GEO Audit Report'),
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
  const compositeScore = Math.max(0, Math.min(100, Number(summary.composite_geo_score ?? 0)));
  const compositeStatus = scoreToStatus(compositeScore);
  const aiPerception = summary.ai_perception || {};
  const platformScores = platform.platform_scores || {};
  const observation = result.observation || summary.observation || {};
  const metricDefinitions = summary.metric_definitions || [];
  const notices = summary.notices || [];
  const pageDiagnostics = Array.isArray(result.page_diagnostics) ? result.page_diagnostics : [];
  const isAiSeoItem = item => item?.id === 'CHK-026' || /AI Search|GEO/i.test(String(item?.category || ''));
  const seoIssues = Array.isArray(seo.issues_table) ? seo.issues_table.filter(item => !isAiSeoItem(item)).sort((a, b) => {
    const priorityRank = { P0: 0, P1: 1, P2: 2, P3: 3 };
    const severityRank = { critical: 0, high: 1, medium: 2, low: 3 };
    return ((priorityRank[a.priority] ?? 4) - (priorityRank[b.priority] ?? 4)) ||
      ((severityRank[a.severity] ?? 4) - (severityRank[b.severity] ?? 4));
  }) : [];
  const seoCoverage = Array.isArray(seo.coverage_checks) ? seo.coverage_checks.filter(item => !isAiSeoItem(item)) : [];
  const seoFailedChecks = seoCoverage.filter(item => item.status === 'fail').length;
  const aiIssues = buildAiIssues({ visibility, content, schema, platform, lang });
  const priorityRank = { P0: 0, P1: 1, P2: 2, P3: 3 };
  const combinedIssues = [...seoIssues, ...aiIssues].sort((a, b) =>
    (priorityRank[a.priority] ?? 4) - (priorityRank[b.priority] ?? 4)
  );
  const sampledCount = Number(seo.measurements?.sampled_url_count ?? discovery.profiled_page_count ?? 0);
  const citability = visibility.findings?.citability || {};
  const homepageCitability = citability.homepage_citability || {};
  const bestPageCitability = citability.best_page_citability || {};
  const citationProbability = citability.citation_probability || 'LOW';
  const citationLabelMap = lang === 'zh'
    ? { LOW: '低', MEDIUM: '中', HIGH: '高' }
    : { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High' };
  const assetTypeSummary = Object.entries(assetSummary.url_type_counts || {}).map(([key, count]) => `${key}:${count}`).join(' · ') || labels.unavailable;
  const assetSourceSummary = Object.entries(assetSummary.discovery_source_counts || {}).map(([key, count]) => `${key}:${count}`).join(' · ') || labels.unavailable;
  const pageProfiles = Object.entries(discovery.page_profiles || {});
  const additionalProfiles = Array.isArray(discovery.additional_page_profiles) ? discovery.additional_page_profiles : [];
  const fallbackPages = Object.values(content.page_analyses || {});
  const dimensionMeta = getDimensionMeta(lang);
  const radarHtml = buildRadarChartHtml({ dimensionMeta, weighted, summary, lang });
  const dimensionStripHtml = dimensionMeta.map((meta, index) => {
    const score = Math.max(0, Math.min(100, Number(weighted?.[meta.key]?.raw_score ?? 0)));
    const displayName = summary?.dimensions?.[meta.key]?.display_name || meta.defaultName;
    return `<div class="combined-dimension-chip tone-${index + 1}"><span><i></i>${escapeHtml(displayName)}</span><strong>${escapeHtml(String(score))}</strong></div>`;
  }).join('');
  const capabilityListHtml = dimensionMeta.map((meta, index) => {
    const score = Math.max(0, Math.min(100, Number(weighted?.[meta.key]?.raw_score ?? 0)));
    const displayName = summary?.dimensions?.[meta.key]?.display_name || meta.defaultName;
    const status = scoreToStatus(score);
    return `
      <div class="ai-capability-item tone-${index + 1}">
        <div class="ai-capability-name"><i></i><span>${escapeHtml(displayName)}</span><small>${escapeHtml(formatStatus(status, lang))}</small></div>
        <div class="ai-capability-meter"><span style="width:${score}%"></span></div>
        <strong class="${escapeHtml(statusTone(status))}">${escapeHtml(String(score))}</strong>
      </div>
    `;
  }).join('');
  const cognitionWords = buildPerceptionWords({ aiPerception, dimensionMeta, weighted, summary, lang });
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

  const noticesHtml = notices.length
    ? `<div class="report-list" style="margin-top:14px">${formatList(notices, labels.noNotices, 8)}</div>`
    : '';

  const seoCoverageHtml = seoCoverage.length
    ? seoCoverage.map(item => `
        <tr>
          <td><code>${escapeHtml(item.id || '-')}</code></td>
          <td>${escapeHtml(localizeCombinedCategory(item.category || '-', lang))}</td>
          <td class="audit-table-main">${escapeHtml(item.check || '-')}</td>
          <td><span class="check-state ${['pass', 'fail', 'na'].includes(item.status) ? item.status : 'na'}">${escapeHtml(({ pass: tx(lang, '通过', 'Pass'), fail: tx(lang, '待优化', 'Needs work'), na: tx(lang, '不适用', 'N/A') })[item.status] || item.status || '-')}</span></td>
          <td class="audit-cell-copy">${escapeHtml(item.summary || '-')}</td>
          <td class="audit-cell-copy evidence">${escapeHtml(item.evidence || '-')}</td>
        </tr>
      `).join('')
    : `<tr><td colspan="6" class="audit-table-empty">${escapeHtml(tx(lang, '旧任务暂无 SEO 覆盖数据，请强制刷新后重新审计。', 'This older task has no SEO coverage data. Force-refresh the audit to generate it.'))}</td></tr>`;

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
    <section class="report-hero combined-report-hero">
      ${radarHtml}
      <main class="combined-report-main">
        <div class="report-kicker">
          <span>${escapeHtml(discovery.domain || discovery.normalized_url || task.url || '-')}</span><span class="dot"></span>
          <span>${escapeHtml(task.mode || 'standard')}</span><span class="dot"></span>
          <span>${escapeHtml(tx(lang, '已完成', 'completed'))}</span><span class="dot"></span>
          <span>${escapeHtml(discovery.resolved_target_locale || discovery.homepage?.lang || '-')}</span>
        </div>
        <h3>${escapeHtml(labels.siteGeoReport)}</h3>
        <div class="report-summary">${escapeHtml(executive)}</div>
        <div class="combined-report-notice">${escapeHtml(tx(lang, '综合分采用 GEO v3 六维 readiness 口径；SEO 诊断作为独立检查层展示，不改变综合分。', 'The composite uses the GEO v3 six-dimension readiness model. SEO diagnostics are shown as a separate layer and do not alter the composite.'))}</div>
        ${noticesHtml}
        <div class="combined-dimension-strip">${dimensionStripHtml}</div>
      </main>
      <aside class="combined-score-panel">
        <div class="report-score-label">${escapeHtml(labels.compositeGeoScore)}</div>
        <div class="report-score-value">${escapeHtml(String(compositeScore))}</div>
        <strong class="combined-score-status">${escapeHtml(formatStatus(compositeStatus, lang))}</strong>
        <div class="report-badges">
          <span class="r-badge ${escapeHtml(statusTone(compositeStatus))}">${escapeHtml(formatStatus(compositeStatus, lang))}</span>
          <span class="r-badge">${task.mode === 'premium' ? labels.premiumBadge : labels.standardBadge}</span>
          <span class="r-badge">${escapeHtml(summary.scoring_version || 'geo-audit-v3')}</span>
        </div>
        <div class="combined-snapshot-grid">
          <div><span>Snapshot</span><strong>${escapeHtml(discovery.site_snapshot_version || 'snapshot-v1')}</strong></div>
          <div><span>AI Crawlers</span><strong>${escapeHtml(String(visibility.checks?.allowed_ai_crawlers ?? 0))}/${escapeHtml(String(visibility.checks?.total_ai_crawlers_checked ?? 0))}</strong></div>
          <div><span>${escapeHtml(tx(lang, '页面诊断', 'Page Diagnostics'))}</span><strong>${escapeHtml(String(pageDiagnostics.length || sampledCount))}</strong></div>
          <div><span>${escapeHtml(tx(lang, 'SEO 待优化', 'SEO Issues'))}</span><strong>${escapeHtml(String(Math.max(seoFailedChecks, seoIssues.length)))}</strong></div>
        </div>
      </aside>
    </section>

    <section class="report-section issue-table-section combined-issues-section">
      <div class="report-section-hdr issue-section-heading"><div><h4>${escapeHtml(tx(lang, '问题清单', 'SEO + GEO Issue List'))}<span class="section-count">${combinedIssues.length}</span></h4><p>${escapeHtml(tx(lang, '沿用 SEO 诊断表结构，统一呈现搜索优化与 AI 可见性问题', 'Uses the SEO diagnostic table format for both search and AI visibility issues'))}</p></div><div class="issue-priority-summary">${renderPrioritySummary(combinedIssues)}</div></div>
      <div class="audit-table-wrap issue-table-wrap">
        <table class="audit-table issue-table">
          <thead><tr><th>${escapeHtml(tx(lang, '检查事项', 'Check'))}</th><th>${escapeHtml(tx(lang, '优先级', 'Priority'))}</th><th>${escapeHtml(tx(lang, '发现的问题', 'Issue'))}</th><th>${escapeHtml(tx(lang, 'SEO / GEO 影响', 'SEO / GEO Impact'))}</th><th>${escapeHtml(tx(lang, '修复建议', 'Recommendation'))}</th></tr></thead>
          <tbody>${renderIssueRows(combinedIssues, lang, tx(lang, '本次未发现明确问题；旧缓存请强制刷新以生成完整 SEO+GEO 诊断。', 'No explicit issues were found. Force-refresh older cached tasks to generate the full SEO + GEO diagnosis.'))}</tbody>
        </table>
      </div>
    </section>

    <section class="report-section ai-cognition-section">
      <div class="report-section-hdr ai-cognition-heading"><div><h4>${escapeHtml(tx(lang, 'AI 认知图', 'AI Perception Map'))}</h4><p>${escapeHtml(tx(lang, '从六项能力与认知语义两个板块识别 AI 对网站的理解', 'Shows how AI systems understand the site through capabilities and perception signals'))}</p></div><span>${escapeHtml(tx(lang, '认知结果用于诊断，不改变综合分', 'Perception is diagnostic and unscored'))}</span></div>
      <div class="ai-cognition-layout">
        <article class="ai-cognition-panel ai-capability-panel">
          <div class="ai-panel-heading"><div><span>01</span><h5>${escapeHtml(tx(lang, '能力项清单与分数', 'Capabilities & Scores'))}</h5></div><b>0 — 100</b></div>
          <div class="ai-capability-list">${capabilityListHtml}</div>
        </article>
        <article class="ai-cognition-panel ai-word-panel">
          <div class="ai-panel-heading"><div><span>02</span><h5>${escapeHtml(tx(lang, 'AI 认知词云', 'AI Perception Word Clouds'))}</h5></div><b>${escapeHtml(tx(lang, '语义信号', 'Signals'))}</b></div>
          <div class="ai-perception-metrics">
            <div><span>${escapeHtml(tx(lang, '正面', 'Positive'))}</span><strong>${escapeHtml(String(aiPerception.positive_percentage ?? 0))}%</strong></div>
            <div><span>${escapeHtml(tx(lang, '中性', 'Neutral'))}</span><strong>${escapeHtml(String(aiPerception.neutral_percentage ?? 0))}%</strong></div>
            <div><span>${escapeHtml(tx(lang, '受限', 'Limited'))}</span><strong>${escapeHtml(String(aiPerception.controversial_percentage ?? 0))}%</strong></div>
            <div><span>${escapeHtml(tx(lang, '引用概率', 'Citation'))}</span><strong>${escapeHtml(citationLabelMap[citationProbability] || citationProbability)}</strong></div>
          </div>
          <div class="ai-word-clouds">
            <div class="ai-word-cloud positive"><h6><i></i>${escapeHtml(tx(lang, '正面认知词云', 'Positive Perception'))}</h6><div>${renderWordCloud(cognitionWords.positive, 'positive')}</div></div>
            <div class="ai-word-cloud limited"><h6><i></i>${escapeHtml(tx(lang, '受限认知词云', 'Limited Perception'))}</h6><div>${renderWordCloud(cognitionWords.limited, 'limited')}</div></div>
          </div>
          <div class="ai-word-footnote">${escapeHtml(tx(lang, `最佳引用页 ${bestPageCitability.page_key || 'homepage'} · ${bestPageCitability.score ?? 0} 分 · 最弱平台 ${PLATFORM_LABELS[weakestPlatform?.[0]] || '-'} ${weakestPlatform?.[1]?.platform_score ?? '-'}`, `Best citation page ${bestPageCitability.page_key || 'homepage'} · ${bestPageCitability.score ?? 0} · Weakest platform ${PLATFORM_LABELS[weakestPlatform?.[0]] || '-'} ${weakestPlatform?.[1]?.platform_score ?? '-'}`))}</div>
        </article>
      </div>
    </section>

    <section class="report-section dimensions-section scored-dimensions-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.scoredDimensionsTitle)}</h4><span>${escapeHtml(labels.scoredDimensionsSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${dimensionHtml}</div></div>
    </section>

    <details class="report-section collapsible-section coverage-section">
      <summary class="report-section-hdr coverage-heading"><h4>${escapeHtml(tx(lang, 'SEO 覆盖清单', 'SEO Coverage Checklist'))}</h4><div class="coverage-heading-actions"><span>${escapeHtml(tx(lang, `${seoCoverage.length - seoFailedChecks} 项通过 · ${seoFailedChecks} 项待优化 · 点击展开`, `${seoCoverage.length - seoFailedChecks} passed · ${seoFailedChecks} need work · Expand`))}</span><a class="checklist-doc-link" href="/api-doc#seo-checklist" target="_blank" rel="noreferrer" onclick="event.stopPropagation()">${escapeHtml(tx(lang, '检测清单说明', 'Checklist Guide'))}<b>↗</b></a></div></summary>
      <div class="audit-table-wrap coverage-table-wrap"><table class="audit-table coverage-table"><thead><tr><th>${escapeHtml(tx(lang, '编号', 'ID'))}</th><th>${escapeHtml(tx(lang, '分类', 'Category'))}</th><th>${escapeHtml(tx(lang, '检查事项', 'Check'))}</th><th>${escapeHtml(tx(lang, '状态', 'Status'))}</th><th>${escapeHtml(tx(lang, '诊断结论', 'Finding'))}</th><th>${escapeHtml(tx(lang, '证据', 'Evidence'))}</th></tr></thead><tbody>${seoCoverageHtml}</tbody></table></div>
    </details>

    <div class="report-grid-2">
      <section class="report-section"><div class="report-section-hdr"><h4>${escapeHtml(labels.keyIssuesTitle)}</h4><span>${escapeHtml(labels.keyIssuesSubtitle)}</span></div><div class="report-section-body"><div class="report-list">${formatList(topIssues, tx(lang, '暂无关键问题。', 'No key issues.'))}</div></div></section>
      <section class="report-section"><div class="report-section-hdr"><h4>${escapeHtml(labels.quickWinsTitle)}</h4><span>${escapeHtml(labels.quickWinsSubtitle)}</span></div><div class="report-section-body"><div class="report-list">${formatList(quickWins, tx(lang, '暂无快速收益建议。', 'No quick wins available.'))}</div></div></section>
    </div>

    <details class="report-section collapsible-section">
      <summary class="report-section-hdr"><h4>${escapeHtml(labels.actionPlanTitle)}</h4><span>${escapeHtml(labels.actionPlanSubtitle)}</span></summary>
      <div class="report-section-body"><div class="report-action-list">${actionHtml}</div></div>
    </details>

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
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '发现层快照', 'Discovery Snapshot'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, 'snapshot 版本', 'Snapshot version'))}</span><span class="kv-val">${escapeHtml(discovery.site_snapshot_version || 'snapshot-v1')}</span></div><div class="kv-row"><span class="kv-key">scope root</span><span class="kv-val">${escapeHtml(discovery.scope_root_url || discovery.site_root_url || '-')}</span></div><div class="kv-row"><span class="kv-key">profiled pages</span><span class="kv-val">${escapeHtml(String(discovery.profiled_page_count || pageSamples.length || 1))} ${escapeHtml(tx(lang, '页', 'pages'))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '关键页面识别', 'Key pages identified'))}</span><span class="kv-val">${escapeHtml(String(Object.values(discovery.key_pages || {}).filter(Boolean).length))} ${escapeHtml(tx(lang, '页', 'pages'))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '站点资产库', 'Asset storage'))}</span><span class="kv-val">${escapeHtml(assetSummary.backend || 'file')} / ${escapeHtml(String(assetSummary.stored_url_count || 0))} URL / ${escapeHtml(String(assetSummary.stored_snapshot_count || 0))} snapshot</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '快照复用 / 新抓取', 'Reused / fetched snapshots'))}</span><span class="kv-val">${escapeHtml(String(assetSummary.reused_snapshot_count || 0))} / ${escapeHtml(String(assetSummary.fetched_snapshot_count || 0))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页引用得分', 'Homepage citability'))}</span><span class="kv-val">${escapeHtml(String(homepageCitability.score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '最佳引用页', 'Best citation page'))}</span><span class="kv-val">${escapeHtml(bestPageCitability.page_key || 'homepage')} / ${escapeHtml(String(bestPageCitability.score ?? 0))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '抓取与实体信号', 'Crawl and Entity Signals'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">robots.txt</span><span class="kv-val">${formatBool(discovery.robots?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))}</span></div><div class="kv-row"><span class="kv-key">llms.txt / ${escapeHtml(tx(lang, '有效性', 'Quality'))}</span><span class="kv-val">${formatBool(discovery.llms?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))} / ${escapeHtml(String(visibility.findings?.llms_quality?.score ?? discovery.llms?.effectiveness_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">Sitemap / Semrush AS</span><span class="kv-val">${formatBool(discovery.sitemap?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))} / ${escapeHtml(String(discovery.backlinks?.authority_score ?? tx(lang, '未接入', 'Unavailable')))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '公司名 / 电话', 'Company / Phone'))}</span><span class="kv-val">${formatBool(discovery.site_signals?.company_name_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.phone_detected, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '地址 / 邮箱 / sameAs', 'Address / Email / sameAs'))}</span><span class="kv-val">${formatBool(discovery.site_signals?.address_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.email_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.same_as_detected, labels.pageFaqYes, labels.pageFaqNo)}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '技术与结构化快照', 'Technical and Structured Snapshot'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '安全头得分', 'Security headers score'))}</span><span class="kv-val">${escapeHtml(String(technical.findings?.security_headers_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">SSR / ${escapeHtml(tx(lang, '性能', 'Performance'))}</span><span class="kv-val">${escapeHtml(technical.findings?.ssr_classification || '-')} / ${escapeHtml(technical.findings?.performance_classification || technical.checks?.performance?.classification || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '唯一 H1 / freshness', 'Unique H1 / freshness'))}</span><span class="kv-val">${formatBool(technical.checks?.unique_h1, labels.pageFaqYes, labels.pageFaqNo)} / ${escapeHtml(String(technical.findings?.freshness_signal_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">ETag / Last-Modified</span><span class="kv-val">${formatBool(technical.checks?.revalidation_headers?.etag, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(technical.checks?.revalidation_headers?.last_modified, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '图片 lazyload / 尺寸', 'Image lazyload / dimensions'))}</span><span class="kv-val">${escapeHtml(String(technical.checks?.image_optimization?.lazyload_ratio ?? 0))} / ${escapeHtml(String(technical.checks?.image_optimization?.dimension_ratio ?? 0))}</span></div><div class="kv-row"><span class="kv-key">Schema / sameAs / ${escapeHtml(tx(lang, '对齐', 'Alignment'))}</span><span class="kv-val">${escapeHtml(String(schema.findings?.schema_type_count ?? 0))} / ${escapeHtml(String(schema.findings?.same_as_count ?? 0))} / ${escapeHtml(String(schema.findings?.visible_alignment_score ?? 0))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '证据与链接上下文', 'Evidence and Link Context'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '参考资料区', 'References section'))}</span><span class="kv-val">${formatBool(content.findings?.has_reference_section_any, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '内联引用', 'Inline citations'))}</span><span class="kv-val">${formatBool(content.findings?.has_inline_citations_any, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">TL;DR / ${escapeHtml(tx(lang, '更新记录', 'Update log'))}</span><span class="kv-val">${formatBool(content.findings?.has_tldr_any, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(content.findings?.has_update_log_any, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '链接语义得分', 'Link context score'))}</span><span class="kv-val">${escapeHtml(String(content.findings?.average_link_context_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '机器日期', 'Machine dates'))}</span><span class="kv-val">${formatBool(schema.checks?.has_date_published, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(schema.checks?.has_date_modified, labels.pageFaqYes, labels.pageFaqNo)}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '引用与平台证据', 'Citation and Platform Evidence'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(labels.citationProbability)}</span><span class="kv-val">${escapeHtml(citationLabelMap[citationProbability] || citationProbability)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '最佳页类型', 'Best page type'))}</span><span class="kv-val">${escapeHtml(bestPageCitability.page_type || bestPageCitability.page_key || 'homepage')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(labels.bestWeakestPlatform)}</span><span class="kv-val">${escapeHtml(PLATFORM_LABELS[strongestPlatform?.[0]] || '-')} / ${escapeHtml(PLATFORM_LABELS[weakestPlatform?.[0]] || '-')}</span></div><div class="kv-row"><span class="kv-key">Observation</span><span class="kv-val">${observation.provided ? tx(lang, '已上传，不计分', 'Uploaded, unscored') : tx(lang, '未上传', 'Not uploaded')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '输入范围', 'Input Scope'))}</span><span class="kv-val">${discovery.input_is_likely_homepage === false ? tx(lang, '非首页，可能偏差', 'Non-homepage, may be biased') : tx(lang, '首页/语言首页', 'Homepage/locale homepage')}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '关键页面与内容采样', 'Key Pages and Content Samples'))}</h5><div class="kv-list" style="margin-bottom:10px">${formatKeyPages(discovery.key_pages || {}, lang)}</div><div class="kv-list" style="margin-bottom:10px"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, 'URL 类型分布', 'URL types'))}</span><span class="kv-val">${escapeHtml(assetTypeSummary)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '发现来源', 'Discovery sources'))}</span><span class="kv-val">${escapeHtml(assetSourceSummary)}</span></div></div><div class="page-samples">${pageSampleHtml}</div></div>
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
