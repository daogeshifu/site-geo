import { tx } from './shared.js';

const SEO_NAMES = [
  ['Robots', 'Robots'], ['站点地图', 'Sitemap'], ['数据追踪', 'Analytics'],
  ['HTTPS', 'HTTPS'], ['主域统一', 'Host'], ['URL 规范', 'URL'],
  ['结构化数据', 'Schema'], ['HTTP 状态', 'HTTP status'], ['移动适配', 'Mobile'],
  ['页面性能', 'Performance'], ['多语言', 'Hreflang'], ['索引指令', 'Noindex'],
  ['JS 渲染', 'Rendering'], ['页面标题', 'Title'], ['页面描述', 'Description'],
  ['标题层级', 'Headings'], ['规范链接', 'Canonical'], ['语言声明', 'Language'],
  ['图片文本', 'Image alt'], ['内部链接', 'Internal links'], ['页面体量', 'Payload'],
  ['图片加载', 'Image loading'], ['内容深度', 'Content depth'], ['内容可信度', 'E-E-A-T'],
  ['内容引用', 'Citability'], ['AI 可见性', 'AI visibility']
];
const CATEGORY_NAMES = {
  'Technical SEO': '技术 SEO', 'Content Quality': '内容质量', 'On-Page SEO': '页面 SEO',
  'Schema': '结构化数据', 'Core Web Vitals / Performance': '性能体验',
  'Performance': '性能体验', 'AI Search / GEO': 'AI 搜索 / GEO',
  'Image SEO': '图片 SEO', 'International SEO': '国际 SEO', 'Measurement': '数据衡量'
};
const STATES = {
  pass: ['通过', 'Pass'], fail: ['待整改', 'Needs work'], partial: ['部分满足', 'Partial'],
  unknown: ['待核验', 'Unverified'], na: ['不适用', 'N/A'], blocked: ['存在阻断', 'Blocked'],
  provisional: ['暂定评分', 'Provisional'], unverified: ['待核验', 'Unverified'],
  ready: ['就绪', 'Ready'], needs_work: ['待优化', 'Needs work'],
  critical: ['严重', 'Critical'], poor: ['较弱', 'Poor'], fair: ['一般', 'Fair'],
  good: ['良好', 'Good'], strong: ['优秀', 'Strong']
};
export const reportState = (state, lang) => STATES[state] ? tx(lang, ...STATES[state]) : state || '—';
export const localizeCategory = (name, lang) => lang === 'zh' ? CATEGORY_NAMES[name] || name : name;
export const checkName = (id, fallback, lang) => {
  const names = SEO_NAMES[Number(String(id).replace('CHK-', '')) - 1];
  return names ? tx(lang, ...names) : fallback || tx(lang, '站点检查', 'Site check');
};
export const displayNumber = value => value == null || !Number.isFinite(Number(value)) ? '—' : String(Math.round(Number(value) * 10) / 10);
export const displayPercent = value => value == null ? '—' : displayNumber(Number(value) * 100) + '%';
export const sortIssues = issues => [...issues].sort((a, b) =>
  (Number(String(a.priority || 'P4').slice(1)) - Number(String(b.priority || 'P4').slice(1))) ||
  (({ critical: 0, high: 1, medium: 2, low: 3 }[a.severity] ?? 4) -
   ({ critical: 0, high: 1, medium: 2, low: 3 }[b.severity] ?? 4)));

function geoPriority(check) {
  return check.blocker ? 'P0' : ['access', 'extraction', 'discovery'].includes(check.dimension) ? 'P1' : 'P2';
}

