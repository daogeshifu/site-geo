import { escapeHtml as e, tx } from './shared.js';
import {
  buildDiagnosticData, displayNumber as n, displayPercent as pct,
  geoDimensionName, platformPolicies, reportState
} from './diagnostic-data.js?v=20261112-geo-labels';

const cleanList = items => [...new Set((items || []).filter(Boolean))];
const safeLink = (url, label = url) => /^https?:\/\//i.test(url || '')
  ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(label)}</a>` : e(label || '—');
const chip = (status, lang) => `<span class="dr-state dr-state-${e(status)}">${e(reportState(status, lang))}</span>`;
const priority = value => `<span class="priority-chip ${e(String(value || '').toLowerCase())}">${e(value || '—')}</span>`;
const empty = text => `<p class="dr-empty">${e(text)}</p>`;
const plain = value => value == null ? '—' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
const kv = rows => `<dl class="dr-facts">${rows.map(([key, value]) => `<div><dt>${e(key)}</dt><dd>${e(plain(value))}</dd></div>`).join('')}</dl>`;
const jsonDetails = (value, lang) => `<details class="dr-raw"><summary>${tx(lang, '查看原始证据', 'View raw evidence')}</summary><pre>${e(JSON.stringify(value ?? {}, null, 2))}</pre></details>`;
const heading = (title, note = '', count = null) => `<div class="dr-section-head"><div><h3>${e(title)}${count == null ? '' : `<span class="section-count">${count}</span>`}</h3>${note ? `<p>${e(note)}</p>` : ''}</div></div>`;

function radar(dimensions, lang) {
  if (!dimensions.length) return '';
  const count = dimensions.length, cx = 160, cy = 126, radius = 80;
  const point = (index, ratio = 1) => {
    const angle = (index * 360 / count - 90) * Math.PI / 180;
    return [cx + radius * ratio * Math.cos(angle), cy + radius * ratio * Math.sin(angle)];
  };
  const points = ratio => dimensions.map((_, index) => point(index, ratio).join(',')).join(' ');
  const known = dimensions.every(d => d.score != null);
  return `<figure class="dr-radar"><figcaption>${tx(lang, '维度概览', 'Dimension overview')}</figcaption>
    <svg viewBox="0 0 320 252" role="img" aria-label="${e(dimensions.map(d => d.label + ': ' + n(d.score)).join('; '))}">
      ${[.25, .5, .75, 1].map(ratio => `<polygon points="${points(ratio)}" class="dr-radar-grid"/>`).join('')}
      ${dimensions.map((dimension, index) => {
        const [x, y] = point(index), [lx, ly] = point(index, 1.38);
        const label = dimension.label || '';
        const parts = /^(.*?[：:])\s*(.*)$/.exec(label);
        const shorten = text => text.length > 13 ? text.slice(0, 12) + '…' : text;
        return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" class="dr-radar-grid"/>
          <text x="${lx}" y="${ly}" text-anchor="middle" class="dr-radar-label">${parts
            ? `<tspan x="${lx}" dy="-4">${e(parts[1])}</tspan><tspan x="${lx}" dy="13">${e(shorten(parts[2]))}</tspan>`
            : e(shorten(label))}</text>`;
      }).join('')}
      ${known ? `<polygon points="${dimensions.map((d, i) => point(i, Math.max(0, Math.min(100, d.score)) / 100).join(',')).join(' ')}" class="dr-radar-area"/>` : ''}
      ${dimensions.filter(d => d.score != null).map(d => { const [x, y] = point(dimensions.indexOf(d), Math.max(0, Math.min(100, d.score)) / 100); return `<circle cx="${x}" cy="${y}" r="3" class="dr-radar-dot"><title>${e(d.label)}: ${n(d.score)}</title></circle>`; }).join('')}
    </svg><span>${tx(lang, '各维度原始分 / 100', 'Raw dimension scores / 100')}</span></figure>`;
}

function renderOverview(task, data, lang) {
  const result = task.result || {}, discovery = result.discovery || {}, geo = data.geo, seo = data.seo;
  const summary = seo && !geo ? result.summary || {} : result.seo_summary || {};
  const scores = [
    ...(seo ? [{ label: tx(lang, 'SEO 健康分', 'SEO health score'), score: seo.overall_score ?? seo.score ?? summary.overall_score, status: seo.status || summary.status, note: 'seo-audit-v1' }] : []),
    ...(geo ? [{ label: tx(lang, '站内 GEO 就绪度', 'On-site GEO readiness'), score: geo.score, status: geo.readiness_status || geo.status, note: geo.provisional ? tx(lang, '暂定评分', 'Provisional score') : geo.scoring_version }] : [])
  ];
  const title = tx(lang, seo && geo ? '网站 SEO+GEO 诊断报告' : seo ? '网站 SEO 诊断报告' : '网站 GEO 诊断报告',
    seo && geo ? 'Website SEO + GEO report' : seo ? 'Website SEO report' : 'Website GEO report');
  const description = result.summary?.summary || tx(lang, '从已采集的页面证据中定位优化事项。', 'Find improvements grounded in the collected page evidence.');
  return `<header class="dr-heading"><div><h2>${title}</h2><p>${safeLink(task.url || discovery.final_url)}${task.completed_at ? `<span>${e(task.completed_at.replace('T', ' ').slice(0, 16))} UTC</span>` : ''}</p></div>
    <span class="dr-edition">${tx(lang, '诊断结果', 'Diagnostic results')}<b>${data.dimensions.length} ${tx(lang, '个维度', 'dimensions')}</b></span></header>
    <section class="dr-overview" id="diagnosis-overview">
      <div class="dr-score-ledger">${scores.map(score => `<div class="dr-score-entry"><span>${score.label}</span><div class="dr-score-value"><strong>${n(score.score)}</strong><small>/100</small></div>${chip(score.status, lang)}<small>${e(score.note || '')}</small></div>`).join('')}</div>
      <div class="dr-overview-copy"><h3>${e(discovery.homepage?.title || discovery.domain || task.domain || tx(lang, '站点诊断概览', 'Site diagnosis'))}</h3><p>${e(description)}</p>
        <div class="dr-scope-notice">${geo && seo
          ? `SEO ${n(seo.overall_score)}/100 · GEO ${n(geo.score)}/100 — ${tx(lang, '两套独立评分，共享页面证据；分数不平均。', 'Independent SEO results and GEO readiness, sharing page evidence. Scores are not averaged.') }`
          : geo ? tx(lang, '站内就绪度不代表实际收录、AI 引用概率或事实核查结果。', 'On-site readiness does not establish indexing, AI citation probability, or factual accuracy.')
            : tx(lang, '基于采样页面的搜索健康检查，先处理阻断和高优先级问题。', 'Search health checks from sampled pages. Resolve blockers and high-priority issues first.')}</div>
        <div class="dr-stat-strip">
          <div><strong>${data.checks.length}</strong><span>${tx(lang, '检查事项', 'Checks')}</span></div>
          <div><strong>${data.issues.length}</strong><span>${tx(lang, '待整改', 'Issues')}</span></div>
          <div><strong>${data.pending.length}</strong><span>${tx(lang, '待核验事项', 'Unverified checks')}</span></div>
          <div><strong>${data.pages.length}</strong><span>${tx(lang, '采样页面', 'Sampled pages')}</span></div>
        </div>
        ${geo ? `<p class="dr-score-bounds">${tx(lang, 'GEO 证据覆盖率', 'GEO evidence coverage')} <b>${pct(geo.coverage?.evidence_coverage)}</b>
          <span>${tx(lang, '分数区间', 'Score bounds')} ${(geo.score_range || []).map(n).join('–') || '—'}</span>
          <span>${geo.coverage?.blocked_pages ?? 0} ${tx(lang, '个阻断页面', 'blocked pages')}</span></p>` : ''}
      </div>${radar(data.dimensions.filter(d => d.engine === (geo ? 'GEO' : 'SEO')), lang)}
    </section>`;
}

function evidenceText(value) {
  if (typeof value === 'string') return value;
  if (!value) return '';
  return JSON.stringify(value);
}

function issueRows(issues, lang) {
  return issues.map(item => `<tr data-issue-row data-engine="${item.engine}" data-priority="${e(item.priority || '')}" data-search="${e([item.label, item.id, item.category, item.summary, evidenceText(item.evidence), item.recommendation].join(' ').toLowerCase())}">
    <td><strong class="issue-check-title">${e(item.label)}</strong><span class="issue-meta"><span>${e(item.category || item.engine)}</span><code>${e(item.id)}</code></span><span class="dr-engine">${item.engine}</span></td>
    <td>${priority(item.priority)}${item.blocker ? `<span class="dr-blocker-label">${tx(lang, '关键阻断', 'Blocker')}</span>` : ''}</td>
    <td class="audit-cell-copy"><strong>${e(item.summary || item.label)}</strong>${item.affected_urls?.length ? `<p>${tx(lang, '影响', 'Affects')} ${item.affected_urls.length} ${tx(lang, '个采样页面', 'sampled pages')} · <a href="#diagnosis-pages" data-open-pages data-target-page="${e(item.affected_urls[0])}">${tx(lang, '查看页面证据', 'View page evidence')}</a></p>` : ''}
      ${item.evidence ? `<details class="dr-inline-evidence"><summary>${tx(lang, '查看检测证据', 'View evidence')}</summary><pre>${e(plain(item.evidence))}</pre></details>` : ''}</td>
    <td class="audit-cell-copy">${e(item.impact || '—')}</td><td class="audit-cell-copy recommendation">${e(item.recommendation || '—')}
      ${item.acceptance_criteria ? `<p><b>${tx(lang, '验收：', 'Accept: ')}</b>${e(item.acceptance_criteria)}</p>` : ''}
      ${item.owner_team || item.estimated_effort ? `<small>${e([item.owner_team, item.estimated_effort].filter(Boolean).join(' · '))}</small>` : ''}</td>
  </tr>`).join('');
}

function renderIssues(data, lang) {
  const priorities = ['P0', 'P1', 'P2', 'P3'].map(p => {
    const count = data.issues.filter(item => item.priority === p).length;
    return count ? `<span class="issue-count"><i class="priority-dot ${p.toLowerCase()}"></i>${p}<strong>${count}</strong></span>` : '';
  }).join('');
  return `<section class="report-section issue-table-section" id="diagnosis-issues">
    <div class="dr-section-head"><div><h3>${tx(lang, '问题清单', 'Diagnostic issues')}<span class="section-count">${data.issues.length}</span></h3><p>${tx(lang, '按优先级排序，逐项查看影响、检测证据与修复建议。', 'Sorted by priority, with impact, evidence, and remediation for each finding.')}</p></div><div class="issue-priority-summary">${priorities}</div></div>
    <div class="dr-filters">
      <label><span class="dr-sr-only">${tx(lang, '搜索问题', 'Search issues')}</span><input type="search" data-issue-search placeholder="${tx(lang, '搜索检查项、证据或建议', 'Search checks, evidence, or recommendations')}"></label>
      ${data.geo && data.seo ? `<label><span class="dr-sr-only">${tx(lang, '诊断类型', 'Audit type')}</span><select data-issue-engine><option value="">${tx(lang, '全部类型', 'All types')}</option><option>SEO</option><option>GEO</option></select></label>` : ''}
      <label><span class="dr-sr-only">${tx(lang, '优先级', 'Priority')}</span><select data-issue-priority><option value="">${tx(lang, '全部优先级', 'All priorities')}</option>${['P0', 'P1', 'P2', 'P3'].map(p => `<option>${p}</option>`).join('')}</select></label>
      <span data-issue-count role="status" aria-live="polite">${data.issues.length} / ${data.issues.length}</span>
    </div><div class="audit-table-wrap issue-table-wrap" tabindex="0" role="region" aria-label="${tx(lang, '诊断问题表，可横向滚动', 'Diagnostic issues, scroll horizontally')}">
      <table class="audit-table issue-table"><thead><tr>${[tx(lang, '检查事项', 'Check'), tx(lang, '优先级', 'Priority'), tx(lang, '发现的问题与证据', 'Issue and evidence'), tx(lang, '影响', 'Impact'), tx(lang, '修复建议', 'Recommendation')].map(label => `<th scope="col">${label}</th>`).join('')}</tr></thead><tbody>
      ${issueRows(data.issues, lang)}<tr data-issue-empty ${data.issues.length ? 'hidden' : ''}><td colspan="5" class="audit-table-empty">${tx(lang, data.issues.length ? '没有匹配的问题，请调整筛选条件。' : '本次诊断未发现明确问题。待核验事项仍需补充证据。', data.issues.length ? 'No matching issues. Adjust your filters.' : 'No diagnostic issues found. Unverified checks still need evidence.')}</td></tr>
      </tbody></table></div></section>`;
}

function renderCoverage(data, lang) {
  const checks = [...data.checks].sort((left, right) => String(left.id).localeCompare(String(right.id), 'en', { numeric: true }));
  return `<details class="report-section collapsible-section coverage-section" id="diagnosis-coverage">
    <summary class="dr-section-head"><div><h3>${tx(lang, '完整覆盖清单', 'Complete coverage checklist')}<span class="section-count">${data.checks.length}</span></h3>
      <p>${tx(lang, '通过', 'Pass')} ${data.counts.pass} · ${tx(lang, '待整改', 'Needs work')} ${data.counts.fail} · ${tx(lang, '部分满足', 'Partial')} ${data.counts.partial} · ${tx(lang, '待核验', 'Unverified')} ${data.counts.unknown} · ${tx(lang, '不适用', 'N/A')} ${data.counts.na}</p></div>
      <a class="checklist-doc-link" href="/api-doc#${data.geo ? 'geo-scoring' : 'seo-checklist'}" target="_blank" rel="noreferrer">${tx(lang, '检测清单说明', 'Checklist guide')}</a></summary>
    ${checks.length ? `<ul class="dr-coverage-grid" aria-label="${tx(lang, '完整检查清单', 'Complete checklist')}">${checks.map(check => `<li class="dr-coverage-item" data-check-id="${e(check.id)}">
      <code>${e(check.id)}</code>${chip(check.status, lang)}<strong>${e(check.check || check.label)}</strong>
    </li>`).join('')}</ul>` : empty(tx(lang, '此历史结果未保存检查清单，可重新诊断以补充。', 'This historical result has no checklist. Run a new audit to collect one.'))}</details>`;
}

function renderDimensions(data, lang) {
  return `<section class="report-section dimensions-section" id="diagnosis-dimensions">${heading(tx(lang, '维度评估', 'Scored dimensions'), tx(lang, 'SEO 与 GEO 各自计分；展开查看权重、计分依据与建议。', 'SEO and GEO are scored separately. Expand for weights, scoring evidence, and recommendations.'), data.dimensions.length)}
    <div class="dr-dimension-groups">${['SEO', 'GEO'].filter(engine => data.dimensions.some(d => d.engine === engine)).map(engine => `<div><div class="dr-group-heading"><h4>${engine === 'SEO' ? tx(lang, 'SEO 搜索健康', 'SEO search health') : tx(lang, 'GEO 站内就绪度', 'GEO on-site readiness')}</h4><span>${engine === 'GEO' ? e(data.geo.scoring_version || tx(lang, '版本未记录', 'Version not recorded')) : 'seo-audit-v1'}</span></div>
    <div class="report-dim-grid">${data.dimensions.filter(d => d.engine === engine).map(d => {
      const owned = data.checks.filter(check => check.engine === engine && (engine === 'GEO' ? check.dimension === d.key : check.category === d.label));
      const score = d.score == null ? null : Math.max(0, Math.min(100, Number(d.score)));
      return `<article class="report-dim-card"><div class="report-dim-head"><h5 class="report-dim-name">${e(d.label)}</h5><span class="report-dim-pill">${pct(d.normalized_weight)}</span></div>
        <div class="report-dim-scoreline"><span class="score">${n(score)}<small>/100</small></span>${engine === 'GEO' ? `<span>${tx(lang, '证据', 'Evidence')} ${pct(d.evidence_coverage)}</span>` : chip(d.status, lang)}</div>
        <div class="dimension-meter"><span style="width:${score ?? 0}%"></span></div>
        <p class="report-dim-note">${e(d.summary || (engine === 'GEO' ? tx(lang, '已核验项暂算；未知项保留在分数区间中。', 'Estimated from measured checks; unknowns remain in the score bounds.') : ''))}</p>
        ${engine === 'GEO' && d.key === 'trust' ? `<p class="report-dim-note">${tx(lang, '可信与时效为推荐提供基础；实际推荐需独立验证。', 'Trust and freshness support recommendation readiness; actual recommendations need separate verification.')}</p>` : ''}
        <details class="dimension-details"><summary>${tx(lang, '查看计分与建议', 'Scoring and recommendations')}</summary><div class="dr-dimension-detail">
          ${kv(engine === 'GEO' ? [
            [tx(lang, '已获积分 / 已测积分', 'Earned / measured points'), n(d.earned_points) + ' / ' + n(d.measured_points)],
            [tx(lang, '适用积分', 'Applicable points'), n(d.applicable_points)],
            [tx(lang, '维度分', 'Dimension score'), tx(lang, '已获积分 ÷ 已测积分 × 100', 'Earned ÷ measured × 100')]
          ] : [[tx(lang, '归一权重', 'Normalized weight'), pct(d.normalized_weight)], [tx(lang, '加权得分', 'Weighted contribution'), n(d.weighted_value)]])}
          ${owned.length ? `<ul class="dr-dim-checks">${owned.map(check => `<li data-check-id="${e(check.id)}"><span>${engine === 'GEO' ? `<strong class="dr-diagnostic-name">${e(check.diagnostic_name)}</strong>` : `<code>${e(check.id)}</code>`} ${e(check.label)}${engine === 'GEO' ? `<small>${tx(lang, '规则积分', 'Rule points')} ${n(check.max_points)}</small>` : ''}</span>${chip(check.status, lang)}</li>`).join('')}</ul>` : ''}
          ${cleanList(d.issues).map(issue => `<p>${e(issue)}</p>`).join('')}
          ${cleanList(d.recommendations).map(rec => `<p class="dr-rec">${e(rec)}</p>`).join('')}
          ${engine === 'GEO' ? cleanList(owned.filter(check => ['fail', 'partial'].includes(check.status)).map(check => check.recommendation)).map(rec => `<p class="dr-rec">${e(rec)}</p>`).join('') : ''}
        </div></details></article>`;
    }).join('')}</div></div>`).join('')}</div></section>`;
}

function renderActions(data, result, lang) {
  const actions = data.issues.filter(item => item.recommendation);
  const fallback = cleanList((result.seo_summary || result.summary || {}).quick_wins);
  return `<section class="dr-actions" id="diagnosis-actions">
    <div class="report-section dr-action-panel">${heading(tx(lang, '优先行动', 'Priority actions'), tx(lang, '先解除阻断，再修复高影响问题。', 'Resolve blockers, then high-impact issues.'))}
      <ul>${actions.slice(0, 6).map(item => `<li>${priority(item.priority)}<div><b>${e(item.label)}</b><p>${e(item.recommendation)}</p></div><span class="dr-engine">${item.engine}</span></li>`).join('') || fallback.slice(0, 6).map(text => `<li><p>${e(text)}</p></li>`).join('') || `<li>${tx(lang, '暂无优先动作。', 'No quick wins.')}</li>`}</ul>
    </div><div class="report-section dr-verification-panel">${heading(tx(lang, '待核验事项', 'Verification queue'), tx(lang, '缺少证据的项目单独跟进，不视为通过。', 'Follow up on missing evidence; unknown checks are not passes.'), data.pending.length)}
      <ul>${data.pending.map(check => `<li><code>${e(check.id)}</code><div><b>${e(check.label)}</b><p>${e(check.recommendation || tx(lang, '补充抓取、渲染或人工核验记录。', 'Collect fetch, rendering, or manual verification evidence.'))}</p>${check.unknown_urls?.length ? `<small>${check.unknown_urls.length} ${tx(lang, '个页面待核验', 'pages unverified')}</small>` : ''}</div></li>`).join('') || `<li>${tx(lang, '当前检查清单没有待核验项。', 'No unverified items in the current checklist.')}</li>`}</ul>
    </div></section>`;
}

function renderEvidenceProfile(data, lang) {
  if (!data.geo) return '';
  const positive = data.checks.filter(check => check.engine === 'GEO' && check.status === 'pass');
  const gaps = data.checks.filter(check => check.engine === 'GEO' && ['fail', 'partial'].includes(check.status));
  return `<section class="report-section" id="diagnosis-profile">${heading(tx(lang, 'AI 读取准备度', 'AI reading readiness'), tx(lang, '仅展示本次页面证据，不推测 AI 对品牌的认知或引用表现。', 'Observed page evidence only; no inferred brand perception or citation performance.'))}
    <div class="dr-profile"><div class="dr-capabilities">${data.dimensions.filter(d => d.engine === 'GEO').map(d => `<div><span>${e(d.label)}</span><div class="dr-capability-track"><i style="width:${Math.max(0, Math.min(100, d.score ?? 0))}%"></i></div><b>${n(d.score)}</b></div>`).join('')}</div>
      <div class="dr-profile-evidence"><div><h4>${tx(lang, '已确认信号', 'Confirmed signals')}</h4><div class="dr-signal-tags">${positive.map(check => `<span>${e(check.label)}</span>`).join('') || empty(tx(lang, '暂无已确认的通过项。', 'No confirmed passing checks.'))}</div></div>
      <div><h4>${tx(lang, '当前缺口', 'Observed gaps')}</h4><div class="dr-signal-tags dr-signal-gaps">${gaps.map(check => `<span>${e(check.label)}</span>`).join('') || empty(tx(lang, '已测项目未发现明确缺口。', 'No gaps in the measured checks.'))}</div></div></div>
    </div></section>`;
}

function renderPlatforms(data, lang) {
  if (!data.geo) return '';
  const policies = platformPolicies(data.geo);
  const platforms = [
    ['ChatGPT', 'OAI-SearchBot'], ['Perplexity', 'PerplexityBot'],
    ['Google AI Overviews', 'Googlebot'], ['Google AI Mode', 'Googlebot'],
    ['Gemini', null], ['Bing Copilot', 'bingbot']
  ];
  return `<section class="report-section" id="diagnosis-platforms">${heading(tx(lang, '平台检索与抓取', 'Platform retrieval and crawling'), tx(lang, '展示采样 URL 的 robots 规则，不计入独立平台分，也不代表实际曝光。', 'Robots policies for sampled URLs, without a platform score or a claim of actual visibility.'))}
    <div class="dr-platform-grid">${platforms.map(([name, crawler]) => {
      const policy = policies.find(p => p.crawler === crawler);
      const status = policy?.blocked ? 'blocked' : !policy || !policy.pages.length || policy.unknown ? 'unknown' : 'pass';
      return `<article class="dr-platform"><h4>${e(name)}</h4>${chip(status, lang)}<p>${e(crawler || tx(lang, '未采集独立平台抓取证据', 'No separate platform crawl evidence'))}</p>
        ${policy ? `<dl><div><dt>${tx(lang, '规则允许', 'Allowed')}</dt><dd>${policy.allowed}</dd></div><div><dt>${tx(lang, '规则阻止', 'Blocked')}</dt><dd>${policy.blocked}</dd></div><div><dt>${tx(lang, '待核验', 'Unknown')}</dt><dd>${policy.unknown}</dd></div></dl>
          <details><summary>${tx(lang, '查看路径规则', 'View path policies')}</summary>${policy.pages.map(page => `<p>${safeLink(page.url)} ${chip(page.allowed == null ? 'unknown' : page.allowed ? 'pass' : 'blocked', lang)}</p>`).join('')}</details>`
          : `<p>${tx(lang, '需补充平台观测或官方验证数据。', 'Add platform observations or verified data.')}</p>`}</article>`;
    }).join('')}</div><p class="dr-footnote">${tx(lang, 'Google 两个搜索入口共用 Googlebot 规则；这不等同于 Gemini 应用的访问或引用验证。', 'Both Google search experiences share Googlebot policy evidence. This does not verify Gemini app access or citations.')}</p></section>`;
}

function renderPages(data, lang) {
  const preview = data.pages.slice(0, 8);
  return `<details class="report-section collapsible-section" id="diagnosis-pages" open>
    <summary class="dr-section-head"><div><h3>${tx(lang, '逐页诊断与证据', 'Page diagnostics and evidence')}<span class="section-count">${data.pages.length}</span></h3>
      <p>${tx(lang, '展示最多 8 个采样页面，展开查看检查状态、抓取信息和整改依据。', 'Preview up to 8 sampled pages. Expand a page for check states, fetch metadata, and remediation evidence.')}</p></div></summary>
    <div class="dr-page-list">${preview.map((item, index) => {
      const page = item.geo || item.seo, seo = item.seo;
      return `<details class="dr-page" id="diagnosis-page-${index}" data-page-url="${e(item.url)}"><summary><div><span class="dr-page-type">${e(page.page_type || 'page')}</span><strong>${e(item.url)}</strong></div>
        <div class="dr-page-scores">${item.seo ? `<span>SEO HTTP ${n(seo.status_code)}</span>` : ''}${item.geo ? `<span>GEO ${n(page.score)}/100</span>${chip(page.status, lang)}` : ''}</div></summary>
        <div class="dr-page-body"><p>${safeLink(item.url)}</p>${kv([
          [tx(lang, '最终 URL', 'Final URL'), page.final_url], ['HTTP', page.status_code],
          [tx(lang, '抓取时间', 'Fetched at'), page.fetched_at], [tx(lang, '响应耗时', 'Response time'), page.response_time_ms == null ? null : page.response_time_ms + ' ms'],
          ...(item.geo ? [[tx(lang, '证据覆盖率', 'Evidence coverage'), pct(page.evidence_coverage)]] : []),
          [tx(lang, '源码截断', 'Source truncated'), page.source_truncated == null ? null : page.source_truncated ? tx(lang, '是', 'Yes') : tx(lang, '否', 'No')]
        ])}
        ${seo ? `<h4>${tx(lang, 'SEO 页面信号', 'SEO page signals')}</h4>${kv([
          ['Title', seo.title], [tx(lang, '描述', 'Description'), seo.meta_description], ['Canonical', seo.canonical],
          ['H1', seo.h1_count], [tx(lang, '正文词数', 'Word count'), seo.word_count],
          [tx(lang, '图片替代文本覆盖', 'Image alt coverage'), pct(seo.alt_coverage_ratio)], ['Noindex', seo.noindex_detected == null ? null : String(seo.noindex_detected)]
        ])}` : ''}
        ${item.geo ? `<div class="dr-page-checks">${Object.entries(item.geo.dimensions || {}).map(([key, d]) => `<h4>${e(geoDimensionName(d.key || key, d.label, lang))}</h4>${(d.checks || []).map(check => `<article><div><code>${e(check.id)}</code><b>${e(check.label)}</b>${chip(check.status, lang)}${check.blocker ? priority('P0') : ''}</div>
          ${['fail', 'partial', 'unknown'].includes(check.status) && check.recommendation ? `<p>${e(check.recommendation)}</p>` : ''}
          ${check.evidence_type === 'structural_proxy' ? `<small>${tx(lang, '结构代理检查，未作事实核查。', 'Structural proxy; not fact-checked.')}</small>` : ''}${jsonDetails(check.evidence, lang)}</article>`).join('')}`).join('')}</div>` : ''}
        </div></details>`;
    }).join('') || empty(tx(lang, '历史结果没有采样页面证据，可重新诊断以补充。', 'No page evidence in this historical result. Run a new audit to collect it.'))}</div>
    ${preview.length ? `<div class="dr-pages-footer"><p>${tx(lang, `已展示 ${preview.length} / ${data.pages.length} 个采样页面`, `Showing ${preview.length} of ${data.pages.length} sampled pages`)}</p>
      <a href="#tab-site-links" data-open-site-links aria-label="${tx(lang, '在站点链接中查看更多页面', 'View more pages in Site links')}">${tx(lang, '查看更多', 'View more')}</a></div>` : ''}</details>`;
}

function renderSnapshot(result, lang) {
  const d = result.discovery || {}, home = d.homepage || {}, fetch = d.fetch || {};
  const count = value => Array.isArray(value) ? value.length : null;
  const yes = value => value == null ? null : tx(lang, value ? '是' : '否', value ? 'Yes' : 'No');
  const groups = [
    [tx(lang, '站点与范围', 'Site and scope'), [
      [tx(lang, '诊断地址', 'Requested URL'), d.url || result.url], [tx(lang, '最终地址', 'Final URL'), d.final_url],
      [tx(lang, '采样范围', 'Sample scope'), d.scope_root_url], [tx(lang, '页面语言', 'Page language'), home.lang],
      [tx(lang, '业务类型', 'Business type'), d.business_type]
    ]],
    [tx(lang, '抓取与响应', 'Fetch and response'), [
      ['HTTP', fetch.status_code], [tx(lang, '响应耗时', 'Response time'), fetch.response_time_ms == null ? null : fetch.response_time_ms + ' ms'],
      [tx(lang, '快照版本', 'Snapshot version'), d.site_snapshot_version], [tx(lang, '已分析页面', 'Profiled pages'), d.profiled_page_count]
    ]],
    [tx(lang, '页面内容', 'Page content'), [
      ['Title', home.title], [tx(lang, '页面描述', 'Meta description'), home.meta_description], ['H1', home.h1],
      [tx(lang, '标题数量', 'Headings'), count(home.headings)], [tx(lang, '正文词数', 'Word count'), home.word_count],
      [tx(lang, '图片数量', 'Images'), count(home.images)], [tx(lang, 'HTML 体积', 'HTML size'), home.html_length]
    ]],
    [tx(lang, '发现与索引', 'Discovery and indexing'), [
      ['Canonical', home.canonical], ['Robots.txt', yes(d.robots?.exists)], ['Sitemap', yes(d.sitemap?.exists)],
      [tx(lang, '地图候选 URL', 'Sitemap candidates'), count(d.sitemap?.discovered_urls)],
      [tx(lang, '内部链接', 'Internal links'), count(home.internal_links)], [tx(lang, '外部链接', 'External links'), count(home.external_links)]
    ]],
    [tx(lang, '结构化数据与实体', 'Structured data and entities'), [
      ['JSON-LD', count(home.json_ld_blocks)], [tx(lang, '结构化数据摘要', 'Schema summary'), d.schema_summary],
      [tx(lang, '业务实体信号', 'Business entity signals'), d.site_signals]
    ]],
    [tx(lang, '辅助信号（不计入 GEO）', 'Auxiliary signals (excluded from GEO)'), [
      ['llms.txt', yes(d.llms?.exists)], ['Open Graph', home.open_graph], ['Twitter Card', home.twitter_cards],
      [tx(lang, '站外权威', 'External authority'), d.backlinks?.available == null ? null : yes(d.backlinks.available)]
    ]]
  ];
  return `<details class="report-section collapsible-section" id="diagnosis-snapshot" open><summary class="dr-section-head"><div><h3>${tx(lang, '站点快照', 'Site snapshot')}</h3><p>${tx(lang, '基础数据、抓取信息、实体信号及响应头。', 'Site facts, fetch metadata, entity signals, and response headers.')}</p></div><span>${e(d.site_snapshot_version || 'snapshot')}</span></summary>
    <div class="dr-snapshot">${groups.map(([title, rows]) => `<section><h4>${title}</h4>${kv(rows)}</section>`).join('')}
    <section><h4>${tx(lang, '关键响应头', 'Response headers')}</h4>${kv(Object.entries(fetch.headers || {}))}</section></div></details>`;
}

function renderMethod(data, result, lang) {
  const notes = cleanList([...(data.geo?.processing_notes || []), ...(result.seo_summary?.processing_notes || []), ...(result.summary?.processing_notes || [])]);
  return `<details class="report-section collapsible-section" id="diagnosis-method"><summary class="dr-section-head"><h3>${tx(lang, '计分方法与诊断说明', 'Scoring methodology and notes')}</h3></summary><div class="dr-method">
    ${data.geo ? `<p>${tx(lang, 'GEO 先逐页计分，再对页面类型等权、同类型页面等权汇总。待核验项不视为通过，暂定分仅基于已测证据，同时展示分数上下界。', 'GEO is scored per page, then equally by page type and by page within each type. Unknowns are not passes; estimates use measured evidence and include score bounds.')}</p>
    <p>${tx(lang, '训练授权、社交卡片、一般安全响应头及站外权威不计入 GEO 总分。实际收录与 AI 引用单独验证。', 'Training permissions, social cards, general security headers, and external authority are excluded from GEO. Actual indexing and AI citations need separate verification.')}</p>
    ${data.geo.scoring_version === 'onsite-geo-v1' ? `<p>${tx(lang, '此历史版本的 llms.txt 不计分，未包含新增的速度和 URL 静态化规则。', 'This historical version does not score llms.txt and predates the loading-speed and static-URL rules.')}</p>` : ''}
    ${kv([[tx(lang, '已发现候选页面', 'Known candidate pages'), data.geo.coverage?.known_candidate_pages],
      [tx(lang, '采样占候选比例', 'Sample-to-candidate ratio'), pct(data.geo.coverage?.sample_coverage)],
      [tx(lang, '范围说明', 'Scope note'), tx(lang, '该比例不代表全站覆盖率。', 'This is not whole-site coverage.')]])}` : ''}
    <ul>${notes.map(note => `<li>${e(note)}</li>`).join('')}</ul>
    ${data.seo && data.geo ? `<p>${tx(lang, 'SEO 使用自己的维度与权重，SEO 与 GEO 两项分数不取平均。', 'SEO uses its own dimensions and weights. SEO and GEO scores are not averaged.')}</p>` : ''}
    </div></details>
    ${result.observation?.provided ? `<section class="report-section">${heading(tx(lang, '独立观测（不计分）', 'Unscored observations'))}<div class="dr-method">${kv(Object.entries(result.observation.metrics || {}))}${jsonDetails(result.observation, lang)}</div></section>` : ''}`;
}

export function renderDiagnosticReport({ task, host, lang = 'zh', setCachedReportHtml }) {
  const result = task?.result || {};
  const data = buildDiagnosticData(result, lang);
  host.className = 'report-shell';
  const nav = [
    ['issues', tx(lang, '问题清单', 'Issues')], ['coverage', tx(lang, '覆盖清单', 'Checklist')],
    ['dimensions', tx(lang, '维度评估', 'Dimensions')], ['actions', tx(lang, '行动建议', 'Actions')],
    ...(data.geo ? [['platforms', tx(lang, '平台检索', 'Platforms')]] : []),
    ['pages', tx(lang, '逐页证据', 'Page evidence')], ['snapshot', tx(lang, '站点快照', 'Snapshot')]
  ];
  host.innerHTML = `<div class="diagnostic-report" data-report-version="diagnostic-report-v2">
    ${renderOverview(task, data, lang)}<nav class="dr-nav" aria-label="${tx(lang, '报告目录', 'Report sections')}">${nav.map(([id, label]) => `<a href="#diagnosis-${id}" data-report-nav>${label}</a>`).join('')}</nav>
    ${data.geo?.blockers?.length ? `<aside class="dr-blockers"><strong>${tx(lang, '关键阻断', 'Critical blockers')}</strong><ul>${data.geo.blockers.map(blocker => `<li>${e(blocker.reason)} · ${safeLink(blocker.url)}</li>`).join('')}</ul></aside>` : ''}
    ${renderIssues(data, lang)}${renderCoverage(data, lang)}${renderEvidenceProfile(data, lang)}
    ${renderDimensions(data, lang)}${renderActions(data, result, lang)}${renderPlatforms(data, lang)}
    ${renderPages(data, lang)}${renderSnapshot(result, lang)}${renderMethod(data, result, lang)}
  </div>`;
  mountDiagnosticReport(host);
  setCachedReportHtml?.(task, lang, host.innerHTML);
}

export function mountDiagnosticReport(host) {
  if (!host?.addEventListener || !host.querySelector('.diagnostic-report') || host._diagnosticReportBound) return;
  host._diagnosticReportBound = true;
  const openSiteLinks = () => {
    const tab = host.ownerDocument?.querySelector('[data-tab="site-links"]');
    tab?.click();
    tab?.focus();
  };
  const filter = () => {
    const search = host.querySelector('[data-issue-search]')?.value.toLowerCase().trim() || '';
    const engine = host.querySelector('[data-issue-engine]')?.value || '';
    const rank = host.querySelector('[data-issue-priority]')?.value || '';
    const rows = [...host.querySelectorAll('[data-issue-row]')];
    let visible = 0;
    for (const row of rows) {
      row.hidden = Boolean((search && !row.dataset.search.includes(search)) || (engine && row.dataset.engine !== engine) || (rank && row.dataset.priority !== rank));
      if (!row.hidden) visible++;
    }
    const count = host.querySelector('[data-issue-count]');
    if (count) count.textContent = visible + ' / ' + rows.length;
    const noRows = host.querySelector('[data-issue-empty]');
    if (noRows) noRows.hidden = visible > 0;
  };
  host.addEventListener('input', event => { if (event.target.matches('[data-issue-search]')) filter(); });
  host.addEventListener('change', event => { if (event.target.matches('[data-issue-engine], [data-issue-priority]')) filter(); });
  host.addEventListener('click', event => {
    const link = event.target.closest('a[data-report-nav], a[data-open-pages], a[data-open-site-links]');
    if (!link) return;
    // The workspace reloads on popstate; keep report navigation inside this view.
    event.preventDefault();
    if (link.hasAttribute('data-open-site-links')) {
      openSiteLinks();
      return;
    }
    const target = host.querySelector(link.getAttribute('href'));
    if (target?.tagName === 'DETAILS') target.open = true;
    if (link.hasAttribute('data-open-pages')) {
      const pages = [...(target?.querySelectorAll('.dr-page') || [])];
      const page = link.dataset.targetPage ? pages.find(item => item.dataset.pageUrl === link.dataset.targetPage) : pages[0];
      if (!page && link.dataset.targetPage) {
        openSiteLinks();
        return;
      }
      if (page) {
        page.open = true;
        page.scrollIntoView({ block: 'start' });
        return;
      }
    }
    target?.scrollIntoView({ block: 'start' });
  });
}

