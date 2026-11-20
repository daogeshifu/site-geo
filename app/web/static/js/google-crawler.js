import { drawStage, resetStage } from './crawler-evidence.js?v=20261120-evidence';

const $ = id => document.getElementById(id);
const form = $('crawler-form');
const runButton = $('run-test');
const agentSelect = $('agent-select');
const tokenInput = $('demo-token');
const DEMO_TOKEN_STORAGE_KEY = 'geo-audit-demo-token-today';
let restoredTokenDate = null;
let activeRequest = null;
const urlInput = $('test-url');
const stages = Array.from(document.querySelectorAll('.stage'));
const errorBox = $('error-box');
let invalidField = null;

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
  const message = $('token-hint');
  message.textContent = remembered ? '今日已记住，无需再次输入' : '此环境已启用访问保护';
}

function clearError() {
  errorBox.hidden = true;
  errorBox.textContent = '';
  if (invalidField) {
    invalidField.removeAttribute('aria-invalid');
    if (invalidField === tokenInput) invalidField.setAttribute('aria-describedby', 'token-hint');
    else invalidField.removeAttribute('aria-describedby');
    invalidField = null;
  }
}

function showError(message, field) {
  clearError();
  errorBox.textContent = message;
  errorBox.hidden = false;
  if (!field) return;
  invalidField = field;
  field.setAttribute('aria-invalid', 'true');
  field.setAttribute('aria-describedby', field === tokenInput ? 'token-hint error-box' : 'error-box');
  field.focus();
}

function endRequest() {
  activeRequest?.abort();
  activeRequest = null;
  runButton.disabled = false;
  runButton.textContent = '开始测试';
  form.removeAttribute('aria-busy');
}

function selectAgent() {
  endRequest();
  $('panel-spider').dataset.preset = agentSelect.selectedOptions[0].dataset.headers;
  clearError();
  $('run-state').textContent = '';
  stages.forEach(panel => resetStage(panel));
}

$('platform-select').addEventListener('change', event => {
  endRequest();
  const next = new URL('/crawler-test/' + encodeURIComponent(event.target.value), location.origin);
  const url = urlInput.value;
  if (url) next.hash = new URLSearchParams({ url }).toString();
  location.assign(next.href);
});
agentSelect?.addEventListener('change', selectAgent);
const carriedUrl = new URLSearchParams(location.hash.slice(1)).get('url');
if (carriedUrl) urlInput.value = carriedUrl;
window.addEventListener('pageshow', () => {
  $('platform-select').value = form.dataset.platform;
  if (agentSelect && $('panel-spider').dataset.preset !== agentSelect.selectedOptions[0].dataset.headers) selectAgent();
});

function maskToken() {
  tokenInput.type = 'password';
  $('toggle-token').checked = false;
}

$('toggle-token').addEventListener('change', event => {
  tokenInput.type = event.target.checked ? 'text' : 'password';
});

async function loadTokenStatus() {
  try {
    const response = await fetch('/api/v1/demo/token-status');
    const payload = await response.json();
    $('token-row').hidden = !payload.data?.token_required;
    tokenInput.required = !$('token-row').hidden;
    if (!$('token-row').hidden && !tokenInput.value) setTokenRowMessage(restoreDemoTokenForToday());
  } catch {
    $('token-row').hidden = false;
  }
}

function validWebAddress(value) {
  if (!value || /\s/.test(value)) return false;
  try {
    const hasScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(value);
    const url = new URL(hasScheme ? value : 'https://' + value);
    return ['http:', 'https:'].includes(url.protocol) && !!url.hostname && !url.username && !url.password;
  } catch {
    return false;
  }
}

for (const input of [urlInput, tokenInput]) {
  input.addEventListener('input', () => { if (invalidField === input) clearError(); });
}

form.addEventListener('keydown', event => {
  if (event.key === 'Enter' && event.isComposing) event.preventDefault();
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (activeRequest || event.isComposing) return;
  clearError();
  const url = urlInput.value.trim();
  if (!validWebAddress(url)) {
    showError(url ? '请输入有效的 HTTP 或 HTTPS 网页地址。' : '请输入要测试的网页地址。', urlInput);
    return;
  }
  if (restoredTokenDate && restoredTokenDate !== localDateKey()) {
    forgetSavedDemoToken();
    tokenInput.value = '';
    maskToken();
    $('token-row').hidden = false;
    setTokenRowMessage(false);
    showError('日期已变化，请重新输入访问 Token。', tokenInput);
    return;
  }
  const token = tokenInput.value.trim();
  if (tokenInput.required && !token) {
    showError('请输入访问 Token 后开始测试。', tokenInput);
    return;
  }
  const controller = new AbortController();
  activeRequest = controller;
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['X-API-Token'] = token;
  runButton.disabled = true;
  runButton.textContent = '测试中…';
  form.setAttribute('aria-busy', 'true');
  $('run-state').textContent = '正在获取 ' + url;
  stages.forEach(panel => resetStage(panel, 'loading'));
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
        maskToken();
        $('token-row').hidden = false;
        tokenInput.required = true;
        setTokenRowMessage(false);
        showError('访问 Token 无效，请重新输入。', tokenInput);
      } else {
        showError(payload.message || '请求失败（HTTP ' + response.status + '）', [400, 422].includes(response.status) ? urlInput : null);
      }
      $('run-state').textContent = '';
      stages.forEach(panel => resetStage(panel, 'error'));
      return;
    }
    rememberDemoToken(token);
    setTokenRowMessage(Boolean(token));
    const data = payload.data;
    drawStage($('panel-spider'), data.spider);
    if (data.render) drawStage($('panel-render'), data.render);
    $('run-state').textContent = '测试结果 · ' + data.url;
  } catch {
    if (controller.signal.aborted) return;
    showError('未能读取测试结果，请检查网络连接后重试。');
    $('run-state').textContent = '';
    stages.forEach(panel => resetStage(panel, 'error'));
  } finally {
    if (activeRequest === controller) endRequest();
  }
});

loadTokenStatus();
