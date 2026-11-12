import assert from 'node:assert/strict';
import test from 'node:test';
import { buildDiagnosticData, platformPolicies } from '../app/web/static/js/demo/diagnostic-data.js';
import { renderDiagnosticReport, mountDiagnosticReport } from '../app/web/static/js/demo/diagnostic-report.js';

const definitions = [
  ['access', .20, [1, 2, 3, 4, 25, 27, 28, 29]],
  ['discovery', .15, [5, 6, 7, 8, 24, 26]],
  ['extraction', .15, [9, 10, 11]],
  ['answers', .25, [12, 13, 14, 15, 16]],
  ['trust', .15, [17, 18, 19, 20]],
  ['semantics', .10, [21, 22, 23, 30]]
];
function fixture() {
  const dimensions = Object.fromEntries(definitions.map(([key, weight, ids]) => [key, {
    key, weight, label: key, score: 70, evidence_coverage: .8, earned_points: 7, measured_points: 10, applicable_points: 12,
    checks: ids.map(id => ({ id: 'SGEO-' + String(id).padStart(3, '0'), label: 'Unified check ' + id,
      dimension: key, status: id === 2 ? 'fail' : id === 11 ? 'unknown' : 'pass', blocker: id === 2,
      value: id === 2 ? 0 : id === 11 ? null : 1, max_points: 2,
      evidence: id === 2 ? { policies: { 'OAI-SearchBot': false, Googlebot: true } } : {},
      impact: 'Unified impact', recommendation: 'Unified remedy', acceptance_criteria: 'Verified on affected pages' }))
  }]));
  return { sgeo: { score: 74.6, status: 'blocked', readiness_status: 'blocked', provisional: true,
    scoring_version: 'onsite-sgeo-v1', score_range: [63, 82], coverage: { evidence_coverage: .8, blocked_pages: 1 },
    dimensions, pages: [{ url: 'https://example.com/', score: 74.6, status: 'blocked', dimensions }],
    blockers: [{ url: 'https://example.com/', check_id: 'SGEO-002', reason: 'Unified blocker' }] },
    summary: { summary: 'Unified SGEO summary' } };
}
function render(result, lang = 'zh') {
  const host = { innerHTML: '', className: '' };
  renderDiagnosticReport({ task: { url: 'https://example.com/', result }, host, lang });
  return host.innerHTML;
}

test('SGEO renders one score, one radar and six integrated dimensions in both languages', () => {
  const result = fixture();
  const original = JSON.stringify(result);
  for (const lang of ['zh', 'en']) {
    const data = buildDiagnosticData(result, lang);
    const html = render(result, lang);
    assert.equal(data.dimensions.length, 6);
    assert.equal(data.checks.length, 30);
    assert.equal((html.match(/class="dr-score-entry"/g) || []).length, 1);
    assert.equal((html.match(/class="dr-radar"/g) || []).length, 1);
    assert.equal((html.match(/<article class="report-dim-card">/g) || []).length, 6);
    assert.equal((html.match(/class="dr-coverage-item"/g) || []).length, 30);
    assert.match(html, /data-report-version="diagnostic-report-v3-sgeo"/);
    assert.match(html, /dr-score-value"><strong>74.6<\/strong>/);
    assert.match(html, /href="\/api-doc#sgeo-scoring"/);
    assert.match(html, /data-issue-dimension/);
    assert.doesNotMatch(html, /data-issue-engine|SEO 搜索健康|GEO 站内就绪度|SEO health score|On-site GEO readiness/);
    assert.doesNotMatch(html, /undefined|NaN/);
  }
  assert.equal(JSON.stringify(result), original);
});

test('saved source SEO and GEO scores and actions never leak into a unified report', () => {
  const result = { ...fixture(), seo: { overall_score: 99, dimensions: { old: { score: 99 } }, issues_table: [{ issue_id: 'old', description: 'Legacy finding' }] },
    geo: { score: 1, dimensions: { old: { score: 1 } } }, seo_summary: { quick_wins: ['Legacy action'], processing_notes: ['Legacy scoring note'] } };
  const data = buildDiagnosticData(result);
  assert.equal(data.seo, null);
  assert.equal(data.dimensions.length, 6);
  assert.equal(data.issues.length, 1);
  const html = render(result, 'en');
  assert.doesNotMatch(html, /Legacy finding|Legacy action|Legacy scoring note|SEO 99\/100|GEO 1\/100/);
  assert.match(html, /Unified SGEO summary/);
});

test('one issue survives multiple affected pages with shared impact and acceptance', () => {
  const result = fixture();
  result.sgeo.pages.push({ ...result.sgeo.pages[0], url: 'https://example.com/docs' });
  const data = buildDiagnosticData(result);
  assert.equal(data.issues.length, 1);
  assert.equal(data.issues[0].priority, 'P0');
  assert.equal(data.issues[0].engine, 'SGEO');
  assert.equal(data.issues[0].affected_urls.length, 2);
  assert.equal(data.pending.length, 1);
  const html = render(result);
  assert.match(html, /Unified impact/);
  assert.match(html, /Verified on affected pages/);
  assert.equal(platformPolicies(result.sgeo).find(p => p.crawler === 'OAI-SearchBot').blocked, 2);
});

test('unified dimension filter combines with priority and updates the visible issue count', () => {
  const handlers = {};
  const rows = [
    { dataset: { search: 'crawler blocked', dimension: 'access', priority: 'P0' } },
    { dataset: { search: 'missing publisher', dimension: 'trust', priority: 'P2' } }
  ];
  const controls = { '[data-issue-dimension]': { value: 'trust' }, '[data-issue-priority]': { value: '' }, '[data-issue-count]': {}, '[data-issue-empty]': {} };
  const host = {
    querySelector: selector => selector === '.diagnostic-report' ? {} : controls[selector],
    querySelectorAll: () => rows,
    addEventListener: (name, handler) => { handlers[name] = handler; }
  };
  mountDiagnosticReport(host);
  handlers.change({ target: { matches: () => true } });
  assert.equal(rows[0].hidden, true);
  assert.equal(rows[1].hidden, false);
  assert.equal(controls['[data-issue-count]'].textContent, '1 / 2');
  controls['[data-issue-priority]'].value = 'P0';
  handlers.change({ target: { matches: () => true } });
  assert.ok(rows.every(row => row.hidden));
  assert.equal(controls['[data-issue-empty]'].hidden, false);
});
