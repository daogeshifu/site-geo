import {
  escapeHtml,
  formatStatus,
  statusTone,
  tx
} from './shared.js';

function localizeSeoText(value, lang = 'zh') {
  if (lang !== 'zh') return value || '';
  return String(value || '')
    .replaceAll('Core Web Vitals / Performance', '性能体验')
    .replaceAll('Performance', '性能体验')
    .replaceAll('Content Quality', '内容质量')
    .replaceAll('On-Page SEO', '页面 SEO')
    .replaceAll('Technical SEO', '技术 SEO')
    .replaceAll('AI Search / GEO', 'AI 搜索 / GEO')
    .replaceAll('AI Search', 'AI 搜索')
    .replaceAll('Image SEO', '图片 SEO')
    .replaceAll('International SEO', '国际 SEO')
    .replaceAll('Schema', '结构化数据')
    .replaceAll('Measurement', '数据衡量');
}

const CHECK_LABELS = {
  'CHK-001': ['Robots', 'Robots'],
  'CHK-002': ['站点地图', 'Sitemap'],
  'CHK-003': ['数据追踪', 'Analytics'],
  'CHK-004': ['HTTPS', 'HTTPS'],
  'CHK-005': ['主域统一', 'Host'],
  'CHK-006': ['URL 规范', 'URL'],
  'CHK-007': ['结构化数据', 'Schema'],
  'CHK-008': ['HTTP 状态', 'HTTP Status'],
  'CHK-009': ['移动适配', 'Mobile'],
  'CHK-010': ['页面性能', 'Performance'],
  'CHK-011': ['多语言', 'Hreflang'],
  'CHK-012': ['索引指令', 'Noindex'],
  'CHK-013': ['JS 渲染', 'Rendering'],
  'CHK-014': ['页面标题', 'Title'],
  'CHK-015': ['页面描述', 'Description'],
  'CHK-016': ['标题层级', 'Headings'],
  'CHK-017': ['规范链接', 'Canonical'],
  'CHK-018': ['语言声明', 'Language'],
  'CHK-019': ['图片文本', 'Image Alt'],
  'CHK-020': ['内部链接', 'Internal Links'],
  'CHK-021': ['页面体量', 'Payload'],
  'CHK-022': ['图片加载', 'Image Loading'],
  'CHK-023': ['内容深度', 'Content Depth'],
  'CHK-024': ['内容可信度', 'E-E-A-T'],
  'CHK-025': ['内容引用', 'Citability'],
  'CHK-026': ['AI 可见性', 'AI Visibility']
};

function shortCheckLabel(checkId, description, lang = 'zh') {
  const configured = CHECK_LABELS[checkId];
  if (configured) return configured[lang === 'zh' ? 0 : 1];
  const text = String(description || '');
  const patterns = [
    [/robots/i, ['Robots', 'Robots']], [/sitemap/i, ['站点地图', 'Sitemap']],
    [/GA4|GSC/i, ['数据追踪', 'Analytics']], [/4xx|5xx|状态码|redirect/i, ['HTTP 状态', 'HTTP Status']],
    [/www|host|主域/i, ['主域统一', 'Host']], [/canonical/i, ['规范链接', 'Canonical']],
    [/schema|结构化/i, ['结构化数据', 'Schema']], [/title/i, ['页面标题', 'Title']],
    [/description/i, ['页面描述', 'Description']], [/H1|H2|H3|H 标签/i, ['标题层级', 'Headings']],
    [/alt/i, ['图片文本', 'Image Alt']], [/懒加载|lazy|width\/height/i, ['图片加载', 'Image Loading']],
    [/E-E-A-T|作者|权威/i, ['内容可信度', 'E-E-A-T']], [/FAQ|answer-first|引用/i, ['内容引用', 'Citability']],
    [/AI |GEO|crawler|llms/i, ['AI 可见性', 'AI Visibility']], [/性能|响应|阻塞/i, ['页面性能', 'Performance']],
    [/内容|深度|主题/i, ['内容深度', 'Content Depth']], [/URL|参数|下划线/i, ['URL 规范', 'URL']]
  ];
  const match = patterns.find(([pattern]) => pattern.test(text));
  return match ? match[1][lang === 'zh' ? 0 : 1] : tx(lang, '站点检查', 'Site Check');
}

