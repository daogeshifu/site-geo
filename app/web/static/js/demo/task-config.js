export const SITE_GEO_STEP_ORDER = ['discovery', 'visibility', 'technical', 'content', 'schema', 'platform', 'observation', 'summary'];
export const SITE_CONTENT_STEP_ORDER = ['discovery', 'content', 'summary'];
export const SITE_SEO_STEP_ORDER = ['discovery', 'seo', 'summary'];
export const STEP_ICON = {
  discovery: '🔍',
  visibility: '👁',
  technical: '⚙️',
  content: '📝',
  seo: '📈',
  schema: '🏷️',
  platform: '🌐',
  observation: '📎',
  summary: '📊',
  structure_graph: '🕸️',
  entity_graph: '🧩'
};

export const TASK_TYPE_CONFIG = {
  site_geo_audit: {
    heading: { zh: '网站 GEO 审计', en: 'Site GEO Audit' },
    subtitle: {
      zh: '提交目标 URL 创建后台任务，支持可选 full audit、非首页偏差提示与逐页诊断结果。',
      en: 'Submit a target URL to run the full GEO audit pipeline with optional full audit expansion and page diagnostics.'
    },
    urlLabel: { zh: '目标 URL', en: 'Target URL' },
    placeholder: 'https://example.com',
    fullAuditVisible: true,
    exportable: true
  },
  site_content_audit: {
    heading: { zh: '网站内容审计', en: 'Website Content Audit' },
    subtitle: {
      zh: '输入具体 blog URL，按 GEO 内容可引用性与页面 SEO 信号做单页审计。',
      en: 'Audit a specific blog URL for GEO citation readiness and on-page SEO signals.'
    },
    urlLabel: { zh: 'Blog URL', en: 'Blog URL' },
    placeholder: 'https://example.com/blog/example-post',
    fullAuditVisible: false,
    exportable: false
  },
  site_seo_audit: {
    heading: { zh: '网站 SEO 审计', en: 'Website SEO Audit' },
    subtitle: {
      zh: '基于 Google SEO 审计模板输出站点级检查清单、问题总表与 30/60/90 路线图。',
      en: 'Run a site-level Google SEO audit with a coverage checklist, issue backlog, and 30/60/90 roadmap.'
    },
    urlLabel: { zh: '站点 URL', en: 'Site URL' },
    placeholder: 'https://example.com',
    fullAuditVisible: true,
    exportable: true
  }
};

export const PLATFORM_LABELS = {
  google_ai_overviews: 'Google AI Overviews',
  google_ai_mode: 'Google AI Mode',
  chatgpt: 'ChatGPT',
  perplexity: 'Perplexity',
  gemini: 'Gemini',
  grok: 'Grok'
};

export const CONTENT_GEO_FACTOR_LABELS = {
  clear_definitions: { zh: '定义清晰度', en: 'Clear definitions' },
  quotable_statements: { zh: '可引用表述', en: 'Quotable statements' },
  factual_density: { zh: '事实密度', en: 'Factual density' },
  source_citations: { zh: '来源与引用', en: 'Source citations' },
  qa_format: { zh: '问答结构', en: 'Q&A format' },
  authority_signals: { zh: '权威信号', en: 'Authority signals' },
  content_freshness: { zh: '内容新鲜度', en: 'Content freshness' },
  structure_clarity: { zh: '结构清晰度', en: 'Structure clarity' }
};

export function getTaskTypeConfig(taskType = 'site_geo_audit') {
  return TASK_TYPE_CONFIG[taskType] || TASK_TYPE_CONFIG.site_geo_audit;
}

export function getTaskStepOrder(taskType = 'site_geo_audit') {
  if (taskType === 'site_content_audit') return SITE_CONTENT_STEP_ORDER;
  if (taskType === 'site_seo_audit') return SITE_SEO_STEP_ORDER;
  return SITE_GEO_STEP_ORDER;
}