function geoChecks(geo, lang) {
  const byId = new Map();
  for (const dimension of Object.values(geo?.dimensions || {})) {
    for (const check of dimension.checks || []) byId.set(check.id, { ...check, category: dimension.label, dimension: check.dimension || dimension.key });
  }
  for (const page of geo?.pages || []) {
    for (const dimension of Object.values(page.dimensions || {})) {
      for (const check of dimension.checks || []) {
        if (!byId.has(check.id)) byId.set(check.id, { ...check, category: dimension.label, dimension: check.dimension || dimension.key, fromPage: true });
      }
    }
  }
  return [...byId.values()].map(check => {
    const occurrences = (geo.pages || []).flatMap(page =>
      Object.values(page.dimensions || {}).flatMap(dimension =>
        (dimension.checks || []).filter(item => item.id === check.id).map(item => ({ ...item, url: page.url }))));
    const counts = occurrences.length ? occurrences.reduce((acc, item) => {
      acc[item.status] = (acc[item.status] || 0) + 1;
      return acc;
    }, {}) : check.evidence?.page_status_counts || {};
    const affected = occurrences.filter(item => ['fail', 'partial'].includes(item.status) || item.blocker);
    const unknown = occurrences.filter(item => item.status === 'unknown');
    let status = check.status || 'unknown';
    if (occurrences.length) {
      status = affected.length ? (counts.fail === occurrences.length ? 'fail' : 'partial')
        : unknown.length ? 'unknown' : counts.pass ? 'pass' : 'na';
    } else if (status === 'partial' && counts.unknown && !counts.fail && !counts.partial) {
      status = 'unknown';
    }
    const blocker = Boolean(check.blocker || occurrences.some(item => item.blocker));
    const priority = geoPriority({ ...check, blocker });
    return {
      ...check, engine: 'GEO', status, blocker, priority, counts,
      label: check.label || check.id, summary: check.label || check.id,
      affected_urls: [...new Set(affected.map(item => item.url))],
      unknown_urls: [...new Set(unknown.map(item => item.url))],
      occurrences, evidence: occurrences.length ? occurrences.map(item => ({ url: item.url, status: item.status, evidence: item.evidence })) : check.evidence,
      recommendation: affected.find(item => item.recommendation)?.recommendation || check.recommendation ||
        (status === 'unknown' ? tx(lang, '补充抓取或人工核验记录，再确认此项。', 'Collect fetch or manual verification evidence before confirming this check.') : ''),
      impact: check.evidence_type === 'structural_proxy'
        ? tx(lang, '影响信息提取与答案准备度；结构检查不能代替事实核查。', 'Affects extraction and answer readiness; structural checks do not verify facts.')
        : tx(lang, '影响页面的发现、读取或检索准备度。', 'Affects page discovery, reading, or retrieval readiness.')
    };
  });
}

export function buildDiagnosticData(result = {}, lang = 'zh') {
  const seo = result.seo;
  const geo = result.geo;
  const seoChecks = (seo?.coverage_checks || []).map(check => ({
    ...check, engine: 'SEO', label: checkName(check.id, check.check, lang),
    category: localizeCategory(check.category, lang), status: check.status || 'unknown'
  }));
  const checks = [...seoChecks, ...geoChecks(geo, lang)];
  const seoIssues = (seo?.issues_table || []).map(issue => {
    const match = seoChecks.find(check => check.summary === issue.description) ||
      seoChecks.find(check => check.evidence === issue.evidence && check.category === localizeCategory(issue.category, lang));
    return {
      ...issue, id: issue.issue_id, engine: 'SEO', label: issue.check_item || checkName(match?.id, issue.description, lang),
      category: localizeCategory(issue.category, lang), summary: issue.description, impact: issue.seo_impact,
      affected_urls: [], status: 'fail'
    };
  });
  const issues = sortIssues([...seoIssues, ...checks.filter(check => check.engine === 'GEO' &&
    (check.status === 'fail' || check.status === 'partial' || check.blocker))]);
  const pending = checks.filter(check => check.status === 'unknown' || (check.counts?.unknown || 0) > 0);
  const dimensions = [
    ...Object.values(seo?.dimensions || {}).map(dimension => ({
      ...dimension, engine: 'SEO', label: localizeCategory(dimension.label || dimension.key, lang),
      normalized_weight: seo?.weighted_scores?.[dimension.key]?.normalized_weight ?? dimension.weight,
      weighted_value: seo?.weighted_scores?.[dimension.key]?.weighted_value
    })),
    ...Object.values(geo?.dimensions || {}).map(dimension => ({ ...dimension, engine: 'GEO', normalized_weight: dimension.weight }))
  ];
  const pages = new Map();
  for (const page of geo?.pages || []) pages.set(page.url, { url: page.url, geo: page });
  for (const page of seo?.sampled_pages || []) pages.set(page.url, { ...pages.get(page.url), url: page.url, seo: page });
  const counts = Object.fromEntries(['pass', 'fail', 'partial', 'unknown', 'na'].map(state =>
    [state, checks.filter(check => check.status === state).length]));
  return { seo, geo, checks, issues, pending, dimensions, pages: [...pages.values()], counts };
}

export function platformPolicies(geo) {
  return ['OAI-SearchBot', 'PerplexityBot', 'Googlebot', 'bingbot'].map(crawler => {
    const pages = (geo?.pages || []).map(page => {
      const check = Object.values(page.dimensions || {}).flatMap(dimension => dimension.checks || []).find(item => item.id === 'GEO-002');
      return { url: page.url, allowed: check?.evidence?.policies?.[crawler] ?? null };
    });
    const allowed = pages.filter(page => page.allowed === true).length;
    const blocked = pages.filter(page => page.allowed === false).length;
    return { crawler, pages, allowed, blocked, unknown: pages.length - allowed - blocked };
  });
}

