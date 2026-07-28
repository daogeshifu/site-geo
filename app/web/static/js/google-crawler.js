const $ = id => document.getElementById(id);
const form = $('crawler-form');
const runButton = $('run-test');
let elapsedTimer = null;
let startedAt = 0;
let currentChecklist = [];
let currentResultUrl = '';

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

function statusLabel(status) {
  return {
    passed: '通过',
    warning: '需关注',
    failed: '未通过',
    skipped: '未执行'
  }[status] || '未知';
}

function valueOrDash(value, suffix = '') {
  return value === null || value === undefined || value === '' ? '—' : `${value}${suffix}`;
}

function renderChecks(checks = []) {
  if (!checks.length) return '<div class="empty-issues">本次没有可展示的检查项。</div>';
  return `<div class="checks">${checks.map(item => `
    <div class="check ${escapeHtml(item.status)}">
      <span class="check-mark">${item.status === 'pass' ? '✓' : item.status === 'fail' ? '!' : '•'}</span>
      <div><strong>${escapeHtml(item.label)}</strong><p>${escapeHtml(item.detail)}</p></div>
    </div>
  `).join('')}</div>`;
}

function renderIssues(issues = []) {
  if (!issues.length) return '<div class="empty-issues">未发现需要修复的主要问题。</div>';
  return `<div class="issues">${issues.map(item => `
    <article class="issue severity-${escapeHtml(item.severity)}">
      <div class="issue-head">
        <span class="severity severity-${escapeHtml(item.severity)}">${escapeHtml(item.severity)}</span>
        <b>${escapeHtml(item.title)}</b>
      </div>
      <p>${escapeHtml(item.detail)}</p>
      <p class="fix"><strong>建议：</strong>${escapeHtml(item.recommendation)}</p>
    </article>
  `).join('')}</div>`;
}

function renderMetrics(items) {
  return `<div class="metric-grid">${items.map(([label, value, title = '']) => `
    <div class="metric"><small>${escapeHtml(label)}</small><strong title="${escapeHtml(title || value)}">${escapeHtml(value)}</strong></div>
  `).join('')}</div>`;
}

