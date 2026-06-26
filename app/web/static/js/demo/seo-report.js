import {
  escapeHtml,
  formatList,
  formatStatus,
  statusTone,
  tx
} from './shared.js';

function groupRoadmapByPhase(roadmap = []) {
  return roadmap.reduce((acc, item) => {
    const phase = item.phase || '31-60';
    if (!acc[phase]) acc[phase] = [];
    acc[phase].push(item);
    return acc;
  }, { '0-30': [], '31-60': [], '61-90': [] });
}

function renderRoadmapItems(items = [], lang = 'zh') {
  if (!items.length) {
    return `<div class="report-list-item">${escapeHtml(tx(lang, '暂无任务。', 'No tasks.'))}</div>`;
  }
  return items.map(item => `
    <div class="report-dim-card">
      <div class="report-dim-head">
        <span class="report-dim-name">${escapeHtml(item.task || '-')}</span>
        <span class="report-dim-pill">${escapeHtml(item.priority || '-')}</span>
      </div>
      <div class="report-dim-note"><strong>${escapeHtml(tx(lang, '问题ID', 'Issue IDs'))}:</strong> ${escapeHtml((item.related_issue_ids || []).join(', ') || '-')}</div>
      <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(tx(lang, '验收标准', 'Acceptance'))}:</strong> ${escapeHtml(item.acceptance_criteria || '-')}</div>
      <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(tx(lang, '负责团队', 'Owner'))}:</strong> ${escapeHtml(item.owner_team || '-')}</div>
    </div>
  `).join('');
}