function renderExecutiveList(items = [], fallback, tone = 'risk') {
  const list = [...new Set((items || []).filter(Boolean))].slice(0, 5);
  if (!list.length) return `<div class="executive-empty">${escapeHtml(fallback)}</div>`;
  return list.map((item, index) => `
    <div class="executive-item ${tone}">
      <span class="executive-index">${String(index + 1).padStart(2, '0')}</span>
      <span>${escapeHtml(item)}</span>
    </div>
  `).join('');
}

function renderDimensionItems(items = [], fallback, tone = 'finding') {
  const list = [...new Set((items || []).filter(Boolean))];
  if (!list.length) return `<div class="dimension-empty">${escapeHtml(fallback)}</div>`;
  return list.map((item, index) => `
    <div class="dimension-list-item ${tone}">
      <span>${String(index + 1).padStart(2, '0')}</span>
      <p>${escapeHtml(item)}</p>
    </div>
  `).join('');
}

function severityLabel(value, lang = 'zh') {
  if (lang !== 'zh') return formatStatus(value, lang);
  return ({ critical: '紧急', high: '高', medium: '常规', low: '低' })[value] || value || '-';
}

export function renderSeoAuditReport({ task, host, lang, setCachedReportHtml }) {
  const result = task?.result || {};
  const summary = result.summary || {};
  const seo = result.seo || {};
  const discovery = result.discovery || {};
  const dimensions = Object.values(seo.dimensions || {});
  const coverageChecks = Array.isArray(seo.coverage_checks) ? seo.coverage_checks : [];
  const priorityRank = { P0: 0, P1: 1, P2: 2, P3: 3 };
  const severityRank = { critical: 0, high: 1, medium: 2, low: 3 };
  const issues = (Array.isArray(seo.issues_table) ? [...seo.issues_table] : []).sort((a, b) =>
    ((priorityRank[a.priority] ?? 4) - (priorityRank[b.priority] ?? 4)) ||
    ((severityRank[a.severity] ?? 4) - (severityRank[b.severity] ?? 4))
  );
  const prioritySummary = Object.keys(priorityRank).map(priority => {
    const count = issues.filter(item => item.priority === priority).length;
    return count ? `<span class="issue-count"><i class="priority-dot ${priority.toLowerCase()}"></i>${priority}<strong>${count}</strong></span>` : '';
  }).join('');
  const sampledPages = Array.isArray(seo.sampled_pages) ? seo.sampled_pages : [];
  const passedChecks = coverageChecks.filter(item => item.status === 'pass').length;
  const failedChecks = coverageChecks.filter(item => item.status === 'fail').length;
  const overallScore = Math.max(0, Math.min(100, Number(summary.overall_score ?? seo.overall_score ?? seo.score) || 0));
  const overallStatus = summary.status || seo.status;
  const totalChecks = summary.coverage_summary?.total_checks ?? seo.coverage_summary?.total_checks ?? coverageChecks.length;
  const sampledCount = seo.measurements?.sampled_url_count ?? sampledPages.length;

  const dimensionHtml = dimensions.length
    ? dimensions.map(item => `
        <article class="report-dim-card tone-${escapeHtml(statusTone(item.status) || 'neutral')}">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(localizeSeoText(item.label || item.key, lang))}</span>
            <span class="report-dim-pill">${escapeHtml(formatStatus(item.status, lang))}</span>
          </div>
          <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(item.score ?? 0))}<small>/100</small></span></div>
          <div class="dimension-meter"><span style="width:${Math.max(0, Math.min(100, Number(item.score) || 0))}%"></span></div>
          <div class="report-dim-note">${escapeHtml(item.summary || '')}</div>
          <details class="dimension-details"><summary>${escapeHtml(tx(lang, '查看问题与建议', 'View findings & recommendations'))}</summary>
            <div class="dimension-detail-body">
              <section class="dimension-subsection findings">
                <h6>${escapeHtml(tx(lang, '发现事项', 'Findings'))}</h6>
                <div class="dimension-item-list">${renderDimensionItems(item.issues || [], tx(lang, '暂无明显缺口。', 'No major gaps.'), 'finding')}</div>
              </section>
              <section class="dimension-subsection recommendations">
                <h6>${escapeHtml(tx(lang, '优化建议', 'Recommendations'))}</h6>
                <div class="dimension-item-list">${renderDimensionItems(item.recommendations || [], tx(lang, '暂无额外建议。', 'No extra recommendations.'), 'recommendation')}</div>
              </section>
            </div>
          </details>
        </article>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(tx(lang, '暂无维度结果。', 'No dimension results.'))}</div>`;

  const coverageHtml = coverageChecks.length
    ? coverageChecks.map(item => `
        <tr>
          <td><code>${escapeHtml(item.id || '-')}</code></td>
          <td>${escapeHtml(localizeSeoText(item.category || '-', lang))}</td>
          <td class="audit-table-main">${escapeHtml(item.check || '-')}</td>
          <td><span class="check-state ${['pass', 'fail', 'na'].includes(item.status) ? item.status : 'na'}">${escapeHtml(({ pass: tx(lang, '通过', 'Pass'), fail: tx(lang, '待优化', 'Needs work'), na: tx(lang, '不适用', 'N/A') })[item.status] || item.status)}</span></td>
          <td class="audit-cell-copy">${escapeHtml(item.summary || '-')}</td>
          <td class="audit-cell-copy evidence">${escapeHtml(item.evidence || '-')}</td>
        </tr>
      `).join('')
    : `<tr><td colspan="6" class="audit-table-empty">${escapeHtml(tx(lang, '暂无覆盖清单。', 'No coverage checklist available.'))}</td></tr>`;

  const issueHtml = issues.length
    ? issues.map(item => {
        const coverageMatch = coverageChecks.find(check => check.summary === item.description) || coverageChecks.find(check =>
          check.evidence === item.evidence && check.category === item.category
        );
        const checkTitle = item.check_item || shortCheckLabel(coverageMatch?.id, item.description, lang);
        return `
        <tr>
          <td><strong class="issue-check-title">${escapeHtml(checkTitle)}</strong><span class="issue-meta"><span>${escapeHtml(localizeSeoText(item.category || '-', lang))}</span><code>${escapeHtml(item.issue_id || '-')}</code></span></td>
          <td><span class="priority-chip ${escapeHtml(String(item.priority || '').toLowerCase())}">${escapeHtml(item.priority || '-')}</span><span class="issue-severity">${escapeHtml(tx(lang, '重要程度：', 'Severity: '))}${escapeHtml(severityLabel(item.severity, lang))}</span></td>
          <td class="audit-table-main audit-cell-copy">${escapeHtml(item.description || '-')}</td>
          <td class="audit-cell-copy">${escapeHtml(item.seo_impact || '-')}</td>
          <td class="audit-cell-copy recommendation">${escapeHtml(item.recommendation || '-')}</td>
        </tr>
      `;
      }).join('')
    : `<tr><td colspan="5" class="audit-table-empty">${escapeHtml(tx(lang, '本次诊断未发现明确问题。', 'No diagnostic issues found.'))}</td></tr>`;

  const sampleHtml = sampledPages.length
    ? sampledPages.map(item => `
        <div class="evidence-card">
          <h5>${escapeHtml(item.page_type || 'page')} · ${escapeHtml(item.url || '-')}</h5>
          <div class="kv-list">
            <div class="kv-row"><span class="kv-key">HTTP</span><span class="kv-val">${escapeHtml(String(item.status_code ?? 0))}</span></div>
            <div class="kv-row"><span class="kv-key">Title</span><span class="kv-val">${escapeHtml(String(item.title_length ?? 0))}</span></div>
            <div class="kv-row"><span class="kv-key">Meta</span><span class="kv-val">${escapeHtml(String(item.meta_description_length ?? 0))}</span></div>
            <div class="kv-row"><span class="kv-key">H1</span><span class="kv-val">${escapeHtml(String(item.h1_count ?? 0))}</span></div>
            <div class="kv-row"><span class="kv-key">Alt</span><span class="kv-val">${escapeHtml(String(item.alt_coverage_ratio ?? 0))}</span></div>
            <div class="kv-row"><span class="kv-key">Noindex</span><span class="kv-val">${escapeHtml(item.noindex_detected ? 'yes' : 'no')}</span></div>
          </div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(tx(lang, '暂无采样页面。', 'No sampled pages available.'))}</div>`;

  host.className = 'report-shell';
  const html = `
    <section class="report-hero">
      <div class="report-score-box tone-${escapeHtml(statusTone(overallStatus) || 'neutral')}">
        <div class="score-ring" style="--score:${overallScore}">
          <div>
            <strong>${escapeHtml(String(overallScore))}</strong>
            <span>/ 100</span>
          </div>
        </div>
        <div class="report-score-copy">
          <div class="report-score-label">${escapeHtml(tx(lang, 'SEO 健康分', 'SEO Health Score'))}</div>
          <div class="report-score-sub">${escapeHtml(formatStatus(summary.status || seo.status, lang))} · ${escapeHtml(tx(lang, 'Google SEO 审计', 'Google SEO Audit'))}</div>
          <div class="report-badges">
            <span class="r-badge ${escapeHtml(statusTone(overallStatus))}">${escapeHtml(formatStatus(overallStatus, lang))}</span>
            <span class="r-badge">${escapeHtml(task.mode === 'premium' ? tx(lang, 'AI 辅助', 'AI-assisted') : tx(lang, '规则诊断', 'Rule-based'))}</span>
          </div>
        </div>
      </div>
      <div class="report-hero-main">
        <div class="report-kicker">
          <span>${escapeHtml(discovery.domain || discovery.normalized_url || task.url || '-')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(tx(lang, '网站 SEO 诊断报告', 'Website SEO Report'))}</span>
        </div>
        <h3>${escapeHtml(discovery.homepage?.title || discovery.domain || task.url || '-')}</h3>
        <div class="report-summary">${escapeHtml(localizeSeoText(summary.summary || '', lang))}</div>
        <div class="report-meta-grid">
          <div class="report-meta-item url-metric"><div class="lbl">${escapeHtml(tx(lang, '审计地址', 'Audited URL'))}</div><div class="val">${escapeHtml(discovery.final_url || task.url || '-')}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(tx(lang, '检查项', 'Checks'))}</div><div class="val metric-value">${escapeHtml(String(totalChecks))}</div></div>
          <div class="report-meta-item danger-metric"><div class="lbl">${escapeHtml(tx(lang, '待优化', 'Needs work'))}</div><div class="val metric-value">${escapeHtml(String(failedChecks))}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(tx(lang, '采样页面', 'Sampled Pages'))}</div><div class="val metric-value">${escapeHtml(String(sampledCount))}</div></div>
        </div>
      </div>
    </section>

    <section class="report-section issue-table-section">
      <div class="report-section-hdr issue-section-heading"><div><h4>${escapeHtml(tx(lang, '问题清单', 'Diagnostic Issues'))}<span class="section-count">${issues.length}</span></h4><p>${escapeHtml(tx(lang, '按优先级排序，先处理影响最大的事项', 'Sorted by priority — address the highest-impact issues first'))}</p></div><div class="issue-priority-summary">${prioritySummary}</div></div>
      <div class="audit-table-wrap issue-table-wrap">
        <table class="audit-table issue-table">
          <thead><tr>
            <th scope="col">${escapeHtml(tx(lang, '检查事项', 'Check'))}</th>
            <th scope="col">${escapeHtml(tx(lang, '优先级', 'Priority'))}</th>
            <th scope="col">${escapeHtml(tx(lang, '发现的问题', 'Issue'))}</th>
            <th scope="col">${escapeHtml(tx(lang, '影响', 'Impact'))}</th>
            <th scope="col">${escapeHtml(tx(lang, '修复建议', 'Recommendation'))}</th>
          </tr></thead>
          <tbody>${issueHtml}</tbody>
        </table>
      </div>
    </section>

    <details class="report-section collapsible-section coverage-section">
      <summary class="report-section-hdr coverage-heading"><h4>${escapeHtml(tx(lang, '覆盖清单', 'Coverage Checklist'))}</h4><div class="coverage-heading-actions"><span>${escapeHtml(tx(lang, `${passedChecks} 项通过 · ${failedChecks} 项待优化 · 点击展开`, `${passedChecks} passed · ${failedChecks} need work · Expand`))}</span><a class="checklist-doc-link" href="/api-doc#seo-checklist" target="_blank" rel="noreferrer" aria-label="${escapeHtml(tx(lang, '查看全部维度与检查事项：检测清单说明', 'View all dimensions and checks: checklist guide'))}" onclick="event.stopPropagation()">${escapeHtml(tx(lang, '检测清单说明', 'Checklist Guide'))}<b>↗</b></a></div></summary>
      <div class="audit-table-wrap coverage-table-wrap">
        <table class="audit-table coverage-table">
          <thead><tr>
            <th>${escapeHtml(tx(lang, '编号', 'ID'))}</th>
            <th>${escapeHtml(tx(lang, '分类', 'Category'))}</th>
            <th>${escapeHtml(tx(lang, '检查事项', 'Check'))}</th>
            <th>${escapeHtml(tx(lang, '状态', 'Status'))}</th>
            <th>${escapeHtml(tx(lang, '诊断结论', 'Finding'))}</th>
            <th>${escapeHtml(tx(lang, '证据', 'Evidence'))}</th>
          </tr></thead>
          <tbody>${coverageHtml}</tbody>
        </table>
      </div>
    </details>

    <details class="report-section collapsible-section quick-wins-section">
      <summary class="report-section-hdr"><h4>${escapeHtml(tx(lang, '优先行动', 'Quick Wins'))}</h4><span>${escapeHtml(tx(lang, '快速查看建议先做的优化', 'Recommended starting points'))}</span></summary>
      <div class="report-section-body executive-list">${renderExecutiveList(summary.quick_wins || [], tx(lang, '暂无优先动作。', 'No quick wins.'), 'action')}</div>
    </details>

    <section class="report-section dimensions-section">
      <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, '六大维度', 'Scored Dimensions'))}</h4><span>${escapeHtml(tx(lang, '评分概览 · 展开查看问题与建议', 'Score overview · Expand for findings and recommendations'))}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${dimensionHtml}</div></div>
    </section>

    <details class="report-section collapsible-section">
      <summary class="report-section-hdr"><h4>${escapeHtml(tx(lang, '采样页面证据', 'Sampled Page Evidence'))}</h4><span>${escapeHtml(tx(lang, '展开速览 · 完整详情见「站点链接」', 'Expand preview · Full details in Site links'))}</span></summary>
      <div class="report-section-body"><div class="report-evidence-grid">${sampleHtml}</div></div>
    </details>

  `;
  host.innerHTML = html;
  setCachedReportHtml(task, lang, html);
}