function copyIcon() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="8" y="8" width="11" height="11" rx="2"></rect>
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path>
    </svg>
  `;
}

function checkIcon() {
  return `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12 4 4L19 6"></path>
    </svg>
  `;
}

function renderCopyButton(label) {
  return `
    <button class="copy-result" type="button" data-copy-content aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">
      ${copyIcon()}
      <span>复制</span>
    </button>
  `;
}

function resultWithoutRawHtmlBody(result) {
  const rawHtml = result?.raw_html;
  if (!rawHtml) return result;
  const summarized = { active_source: rawHtml.active_source };
  for (const key of ['googlebot', 'browser_control']) {
    const item = rawHtml[key];
    summarized[key] = item
      ? { ...item, html: '[Raw HTML 已在下方单独展示，可使用对应按钮复制]' }
      : null;
  }
  return { ...result, raw_html: summarized };
}

function renderRawDetails(result, label) {
  const displayResult = resultWithoutRawHtmlBody(result);
  return `
    <details class="details" data-copy-container>
      <summary>
        <span>${escapeHtml(label)}</span>
        ${renderCopyButton('复制 JSON 检测结果')}
      </summary>
      <pre>${escapeHtml(JSON.stringify(displayResult, null, 2))}</pre>
    </details>
  `;
}

function renderRawHtml(result) {
  const rawHtml = result?.raw_html || {};
  const entries = ['googlebot', 'browser_control']
    .map(key => [key, rawHtml[key]])
    .filter(([, item]) => item && typeof item.html === 'string');
  if (!entries.length) return '';

  return `
    <section class="raw-html-section">
      <div class="raw-html-title">
        <div>
          <h4>网页原始 Raw HTML</h4>
          <p>完整展示实际取得的原始响应；标记“用于检测”的响应是本次内容与渲染判断的数据源。</p>
        </div>
        <span>${entries.length} 份响应</span>
      </div>
      <div class="raw-html-list">
        ${entries.map(([key, item]) => `
          <article class="raw-html-card${item.used_for_analysis ? ' active-source' : ''}" data-copy-container>
            <header>
              <div>
                <strong>${escapeHtml(item.label || key)}</strong>
                <p>
                  HTTP ${escapeHtml(valueOrDash(item.status_code))}
                  · ${escapeHtml(valueOrDash(item.html_bytes, ' bytes'))}
                  ${item.truncated ? ' · 已截断' : ''}
                </p>
              </div>
              <div class="raw-html-actions">
                ${item.used_for_analysis ? '<span class="source-badge">用于检测</span>' : ''}
                ${renderCopyButton(`复制${item.label || '原始 HTML'}`)}
              </div>
            </header>
            <pre>${escapeHtml(item.html)}</pre>
          </article>
        `).join('')}
      </div>
    </section>
  `;
}

function renderOverview(overview = {}) {
  const seo = overview.seo || {};
  $('overview-summary').textContent = overview.summary || '本次检测未返回总览结论，请查看下方问题清单。';
  $('overview-verdict').textContent = statusLabel(overview.status || seo.status);
  $('overview-verdict').className = `status-pill status-${overview.status || seo.status || 'warning'}`;
}

function checklistStatus(status) {
  if (status === 'pass' || status === 'passed') return { key: 'passed', label: '无问题' };
  if (status === 'fail' || status === 'failed') return { key: 'failed', label: '有问题' };
  if (status === 'skipped') return { key: 'skipped', label: '未检测' };
  return { key: 'warning', label: '需关注' };
}

function buildProblemChecklist(data) {
  const googlebot = data.googlebot || {};
  const googleRender = data.google_render || {};
  const request = googlebot.request || {};
  const content = googlebot.content || {};
  const crawlability = googlebot.crawlability || {};
  const indexability = googlebot.indexability || {};
  const renderedContent = googleRender.rendered_content || {};
  const diagnostics = googleRender.diagnostics || {};
  const checks = [...(googlebot.checks || []), ...(googleRender.checks || [])];
  const findCheck = key => checks.find(item => item.key === key);
  const row = (category, item, status, finding, recommendation) => ({
    category,
    item,
    ...checklistStatus(status),
    finding: finding || '本次未返回检测详情。',
    recommendation
  });
  const finalUrl = request.final_url || data.url || '';
  const htmlBytes = Number(content.html_bytes ?? request.html_bytes ?? 0);
  const resourceFailures = (diagnostics.failed_resources || []).length + (diagnostics.http_errors || []).length;
  const jsErrors = (diagnostics.page_errors || []).length;
  const rows = [];

  rows.push(row('SEO 规则', 'Robots.txt 抓取权限',
    findCheck('robots')?.status || (crawlability.allowed === true ? 'pass' : crawlability.allowed === false ? 'fail' : 'warning'),
    findCheck('robots')?.detail || crawlability.detail,
    crawlability.allowed === false ? '调整 robots.txt，允许 Googlebot 抓取需要参与搜索的页面与资源。' : '保持规则清晰，并避免屏蔽核心 CSS、JS 和页面路径。'));
  rows.push(row('SEO 规则', 'HTTPS 页面访问',
    finalUrl.startsWith('https://') ? 'pass' : 'warning',
    finalUrl ? `最终访问地址：${finalUrl}` : '未取得最终访问地址。',
    '全站启用 HTTPS，并将 HTTP 版本通过 301 永久重定向到 HTTPS。'));
  rows.push(row('引擎规范', 'HTTP 状态码',
    findCheck('http')?.status || (request.status_code === 200 ? 'pass' : 'fail'),
    findCheck('http')?.detail || `页面返回 HTTP ${valueOrDash(request.status_code)}。`,
    '核心可索引页面应稳定返回 HTTP 200；修复 4xx、5xx 和不必要的重定向。'));
  rows.push(row('引擎规范', 'URL 重定向',
    Number(request.redirect_count || 0) <= 1 ? 'pass' : 'warning',
    `本次经过 ${Number(request.redirect_count || 0)} 次重定向。`,
    '减少重定向链，目标页面尽量一次跳转到最终规范 URL。'));
  rows.push(row('引擎规范', 'Noindex 索引指令',
    findCheck('indexable')?.status || (indexability.indexable === true ? 'pass' : indexability.indexable === false ? 'fail' : 'warning'),
    findCheck('indexable')?.detail || `索引状态：${indexability.state || '待确认'}。`,
    '需要参与搜索的页面不要设置 noindex，并确认响应头与 HTML Meta 指令一致。'));
  rows.push(row('引擎规范', '移动端渲染',
    googleRender.status === 'skipped' ? 'skipped' : findCheck('render_status')?.status || googleRender.status,
    googleRender.status === 'skipped' ? 'Google Render 本次未执行。' : `使用 ${googleRender.engine || '移动端渲染引擎'} 完成模拟。`,
    '使用移动优先布局，并在 Google Search Console 中复核真实移动版渲染结果。'));
  rows.push(row('引擎规范', 'JavaScript 加载',
    googleRender.status === 'skipped' ? 'skipped' : findCheck('javascript')?.status || (jsErrors ? 'fail' : 'pass'),
    findCheck('javascript')?.detail || `发现 ${jsErrors} 个页面级 JavaScript 异常。`,
    '修复首屏 JavaScript 异常，确保核心正文和链接不依赖失败的客户端请求。'));
  rows.push(row('SEO 元素', 'Title 标题',
    content.title ? 'pass' : 'fail',
    content.title ? `已检测到：${content.title}` : '初始 HTML 未检测到 Title。',
    '为页面设置唯一、准确且与搜索意图相关的 Title 标题。'));
  rows.push(row('SEO 元素', 'H1 主标题',
    Number(content.h1_count) === 1 ? 'pass' : Number(content.h1_count) === 0 ? 'fail' : 'warning',
    Number(content.h1_count) === 1 ? `已检测到 1 个 H1：${content.h1 || '有主标题'}` : `检测到 ${Number(content.h1_count || 0)} 个 H1。`,
    '每个页面保留一个清晰的主 H1，并让层级标题准确描述内容结构。'));
  rows.push(row('SEO 元素', 'Canonical 规范链接',
    content.canonical ? 'pass' : 'warning',
    content.canonical ? `Canonical：${content.canonical}` : '初始 HTML 未检测到 Canonical。',
    '为可索引页面设置指向首选 URL 的绝对 Canonical，并避免冲突信号。'));
  rows.push(row('网站内容', '初始 HTML 核心内容',
    findCheck('content')?.status || (Number(content.word_count || 0) >= 50 ? 'pass' : 'warning'),
    findCheck('content')?.detail || `初始 HTML 约 ${Number(content.word_count || 0)} 个词/字符单元。`,
    '优先在初始 HTML 输出核心正文；强依赖 JavaScript 的页面建议使用 SSR 或静态生成。'));
  rows.push(row('网站内容', '网页 HTML 体积',
    htmlBytes > 3 * 1024 * 1024 ? 'fail' : htmlBytes > 1024 * 1024 ? 'warning' : htmlBytes ? 'pass' : 'warning',
    htmlBytes ? `初始 HTML 约 ${Math.round(htmlBytes / 1024)} KB。` : '未取得 HTML 体积。',
    '精简重复标签、内联数据和无用代码，避免过大的 HTML 延迟抓取与解析。'));
  rows.push(row('网站内容', '渲染后核心内容',
    googleRender.status === 'skipped' ? 'skipped' : findCheck('rendered_content')?.status || (Number(renderedContent.word_count || 0) >= 50 ? 'pass' : 'fail'),
    findCheck('rendered_content')?.detail || `渲染后约 ${Number(renderedContent.word_count || 0)} 个词/字符单元。`,
    '确保渲染完成后正文稳定存在，不被 hydration、鉴权或异步失败覆盖。'));
  rows.push(row('网站内容', '核心资源加载',
    googleRender.status === 'skipped' ? 'skipped' : findCheck('resources')?.status || (resourceFailures ? 'warning' : 'pass'),
    findCheck('resources')?.detail || `发现 ${resourceFailures} 个异常资源。`,
    '确保核心 JS、CSS、图片、字体和 API 可公开访问并稳定返回成功状态。'));
  return rows;
}

function renderProblemChecklist(data) {
  currentChecklist = buildProblemChecklist(data);
  currentResultUrl = data.url || $('test-url').value;
  const totals = currentChecklist.reduce((acc, item) => {
    acc[item.key] = (acc[item.key] || 0) + 1;
    return acc;
  }, {});
  $('checklist-stats').innerHTML = [
    ['all', '检查事项', currentChecklist.length],
    ['failed', '有问题', totals.failed || 0],
    ['warning', '需关注', totals.warning || 0],
    ['passed', '无问题', totals.passed || 0],
    ['skipped', '未检测', totals.skipped || 0]
  ].map(([key, label, value]) => `
    <div class="checklist-stat status-${key}"><strong>${value}</strong><span>${label}</span></div>
  `).join('');
  $('checklist-body').innerHTML = currentChecklist.map(item => `
    <tr>
      <td data-label="分类"><span class="category-label">${escapeHtml(item.category)}</span></td>
      <td data-label="检查事项"><strong>${escapeHtml(item.item)}</strong></td>
      <td data-label="是否有问题"><span class="checklist-status status-${escapeHtml(item.key)}">${escapeHtml(item.label)}</span></td>
      <td data-label="检测结论">${escapeHtml(item.finding)}</td>
      <td data-label="修改建议">${escapeHtml(item.recommendation)}</td>
    </tr>
  `).join('');
}

function xmlCell(value, styleId = '') {
  const safe = escapeHtml(String(value ?? '')).replaceAll('\n', '&#10;');
  return `<Cell${styleId ? ` ss:StyleID="${styleId}"` : ''}><Data ss:Type="String">${safe}</Data></Cell>`;
}

function exportChecklistExcel() {
  if (!currentChecklist.length) return;
  const rows = currentChecklist.map(item => `<Row>${
    [item.category, item.item, item.label, item.finding, item.recommendation]
      .map(value => xmlCell(value, 'Body')).join('')
  }</Row>`).join('');
  const workbook = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Styles>
  <Style ss:ID="Default"><Alignment ss:Vertical="Top" ss:WrapText="1"/><Font ss:FontName="Arial" ss:Size="10"/></Style>
  <Style ss:ID="Title"><Font ss:Bold="1" ss:Size="15" ss:Color="#FFFFFF"/><Interior ss:Color="#1677FF" ss:Pattern="Solid"/></Style>
  <Style ss:ID="Meta"><Font ss:Color="#526176"/><Interior ss:Color="#EEF5FF" ss:Pattern="Solid"/></Style>
  <Style ss:ID="Header"><Font ss:Bold="1" ss:Color="#FFFFFF"/><Interior ss:Color="#132238" ss:Pattern="Solid"/><Alignment ss:Vertical="Center"/></Style>
  <Style ss:ID="Body"><Borders><Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#DFE5EC"/></Borders></Style>
 </Styles>
 <Worksheet ss:Name="SEO问题清单"><Table>
  <Column ss:Width="90"/><Column ss:Width="150"/><Column ss:Width="80"/><Column ss:Width="300"/><Column ss:Width="360"/>
  <Row ss:Height="28">${xmlCell('页面 SEO 基础问题清单', 'Title')}<Cell ss:MergeAcross="3" ss:StyleID="Title"/></Row>
  <Row>${xmlCell('检测页面', 'Meta')}${xmlCell(currentResultUrl, 'Meta')}<Cell ss:MergeAcross="2" ss:StyleID="Meta"/></Row>
  <Row>${xmlCell('导出时间', 'Meta')}${xmlCell(new Date().toLocaleString('zh-CN'), 'Meta')}<Cell ss:MergeAcross="2" ss:StyleID="Meta"/></Row>
  <Row>${['分类', '检查事项', '是否有问题', '检测结论', '修改建议'].map(value => xmlCell(value, 'Header')).join('')}</Row>
  ${rows}
 </Table><WorksheetOptions xmlns="urn:schemas-microsoft-com:office:excel"><FreezePanes/><FrozenNoSplit/><SplitHorizontal>4</SplitHorizontal><TopRowBottomPane>4</TopRowBottomPane><ProtectObjects>False</ProtectObjects><ProtectScenarios>False</ProtectScenarios></WorksheetOptions></Worksheet>
</Workbook>`;
  const blob = new Blob(['\ufeff', workbook], { type: 'application/vnd.ms-excel;charset=utf-8' });
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement('a');
  const hostname = (() => {
    try { return new URL(currentResultUrl).hostname.replaceAll('.', '-'); } catch { return 'page'; }
  })();
  link.href = downloadUrl;
  link.download = `SEO问题清单-${hostname}.xls`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
  const exportButton = $('export-checklist');
  exportButton.classList.add('exported');
  exportButton.querySelector('span').textContent = '已开始下载';
  window.setTimeout(() => {
    exportButton.classList.remove('exported');
    exportButton.querySelector('span').textContent = '一键导出 Excel';
  }, 1600);
}

