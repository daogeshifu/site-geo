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
      scoring_version: 'onsite-geo-v2',
      pages: [{ url: 'https://example.com/', dimensions: { all: { checks: Array.from({ length: 26 }, (_, i) => ({ id: 'GEO-' + String(i + 1).padStart(3, '0'), label: 'GEO check ' + i, status: 'unknown' })) } } }]
    }
  };
  const data = buildDiagnosticData(result);
  assert.equal(data.dimensions.length, 12);
  assert.equal(data.checks.length, 52);
  const html = render(result, 'en');
  assert.equal((html.match(/<article class="report-dim-card">/g) || []).length, 12);
  for (const check of data.checks) assert.ok(html.includes(check.id), check.id);
  assert.match(html, /SEO 80\/100 · GEO 40\/100/);
  assert.match(html, /not averaged/);
  assert.equal((html.match(/class="dr-coverage-item"/g) || []).length, 52);
});

test('coverage cards retain every ID, label and state in both languages, including old 23-check reports', () => {
  for (const count of [23, 26]) {
    const states = ['pass', 'fail', 'partial', 'unknown', 'na'];
    const checks = Array.from({ length: count }, (_, i) => ({ id: 'GEO-' + String(i + 1).padStart(3, '0'),
      label: `Check ${i + 1}`, status: states[i % states.length] }));
    for (const lang of ['zh', 'en']) {
      const html = render({ geo: { scoring_version: count === 23 ? 'onsite-geo-v1' : 'onsite-geo-v2',
        dimensions: { all: { checks } } } }, lang);
      const coverage = html.split('id="diagnosis-coverage"')[1].split('id="diagnosis-dimensions"')[0];
      assert.equal((coverage.match(/class="dr-coverage-item"/g) || []).length, count);
      assert.doesNotMatch(coverage, /<table|查看原始证据|View raw evidence/);
      for (const check of checks) {
        assert.ok(coverage.includes(`data-check-id="${check.id}"`));
        assert.ok(coverage.includes(`<strong>${check.label}</strong>`));
        assert.ok(coverage.includes(`dr-state-${check.status}`));
      }
    }
  }
});

test('six GEO dimensions use stage prefixes and concrete diagnostics without changing historical scores or IDs', () => {
  const definitions = [
    ['access', '访问与抓取可达性', '可获取：', 'Retrievable:', 'GEO-001', 20],
    ['discovery', '页面发现与可索引性', '可获取：', 'Retrievable:', 'GEO-007', 15],
    ['extraction', '正文读取与信息提取', '可理解：', 'Understandable:', 'GEO-009', 20],
    ['answers', '内容价值与答案适配', '可引用：', 'Citable:', 'GEO-012', 25],
    ['trust', '站内可信度与时效性', '可推荐：', 'Recommendable:', 'GEO-017', 15],
    ['semantics', '元数据与实体语义', '可理解：', 'Understandable:', 'GEO-023', 5]
  ];
  const result = { geo: { score: 76.4, dimensions: Object.fromEntries(definitions.map(([key, label, , , id, weight]) =>
    [key, { label, score: 72, weight: weight / 100, checks: [{ id, label: 'Existing diagnostic description', status: 'partial', max_points: 2 }] }])) } };
  const original = JSON.stringify(result);
  for (const lang of ['zh', 'en']) {
    const data = buildDiagnosticData(result, lang);
    for (const [key, , zhPrefix, enPrefix, id, weight] of definitions) {
      const dimension = data.dimensions.find(item => item.key === key);
      assert.ok(dimension.label.startsWith(lang === 'zh' ? zhPrefix : enPrefix));
      assert.equal(dimension.score, 72);
      assert.equal(dimension.weight, weight / 100);
      assert.equal(data.checks.find(item => item.id === id).dimension, key);
    }
    const html = render(result, lang);
    const dimensions = html.split('id="diagnosis-dimensions"')[1].split('id="diagnosis-actions"')[0];
    assert.match(dimensions, /HTTP \/ HTTPS/);
    assert.match(dimensions, /JSON-LD \/ Schema.org/);
    assert.equal((dimensions.match(/class="dr-diagnostic-name"/g) || []).length, 6);
    assert.doesNotMatch(dimensions.replace(/<[^>]*>/g, ''), /GEO-\d{3}/);
    assert.match(html.split('id="diagnosis-coverage"')[1], /<code>GEO-001<\/code>/);
    assert.match(dimensions, lang === 'zh' ? /实际推荐需独立验证/ : /actual recommendations need separate verification/);
  }
  assert.equal(JSON.stringify(result), original);
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

test('page preview caps merged SEO and GEO pages at eight without changing the full report data', () => {
  const urls = Array.from({ length: 12 }, (_, index) => `https://example.com/page-${index + 1}`);
  const result = {
    geo: { pages: urls.slice(0, 6).map(url => page(url, check)) },
    seo: { sampled_pages: urls.slice(3).map(url => ({ url, status_code: 200 })) }
  };
  const original = JSON.stringify(result);
  const html = render(result);
  assert.equal((html.match(/class="dr-page"/g) || []).length, 8);
  for (const url of urls.slice(0, 8)) assert.ok(html.includes(`data-page-url="${url}"`));
  for (const url of urls.slice(8)) assert.ok(!html.includes(`data-page-url="${url}"`));
  assert.match(html, /已展示 8 \/ 12 个采样页面/);
  assert.match(html, /href="#tab-site-links" data-open-site-links/);
  for (const id of ['diagnosis-pages', 'diagnosis-snapshot']) assert.ok(html.includes(`id="${id}" open`));
  assert.equal(buildDiagnosticData(result).pages.length, 12);
  assert.equal(JSON.stringify(result), original);
});

for (const action of ['view-more', 'page-outside-preview']) {
  test(`${action} opens the Site links tab without changing the URL or opening the wrong page`, () => {
    const handlers = {};
    let clicks = 0, focus = 0;
    const firstPage = { dataset: { pageUrl: 'https://example.com/first' }, open: false };
    const section = { tagName: 'DETAILS', open: true, querySelectorAll: () => [firstPage] };
    const tab = { click: () => { clicks++; }, focus: () => { focus++; } };
    const host = {
      ownerDocument: { querySelector: selector => selector === '[data-tab="site-links"]' ? tab : null },
      querySelector: selector => selector === '.diagnostic-report' ? {} : selector === '#diagnosis-pages' ? section : null,
      addEventListener: (name, handler) => { handlers[name] = handler; }
    };
    const link = {
      getAttribute: () => action === 'view-more' ? '#tab-site-links' : '#diagnosis-pages',
      hasAttribute: name => name === (action === 'view-more' ? 'data-open-site-links' : 'data-open-pages'),
      dataset: { targetPage: 'https://example.com/ninth' }
    };
    const event = new Event('click', { cancelable: true });
    Object.defineProperty(event, 'target', { value: { closest: () => link } });
    mountDiagnosticReport(host);
    handlers.click(event);
    assert.equal(event.defaultPrevented, true);
    assert.equal(clicks, 1);
    assert.equal(focus, 1);
    assert.equal(firstPage.open, false);
  });
}

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

