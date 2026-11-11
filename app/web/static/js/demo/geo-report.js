import { escapeHtml, tx } from './shared.js';
import { renderSeoAuditReport } from './seo-report.js?v=20260909-checklist';

const labels = {
  pass: ['通过', 'Pass'], partial: ['部分满足', 'Partial'], fail: ['待整改', 'Fail'],
  unknown: ['待核验', 'Unverified'], na: ['不适用', 'N/A'], blocked: ['存在阻断', 'Blocked'],
  provisional: ['暂定评分', 'Provisional'], unverified: ['待核验', 'Unverified'],
  ready: ['就绪', 'Ready'], needs_work: ['待优化', 'Needs work']
};
const state = (value, lang) => labels[value] ? tx(lang, ...labels[value]) : value || '—';
const percentage = value => `${Math.round(Number(value || 0) * 100)}%`;
const number = value => value == null ? '—' : String(Math.round(Number(value) * 10) / 10);
const list = items => items.map(item => `<li>${escapeHtml(item)}</li>`).join('');
const link = url => /^https?:\/\//i.test(url || '')
  ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>`
  : escapeHtml(url);

export function renderGeoAuditReport({ task, host, lang = 'zh', setCachedReportHtml }) {
  const result = task?.result || {};
  const geo = result.geo || {};
  const coverage = geo.coverage || {};
  const dimensions = Object.values(geo.dimensions || {});
  const pages = geo.pages || [];
  const blockers = geo.blockers || [];
  const dimensionHtml = dimensions.map(d => `<article class="report-dim-card">
    <div class="report-dim-head"><span class="report-dim-name">${escapeHtml(d.label)}</span><span class="report-dim-pill">${percentage(d.weight)}</span></div>
    <div class="report-dim-scoreline"><span class="score">${number(d.score)}<small>/100</small></span></div>
    <p>${tx(lang, '证据覆盖率', 'Evidence coverage')} ${percentage(d.evidence_coverage)}</p>
    <details class="dimension-details"><summary>${tx(lang, '查看计分规则', 'Scoring checks')}</summary><ul class="geo-check-list">${(d.checks || []).map(c => `<li><b>${escapeHtml(c.id)} · ${escapeHtml(c.label)}</b><span>${escapeHtml(state(c.status, lang))} · ${number(c.max_points)} ${tx(lang, '分', 'pts')}</span></li>`).join('')}</ul></details>
  </article>`).join('');
  const pageHtml = pages.map(page => `<details class="geo-page-evidence"><summary>${link(page.url)} <span>${escapeHtml(state(page.status, lang))} · ${number(page.score)}/100</span></summary>
    <p>${escapeHtml(page.page_type)} · ${tx(lang, '证据覆盖率', 'Evidence coverage')} ${percentage(page.evidence_coverage)}</p>
    <div class="audit-table-wrap"><table class="audit-table"><thead><tr><th>${tx(lang, '检查项', 'Check')}</th><th>${tx(lang, '状态', 'State')}</th><th>${tx(lang, '证据与建议', 'Evidence and recommendation')}</th></tr></thead><tbody>${Object.values(page.dimensions || {}).flatMap(d => (d.checks || []).map(c => `<tr><td>${escapeHtml(c.id)}<br>${escapeHtml(c.label)}</td><td>${escapeHtml(state(c.status, lang))}${c.blocker ? ` · ${tx(lang, '阻断', 'Blocker')}` : ''}</td><td><pre class="geo-evidence-json">${escapeHtml(JSON.stringify(c.evidence || {}, null, 2))}</pre>${['fail', 'partial'].includes(c.status) ? `<p>${escapeHtml(c.recommendation)}</p>` : ''}${c.evidence_type === 'structural_proxy' ? `<small>${tx(lang, '结构代理检查，未作事实核查。', 'Structural proxy; not fact-checked.')}</small>` : ''}</td></tr>`)).join('')}</tbody></table></div></details>`).join('');
  let seoHtml = '';
  if (result.seo) {
    const seoHost = { innerHTML: '', className: '' };
    renderSeoAuditReport({ task: { ...task, result: { ...result, summary: result.seo_summary || {} } }, host: seoHost, lang, setCachedReportHtml: () => {} });
    seoHtml = `<section class="geo-separate-seo"><h2>${tx(lang, '独立 SEO 审计结果', 'Independent SEO results')}</h2><p>${tx(lang, 'SEO 使用自己的维度与权重；外链支持信号、OG/Twitter 等不计入上述 GEO 分数。两项分数不取平均。', 'SEO uses its own dimensions and weights. Backlink support signals and OG/Twitter cards do not enter the GEO score above. The scores are not averaged.')}</p>${seoHost.innerHTML}</section>`;
  }
  host.className = 'report-shell';
  host.innerHTML = `<div class="geo-readiness-report">
    <header><span class="workspace-kicker">ON-SITE GEO READINESS</span><h2>${tx(lang, result.seo ? '网站 SEO+GEO 审计' : '网站 GEO 审计', result.seo ? 'Website SEO + GEO Audit' : 'Website GEO Audit')}</h2><p>${link(task.url || result.url)}</p></header>
    <div class="single-page-metrics"><div><strong>${number(geo.score)}</strong><span>${tx(lang, '站内 GEO 就绪度', 'On-site GEO readiness')}${geo.provisional ? ` · ${tx(lang, '暂定', 'provisional')}` : ''}</span></div><div><strong>${percentage(coverage.evidence_coverage)}</strong><span>${tx(lang, '加权证据覆盖率', 'Weighted evidence coverage')}</span></div><div><strong>${coverage.sampled_pages || 0}</strong><span>${tx(lang, '采样页面', 'Sampled pages')}</span></div><div><strong>${coverage.blocked_pages || 0}</strong><span>${tx(lang, '存在阻断的页面', 'Pages with blockers')}</span></div></div>
    <p class="geo-readiness-notice"><b>${escapeHtml(state(geo.readiness_status, lang))}</b> · ${tx(lang, '分数区间', 'Score bounds')} ${(geo.score_range || []).map(number).join('–')} · ${escapeHtml(geo.scoring_version || '')}</p>
    <p>${tx(lang, '已发现候选页面', 'Known candidate pages')} ${coverage.known_candidate_pages || 0}；${tx(lang, '采样占候选比例', 'Sample-to-candidate ratio')} ${percentage(coverage.sample_coverage)}。${tx(lang, '该比例不代表全站覆盖率。', 'This is not whole-site coverage.')}</p>
    ${result.seo ? `<p class="geo-readiness-notice">SEO ${number(result.seo.overall_score)}/100 · GEO ${number(geo.score)}/100 — ${tx(lang, '两套独立评分，共享页面证据。', 'Independent scores, shared page evidence.')}</p>` : ''}
    <section><h3>${tx(lang, '关键阻断', 'Critical blockers')}</h3>${blockers.length ? `<ul class="geo-blockers">${blockers.map(b => `<li><strong>${escapeHtml(b.reason)}</strong> · ${link(b.url)}</li>`).join('')}</ul>` : `<p>${tx(lang, '已测项目未发现阻断；待核验项目仍需补充证据。', 'No blockers in measured checks. Unverified checks still need evidence.')}</p>`}</section>
    <section><h3>${tx(lang, '六维评分', 'Six scoring dimensions')}</h3><div class="report-dim-grid">${dimensionHtml}</div></section>
    <section><h3>${tx(lang, '逐页证据与整改建议', 'Page evidence and recommendations')}</h3>${pageHtml}</section>
    <section><h3>${tx(lang, '方法与限制', 'Methodology and limits')}</h3><ul>${list(geo.processing_notes || [])}</ul><p>${tx(lang, 'llms.txt、训练授权、社交卡片、一般安全响应头及站外权威不计入 GEO 总分。实际收录与 AI 引用单独验证。', 'llms.txt, training permission, social cards, general security headers, and external authority are excluded. Actual indexing and AI citations require separate verification.')}</p></section>
    ${result.observation?.provided ? `<section><h3>${tx(lang, '独立观测（不计分）', 'Unscored observations')}</h3><pre class="geo-evidence-json">${escapeHtml(JSON.stringify(result.observation.metrics || {}, null, 2))}</pre></section>` : ''}
    ${seoHtml}</div>`;
  setCachedReportHtml?.(task, lang, host.innerHTML);
}
