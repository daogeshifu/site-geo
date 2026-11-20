const $ = id => document.getElementById(id);
const form = $('crawler-form');
const runButton = $('run-test');
const agentSelect = $('agent-select');
const tokenInput = $('demo-token');
const DEMO_TOKEN_STORAGE_KEY = 'geo-audit-demo-token-today';
let restoredTokenDate = null;
let activeRequest = null;
let timer = null;

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

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function addMetrics(body, rows) {
  const list = element('dl', undefined, 'metrics');
  for (const [label, value] of rows) {
    if (value == null || value === '') continue;
    const pair = element('div');
    pair.append(element('dt', label), element('dd', value));
    list.append(pair);
  }
  body.append(list);
}

function addDetails(body, label, text, open = false) {
  if (text == null || text === '') return;
  const details = element('details', undefined, 'evidence');
  details.open = open;
  const heading = element('summary', label);
  const pre = element('pre', text);
  const button = element('button', '复制', 'copy');
  button.type = 'button';
  button.setAttribute('aria-label', '复制' + label);
  button.addEventListener('click', async () => {
    try {
      await copyResultText(pre.textContent);
      button.textContent = '已复制';
    } catch {
      button.textContent = '请选中文本复制';
    }
    window.setTimeout(() => { button.textContent = '复制'; }, 1800);
  });
  const content = element('div', undefined, 'evidence-content');
  content.append(button, pre);
  details.append(heading, content);
  body.append(details);
}

function headerLines(headers = {}) {
  return Object.entries(headers).map(([name, value]) => name + ': ' + value).join('\n');
}

function httpEvidence(body, request) {
  if (!request) return;
  const redirects = request.redirect_chain || [];
  const hops = [...redirects.map(hop => [hop.status_code, hop.from]), [request.status_code, request.final_url]];
  const path = element('ol', undefined, 'http-path');
  path.setAttribute('aria-label', 'HTTP 请求路径');
  for (const [code, url] of hops) {
    const row = element('li');
    row.append(element('b', code == null ? '无响应' : 'HTTP ' + code), element('span', url));
    path.append(row);
  }
  body.append(path);
  if (request.retry_after) body.append(element('p', 'Retry-After: ' + request.retry_after, 'notice'));
  addDetails(body, '实际请求头（主要字段）', headerLines(request.headers));
  addDetails(body, '响应头', headerLines(request.response_headers));
}

function robotsEvidence(body, rules) {
  if (!rules) return;
  const text = [rules.url, rules.token + ' · ' + rules.detail];
  if (rules.status_code != null) text.push('HTTP ' + rules.status_code);
  if (rules.request_headers) text.push('', headerLines(rules.request_headers));
  addDetails(body, 'robots.txt 抓取规则', text.join('\n'));
  if (rules.content_use) {
    const usage = rules.content_use;
    body.append(element('p', usage.token + ' 内容使用规则 · ' + (usage.allowed ? '允许' : '禁止') + '（匹配 ' + usage.matched + '）', 'notice'));
  }
}

function drawStage(stageId, result) {
  const body = $(stageId).querySelector('.stage-body');
  body.replaceChildren();
  const request = result.request;
  if (result.reason) body.append(element('p', result.reason, 'notice'));
  if (result.status === 'skipped' || !request) {
    robotsEvidence(body, result.robots);
    return;
  }

  const isRender = stageId === 'panel-render';
  const rows = [
    ['最终响应', request.status_code == null ? '无响应' : 'HTTP ' + request.status_code],
    ['耗时', (isRender ? request.render_time_ms : request.response_time_ms) + ' ms'],
  ];
  if (isRender && request.status_code === 200) {
    const comparison = result.comparison || {};
    rows.push(['渲染后文本', comparison.rendered_word_count], ['文本增减', comparison.word_delta]);
  } else if (!isRender) {
    rows.push(['读取字节', request.size_bytes?.toLocaleString()], ['内容类型', request.content_type]);
  }
  addMetrics(body, rows);
  if (result.content?.title || result.comparison?.title_after) {
    body.append(element('p', '页面标题 · ' + (result.content?.title || result.comparison.title_after), 'page-title'));
  }
  httpEvidence(body, request);
  robotsEvidence(body, result.robots);
  const { raw_html, rendered_html, ...metadata } = result;
  addDetails(body, isRender ? '渲染详情（JSON）' : '抓取详情（JSON）', JSON.stringify(metadata, null, 2));

  if (isRender) {
    const snapshot = rendered_html;
    if (request.network_idle_timed_out) body.append(element('p', '等待网络空闲超时，以下为当时取得的 DOM。', 'notice'));
    const diagnostics = result.diagnostics || {};
    if (Object.values(diagnostics).some(items => items.length)) {
      addDetails(body, '脚本与资源异常', JSON.stringify(diagnostics, null, 2));
    }
    if (snapshot) addDetails(body, '渲染后 HTML' + (snapshot.truncated ? '（已截断）' : ''), snapshot.html, true);
  } else if (raw_html) {
    const label = result.is_html ? '原始 HTML' : '响应正文';
    addDetails(body, label + (result.truncated ? '（已截断）' : ''), raw_html, true);
  } else {
    body.append(element('p', raw_html === '' ? '服务器返回了空正文。' : '此响应为非文本内容。', 'notice'));
  }
}

