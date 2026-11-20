/* Shared by every crawler profile, for both the HTTP fetch and the Chromium document. */
const numbers = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 });

function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text != null) el.textContent = text;
  if (className) el.className = className;
  return el;
}

function pairs(className, entries) {
  const list = node('dl', null, className);
  for (const [label, value] of entries) {
    const row = node('div');
    row.append(node('dt', label), node('dd', value ?? '—'));
    list.append(row);
  }
  return list;
}

function headerTable(headers) {
  // User-Agent is what distinguishes profiles and remains first after a profile change.
  const entries = Object.entries(headers);
  return pairs('header-table', [
    ...entries.filter(([key]) => key === 'User-Agent'),
    ...entries.filter(([key]) => key !== 'User-Agent'),
  ]);
}

function emptyContent(title, hint) {
  const box = node('div', null, 'empty-content');
  const icon = node('span', null, 'document-mark');
  icon.setAttribute('aria-hidden', 'true');
  box.append(icon, node('p', title), node('small', hint));
  return box;
}

function disclosure(title, meta) {
  const details = node('details', null, 'record');
  const summary = node('summary');
  summary.append(node('span', title));
  if (meta) summary.append(node('small', meta));
  details.append(summary);
  return details;
}

async function copyText(text, button) {
  if (window.isSecureContext && navigator.clipboard) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const field = node('textarea');
  field.className = 'clipboard-field';
  field.value = text;
  field.readOnly = true;
  document.body.append(field);
  try {
    field.select();
    if (!document.execCommand('copy')) throw new Error();
  } finally {
    field.remove();
    button.focus({ preventScroll: true });
  }
}

function textRecord(title, source, meta = '') {
  const record = disclosure(title, meta);
  // Large HTML and JSON are materialized only when their disclosure is opened.
  record.addEventListener('toggle', () => {
    if (!record.open || record.childElementCount > 1) return;
    const text = typeof source === 'function' ? source() : source;
    const block = node('div', null, 'source-block');
    const pre = node('pre', text);
    pre.tabIndex = 0;
    pre.setAttribute('aria-label', title);
    const button = node('button', '复制', 'copy');
    button.type = 'button';
    button.setAttribute('aria-label', '复制' + title);
    const feedback = node('span', '', 'copy-feedback');
    feedback.setAttribute('role', 'status');
    button.addEventListener('click', async () => {
      try {
        await copyText(text, button);
        feedback.textContent = '已复制';
      } catch {
        feedback.textContent = '请选中文本复制';
      }
    });
    const tools = node('div', null, 'source-tools');
    tools.append(feedback, button);
    block.append(tools, pre);
    record.append(block);
  });
  return record;
}

function stageState(panel, state, label) {
  panel.dataset.state = state;
  panel.querySelector('.stage-status').textContent = label;
}

export function resetStage(panel, phase = 'idle') {
  const render = panel.classList.contains('render');
  const waiting = phase === 'loading';
  const failed = phase === 'error';
  stageState(panel, phase, failed ? '未完成' : waiting ? (render ? '等待抓取' : '测试中') : '待测试');
  panel.querySelector('.header-origin').textContent = '预设字段';
  panel.querySelector('.request-data').replaceChildren(headerTable(JSON.parse(panel.dataset.preset)));
  const title = render ? '等待渲染' : '等待网页响应';
  let hint = render ? '抓取到 HTML 后，可查看执行 JavaScript 后的正文和源码。' : '输入网址开始测试，可查看页面标题、正文及原始数据。';
  if (waiting) hint = render ? '取得可渲染的 HTML 后开始加载。' : '正在检查 robots.txt 并等待网页返回数据。';
  if (failed) hint = '请查看表单中的提示，再次开始测试。';
  panel.querySelector('.content-origin').textContent = render ? '渲染后的 DOM' : '原始响应';
  panel.querySelector('.content-data').replaceChildren(emptyContent(failed ? '未取得测试结果' : title, hint));
  for (const el of panel.querySelectorAll('.stage-summary, .stage-supplement')) {
    el.replaceChildren();
    el.hidden = true;
  }
}