export function renderSeoAuditReport({ task, host, lang, setCachedReportHtml }) {
  const result = task?.result || {};
  const summary = result.summary || {};
  const seo = result.seo || {};
  const discovery = result.discovery || {};
  const dimensions = Object.values(seo.dimensions || {});
  const coverageChecks = Array.isArray(seo.coverage_checks) ? seo.coverage_checks : [];
  const issues = Array.isArray(seo.issues_table) ? seo.issues_table : [];
  const sampledPages = Array.isArray(seo.sampled_pages) ? seo.sampled_pages : [];
  const roadmapGroups = groupRoadmapByPhase(Array.isArray(seo.roadmap) ? seo.roadmap : []);

  const dimensionHtml = dimensions.length
    ? dimensions.map(item => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(item.label || item.key)}</span>
            <span class="report-dim-pill">${escapeHtml(formatStatus(item.status, lang))}</span>
          </div>
          <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(item.score ?? 0))}</span></div>
          <div class="report-dim-note">${escapeHtml(item.summary || '')}</div>
          <div class="report-list" style="margin-top:10px">${formatList(item.issues || [], tx(lang, '暂无明显缺口。', 'No major gaps.'))}</div>
          <div class="report-list" style="margin-top:10px">${formatList(item.recommendations || [], tx(lang, '暂无额外建议。', 'No extra recommendations.'))}</div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(tx(lang, '暂无维度结果。', 'No dimension results.'))}</div>`;

  const coverageHtml = coverageChecks.length
    ? coverageChecks.map(item => `
        <div class="evidence-card">
          <h5>${escapeHtml(item.id)} · ${escapeHtml(item.check)}</h5>
          <div class="kv-list">
            <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '分类', 'Category'))}</span><span class="kv-val">${escapeHtml(item.category || '-')}</span></div>
            <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '状态', 'Status'))}</span><span class="kv-val">${escapeHtml(item.status || '-')}</span></div>
            <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '结论', 'Summary'))}</span><span class="kv-val">${escapeHtml(item.summary || '-')}</span></div>
            <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '证据', 'Evidence'))}</span><span class="kv-val">${escapeHtml(item.evidence || '-')}</span></div>
          </div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(tx(lang, '暂无覆盖清单。', 'No coverage checklist available.'))}</div>`;

  const issueHtml = issues.length
    ? issues.map(item => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(item.issue_id)} · ${escapeHtml(item.category || '-')}</span>
            <span class="report-dim-pill">${escapeHtml(item.priority || '-')} / ${escapeHtml(item.severity || '-')}</span>
          </div>
          <div class="report-dim-note">${escapeHtml(item.description || '-')}</div>
          <div class="report-dim-note" style="margin-top:8px"><strong>${escapeHtml(tx(lang, '建议', 'Recommendation'))}:</strong> ${escapeHtml(item.recommendation || '-')}</div>
          <div class="report-dim-note" style="margin-top:8px"><strong>${escapeHtml(tx(lang, '影响', 'Impact'))}:</strong> ${escapeHtml(item.seo_impact || '-')}</div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(tx(lang, '暂无问题表。', 'No issue backlog available.'))}</div>`;

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
      <div class="report-score-box">
        <div>
          <div class="report-score-label">${escapeHtml(tx(lang, 'SEO 健康分', 'SEO Health Score'))}</div>
          <div class="report-score-value">${escapeHtml(String(summary.overall_score ?? seo.overall_score ?? seo.score ?? 0))}</div>
          <div class="report-score-sub">${escapeHtml(formatStatus(summary.status || seo.status, lang))} · ${escapeHtml(tx(lang, 'Google SEO 审计', 'Google SEO Audit'))}</div>
        </div>
        <div class="report-badges">
          <span class="r-badge ${escapeHtml(statusTone(summary.status || seo.status))}">${escapeHtml(formatStatus(summary.status || seo.status, lang))}</span>
          <span class="r-badge">${escapeHtml(task.mode === 'premium' ? tx(lang, '会员版 / AI 辅助', 'Premium / AI-assisted') : tx(lang, '普通版 / 规则版', 'Standard / Rule-based'))}</span>
        </div>
      </div>
      <div class="report-hero-main">
        <div class="report-kicker">
          <span>${escapeHtml(discovery.domain || discovery.normalized_url || task.url || '-')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(tx(lang, '检查清单 + 问题总表 + 路线图', 'Checklist + Issue Backlog + Roadmap'))}</span>
        </div>
        <h3>${escapeHtml(discovery.homepage?.title || discovery.domain || task.url || '-')}</h3>
        <div class="report-summary">${escapeHtml(summary.summary || '')}</div>
        <div class="report-meta-grid">
          <div class="report-meta-item"><div class="lbl">${escapeHtml(tx(lang, 'URL', 'URL'))}</div><div class="val">${escapeHtml(discovery.final_url || task.url || '-')}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(tx(lang, '已检查项', 'Checks Reviewed'))}</div><div class="val">${escapeHtml(String(summary.coverage_summary?.total_checks ?? seo.coverage_summary?.total_checks ?? 0))}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(tx(lang, '失败项', 'Failed Checks'))}</div><div class="val">${escapeHtml(String(summary.coverage_summary?.failed_checks ?? seo.coverage_summary?.failed_checks ?? 0))}</div></div>
          <div class="report-meta-item"><div class="lbl">${escapeHtml(tx(lang, '采样页数', 'Sampled Pages'))}</div><div class="val">${escapeHtml(String(seo.measurements?.sampled_url_count ?? sampledPages.length))}</div></div>
        </div>
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, '六大维度', 'Scored Dimensions'))}</h4><span>${escapeHtml(tx(lang, '对齐参考模板的站点级 SEO 维度评分', 'Site-level SEO scoring aligned to the reference template'))}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${dimensionHtml}</div></div>
    </section>

    <div class="report-grid-2">
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, 'Top Issues', 'Top Issues'))}</h4><span>${escapeHtml(tx(lang, '当前最影响自然搜索表现的问题', 'The main blockers hurting organic performance right now'))}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(summary.top_issues || [], tx(lang, '暂无主要问题。', 'No major issues.'))}</div></div>
      </section>
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, 'Quick Wins', 'Quick Wins'))}</h4><span>${escapeHtml(tx(lang, '优先修复的高杠杆动作', 'High-leverage fixes to prioritize first'))}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(summary.quick_wins || [], tx(lang, '暂无优先动作。', 'No quick wins.'))}</div></div>
      </section>
    </div>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, '覆盖清单', 'Coverage Checklist'))}</h4><span>${escapeHtml(tx(lang, '记录检查过的事项，不只是问题项', 'Record what was checked, not just what failed'))}</span></div>
      <div class="report-section-body"><div class="report-evidence-grid">${coverageHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, '问题总表', 'Issue Backlog'))}</h4><span>${escapeHtml(tx(lang, '按优先级收敛为可执行整改项', 'Actionable backlog prioritized for implementation'))}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${issueHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, '采样页面证据', 'Sampled Page Evidence'))}</h4><span>${escapeHtml(tx(lang, '展示参与 SEO 审计的页面样本', 'Page samples used to support the SEO audit'))}</span></div>
      <div class="report-section-body"><div class="report-evidence-grid">${sampleHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(tx(lang, '30 / 60 / 90 天路线图', '30 / 60 / 90 Day Roadmap'))}</h4><span>${escapeHtml(tx(lang, '按阶段拆分执行顺序', 'Phase the work into realistic execution windows'))}</span></div>
      <div class="report-section-body">
        <div class="report-grid-3">
          <div><h5 style="margin:0 0 12px">${escapeHtml(tx(lang, '0-30 天', '0-30 Days'))}</h5>${renderRoadmapItems(roadmapGroups['0-30'], lang)}</div>
          <div><h5 style="margin:0 0 12px">${escapeHtml(tx(lang, '31-60 天', '31-60 Days'))}</h5>${renderRoadmapItems(roadmapGroups['31-60'], lang)}</div>
          <div><h5 style="margin:0 0 12px">${escapeHtml(tx(lang, '61-90 天', '61-90 Days'))}</h5>${renderRoadmapItems(roadmapGroups['61-90'], lang)}</div>
        </div>
      </div>
    </section>
  `;
  host.innerHTML = html;
  setCachedReportHtml(task, lang, html);
}