function renderGooglebot(result) {
  const request = result.request || {};
  const crawl = result.crawlability || {};
  const indexability = result.indexability || {};
  const content = result.content || {};
  const usedBrowserFallback = result.access?.browser_fallback_used === true;
  const controlRequest = result.control_request || {};
  const analyzedHtmlBytes = usedBrowserFallback
    ? controlRequest.html_bytes
    : request.html_bytes;
  return `
    <div class="panel-head">
      <div><h3>Googlebot Smartphone</h3><p>${usedBrowserFallback
        ? '模拟 Googlebot 请求被 WAF 拦截；本区保留 Googlebot HTTP 结果，并使用普通浏览器对照响应补充 robots、索引指令和初始 HTML 分析。'
        : '使用公开的移动版 Googlebot User-Agent 请求页面，并检查 robots.txt、HTTP 响应、索引指令与初始 HTML。'}</p></div>
      <div class="panel-score"><strong>${valueOrDash(result.score)}</strong>/ 100 <span class="mini-status status-${escapeHtml(result.status)}">${statusLabel(result.status)}</span></div>
    </div>
    ${renderMetrics([
      ['HTTP 状态', valueOrDash(request.status_code)],
      ['响应时间', valueOrDash(request.response_time_ms, ' ms')],
      ['robots.txt', crawl.allowed === true ? '允许' : crawl.allowed === false ? '阻止' : '不确定'],
      ['索引状态', indexability.indexable === true ? '允许' : indexability.indexable === false ? '不允许' : '待确认'],
      [usedBrowserFallback ? '初始内容（浏览器对照）' : '初始内容', valueOrDash(content.word_count, ' 词/字符')],
      ['内部链接', valueOrDash(content.internal_link_count)],
      ['重定向', valueOrDash(request.redirect_count)],
      [usedBrowserFallback ? 'Raw HTML（浏览器对照）' : 'HTML 体积', analyzedHtmlBytes ? `${Math.round(analyzedHtmlBytes / 1024)} KB` : '—']
    ])}
    <h4 class="section-title">检查项 <span>${(result.checks || []).length} 项</span></h4>
    ${renderChecks(result.checks)}
    <h4 class="section-title">问题与修复建议 <span>${(result.issues || []).length} 项</span></h4>
    ${renderIssues(result.issues)}
    ${renderRawDetails(result, '查看抓取详情与原始结果')}
    ${renderRawHtml(result)}
  `;
}

