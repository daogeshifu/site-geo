import assert from 'node:assert/strict';
import test from 'node:test';
import { buildDiagnosticData, platformPolicies } from '../app/web/static/js/demo/diagnostic-data.js';
import { mountDiagnosticReport, renderDiagnosticReport } from '../app/web/static/js/demo/diagnostic-report.js';

function render(result, lang = 'zh') {
  const host = { innerHTML: '', className: '' };
  let cached;
  renderDiagnosticReport({ task: { url: 'https://example.com/', result }, host, lang, setCachedReportHtml: (_task, _lang, html) => { cached = html; } });
  assert.equal(cached, host.innerHTML);
  return host.innerHTML;
}
function page(url, check) {
  return { url, dimensions: { access: { key: 'access', label: '可达性', checks: [check] } } };
}
const check = { id: 'GEO-002', label: '路径策略', dimension: 'access', status: 'pass', max_points: 7, recommendation: '解除检索阻断', evidence: {} };

test('mixed measured passes and unknown pages remain unverified, without inventing an issue', () => {
  const result = { geo: { dimensions: { access: { key: 'access', checks: [{ ...check, status: 'partial', evidence: { page_status_counts: { pass: 1, unknown: 1 } } }] } },
    pages: [page('https://example.com/', check), page('https://example.com/docs', { ...check, status: 'unknown' })] } };
  const original = JSON.stringify(result);
  const data = buildDiagnosticData(result);
  assert.equal(data.issues.length, 0);
  assert.equal(data.pending.length, 1);
  assert.equal(data.checks[0].status, 'unknown');
  assert.deepEqual(data.pending[0].unknown_urls, ['https://example.com/docs']);
  assert.equal(JSON.stringify(result), original);
});

test('measured failures survive unknowns and retain the affected URL and blocker priority', () => {
  const data = buildDiagnosticData({ geo: { pages: [
    page('https://example.com/blocked', { ...check, status: 'fail', blocker: true }),
    page('https://example.com/unknown', { ...check, status: 'unknown' })
  ] } });
  assert.equal(data.issues.length, 1);
  assert.equal(data.issues[0].priority, 'P0');
  assert.deepEqual(data.issues[0].affected_urls, ['https://example.com/blocked']);
  assert.equal(data.pending.length, 1);
});

test('older aggregate-only results keep missing evidence separate from measured failure', () => {
  const data = buildDiagnosticData({ geo: { dimensions: { access: { key: 'access', checks: [
    { ...check, status: 'partial', evidence: { page_status_counts: { pass: 1, unknown: 1 } } },
    { ...check, id: 'GEO-003', status: 'fail' }
  ] } } } });
  assert.equal(data.pending.length, 1);
  assert.deepEqual(data.issues.map(issue => issue.id), ['GEO-003']);
});

