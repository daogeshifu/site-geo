import assert from 'node:assert/strict';
import test from 'node:test';
import { renderSeoAuditReport } from '../app/web/static/js/demo/seo-report.js';

function render(seo = {}, lang = 'zh') {
  const host = {};
  let cached;
  renderSeoAuditReport({
    task: { url: 'https://example.com', result: { seo } }, host, lang,
    setCachedReportHtml: (_task, _lang, html) => { cached = html; }
  });
  assert.equal(host.innerHTML, cached);
  return host.innerHTML;
}

test('issues precede coverage and compact, collapsed dimensions', () => {
  const html = render({ dimensions: { technical: { label: 'Technical SEO', score: 64, issues: ['A'] } } });
  assert.ok(html.indexOf('issue-table-section') < html.indexOf('覆盖清单'));
  assert.ok(html.indexOf('覆盖清单') < html.indexOf('dimensions-section'));
  assert.match(html, /<details class="dimension-details">/);
  assert.doesNotMatch(html, /<details class="dimension-details" open/);
  assert.doesNotMatch(html, /核心问题/);
  assert.doesNotMatch(html, /30 \/ 60 \/ 90/);
  assert.match(html, /href="\/api-doc#seo-checklist"/);
});

test('historical issues sort by priority and severity without mutating source', () => {
  const issues = [
    { issue_id: 'late', priority: 'P2', severity: 'medium' },
    { issue_id: 'high', priority: 'P0', severity: 'high' },
    { issue_id: 'urgent', priority: 'P0', severity: 'critical', description: '<script>unsafe</script>' }
  ];
  const html = render({ issues_table: issues });
  assert.ok(html.indexOf('<code>urgent</code>') < html.indexOf('<code>high</code>'));
  assert.ok(html.indexOf('<code>high</code>') < html.indexOf('<code>late</code>'));
  assert.equal(issues[0].issue_id, 'late');
  assert.match(html, /&lt;script&gt;unsafe&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /P0<strong>2<\/strong>/);
});

test('issues show a concise check name above small dimension metadata', () => {
  const html = render({
    coverage_checks: [{ id: 'CHK-014', summary: '采样页存在 title 缺失或长度明显异常。' }],
    issues_table: [{ issue_id: 'P-001', category: 'On-Page SEO', priority: 'P1', description: '采样页存在 title 缺失或长度明显异常。' }]
  });
  assert.match(html, /issue-check-title">页面标题/);
  assert.match(html, /issue-meta"><span>页面 SEO<\/span><code>P-001/);
});

test('empty report renders a five-column empty state in both languages', () => {
  assert.match(render(), /colspan="5"/);
  assert.match(render({}, 'en'), /No diagnostic issues found/);
});
