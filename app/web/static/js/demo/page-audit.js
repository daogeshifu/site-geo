import { escapeHtml, tx } from './shared.js';

// Keep site requests unchanged except for their explicit scope. Page requests
// cannot accidentally retain site crawling, graph or premium options.
export function withAuditScope(payload, scope = 'site') {
  const body = { ...payload, audit_scope: scope === 'page' ? 'page' : 'site' };
  if (body.audit_scope === 'page') {
    Object.assign(body, { mode: 'standard', full_audit: false, max_pages: 1, build_knowledge_graph: false });
    delete body.llm;
  }
  return body;
}

export function renderSinglePageReport({ task, host, lang = 'zh', setCachedReportHtml }) {
  const result = task.result || {};
  const page = result.page || {};
  const summary = result.summary || {};
  const findings = page.findings || (page.checks || []).filter(check => !check.passed);
  const issueList = findings.filter(item => item.severity !== 'advisory');
  const adviceList = findings.filter(item => item.severity === 'advisory');
  const showValue = value => typeof value === 'string' ? value : JSON.stringify(value ?? null, null, 2);
  const section = (title, items) => `<section class="single-page-section"><h3>${escapeHtml(title)} · ${items.length}</h3>${items.length ? items.map(item => `<article class="single-page-finding"><h4>${escapeHtml(item.label || item.key)}</h4><p><b>${tx(lang, '依据', 'Evidence')}</b> ${escapeHtml(showValue(item.evidence))}</p>${item.recommendation ? `<p><b>${tx(lang, '建议', 'Recommendation')}</b> ${escapeHtml(item.recommendation)}</p>` : ''}</article>`).join('') : `<p>${tx(lang, '本次检查未发现此类问题。', 'No findings in this category.')}</p>`}</section>`;
  host.className = 'report-shell';
  host.innerHTML = `<div class="single-page-report"><header><span class="workspace-kicker">${tx(lang, '单页诊断', 'SINGLE PAGE AUDIT')}</span><h2>${escapeHtml(page.title || tx(lang, '页面诊断结果', 'Page diagnosis'))}</h2><p class="single-page-url">${escapeHtml(result.requested_url || task.url)}</p><p>${tx(lang, '仅检查上述链接的响应 HTML，不访问首页或其他页面，不执行 JavaScript。', 'Only the response HTML of this URL was checked. No homepage, other pages or JavaScript execution.')}</p></header><div class="single-page-metrics"><div><strong>${escapeHtml(summary.score ?? page.overall_score ?? '—')}</strong><span>${tx(lang, '规则检查通过率', 'Rule pass rate')}</span></div><div><strong>${escapeHtml(summary.total_checks ?? page.checks?.length ?? 0)}</strong><span>${tx(lang, '检查项', 'Checks')}</span></div><div><strong>${issueList.length}</strong><span>${tx(lang, '明确问题', 'Issues')}</span></div><div><strong>${adviceList.length}</strong><span>${tx(lang, '优化建议', 'Suggestions')}</span></div></div>${section(tx(lang, '明确问题', 'Issues'), issueList)}${section(tx(lang, '优化建议', 'Suggestions'), adviceList)}</div>`;
  setCachedReportHtml?.(task, lang, host.innerHTML);
}
