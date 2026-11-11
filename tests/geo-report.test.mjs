import test from 'node:test';
import assert from 'node:assert/strict';
import { renderGeoAuditReport } from '../app/web/static/js/demo/geo-report.js';
import { getTaskStepOrder, getTaskTypeConfig } from '../app/web/static/js/demo/task-config.js';

function render(result, lang = 'zh') {
  const host = { innerHTML: '', className: '' };
  renderGeoAuditReport({ task: { url: 'https://example.com/', result }, host, lang, setCachedReportHtml: () => {} });
  return host.innerHTML;
}

test('GEO report exposes provisional score, blockers and unknown evidence without inferred perception', () => {
  const html = render({ geo: { score: 0, provisional: true, score_range: [0, 40], readiness_status: 'blocked',
    coverage: { sampled_pages: 2, evidence_coverage: .6, blocked_pages: 1 },
    blockers: [{ url: 'https://example.com/docs', reason: '<script>unsafe</script>' }],
    pages: [{ url: 'https://example.com/docs', status: 'blocked', score: null, dimensions: {
      extraction: { checks: [{ id: 'GEO-011', label: 'Render', status: 'unknown', evidence: { text: '<img onerror=alert(1)>' } }] }
    } }]
  } });
  assert.match(html, /<strong>0<\/strong>/);
  assert.match(html, /暂定/);
  assert.match(html, /待核验/);
  assert.match(html, /证据覆盖率/);
  assert.match(html, /&lt;script&gt;unsafe/);
  assert.doesNotMatch(html, /<script>unsafe|<img onerror/);
  assert.doesNotMatch(html, /ai-word-cloud|引用概率：/);
});

test('combined report preserves independent SEO summary and GEO score', () => {
  const html = render({
    geo: { score: 61, score_range: [55, 70], coverage: {}, dimensions: {} },
    summary: { overall_score: 99 },
    seo: { overall_score: 88, dimensions: {}, coverage_checks: [], issues_table: [] },
    seo_summary: { overall_score: 88 }
  }, 'en');
  assert.match(html, /SEO 88\/100 · GEO 61\/100/);
  assert.match(html, /Independent SEO results/);
  assert.match(html, /not averaged/);
  assert.doesNotMatch(html, /SEO 99/);
});

test('new task selection and step configuration stay separate from combined audits', () => {
  assert.equal(getTaskTypeConfig().heading.zh, '网站 GEO 审计');
  assert.deepEqual(getTaskStepOrder('site_geo_only_audit'), ['discovery', 'geo', 'observation', 'summary']);
  assert.deepEqual(getTaskStepOrder('site_geo_audit'), ['discovery', 'seo', 'geo', 'observation', 'summary']);
  assert.deepEqual(getTaskStepOrder('site_geo_only_audit', 'page'), ['page', 'summary']);
});