function renderGoogleRender(result) {
  const request = result.request || {};
  const comparison = result.comparison || {};
  const diagnostics = result.diagnostics || {};
  const metrics = result.status === 'skipped'
    ? [
        ['执行状态', statusLabel(result.status)],
        ['渲染引擎', result.engine || '—'],
        ['服务可用', result.available ? '是' : '否'],
        ['评分', valueOrDash(result.score)]
      ]
    : [
        ['HTTP 状态', valueOrDash(request.status_code)],
        ['渲染耗时', valueOrDash(request.render_time_ms, ' ms')],
        ['渲染后内容', valueOrDash(comparison.rendered_word_count, ' 词/字符')],
        ['内容变化', valueOrDash(comparison.word_delta)],
        ['渲染后内链', valueOrDash(comparison.rendered_internal_links)],
        ['链接变化', valueOrDash(comparison.link_delta)],
        ['JS 页面异常', valueOrDash((diagnostics.page_errors || []).length)],
        ['异常资源', valueOrDash((diagnostics.failed_resources || []).length + (diagnostics.http_errors || []).length)]
      ];
  return `
    <div class="panel-head">
      <div><h3>Google Web Rendering 模拟</h3><p>${result.mode === 'browser_fallback'
        ? '模拟 Googlebot 被 WAF 拦截，本次改用普通浏览器 UA 执行 JavaScript，仅用于判断 CSR/SSR 与页面资源状态；真实 Googlebot 结果需由 Search Console 确认。'
        : '使用移动视口和 Googlebot Smartphone UA 的无头 Chromium 执行 JavaScript，对比初始 HTML 与渲染 DOM，并记录脚本、资源和网络异常。'}</p></div>
      <div class="panel-score"><strong>${valueOrDash(result.score)}</strong>${result.score === null ? '' : ' / 100'} <span class="mini-status status-${escapeHtml(result.status)}">${statusLabel(result.status)}</span></div>
    </div>
    ${renderMetrics(metrics)}
    <h4 class="section-title">检查项 <span>${(result.checks || []).length} 项</span></h4>
    ${renderChecks(result.checks)}
    <h4 class="section-title">问题与修复建议 <span>${(result.issues || []).length} 项</span></h4>
    ${renderIssues(result.issues)}
    ${renderRawDetails(result, '查看渲染详情与原始结果')}
  `;
}

