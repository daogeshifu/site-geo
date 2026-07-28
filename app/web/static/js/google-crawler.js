const $ = id => document.getElementById(id);
const form = $('crawler-form');
const runButton = $('run-test');
const DEMO_TOKEN_STORAGE_KEY = 'geo-audit-demo-token-today';
let elapsedTimer = null;
let startedAt = 0;
let currentChecklist = [];
let currentResultUrl = '';
let restoredTokenDate = null;

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

function localDateKey(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function forgetSavedDemoToken() {
  restoredTokenDate = null;
  try {
    localStorage.removeItem(DEMO_TOKEN_STORAGE_KEY);
  } catch {
    // 浏览器禁用本地存储时仍可正常手动输入。
  }
}

function rememberDemoToken(token) {
  if (!token) return;
  restoredTokenDate = localDateKey();
  try {
    localStorage.setItem(DEMO_TOKEN_STORAGE_KEY, JSON.stringify({
      token,
      date: restoredTokenDate
    }));
  } catch {
    // 隐私模式或存储空间受限时不影响本次检测。
  }
}

function restoreDemoTokenForToday() {
  try {
    const saved = JSON.parse(localStorage.getItem(DEMO_TOKEN_STORAGE_KEY) || 'null');
    if (saved?.date === localDateKey() && typeof saved.token === 'string' && saved.token) {
      $('demo-token').value = saved.token;
      restoredTokenDate = saved.date;
      return true;
    }
  } catch {
    // 无效或不可读的数据按未保存处理。
  }
  forgetSavedDemoToken();
  $('demo-token').value = '';
  return false;
}

function setTokenRowMessage(remembered) {
  const message = $('token-row').querySelector('span');
  message.textContent = remembered ? '今日已记住，无需再次输入' : '此环境已启用访问保护';
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
  const rendering = overview.rendering || {};
  const isClientRendered = rendering.type === 'client_rendered';
  const isServerRendered = ['server_rendered', 'hybrid_rendered'].includes(rendering.type);
  const isRenderingFailure = ['thin_content', 'hydration_loss'].includes(rendering.type)
    || rendering.status === 'failed';
  const renderingLabel = rendering.label || (isClientRendered
    ? '客户端渲染'
    : isServerRendered
      ? '服务端渲染 / 静态输出'
      : '渲染方式待确认');
  const renderingPanel = $('overview-rendering');
  renderingPanel.className = `rendering-verdict ${
    isClientRendered ? 'is-client' : isServerRendered ? 'is-server' : isRenderingFailure ? 'is-error' : 'is-unknown'
  }`;
  renderingPanel.innerHTML = `
    <span class="rendering-verdict-icon">${isClientRendered || isRenderingFailure ? '!' : isServerRendered ? '✓' : '?'}</span>
    <div>
      <small>页面渲染方式</small>
      <strong>${escapeHtml(renderingLabel)}</strong>
      <p>${isClientRendered
        ? '核心内容依赖 JavaScript 客户端渲染，对搜索引擎抓取、稳定索引和内容识别不利。'
        : isServerRendered
          ? '核心内容已在初始 HTML 中输出，对搜索引擎抓取和索引更友好。'
          : isRenderingFailure
            ? '页面核心内容不足或渲染后发生丢失，需要优先检查内容输出和 hydration。'
            : '当前数据不足，暂时无法准确判断页面渲染方式。'}</p>
    </div>
    <em>${isClientRendered ? '黄色警告 · 需关注' : isServerRendered ? 'SEO 友好' : isRenderingFailure ? '未通过' : '待确认'}</em>
  `;
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

function combineChecklistStatuses(rawStatus, renderStatus) {
  const statuses = [rawStatus, renderStatus].map(status => checklistStatus(status).key);
  if (statuses.includes('failed')) return 'failed';
  if (statuses.includes('warning')) return 'warning';
  if (statuses.every(status => status === 'skipped')) return 'skipped';
  if (statuses.includes('skipped')) return 'warning';
  return 'passed';
}

function buildProblemChecklist(data) {
  const googlebot = data.googlebot || {};
  const googleRender = data.google_render || {};
  const googlebotRequest = googlebot.request || {};
  const fallbackUsed = googlebot.access?.browser_fallback_used === true;
  const rawRequest = fallbackUsed ? googlebot.control_request || googlebotRequest : googlebotRequest;
  const content = googlebot.content || {};
  const crawlability = googlebot.crawlability || {};
  const indexability = googlebot.indexability || {};
  const renderedContent = googleRender.rendered_content || {};
  const renderRequest = googleRender.request || {};
  const diagnostics = googleRender.diagnostics || {};
  const checks = [...(googlebot.checks || []), ...(googleRender.checks || [])];
  const findCheck = key => checks.find(item => item.key === key);
  const renderExecuted = googleRender.status !== 'skipped'
    && Boolean(googleRender.request || googleRender.rendered_content);
  const rawSource = fallbackUsed ? '用户 UA' : 'Googlebot';
  const row = (category, item, whitepaperUrl, rawStatus, rawFinding, renderStatus, renderFinding, recommendation) => {
    const status = combineChecklistStatuses(rawStatus, renderStatus);
    return {
      category,
      item,
      whitepaperUrl,
      ...checklistStatus(status),
      rawSource,
      rawFinding: rawFinding || '未取得结果',
      renderFinding: renderFinding || '未取得结果',
      finding: `Raw HTML（${rawSource}）：${rawFinding || '未取得结果'}\nRender HTML：${renderFinding || '未取得结果'}`,
      recommendation
    };
  };
  const finalUrl = rawRequest.final_url || data.url || '';
  const htmlBytes = Number(content.html_bytes ?? rawRequest.html_bytes ?? 0);
  const renderedHtmlBytes = Number(renderedContent.html_bytes || 0);
  const resourceFailures = (diagnostics.failed_resources || []).length + (diagnostics.http_errors || []).length;
  const jsErrors = (diagnostics.page_errors || []).length;
  const renderUnavailableText = googleRender.status === 'skipped' ? '本次未执行渲染' : '未取得渲染数据';
  const renderedDirectives = renderedContent.directives || [];
  const renderedNoindex = renderedDirectives.includes('noindex');
  const renderedFinalUrl = renderRequest.final_url || '';
  const pageSizeStatus = bytes => bytes > 3 * 1024 * 1024
    ? 'fail'
    : bytes > 1024 * 1024
      ? 'warning'
      : bytes
        ? 'pass'
        : 'warning';
  const h1Status = (count, missingStatus = 'fail') => Number(count) === 1
    ? 'pass'
    : Number(count) === 0
      ? missingStatus
      : 'warning';
  const rows = [];

  rows.push(row(
    'SEO 规则', 'Robots.txt 抓取权限', 'https://www.idtcpack.com/seo_book/robots',
    findCheck('robots')?.status || (crawlability.allowed === true ? 'pass' : crawlability.allowed === false ? 'fail' : 'warning'),
    findCheck('robots')?.detail || crawlability.detail,
    renderExecuted ? (crawlability.allowed === false ? 'fail' : 'pass') : 'skipped',
    renderExecuted
      ? crawlability.allowed === false ? '抓取被阻止，渲染结果不能代表可正常访问' : '已在当前抓取权限基础上执行渲染'
      : renderUnavailableText,
    crawlability.allowed === false ? '调整 robots.txt，允许 Googlebot 抓取需要参与搜索的页面与资源。' : '保持规则清晰，并避免屏蔽核心 CSS、JS 和页面路径。'
  ));
  rows.push(row(
    'SEO 规则', 'HTTPS 页面访问', 'https://www.idtcpack.com/seo_book/https',
    finalUrl.startsWith('https://') ? 'pass' : 'warning',
    finalUrl ? `最终访问地址为 ${finalUrl}` : '未取得最终访问地址',
    renderExecuted ? (renderedFinalUrl.startsWith('https://') ? 'pass' : 'warning') : 'skipped',
    renderExecuted ? renderedFinalUrl ? `最终渲染地址为 ${renderedFinalUrl}` : '未取得最终渲染地址' : renderUnavailableText,
    '全站启用 HTTPS，并将 HTTP 版本通过 301 永久重定向到 HTTPS。'
  ));
  rows.push(row(
    '引擎规范', 'HTTP 状态码', 'https://www.idtcpack.com/seo_book/http',
    rawRequest.status_code === 200 ? 'pass' : 'fail',
    `返回 HTTP ${valueOrDash(rawRequest.status_code)}，耗时 ${valueOrDash(rawRequest.response_time_ms, ' ms')}`,
    renderExecuted ? (renderRequest.status_code === 200 ? 'pass' : 'fail') : 'skipped',
    renderExecuted ? `主文档返回 HTTP ${valueOrDash(renderRequest.status_code)}` : renderUnavailableText,
    '核心可索引页面应稳定返回 HTTP 200；修复 4xx、5xx 和不必要的重定向。'
  ));
  rows.push(row(
    '引擎规范', 'URL 重定向', 'https://www.idtcpack.com/seo_book/url',
    Number(rawRequest.redirect_count || 0) <= 1 ? 'pass' : 'warning',
    `本次经过 ${Number(rawRequest.redirect_count || 0)} 次重定向`,
    renderExecuted ? (!renderedFinalUrl || renderedFinalUrl === finalUrl ? 'pass' : 'warning') : 'skipped',
    renderExecuted
      ? renderedFinalUrl === finalUrl ? '渲染最终地址与 Raw HTML 一致' : `渲染最终地址为 ${renderedFinalUrl || '未知'}`
      : renderUnavailableText,
    '减少重定向链，目标页面尽量一次跳转到最终规范 URL。'
  ));
  rows.push(row(
    '引擎规范', 'Noindex 索引指令', 'https://www.idtcpack.com/seo_book/noindex',
    findCheck('indexable')?.status || (indexability.indexable === true ? 'pass' : indexability.indexable === false ? 'fail' : 'warning'),
    findCheck('indexable')?.detail || `索引状态为 ${indexability.state || '待确认'}`,
    renderExecuted ? (renderedNoindex ? 'fail' : 'pass') : 'skipped',
    renderExecuted ? renderedNoindex ? '渲染 DOM 检测到 noindex' : '渲染 DOM 未检测到 noindex' : renderUnavailableText,
    '需要参与搜索的页面不要设置 noindex，并确认响应头与 HTML Meta 指令一致。'
  ));
  rows.push(row(
    '引擎规范', '移动端渲染', 'https://www.idtcpack.com/seo_book/mobile',
    rawRequest.status_code === 200 ? 'pass' : 'warning',
    `作为 Googlebot Smartphone 的初始 HTML 输入，HTTP ${valueOrDash(rawRequest.status_code)}`,
    renderExecuted ? findCheck('render_status')?.status || googleRender.status : 'skipped',
    renderExecuted ? `使用 ${googleRender.engine || '移动端渲染引擎'} 完成模拟` : renderUnavailableText,
    '使用移动优先布局，并在 Google Search Console 中复核真实移动版渲染结果。'
  ));
  rows.push(row(
    '引擎规范', 'JavaScript 加载', 'https://www.idtcpack.com/seo_book/js',
    Number(content.word_count || 0) >= 50 ? 'pass' : 'warning',
    `初始 HTML 约 ${Number(content.word_count || 0)} 个词/字符单元`,
    renderExecuted ? findCheck('javascript')?.status || (jsErrors ? 'fail' : 'pass') : 'skipped',
    renderExecuted ? findCheck('javascript')?.detail || `发现 ${jsErrors} 个页面级 JavaScript 异常` : renderUnavailableText,
    '修复首屏 JavaScript 异常，确保核心正文和链接不依赖失败的客户端请求。'
  ));
  rows.push(row(
    'SEO 元素', 'Title 标题', 'https://www.idtcpack.com/seo_book/title',
    content.title ? 'pass' : 'warning',
    content.title ? `检测到 Title：${content.title}` : '未检测到 Title',
    renderExecuted ? (renderedContent.title ? 'pass' : 'fail') : 'skipped',
    renderExecuted ? renderedContent.title ? `检测到 Title：${renderedContent.title}` : '未检测到 Title' : renderUnavailableText,
    '为页面设置唯一、准确且与搜索意图相关的 Title 标题。'
  ));
  rows.push(row(
    'SEO 元素', 'H1 主标题', 'https://www.idtcpack.com/seo_book/h',
    h1Status(content.h1_count, 'warning'),
    `检测到 ${Number(content.h1_count || 0)} 个 H1${content.h1 ? `：${content.h1}` : ''}`,
    renderExecuted ? h1Status(renderedContent.h1_count) : 'skipped',
    renderExecuted
      ? `检测到 ${Number(renderedContent.h1_count || 0)} 个 H1${renderedContent.h1 ? `：${renderedContent.h1}` : ''}`
      : renderUnavailableText,
    '每个页面保留一个清晰的主 H1，并让层级标题准确描述内容结构。'
  ));
  rows.push(row(
    'SEO 元素', 'Canonical 规范链接', 'https://www.idtcpack.com/seo_book/canonical',
    content.canonical ? 'pass' : 'warning',
    content.canonical ? `Canonical 为 ${content.canonical}` : '未检测到 Canonical',
    renderExecuted
      ? renderedContent.canonical
        ? content.canonical && renderedContent.canonical !== content.canonical ? 'warning' : 'pass'
        : 'warning'
      : 'skipped',
    renderExecuted
      ? renderedContent.canonical ? `Canonical 为 ${renderedContent.canonical}` : '未检测到 Canonical'
      : renderUnavailableText,
    '为可索引页面设置指向首选 URL 的绝对 Canonical，并避免冲突信号。'
  ));
  rows.push(row(
    '网站内容', '核心内容完整性', 'https://www.idtcpack.com/seo_book/js',
    findCheck('content')?.status || (Number(content.word_count || 0) >= 50 ? 'pass' : 'warning'),
    findCheck('content')?.detail || `初始 HTML 约 ${Number(content.word_count || 0)} 个词/字符单元`,
    renderExecuted
      ? findCheck('rendered_content')?.status || (Number(renderedContent.word_count || 0) >= 50 ? 'pass' : 'fail')
      : 'skipped',
    renderExecuted
      ? findCheck('rendered_content')?.detail || `渲染后约 ${Number(renderedContent.word_count || 0)} 个词/字符单元`
      : renderUnavailableText,
    '优先在初始 HTML 输出核心正文；强依赖 JavaScript 的页面建议使用 SSR 或静态生成。'
  ));
  rows.push(row(
    '网站内容', '网页 HTML 体积', 'https://www.idtcpack.com/seo_book/pagesize',
    pageSizeStatus(htmlBytes),
    htmlBytes ? `初始 HTML 约 ${Math.round(htmlBytes / 1024)} KB` : '未取得 HTML 体积',
    renderExecuted ? pageSizeStatus(renderedHtmlBytes) : 'skipped',
    renderExecuted
      ? renderedHtmlBytes ? `渲染 DOM 约 ${Math.round(renderedHtmlBytes / 1024)} KB` : '未取得渲染 DOM 体积'
      : renderUnavailableText,
    '精简重复标签、内联数据和无用代码，避免过大的 HTML 延迟抓取与解析。'
  ));
  rows.push(row(
    '网站内容', '核心资源加载', 'https://www.idtcpack.com/seo_book/js',
    rawRequest.status_code === 200 ? 'pass' : 'warning',
    `初始 HTML 引用了 ${Number(content.script_count || 0)} 个脚本`,
    renderExecuted ? findCheck('resources')?.status || (resourceFailures ? 'warning' : 'pass') : 'skipped',
    renderExecuted ? findCheck('resources')?.detail || `发现 ${resourceFailures} 个异常资源` : renderUnavailableText,
    '确保核心 JS、CSS、图片、字体和 API 可公开访问并稳定返回成功状态。'
  ));
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
      <td data-label="检查事项">
        <a class="checklist-item-link" href="${escapeHtml(item.whitepaperUrl)}" target="_blank" rel="noreferrer">
          ${escapeHtml(item.item)}
        </a>
      </td>
      <td data-label="是否有问题"><span class="checklist-status status-${escapeHtml(item.key)}">${escapeHtml(item.label)}</span></td>
      <td data-label="检测结论">
        <div class="checklist-source-line">
          <strong>Raw HTML（${escapeHtml(item.rawSource)}）</strong>
          <span>${escapeHtml(item.rawFinding)}</span>
        </div>
        <div class="checklist-source-line">
          <strong>Render HTML</strong>
          <span>${escapeHtml(item.renderFinding)}</span>
        </div>
      </td>
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
    [item.category, item.item, item.label, item.finding, item.recommendation, item.whitepaperUrl]
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
  <Column ss:Width="90"/><Column ss:Width="150"/><Column ss:Width="80"/><Column ss:Width="410"/><Column ss:Width="360"/><Column ss:Width="240"/>
  <Row ss:Height="28">${xmlCell('页面 SEO 基础问题清单', 'Title')}<Cell ss:MergeAcross="4" ss:StyleID="Title"/></Row>
  <Row>${xmlCell('检测页面', 'Meta')}${xmlCell(currentResultUrl, 'Meta')}<Cell ss:MergeAcross="3" ss:StyleID="Meta"/></Row>
  <Row>${xmlCell('导出时间', 'Meta')}${xmlCell(new Date().toLocaleString('zh-CN'), 'Meta')}<Cell ss:MergeAcross="3" ss:StyleID="Meta"/></Row>
  <Row>${['分类', '检查事项', '是否有问题', '检测结论', '修改建议', '白皮书链接'].map(value => xmlCell(value, 'Header')).join('')}</Row>
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
    const tokenRequired = Boolean(payload.data?.token_required);
    $('token-row').hidden = !tokenRequired;
    if (tokenRequired) {
      setTokenRowMessage(restoreDemoTokenForToday());
    } else {
      forgetSavedDemoToken();
    }
  } catch {
    $('token-row').hidden = true;
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  const url = $('test-url').value.trim();
  if (!url) return;
  if (restoredTokenDate && restoredTokenDate !== localDateKey()) {
    forgetSavedDemoToken();
    $('demo-token').value = '';
    $('token-row').hidden = false;
    setTokenRowMessage(false);
    $('error-message').textContent = '日期已变化，请重新输入 Demo Token。';
    $('error-box').hidden = false;
    return;
  }
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
    if (!response.ok) {
      if (response.status === 401) {
        forgetSavedDemoToken();
        $('demo-token').value = '';
        $('token-row').hidden = false;
        setTokenRowMessage(false);
      }
      throw new Error(await readError(response));
    }
    const payload = await response.json();
    if (!payload.success) throw new Error(payload.message || '检测请求失败');
    rememberDemoToken(token);
    setTokenRowMessage(Boolean(token));
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
