const $ = id => document.getElementById(id);
const form = $('crawler-form');
const runButton = $('run-test');
let elapsedTimer = null;
let startedAt = 0;

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

function overviewToneIcon(status) {
  return status === 'passed' ? '✓' : status === 'failed' ? '!' : '•';
}

function renderOverviewIssues(issues = []) {
  if (!issues.length) {
    return '<div class="overview-clear"><span>✓</span><div><strong>未发现主要技术问题</strong><p>抓取、索引与渲染结果符合本次模拟检测的基础标准。</p></div></div>';
  }
  return issues.map(item => `
    <article class="overview-issue severity-${escapeHtml(item.severity)}">
      <div class="overview-issue-source">${escapeHtml(item.source || '检测结果')}</div>
      <div>
        <div class="issue-head">
          <span class="severity severity-${escapeHtml(item.severity)}">${escapeHtml(item.severity)}</span>
          <b>${escapeHtml(item.title)}</b>
        </div>
        <p>${escapeHtml(item.detail)}</p>
        <p class="fix"><strong>优先建议：</strong>${escapeHtml(item.recommendation)}</p>
      </div>
    </article>
  `).join('');
}

function renderOverview(overview = {}) {
  const rendering = overview.rendering || {};
  const seo = overview.seo || {};
  const crawl = overview.crawl || {};
  const indexing = overview.indexing || {};
  const cards = [
    {
      eyebrow: '页面渲染方式',
      label: rendering.label || '无法判定',
      detail: rendering.detail || '本次返回数据不足，无法确认页面渲染方式。',
      status: rendering.status || 'warning',
      metric: rendering.rendered_word_count === null || rendering.rendered_word_count === undefined
        ? '初始内容 ' + valueOrDash(rendering.initial_word_count)
        : `${valueOrDash(rendering.initial_word_count)} → ${valueOrDash(rendering.rendered_word_count)}`
    },
    {
      eyebrow: 'SEO 技术结论',
      label: seo.label || '等待结论',
      detail: seo.detail || '请查看 Googlebot 与 Google Render 检测细项。',
      status: seo.status || overview.status || 'warning',
      metric: '抓取与渲染标准'
    },
    {
      eyebrow: '抓取 / 索引状态',
      label: `${crawl.label || '未知'} · ${indexing.label || '未知'}`,
      detail: `${crawl.detail || ''} ${indexing.detail || ''}`.trim(),
      status: crawl.status === 'failed' || indexing.status === 'failed'
        ? 'failed'
        : crawl.status === 'warning'
          ? 'warning'
          : 'passed',
      metric: 'Googlebot Smartphone'
    }
  ];

  $('overview-summary').textContent = overview.summary || '本次检测未返回总览结论，请查看下方模式细项。';
  $('overview-verdict').textContent = statusLabel(overview.status || seo.status);
  $('overview-verdict').className = `status-pill status-${overview.status || seo.status || 'warning'}`;
  $('overview-cards').innerHTML = cards.map(card => `
    <article class="overview-card status-${escapeHtml(card.status)}">
      <div class="overview-card-top">
        <span class="overview-card-icon">${overviewToneIcon(card.status)}</span>
        <small>${escapeHtml(card.eyebrow)}</small>
        <em>${escapeHtml(card.metric)}</em>
      </div>
      <strong>${escapeHtml(card.label)}</strong>
      <p>${escapeHtml(card.detail)}</p>
    </article>
  `).join('');
  $('overview-issues').innerHTML = renderOverviewIssues(overview.major_issues || []);
}

function renderGooglebot(result) {
  const request = result.request || {};
  const crawl = result.crawlability || {};
  const indexability = result.indexability || {};
  const content = result.content || {};
  return `
    <div class="panel-head">
      <div><h3>Googlebot Smartphone</h3><p>使用公开的移动版 Googlebot User-Agent 请求页面，并检查 robots.txt、HTTP 响应、索引指令与初始 HTML。</p></div>
      <div class="panel-score"><strong>${valueOrDash(result.score)}</strong>/ 100 <span class="mini-status status-${escapeHtml(result.status)}">${statusLabel(result.status)}</span></div>
    </div>
    ${renderMetrics([
      ['HTTP 状态', valueOrDash(request.status_code)],
      ['响应时间', valueOrDash(request.response_time_ms, ' ms')],
      ['robots.txt', crawl.allowed === true ? '允许' : crawl.allowed === false ? '阻止' : '不确定'],
      ['可索引', indexability.indexable ? '是' : '否'],
      ['初始内容', valueOrDash(content.word_count, ' 词/字符')],
      ['内部链接', valueOrDash(content.internal_link_count)],
      ['重定向', valueOrDash(request.redirect_count)],
      ['HTML 体积', request.html_bytes ? `${Math.round(request.html_bytes / 1024)} KB` : '—']
    ])}
    <h4 class="section-title">检查项 <span>${(result.checks || []).length} 项</span></h4>
    ${renderChecks(result.checks)}
    <h4 class="section-title">问题与修复建议 <span>${(result.issues || []).length} 项</span></h4>
    ${renderIssues(result.issues)}
    <details class="details">
      <summary>查看抓取详情与原始结果</summary>
      <pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>
    </details>
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
      <div><h3>Google Web Rendering 模拟</h3><p>使用移动视口的无头 Chromium 执行 JavaScript，对比初始 HTML 与渲染 DOM，并记录脚本、资源和网络异常。</p></div>
      <div class="panel-score"><strong>${valueOrDash(result.score)}</strong>${result.score === null ? '' : ' / 100'} <span class="mini-status status-${escapeHtml(result.status)}">${statusLabel(result.status)}</span></div>
    </div>
    ${renderMetrics(metrics)}
    <h4 class="section-title">检查项 <span>${(result.checks || []).length} 项</span></h4>
    ${renderChecks(result.checks)}
    <h4 class="section-title">问题与修复建议 <span>${(result.issues || []).length} 项</span></h4>
    ${renderIssues(result.issues)}
    <details class="details">
      <summary>查看渲染详情与原始结果</summary>
      <pre>${escapeHtml(JSON.stringify(result, null, 2))}</pre>
    </details>
  `;
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
  $('googlebot-tab-status').className = data.googlebot?.status || '';
  $('render-tab-status').className = data.google_render?.status || '';
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

document.querySelectorAll('.result-tab').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.result-tab').forEach(item => {
      const active = item === button;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('.result-panel').forEach(panel => panel.classList.remove('active'));
    $(`panel-${button.dataset.tab}`).classList.add('active');
  });
});

loadTokenStatus();
