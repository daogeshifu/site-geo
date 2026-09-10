import assert from 'node:assert/strict';
import test from 'node:test';
import { renderSiteAuditReport } from '../app/web/static/js/demo/site-report.js';

function render(result = {}, lang = 'zh') {
  const host = {};
  let cached;
  renderSiteAuditReport({
    task: { url: 'https://example.com', mode: 'standard', result },
    host,
    lang,
    setCachedReportHtml: (_task, _lang, html) => { cached = html; }
  });
  assert.equal(host.innerHTML, cached);
  return host.innerHTML;
}

test('combined audit report follows the overview, issues, AI cognition, and dimensions order', () => {
  const html = render({
    discovery: { domain: 'example.com', site_snapshot_version: 'snapshot-v3', profiled_page_count: 4 },
    summary: {
      composite_geo_score: 77,
      status: 'good',
      summary: '综合表现良好。',
      weighted_scores: {
        'AI Citability & Visibility': { raw_score: 87 },
        'Brand Authority Signals': { raw_score: 82 },
        'Content Quality & E-E-A-T': { raw_score: 74 },
        'Technical Foundations': { raw_score: 79 },
        'Structured Data': { raw_score: 41 },
        'Platform Optimization': { raw_score: 73 }
      },
      ai_perception: {
        positive_percentage: 58,
        neutral_percentage: 22,
        controversial_percentage: 20,
        cognition_keywords: ['值得信赖', '信息清晰', '结构化不足']
      }
    },
    seo: {
      coverage_checks: [{ id: 'CHK-014', status: 'fail', category: 'On-Page SEO', check: 'Title' }],
      issues_table: [{ issue_id: 'SEO-001', check_item: '页面标题', priority: 'P1', severity: 'high', category: 'On-Page SEO', description: '标题缺失', recommendation: '补齐标题' }]
    },
    visibility: { score: 42, issues: ['AI crawler 被阻止'], recommendations: ['调整 robots.txt'], checks: { allowed_ai_crawlers: 4, total_ai_crawlers_checked: 6 } },
    content: { score: 70 },
    schema: { score: 70 },
    platform: { score: 70 }
  });

  assert.match(html, /combined-report-hero/);
  assert.match(html, /网站 SEO\+GEO 审计报告/);
  assert.match(html, /问题清单/);
  assert.match(html, /SEO \/ GEO 影响/);
  assert.match(html, /AI-001/);
  assert.match(html, /AI 认知图/);
  assert.match(html, /能力项清单与分数/);
  assert.match(html, /正面认知词云/);
  assert.match(html, /受限认知词云/);
  assert.match(html, /值得信赖/);
  assert.match(html, /结构化不足/);
  assert.match(html, /6 个汇总维度评估/);
  assert.ok(html.indexOf('combined-radar-panel') < html.indexOf('combined-report-main'));
  assert.ok(html.indexOf('问题清单') < html.indexOf('AI 认知图'));
  assert.ok(html.indexOf('AI 认知图') < html.indexOf('6 个汇总维度评估'));
  assert.match(html, /SEO 覆盖清单/);
});

test('combined audit report explains missing SEO data for older cached tasks', () => {
  const html = render({ summary: { composite_geo_score: 0, status: 'critical' } });
  assert.match(html, /旧缓存请强制刷新/);
  assert.match(html, /旧任务暂无 SEO 覆盖数据/);
});
