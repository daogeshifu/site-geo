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
    platform: {
      score: 70,
      platform_scores: {
        chatgpt: { platform_score: 76, optimization_focus: '可引用事实', primary_gap: '证据不足', preferred_sources: ['官网', '行业媒体'], key_recommendations: ['增加数据来源'] },
        perplexity: { platform_score: 62 },
        grok: { platform_score: 99 }
      }
    },
    page_diagnostics: [{
      page_type: 'homepage', source: 'core', url: 'https://example.com', overall_score: 66,
      citability_score: 61, content_score: 72, technical_score: 68, schema_score: 40,
      issue_details: { content: ['缺少来源'] }, recommendation_details: { content: ['补充引用'] }
    }]
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
  assert.ok(html.indexOf('combined-score-panel') < html.indexOf('combined-report-main'));
  assert.ok(html.indexOf('combined-report-main') < html.indexOf('combined-radar-panel'));
  assert.ok(html.indexOf('问题清单') < html.indexOf('AI 认知图'));
  assert.ok(html.indexOf('AI 认知图') < html.indexOf('6 个汇总维度评估'));
  assert.match(html, /SEO 覆盖清单/);
  assert.match(html, /summary-insight-section risk/);
  assert.match(html, /platform-readiness-card platform-chatgpt/);
  assert.doesNotMatch(html, />Grok</);
  assert.doesNotMatch(html, /优先行动计划/);
  assert.doesNotMatch(html, /Observation Layer/);
  assert.doesNotMatch(html, /指标说明/);
  assert.match(html, /<h4>页面诊断<\/h4>/);
  assert.match(html, /AI 可引用性/);
  assert.match(html, /首页/);
});

test('page diagnostics title follows the report language', () => {
  const html = render({
    summary: { composite_geo_score: 60 },
    page_diagnostics: [{ page_type: 'product', url: 'https://example.com/p', overall_score: 60 }]
  }, 'en');
  assert.match(html, /<h4>Page Diagnostics<\/h4>/);
  assert.match(html, /AI Citability/);
  assert.doesNotMatch(html, /<h4>页面诊断<\/h4>/);
});

test('combined audit report explains missing SEO data for older cached tasks', () => {
  const html = render({ summary: { composite_geo_score: 0, status: 'critical' } });
  assert.match(html, /旧缓存请强制刷新/);
  assert.match(html, /旧任务暂无 SEO 覆盖数据/);
});

test('perception clouds expand from observed signals and key issues cover distinct dimensions', () => {
  const html = render({
    discovery: { site_signals: { company_name_detected: true, same_as_detected: true, email_detected: false } },
    content: { findings: { has_faq_any: true, has_reference_section_any: false, has_quantified_data_any: true, has_publish_date_any: false, has_author_any: true } },
    technical: { checks: { unique_h1: true } },
    schema: { findings: { schema_type_count: 1 } },
    visibility: { findings: { llms_quality: { score: 35 }, citability: { score: 45 } } },
    summary: {
      composite_geo_score: 55,
      ai_perception: { cognition_keywords: ['值得信赖', '结构待强化'] },
      weighted_scores: {
        'Content Quality & E-E-A-T': { raw_score: 35 },
        'Brand Authority Signals': { raw_score: 81 },
        'Technical Foundations': { raw_score: 76 }
      },
      dimensions: {
        'Content Quality & E-E-A-T': { display_name: '内容与 E-E-A-T', score: 35, issues: ['作者缺失', '证据不足', '内容太短'] },
        'Brand Authority Signals': { display_name: '品牌权威', score: 40, issues: ['第三方引用较少'] },
        'Technical Foundations': { display_name: '技术基础', score: 62, issues: ['部分页面加载慢'] }
      },
      top_issues: ['内容与 E-E-A-T: 作者缺失', '内容与 E-E-A-T: 证据不足']
    }
  });
  const positive = html.match(/<div class="ai-word-cloud positive">[\s\S]*?<\/div><\/div>/)?.[0] || '';
  const limited = html.match(/<div class="ai-word-cloud limited">[\s\S]*?<\/div><\/div>/)?.[0] || '';
  assert.ok((positive.match(/class="ai-word /g) || []).length >= 6);
  assert.ok((limited.match(/class="ai-word /g) || []).length >= 6);
  assert.match(positive, /品牌身份明确/);
  assert.match(limited, /参考来源不足/);
  assert.match(limited, /结构待强化/);
  const keyIssues = html.match(/<div class="summary-insight-list risk">[\s\S]*?<\/div><\/div>/)?.[0] || '';
  assert.equal((keyIssues.match(/内容与 E-E-A-T:/g) || []).length, 1);
  assert.match(keyIssues, /品牌权威: 第三方引用较少/);
  assert.match(keyIssues, /技术基础: 部分页面加载慢/);
});