function showStageMessage(message, renderMessage = message) {
  $('panel-spider').querySelector('.stage-body').replaceChildren(element('p', message, 'stage-empty'));
  $('panel-render')?.querySelector('.stage-body').replaceChildren(element('p', renderMessage, 'stage-empty'));
}

function endRequest() {
  if (activeRequest) activeRequest.abort();
  activeRequest = null;
  clearInterval(timer);
  runButton.disabled = false;
  runButton.textContent = '开始测试';
  form.removeAttribute('aria-busy');
}

function selectAgent() {
  endRequest();
  const token = agentSelect.value;
  $('spider-agent').textContent = token;
  for (const profile of form.querySelectorAll('[data-agent-profile]')) {
    profile.hidden = profile.dataset.agentProfile !== token;
  }
  $('error-box').hidden = true;
  $('run-state').textContent = '';
  showStageMessage('使用所选标识开始测试后，可查看本次响应。');
}

$('platform-select').addEventListener('change', event => {
  endRequest();
  const next = new URL('/crawler-test/' + encodeURIComponent(event.target.value), location.origin);
  const url = $('test-url').value;
  if (url) next.hash = new URLSearchParams({ url }).toString();
  location.assign(next.href);
});
agentSelect?.addEventListener('change', selectAgent);
const carriedUrl = new URLSearchParams(location.hash.slice(1)).get('url');
if (carriedUrl) $('test-url').value = carriedUrl;
window.addEventListener('pageshow', () => {
  $('platform-select').value = form.dataset.platform;
  if (agentSelect && $('spider-agent').textContent !== agentSelect.value) selectAgent();
});

async function loadTokenStatus() {
  try {
    const response = await fetch('/api/v1/demo/token-status');
    const payload = await response.json();
    $('token-row').hidden = !payload.data?.token_required;
    if (!$('token-row').hidden) setTokenRowMessage(restoreDemoTokenForToday());
  } catch {
    $('token-row').hidden = false;
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (activeRequest) return;
  const url = $('test-url').value.trim();
  const errorBox = $('error-box');
  errorBox.hidden = true;
  if (restoredTokenDate && restoredTokenDate !== localDateKey()) {
    forgetSavedDemoToken();
    tokenInput.value = '';
    $('token-row').hidden = false;
    setTokenRowMessage(false);
    errorBox.textContent = '日期已变化，请重新输入访问 Token。';
    errorBox.hidden = false;
    return;
  }
  const controller = new AbortController();
  activeRequest = controller;
  const token = tokenInput.value.trim();
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['X-API-Token'] = token;
  runButton.disabled = true;
  runButton.textContent = '测试中…';
  form.setAttribute('aria-busy', 'true');
  $('run-state').textContent = '正在测试';
  const start = performance.now();
  timer = setInterval(() => { $('run-state').textContent = '正在测试 · ' + Math.floor((performance.now() - start) / 1000) + ' 秒'; }, 1000);
  showStageMessage('正在读取 robots.txt 与网页响应…', '等待抓取结果…');
  try {
    const response = await fetch('/api/v1/crawler/test', {
      method: 'POST', headers, signal: controller.signal,
      body: JSON.stringify({ url, platform: form.dataset.platform, agent: agentSelect?.value }),
    });
    const payload = await response.json();
    if (controller.signal.aborted) return;
    if (!response.ok || !payload.success) {
      if (response.status === 401) {
        forgetSavedDemoToken();
        tokenInput.value = '';
        $('token-row').hidden = false;
        setTokenRowMessage(false);
      }
      throw new Error(payload.message || '请求失败（HTTP ' + response.status + '）');
    }
    rememberDemoToken(token);
    setTokenRowMessage(Boolean(token));
    const data = payload.data;
    drawStage('panel-spider', data.spider);
    if (data.render) drawStage('panel-render', data.render);
    $('run-state').textContent = '测试完成 · ' + data.url;
  } catch (error) {
    if (controller.signal.aborted) return;
    errorBox.textContent = error.message || '测试请求失败';
    errorBox.hidden = false;
    $('run-state').textContent = '';
    showStageMessage('测试未完成。');
  } finally {
    if (activeRequest === controller) endRequest();
  }
});

loadTokenStatus();