test('zero scores and missing scores render distinctly', () => {
  const html = render({ geo: { score: null, dimensions: { empty: { key: 'empty', label: '未测', score: null }, zero: { key: 'zero', label: '已测', score: 0 } } } });
  assert.match(html, /dr-score-value"><strong>—<\/strong>/);
  assert.match(html, /class="score">0<small>\/100/);
  assert.match(html, /class="score">—<small>\/100/);
  assert.doesNotMatch(html, /NaN|undefined/);
});

test('combined reports retain every SEO and GEO dimension and checklist row', () => {
  const result = {
    seo: {
      overall_score: 80,
      dimensions: Object.fromEntries(Array.from({ length: 6 }, (_, i) => ['s' + i, { key: 's' + i, label: 'SEO dimension ' + i, score: 80 }])),
      coverage_checks: Array.from({ length: 26 }, (_, i) => ({ id: 'CHK-' + String(i + 1).padStart(3, '0'), check: 'SEO check ' + i, status: 'pass' }))
    },
    geo: {
      score: 40,
      dimensions: Object.fromEntries(Array.from({ length: 6 }, (_, i) => ['g' + i, { key: 'g' + i, label: 'GEO dimension ' + i, score: 40, checks: [] }])),
      pages: [{ url: 'https://example.com/', dimensions: { all: { checks: Array.from({ length: 23 }, (_, i) => ({ id: 'GEO-' + String(i + 1).padStart(3, '0'), label: 'GEO check ' + i, status: 'unknown' })) } } }]
    }
  };
  const data = buildDiagnosticData(result);
  assert.equal(data.dimensions.length, 12);
  assert.equal(data.checks.length, 49);
  const html = render(result, 'en');
  assert.equal((html.match(/<article class="report-dim-card">/g) || []).length, 12);
  for (const check of data.checks) assert.ok(html.includes(check.id), check.id);
  assert.match(html, /SEO 80\/100 · GEO 40\/100/);
  assert.match(html, /not averaged/);
});

test('SEO issues use their own score and evidence, regardless of the combined summary', () => {
  const html = render({ summary: { overall_score: 99 }, seo_summary: { overall_score: 88 }, geo: { score: 20 }, seo: {
    overall_score: 88, issues_table: [{ issue_id: 'SEO-1', description: 'Broken title', evidence: 'Unique evidence URL', priority: 'P0', recommendation: 'Repair it', acceptance_criteria: 'One visible title' }]
  } }, 'en');
  assert.match(html, /SEO 88\/100 · GEO 20\/100/);
  assert.match(html, /Unique evidence URL/);
  assert.match(html, /One visible title/);
  assert.doesNotMatch(html, /SEO 99/);
});

test('platform path evidence preserves blocked and unknown states without fictional scores', () => {
  const geo = { pages: [page('https://example.com/a', { ...check, evidence: { policies: { Googlebot: true, 'OAI-SearchBot': false } } }), page('https://example.com/b', check)] };
  const policies = platformPolicies(geo);
  assert.deepEqual(policies.find(item => item.crawler === 'OAI-SearchBot').pages.map(item => item.allowed), [false, null]);
  const html = render({ geo });
  assert.match(html, /Gemini/);
  assert.match(html, /<h4>ChatGPT<\/h4><span class="dr-state dr-state-blocked">/);
  assert.match(html, /未采集独立平台抓取证据/);
  assert.doesNotMatch(html, /platform_score|citation_probability/);
});

test('unsafe URLs, evidence, schema and labels are escaped throughout the report', () => {
  const unsafe = '<img src=x onerror=alert(1)>';
  const html = render({ geo: { pages: [page('javascript:alert(1)', { ...check, label: unsafe, evidence: { html: unsafe } })], blockers: [{ reason: unsafe, url: 'javascript:alert(1)' }] }, discovery: { homepage: { title: unsafe }, schema_summary: { unsafe } } });
  assert.doesNotMatch(html, /<img |href="javascript:/);
  assert.match(html, /&lt;img/);
});

test('legacy partial SEO data renders usable empty states in both languages', () => {
  for (const lang of ['zh', 'en']) {
    const html = render({ seo: { overall_score: 0 } }, lang);
    assert.match(html, /data-report-version="diagnostic-report-v2"/);
    assert.match(html, /colspan="5"/);
    assert.doesNotMatch(html, /NaN|undefined/);
  }
});

test('report navigation opens its section without triggering workspace history reload', () => {
  const handlers = {};
  let scrolls = 0;
  const section = { tagName: 'DETAILS', open: false, scrollIntoView: () => { scrolls++; } };
  const host = {
    querySelector: selector => selector === '.diagnostic-report' ? {} : selector === '#diagnosis-coverage' ? section : null,
    addEventListener: (name, handler) => { handlers[name] = handler; }
  };
  const link = { getAttribute: () => '#diagnosis-coverage', hasAttribute: () => false };
  const event = new Event('click', { cancelable: true });
  Object.defineProperty(event, 'target', { value: { closest: () => link } });
  mountDiagnosticReport(host);
  handlers.click(event);
  assert.equal(event.defaultPrevented, true);
  assert.equal(section.open, true);
  assert.equal(scrolls, 1);
});