function requestEvidence(panel, result, observed) {
  const request = result.request || observed.at(-1);
  const rules = result.robots;
  const attempt = result.attempted_request;
  let headers = request?.headers;
  let origin = result.request ? '网页请求 · 实测' : '最近响应 · 实测';
  let caption = result.request ? null : request?.url;
  const unconfirmed = attempt && attempt.url !== request?.url;
  if (unconfirmed) {
    headers = attempt.headers;
    origin = '网页请求 · 已尝试';
    caption = attempt.url;
  }
  if (!headers || !Object.keys(headers).length) {
    if (rules?.request_headers && Object.keys(rules.request_headers).length) {
      headers = rules.request_headers;
      origin = 'robots.txt 请求 · 实测';
      caption = rules.url;
    } else {
      headers = JSON.parse(panel.dataset.preset);
      origin = '预设字段';
      caption = '本次未记录到网页请求头。';
    }
  }
  panel.querySelector('.header-origin').textContent = origin;
  const body = panel.querySelector('.request-data');
  body.replaceChildren(headerTable(headers));
  if (caption) body.prepend(node('p', caption, 'field-caption'));
  const received = request?.response_headers;
  if (received && Object.keys(received).length) {
    const details = disclosure(unconfirmed ? '上一步响应头' : '响应头', Object.keys(received).length + ' 个字段');
    details.append(headerTable(received));
    body.append(details);
  }
}

function outcome(result, render) {
  const code = result.request?.status_code;
  if (result.status === 'skipped') return ['skipped', '已跳过'];
  if (code === 429) return ['warning', '受到限流'];
  if (code === 403) return ['error', '访问被拒绝'];
  if (result.status === 'failed') return ['error', render ? '渲染失败' : '抓取失败'];
  if (result.status === 'warning') return ['warning', '部分渲染'];
  if (code === 206 || result.truncated || result.rendered_html?.truncated) return ['warning', '部分内容'];
  return ['success', render ? '渲染完成' : '抓取完成'];
}

function sizeLabel(bytes) {
  if (bytes == null) return '—';
  if (bytes < 1024) return numbers.format(bytes) + ' B';
  if (bytes < 1024 * 1024) return numbers.format(bytes / 1024) + ' KiB';
  return numbers.format(bytes / (1024 * 1024)) + ' MiB';
}

function summaryEvidence(panel, result, render, lastObserved) {
  const summary = panel.querySelector('.stage-summary');
  const request = result.request || lastObserved;
  summary.hidden = !request;
  if (!request) return;
  const bytes = render ? (request.status_code != null ? result.rendered_html?.html_bytes : null) : request.size_bytes;
  const time = render ? request.render_time_ms : request.response_time_ms;
  const mime = request.content_type || request.response_headers?.['content-type'] || '';
  const metrics = pairs('metrics', [
    [result.request ? 'HTTP 状态' : '最近响应', request.status_code ?? '无响应'],
    [render ? '渲染耗时' : '抓取耗时', time == null ? null : numbers.format(time) + ' ms'],
    [render ? 'DOM 大小' : '已读大小', sizeLabel(bytes)],
    ['内容类型', mime.split(';')[0] || null],
  ]);
  if (bytes != null) metrics.children[2].title = numbers.format(bytes) + ' 字节';
  summary.replaceChildren(metrics);
}