async function copyResultText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.setAttribute('readonly', '');
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  textarea.style.pointerEvents = 'none';
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand('copy');
  textarea.remove();
  if (!copied) throw new Error('浏览器未允许复制');
}

function setLoading(loading) {
  runButton.disabled = loading;
  runButton.classList.toggle('busy', loading);
  $('empty-state').hidden = true;
  $('results').hidden = true;
  $('error-box').hidden = true;
  $('loading-state').hidden = !loading;
  if (loading) {
    startedAt = performance.now();
    elapsedTimer = window.setInterval(() => {
      $('elapsed-time').textContent = `${((performance.now() - startedAt) / 1000).toFixed(1)}s`;
    }, 100);
  } else {
    clearInterval(elapsedTimer);
  }
}

function showResults(data) {
  const url = data.url || $('test-url').value;
  $('result-title').textContent = data.status === 'passed' ? '页面可正常抓取与渲染' : data.status === 'failed' ? '检测到阻断性问题' : '检测完成，有项目需要关注';
  $('result-url').textContent = url;
  $('result-url').href = url;
  $('overall-score').querySelector('strong').textContent = valueOrDash(data.score);
  $('overall-status').textContent = statusLabel(data.status);
  $('overall-status').className = `status-pill status-${data.status}`;
  $('disclaimer').textContent = data.disclaimer || '';
  renderOverview(data.overview || {});
  renderProblemChecklist(data);
  $('panel-googlebot').innerHTML = renderGooglebot(data.googlebot || {});
  $('panel-google-render').innerHTML = renderGoogleRender(data.google_render || {});
  $('results').hidden = false;
  $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function readError(response) {
  try {
    const payload = await response.json();
    return payload.message || payload.detail || '检测请求失败';
  } catch {
    return `检测请求失败（HTTP ${response.status}）`;
  }
}

async function loadTokenStatus() {
  try {
    const response = await fetch('/api/v1/demo/token-status');
    const payload = await response.json();
    $('token-row').hidden = !payload.data?.token_required;
  } catch {
    $('token-row').hidden = true;
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const url = $('test-url').value.trim();
  if (!url) return;
  setLoading(true);
  try {
    const headers = { 'Content-Type': 'application/json' };
    const token = $('demo-token').value.trim();
    if (token) headers['X-Demo-Token'] = token;
    const response = await fetch('/api/v1/demo/google-crawler/test', {
      method: 'POST',
      headers,
      body: JSON.stringify({ url })
    });
    if (!response.ok) throw new Error(await readError(response));
    const payload = await response.json();
    if (!payload.success) throw new Error(payload.message || '检测请求失败');
    setLoading(false);
    showResults(payload.data);
  } catch (error) {
    setLoading(false);
    $('error-message').textContent = error.message || '检测请求失败';
    $('error-box').hidden = false;
  }
});

$('export-checklist').addEventListener('click', exportChecklistExcel);

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-copy-content]');
  if (!button) return;
  event.preventDefault();
  event.stopPropagation();
  const pre = button.closest('[data-copy-container]')?.querySelector('pre');
  if (!pre) return;
  try {
    await copyResultText(pre.textContent || '');
    button.classList.add('copied');
    button.innerHTML = `${checkIcon()}<span>已复制</span>`;
    window.setTimeout(() => {
      button.classList.remove('copied');
      button.innerHTML = `${copyIcon()}<span>复制</span>`;
    }, 1600);
  } catch {
    button.classList.add('copy-failed');
    button.querySelector('span').textContent = '复制失败';
    window.setTimeout(() => {
      button.classList.remove('copy-failed');
      button.innerHTML = `${copyIcon()}<span>复制</span>`;
    }, 1800);
  }
});

loadTokenStatus();