function contentEvidence(panel, result, render) {
  const body = panel.querySelector('.content-data');
  const tag = panel.querySelector('.content-origin');
  const request = result.request;
  body.replaceChildren();
  if (!request || request.status_code == null) {
    tag.textContent = '未取得内容';
    const reason = result.reason || (render ? '浏览器未取得目标文档的 HTTP 响应。' : '未取得网页响应。');
    body.append(emptyContent(render ? '未取得目标 DOM' : '未取得网页正文', reason));
    return;
  }
  const snapshot = result.rendered_html;
  const content = render ? result.rendered_content : result.content;
  const source = render ? snapshot?.html : result.raw_html;
  const errorResponse = request.status_code >= 400;
  const partial = render ? snapshot?.truncated : result.truncated;
  tag.textContent = errorResponse ? '错误响应' : render ? '渲染后的 DOM' : result.is_html ? '原始 HTML' : '响应正文';
  if (request.status_code === 206) body.append(node('p', '服务器返回了部分响应（HTTP 206）。', 'notice'));
  if (partial) {
    const message = render ? 'DOM 源码已截断，正文统计来自本次完整快照。' : '已达到读取上限，展示已截取的内容。';
    body.append(node('p', message, 'notice'));
  }
  if (request.network_idle_timed_out) body.append(node('p', '等待网络空闲超时，展示当时取得的 DOM。', 'notice'));
  if (source === '' || (!render && request.size_bytes === 0)) {
    const empty = render ? emptyContent('渲染快照为空', '浏览器未记录到 DOM 源码。') : emptyContent('响应正文为空', '服务器返回了响应头，正文为 0 字节。');
    body.append(empty);
    return;
  }
  if (source == null) {
    body.append(emptyContent('无文本预览', render ? '未取得可展示的 DOM。' : '该响应类型未提供文本预览，可查看内容类型和已读大小。'));
    return;
  }
  if (content) {
    body.append(node('p', errorResponse ? '响应标题' : '页面标题', 'field-label'));
    body.append(node('p', content.title || '未提取到标题', 'page-title'));
    const length = content.body_text_length;
    const fields = [
      ['正文字符', length], ['H1 数量', content.h1_count], ['站内链接', content.internal_link_count],
    ];
    body.append(pairs('content-facts', fields.map(([label, value]) => [label, value == null ? null : numbers.format(value)])));
  }
  const preview = content ? content.body_text_preview ?? content.text_preview ?? '' : Array.from(source.slice(0, 1000)).slice(0, 500).join('');
  const previewLabel = errorResponse ? '错误响应文本' : content ? '正文预览' : '文本预览';
  body.append(node('p', previewLabel, 'field-label'));
  const excerpt = node('div', null, 'excerpt');
  excerpt.append(node('p', preview.trim() ? preview : (content ? '未提取到正文文本。' : '该段仅含空白字符。')));
  const hasMore = content ? content.body_text_length > 500 : source.length > preview.length;
  if (hasMore) excerpt.append(node('small', '显示前 500 个字符'));
  body.append(excerpt);
  if (render && result.comparison?.body_text_delta != null && !errorResponse) {
    const delta = result.comparison.body_text_delta;
    const baseline = result.comparison.initial_truncated ? '较已截取的原始正文' : '较原始正文';
    body.append(node('p', baseline + '　' + (delta > 0 ? '+' : '') + numbers.format(delta) + ' 个字符', 'field-caption'));
  }
  const label = render ? '渲染后 HTML' : result.is_html ? '原始 HTML' : '响应文本';
  body.append(textRecord(label, source, partial ? '已截断' : render || result.is_html ? '查看源码' : '查看文本'));
}

function relatedEvidence(panel, result, observed) {
  const box = panel.querySelector('.stage-supplement');
  box.replaceChildren();
  const request = result.request;
  if (request?.retry_after) box.append(node('p', '服务器给出的 Retry-After 为 ' + request.retry_after, 'notice'));
  const path = (request?.redirect_chain || []).map(hop => [hop.status_code, hop.from]);
  if (request?.status_code != null) path.push([request.status_code, request.final_url]);
  for (const entry of observed) path.push([entry.status_code, entry.url]);
  if (path.length) {
    const details = disclosure('HTTP 请求路径', path.length + ' 次响应');
    const list = node('ol', null, 'http-path');
    for (const [code, url] of path) {
      const row = node('li');
      row.append(node('b', 'HTTP ' + code), node('span', url));
      list.append(row);
    }
    details.append(list);
    box.append(details);
  }
  const rules = result.robots;
  if (rules?.url) {
    const verdict = rules.allowed == null ? '规则待确认' : rules.allowed ? '允许抓取' : '禁止抓取';
    const details = disclosure('robots.txt 抓取规则', verdict + (rules.status_code == null ? '' : ' · HTTP ' + rules.status_code));
    details.append(node('p', rules.detail, 'rule-message'), pairs('header-table', [
      ['规则地址', rules.url], ['检查路径', rules.target], ['匹配标识', rules.matched || rules.token],
    ]));
    if (rules.request_headers) details.append(headerTable(rules.request_headers));
    box.append(details);
    if (rules.content_use) {
      const use = rules.content_use;
      box.append(node('p', use.token + ' 内容使用规则 · ' + (use.allowed ? '允许' : '禁止') + '（匹配 ' + use.matched + '）', 'notice'));
    }
  }
  const diagnostics = result.diagnostics || {};
  const issues = Object.values(diagnostics).reduce((sum, items) => sum + items.length, 0);
  if (issues) box.append(textRecord('脚本与资源异常', () => JSON.stringify(diagnostics, null, 2), issues + ' 条记录'));
  box.append(textRecord('抓取数据', () => {
    const { raw_html, rendered_html, ...metadata } = result;
    if (rendered_html) {
      const { html, ...snapshot } = rendered_html;
      metadata.rendered_html = snapshot;
    }
    return JSON.stringify(metadata, null, 2);
  }, 'JSON'));
  box.hidden = false;
}

export function drawStage(panel, result) {
  const render = panel.classList.contains('render');
  const observed = result.observed_responses || [];
  stageState(panel, ...outcome(result, render));
  summaryEvidence(panel, result, render, observed.at(-1));
  requestEvidence(panel, result, observed);
  contentEvidence(panel, result, render);
  relatedEvidence(panel, result, observed);
}
