import { renderContentAuditReport } from './content-report.js';
import { renderKnowledgeGraph } from './knowledge-graph.js';
import { renderSiteAuditReport } from './site-report.js';
import {
  getTaskStepOrder,
  getTaskTypeConfig,
  STEP_ICON
} from './task-config.js';
import {
  $,
  tx
} from './shared.js';

/* ── Tabs ── */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $(`tab-${btn.dataset.tab}`).classList.add('active');
    if (btn.dataset.tab === 'graph' && currentTask?.task_id && currentTask?.build_knowledge_graph !== false) {
      loadKnowledgeGraph(currentTask).catch(() => {});
    }
  });
});

/* ── Toast ── */
let toastTimer = null;
function showToast(msg, type = 'error') {
  const toast = $('toast');
  $('toast-msg').textContent = msg;
  $('toast-icon').textContent = type === 'success' ? '✅' : '⚠️';
  toast.className = `toast t-${type} show`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 4200);
}
$('toast-close').addEventListener('click', () => $('toast').classList.remove('show'));

/* ── State ── */
let pollTimer = null;
let knowledgeGraphPollTimer = null;
let currentTaskId = null;
let currentTaskStatus = 'idle';
let currentTask = null;
let currentKnowledgeGraph = null;
let knowledgeGraphLoading = false;
let demoTokenRequired = true;
let demoTokenVerified = false;
const REPORT_CACHE_PREFIX = 'geo-audit-report:';
const DEMO_API_PREFIX = '/api/v1/demo';
const DEMO_TOKEN_HEADER = 'X-Demo-Token';
const DEMO_TOKEN_STORAGE_KEY = 'geo-audit-demo-token';

function getSelectedDemoToken() {
  return $('demo-token')?.value?.trim() || '';
}

function loadStoredDemoToken() {
  try {
    return sessionStorage.getItem(DEMO_TOKEN_STORAGE_KEY) || '';
  } catch (err) {
    return '';
  }
}

function saveDemoToken(token) {
  try {
    if (token) {
      sessionStorage.setItem(DEMO_TOKEN_STORAGE_KEY, token);
    } else {
      sessionStorage.removeItem(DEMO_TOKEN_STORAGE_KEY);
    }
  } catch (err) {
    // Ignore storage failures.
  }
}

function setVerifyButtonLoading(loading = false) {
  const btn = $('verify-token-btn');
  btn.disabled = loading || (!getSelectedDemoToken() && demoTokenRequired);
  btn.textContent = loading ? '验证中…' : '验证 Token';
}

function setDemoAccessState({
  badgeText,
  badgeClass = 'b-default',
  description,
  hint,
  ready = false
}) {
  const panel = $('demo-access-panel');
  panel.classList.toggle('ready', ready);
  panel.classList.toggle('locked', !ready);
  $('demo-token-badge').textContent = badgeText;
  $('demo-token-badge').className = `badge ${badgeClass}`;
  $('demo-token-desc').textContent = description;
  $('demo-token-hint').textContent = hint;
}

function syncSubmitButtonState() {
  const btn = $('submit-btn');
  if (btn.dataset.busy === 'true') {
    btn.disabled = true;
    return;
  }
  btn.disabled = !demoTokenVerified;
  btn.innerHTML = demoTokenVerified ? '开始审计' : '输入 Token 后可开始审计';
}

function setSubmitBusy(label) {
  const btn = $('submit-btn');
  btn.dataset.busy = 'true';
  btn.disabled = true;
  btn.innerHTML = `<div class="spin"></div> ${label}`;
}

function resetBtn() {
  const btn = $('submit-btn');
  btn.dataset.busy = 'false';
  syncSubmitButtonState();
}

async function readErrorMessage(response, fallback) {
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      const payload = await response.json();
      return payload?.message || fallback;
    } catch (err) {
      return fallback;
    }
  }
  try {
    const text = await response.text();
    return text || fallback;
  } catch (err) {
    return fallback;
  }
}

function buildDemoHeaders(baseHeaders = {}) {
  const headers = new Headers(baseHeaders);
  const token = getSelectedDemoToken();
  if (token) {
    headers.set(DEMO_TOKEN_HEADER, token);
  }
  return headers;
}

function handleDemoAuthFailure(message = 'Demo token required or invalid') {
  demoTokenVerified = false;
  saveDemoToken('');
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
  clearKnowledgeGraphPolling();
  setDemoAccessState({
    badgeText: '验证失败',
    badgeClass: 'b-danger',
    description: '当前 demo 受 token 保护，请输入环境变量 DEMO_ACCESS_TOKEN 对应的值后再继续。',
    hint: message
  });
  resetBtn();
  $('export-btn').disabled = true;
}

async function demoApiFetch(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: buildDemoHeaders(options.headers || {})
  });
  if (response.status === 401) {
    const message = await readErrorMessage(response, 'Demo token required or invalid');
    handleDemoAuthFailure(message);
    throw new Error(message);
  }
  return response;
}

async function verifyDemoToken({ silent = false } = {}) {
  if (!demoTokenRequired) {
    demoTokenVerified = true;
    syncSubmitButtonState();
    return true;
  }
  const token = getSelectedDemoToken();
  if (!token) {
    demoTokenVerified = false;
    setDemoAccessState({
      badgeText: '待验证',
      badgeClass: 'b-default',
      description: '当前 demo 受 token 保护。请先输入 DEMO_ACCESS_TOKEN 对应的值，再开始任务。',
      hint: '输入并验证 token 后，页面才会解锁创建任务、轮询状态、查看图谱和导出报告。'
    });
    syncSubmitButtonState();
    if (!silent) showToast('请先输入 demo token');
    setVerifyButtonLoading(false);
    return false;
  }
  setVerifyButtonLoading(true);
  try {
    const response = await demoApiFetch(`${DEMO_API_PREFIX}/verify-token`, { method: 'POST' });
    const payload = await response.json();
    if (!payload.success) throw new Error(payload.message || 'token 验证失败');
    demoTokenVerified = true;
    saveDemoToken(token);
    setDemoAccessState({
      badgeText: '已解锁',
      badgeClass: 'b-success',
      description: 'token 验证通过，当前页面已解锁，可继续创建任务并访问任务相关接口。',
      hint: `后续 demo 请求会自动携带 ${DEMO_TOKEN_HEADER} 请求头。`,
      ready: true
    });
    syncSubmitButtonState();
    if (!silent) showToast('Token 验证成功', 'success');
    return true;
  } catch (err) {
    demoTokenVerified = false;
    saveDemoToken('');
    setDemoAccessState({
      badgeText: '验证失败',
      badgeClass: 'b-danger',
      description: '输入的 token 未通过校验，请确认和环境变量 DEMO_ACCESS_TOKEN 保持一致。',
      hint: '验证失败后，开始审计按钮会继续保持禁用。'
    });
    syncSubmitButtonState();
    if (!silent) showToast(err?.message || 'token 验证失败');
    return false;
  } finally {
    setVerifyButtonLoading(false);
  }
}

async function initDemoAccess() {
  $('demo-token').value = loadStoredDemoToken();
  setDemoAccessState({
    badgeText: '检查中',
    badgeClass: 'b-warn',
    description: '正在读取 demo token 保护配置。',
    hint: '如果当前环境启用了 DEMO_ACCESS_TOKEN，验证通过后才允许执行任务。'
  });
  try {
    const response = await fetch(`${DEMO_API_PREFIX}/token-status`);
    const payload = await response.json();
    if (!payload.success) throw new Error(payload.message || 'token status load failed');
    demoTokenRequired = payload.data?.token_required !== false;
    if (!demoTokenRequired) {
      demoTokenVerified = true;
      $('demo-token').disabled = true;
      $('verify-token-btn').disabled = true;
      setDemoAccessState({
        badgeText: '未启用',
        badgeClass: 'b-success',
        description: '当前环境未配置 DEMO_ACCESS_TOKEN，demo 页面已自动开放。',
        hint: '如需保护该页面，可在 env 中设置 DEMO_ACCESS_TOKEN。',
        ready: true
      });
      syncSubmitButtonState();
      return;
    }
    $('demo-token').disabled = false;
    setVerifyButtonLoading(false);
    if (getSelectedDemoToken()) {
      await verifyDemoToken({ silent: true });
      return;
    }
    demoTokenVerified = false;
    setDemoAccessState({
      badgeText: '待验证',
      badgeClass: 'b-default',
      description: '当前 demo 受 token 保护。请先输入 DEMO_ACCESS_TOKEN 对应的值，再开始任务。',
      hint: '验证通过后，开始审计、轮询状态、知识图谱和导出报告才会解锁。'
    });
  } catch (err) {
    demoTokenRequired = true;
    demoTokenVerified = false;
    setDemoAccessState({
      badgeText: '异常',
      badgeClass: 'b-danger',
      description: '读取 demo token 配置失败，页面暂时保持锁定。',
      hint: err?.message || '无法确认 demo token 配置状态。'
    });
    showToast(err?.message || '获取 demo token 配置失败');
  }
  syncSubmitButtonState();
}

function getSelectedTaskType() {
  return $('task-type')?.value || 'site_geo_audit';
}

function applyTaskTypeUi(taskType = null) {
  const resolvedTaskType = taskType || getSelectedTaskType();
  const config = getTaskTypeConfig(resolvedTaskType);
  const lang = $('feedback-lang')?.value || 'en';
  $('page-heading').textContent = config.heading[lang] || config.heading.zh;
  $('page-subtitle').textContent = config.subtitle[lang] || config.subtitle.zh;
  $('url-label').textContent = config.urlLabel[lang] || config.urlLabel.zh;
  $('url').placeholder = config.placeholder;
  $('full-audit-row').style.display = config.fullAuditVisible ? 'grid' : 'none';
  if (!config.fullAuditVisible) {
    $('full-audit').checked = false;
    $('max-pages').disabled = true;
    $('max-pages').style.opacity = '0.45';
  } else {
    const enabled = $('full-audit').checked;
    $('max-pages').disabled = !enabled;
    $('max-pages').style.opacity = enabled ? '1' : '0.45';
  }
  if (currentTask && currentTask.task_type !== resolvedTaskType) {
    $('export-btn').disabled = true;
  } else if (currentTask) {
    $('export-btn').disabled = !demoTokenVerified || currentTask.status !== 'completed' || config.exportable === false;
  }
}

function getReportLang(task = null) {
  return task?.feedback_lang || currentTask?.feedback_lang || $('feedback-lang')?.value || 'en';
}

function getReportCacheKey(task, lang) {
  if (!task?.task_id) return null;
  return `${REPORT_CACHE_PREFIX}${task.task_id}:${lang}:${task.updated_at || task.completed_at || task.status || 'draft'}`;
}

function getCachedReportHtml(task, lang) {
  const key = getReportCacheKey(task, lang);
  if (!key || task?.status !== 'completed') return null;
  try {
    return sessionStorage.getItem(key);
  } catch (err) {
    return null;
  }
}

function setCachedReportHtml(task, lang, html) {
  const key = getReportCacheKey(task, lang);
  if (!key || task?.status !== 'completed') return;
  try {
    sessionStorage.setItem(key, html);
  } catch (err) {
    // Ignore storage failures and keep rendering live output.
  }
}

function getAssetSummary(task) {
  return task?.site_asset_summary || task?.result?.discovery?.asset_summary || task?.steps?.discovery?.data?.asset_summary || null;
}

function formatAssetCounts(summary, lang) {
  if (!summary?.enabled) return tx(lang, '文件缓存', 'File cache');
  const urls = Number(summary.stored_url_count || 0);
  const snapshots = Number(summary.stored_snapshot_count || 0);
  const graph = summary?.knowledge_graph;
  if (graph?.built) {
    return tx(
      lang,
      `${urls} URL / ${snapshots} 快照 / 图谱 ${Number(graph.entity_count || 0)} 实体 ${Number(graph.edge_count || 0)} 关系`,
      `${urls} URLs / ${snapshots} snapshots / Graph ${Number(graph.entity_count || 0)} entities ${Number(graph.edge_count || 0)} edges`
    );
  }
  return tx(lang, `${urls} URL / ${snapshots} 快照`, `${urls} URLs / ${snapshots} snapshots`);
}

function renderReport(task) {
  const host = $('summary-text');
  const lang = getReportLang(task);
  const cachedHtml = getCachedReportHtml(task, lang);
  if (cachedHtml) {
    host.className = 'report-shell';
    host.innerHTML = cachedHtml;
    return;
  }
  const result = task?.result;
  if (!result?.summary) {
    host.className = 'report-empty placeholder';
    host.innerHTML = tx(
      lang,
      '等待任务完成后生成完整报告。报告将展示综合评分、6 个汇总维度、平台适配、关键问题、行动计划、snapshot 发现与引用证据。',
      'Wait for task completion to generate the full report. The report will show the composite score, 6 scored dimensions, platform readiness, key issues, action plan, snapshot findings, and source evidence.'
    );
    return;
  }
  if (task?.task_type === 'site_content_audit') {
    renderContentAuditReport({ task, host, lang, setCachedReportHtml });
    return;
  }
  renderSiteAuditReport({ task, host, lang, setCachedReportHtml });
}

function buildRawPayload(task = currentTask, knowledgeGraph = currentKnowledgeGraph) {
  return {
    task: task || null,
    knowledge_graph: knowledgeGraph || null
  };
}

function renderRawPayload(task = currentTask, knowledgeGraph = currentKnowledgeGraph) {
  $('json-output').textContent = JSON.stringify(buildRawPayload(task, knowledgeGraph), null, 2);
}

function renderKnowledgeGraphPanel(task = currentTask, knowledgeGraph = currentKnowledgeGraph) {
  renderKnowledgeGraph({
    task,
    graph: knowledgeGraph,
    host: $('graph-output'),
    lang: getReportLang(task)
  });
}

function setKnowledgeGraphPlaceholder(task = currentTask, note = null) {
  const lang = getReportLang(task);
  currentKnowledgeGraph = {
    task_id: task?.task_id || null,
    backend: task?.storage_backend || getAssetSummary(task)?.backend || 'file',
    available: Boolean(task?.build_knowledge_graph),
    built: false,
    note: note || (
      task?.build_knowledge_graph === false
        ? tx(lang, '当前任务未开启知识图谱构建。', 'Knowledge graph build is disabled for this task.')
        : tx(lang, '等待任务完成后返回知识图谱结构。', 'Waiting for the task to finish before loading the knowledge graph.')
    ),
    task: task ? {
      task_id: task.task_id,
      site_id: getAssetSummary(task)?.site_id || null,
      domain: task.domain,
      status: task.status,
      url: task.url,
      normalized_url: task.normalized_url,
      full_audit: task.full_audit,
      requested_max_pages: task.max_pages,
      created_at: task.created_at,
      updated_at: task.updated_at,
      completed_at: task.completed_at
    } : null,
    site_id: getAssetSummary(task)?.site_id || null,
    graph_version: null,
    built_at: null,
    summary: {
      entity_count: 0,
      edge_count: 0,
      evidence_count: 0,
      source_snapshot_count: 0,
      entity_type_counts: {},
      relation_type_counts: {}
    },
    site: {},
    entities: [],
    edges: [],
    evidence: [],
    source_pages: []
  };
  renderKnowledgeGraphPanel(task, currentKnowledgeGraph);
  renderRawPayload(task, currentKnowledgeGraph);
}

function clearKnowledgeGraphPolling() {
  if (knowledgeGraphPollTimer) {
    clearInterval(knowledgeGraphPollTimer);
    knowledgeGraphPollTimer = null;
  }
}

function shouldPollKnowledgeGraph(task = currentTask, graph = currentKnowledgeGraph) {
  if (!task?.task_id || task?.build_knowledge_graph === false) return false;
  if (task.status === 'failed') return false;
  return graph?.built !== true;
}

function ensureKnowledgeGraphPolling(task = currentTask) {
  if (!shouldPollKnowledgeGraph(task, currentKnowledgeGraph)) {
    clearKnowledgeGraphPolling();
    return;
  }
  if (knowledgeGraphPollTimer) return;
  knowledgeGraphPollTimer = setInterval(() => {
    if (!shouldPollKnowledgeGraph(currentTask, currentKnowledgeGraph)) {
      clearKnowledgeGraphPolling();
      return;
    }
    loadKnowledgeGraph(currentTask).catch(() => {});
  }, 1500);
}

async function loadKnowledgeGraph(task = currentTask) {
  if (!task?.task_id) {
    setKnowledgeGraphPlaceholder(task, tx(getReportLang(task), '尚未生成任务 ID。', 'Task ID is not available yet.'));
    clearKnowledgeGraphPolling();
    return;
  }
  if (task.build_knowledge_graph === false) {
    setKnowledgeGraphPlaceholder(task);
    clearKnowledgeGraphPolling();
    return;
  }
  if (knowledgeGraphLoading) {
    return;
  }
  knowledgeGraphLoading = true;
  try {
    const res = await demoApiFetch(`${DEMO_API_PREFIX}/tasks/${task.task_id}/knowledge-graph`);
    const payload = await res.json();
    if (!payload.success) throw new Error(payload.message || 'knowledge graph load failed');
    currentKnowledgeGraph = payload.data;
  } catch (err) {
    currentKnowledgeGraph = {
      task_id: task.task_id,
      backend: getAssetSummary(task)?.backend || task.storage_backend || 'file',
      available: false,
      built: false,
      note: tx(getReportLang(task), '知识图谱接口请求失败，请稍后重试。', 'Knowledge graph request failed. Please retry later.'),
      task: {
        task_id: task.task_id,
        site_id: getAssetSummary(task)?.site_id || null,
        domain: task.domain,
        status: task.status,
        url: task.url,
        normalized_url: task.normalized_url,
        full_audit: task.full_audit,
        requested_max_pages: task.max_pages,
        created_at: task.created_at,
        updated_at: task.updated_at,
        completed_at: task.completed_at
      },
      site_id: getAssetSummary(task)?.site_id || null,
      graph_version: null,
      built_at: null,
      summary: {
        entity_count: 0,
        edge_count: 0,
        evidence_count: 0,
        source_snapshot_count: 0,
        entity_type_counts: {},
        relation_type_counts: {}
      },
      site: {},
      entities: [],
      edges: [],
      evidence: [],
      source_pages: []
    };
  } finally {
    knowledgeGraphLoading = false;
  }
  renderKnowledgeGraphPanel(task, currentKnowledgeGraph);
  renderRawPayload(task, currentKnowledgeGraph);
  ensureKnowledgeGraphPolling(task);
}

  function renderTimeline(steps) {
    const el = $('timeline');
    el.innerHTML = '';
    getTaskStepOrder(currentTask?.task_type || getSelectedTaskType()).forEach((name, i) => {
      const step = steps?.[name] || { status: 'pending' };
      const raw  = step.data ? JSON.stringify(step.data) : null;
      const preview = raw
        ? raw.slice(0, 130) + (raw.length > 130 ? '…' : '')
        : (step.error || '等待执行');
      const item = document.createElement('div');
      item.className = 'tl-item';
      item.innerHTML = `
        <div class="tl-dot ${step.status}">${STEP_ICON[name] || i+1}</div>
        <div class="tl-body">
          <div class="tl-head">
            <span class="tl-name">${name}</span>
            <span class="tl-st s-${step.status}">${step.status}</span>
          </div>
          <div class="tl-preview">${preview}</div>
        </div>`;
      el.appendChild(item);
    });
  }

  /* ── Update status badge ── */
  function setStatusBadge(status) {
    const el = $('status-badge');
    const map = { idle:['空闲','b-default'], pending:['排队中','b-warn'], running:['进行中','b-warn'], completed:['已完成','b-success'], failed:['失败','b-danger'] };
    const [text, cls] = map[status] || ['未知','b-default'];
    el.textContent = text;
    el.className = `badge ${cls}`;
  }

  /* ── Populate meta fields ── */
  function setMeta(task) {
    currentTask = task || null;
    currentTaskId     = task.task_id || null;
    currentTaskStatus = task.status  || 'idle';
    const assetSummary = getAssetSummary(task);
    if (task.task_type && $('task-type').value !== task.task_type) {
      $('task-type').value = task.task_type;
    }
    if (task.feedback_lang && $('feedback-lang').value !== task.feedback_lang) {
      $('feedback-lang').value = task.feedback_lang;
    }
    if ($('target-locale')) {
      $('target-locale').value = task.target_locale || '';
    }
    if (typeof task.build_knowledge_graph === 'boolean') {
      $('build-knowledge-graph').checked = task.build_knowledge_graph;
    }
    applyTaskTypeUi(task.task_type);
    const shortId = task.task_id ? task.task_id.slice(0, 10) + '…' : '—';
    $('task-id').textContent     = shortId;
    $('current-step').textContent = task.current_step || '—';
    const pct = task.progress_percent || 0;
    $('progress').textContent   = `${pct}%`;
    $('prog-fill').style.width  = `${pct}%`;
    $('cached-flag').textContent = task.cached ? '是 ✓' : '否';
    $('llm-model-used-flag').textContent = task.llm_model_used ? '是 ✓' : '否';
    $('mode-display').textContent = task.mode === 'premium' ? '会员版' : (task.mode ? '普通版' : '—');
    $('storage-backend').textContent = assetSummary?.backend ? assetSummary.backend : (task.storage_backend || 'file');
    $('asset-counts').textContent = formatAssetCounts(assetSummary, getReportLang(task));
    $('asset-reuse').textContent = assetSummary?.enabled
      ? `${assetSummary.reused_snapshot_count || 0} / ${assetSummary.fetched_snapshot_count || 0}`
      : tx(getReportLang(task), '未启用', 'Disabled');
    $('current-mode-display').textContent = task.mode === 'premium'
      ? '会员版（规则 + OpenRouter）'
      : (task.mode ? '普通版（规则）' : '—');
    setStatusBadge(task.status || 'idle');
    $('export-btn').disabled = !demoTokenVerified || task.status !== 'completed' || getTaskTypeConfig(task.task_type).exportable === false;
  }

  /* ── LLM status panel ── */
  function renderLlmStatus(task) {
    const result  = task.result || {};
    const modules = task.task_type === 'site_content_audit'
      ? ['content', 'summary']
      : ['visibility', 'content', 'platform', 'summary'];
    const available = modules.filter(n => result?.[n]);
    const enhanced  = modules.filter(n => result?.[n]?.llm_enhanced);
    const notes = [];
    modules.forEach(n => {
      const m = result?.[n];
      if (m?.processing_notes?.length) notes.push(`${n}: ${m.processing_notes.join(' | ')}`);
    });

    $('llm-count').textContent = enhanced.length;
    const llmStatus = $('llm-status');
    const notesEl   = $('llm-notes');

    if (task.mode !== 'premium') {
      llmStatus.innerHTML = '<span class="badge b-default">普通版无需 LLM</span>';
      notesEl.textContent = '普通版只执行规则审计，不调用 OpenRouter。';
      return;
    }
    if (available.length === 0) {
      llmStatus.innerHTML = '<span class="badge b-warn">等待执行</span>';
      notesEl.textContent = task.task_type === 'site_content_audit'
        ? '会员版已提交，等待 content / summary 返回增强结果。'
        : '会员版已提交，等待 visibility / content / platform / summary 返回增强结果。';
      return;
    }
    if (enhanced.length > 0) {
      llmStatus.innerHTML = '<span class="badge b-success">已增强</span>';
      notesEl.textContent = `已增强模块：${enhanced.join('、')}${notes.length ? '\\n' + notes.join('\\n') : ''}`;
      return;
    }
    llmStatus.innerHTML = '<span class="badge b-danger">增强未生效</span>';
    notesEl.textContent = notes.length
      ? notes.join('\\n')
      : '会员版已选中，但没有任何模块返回 llm_enhanced=true。\\n常见原因：OpenRouter key 未配置、请求失败，或模型返回格式不符合预期。';
  }

  /* ── Poll ── */
  async function pollTask(taskId) {
    const res     = await demoApiFetch(`${DEMO_API_PREFIX}/tasks/${taskId}`);
    const payload = await res.json();
    if (!payload.success) throw new Error(payload.message || '轮询失败');
    const task = payload.data;
    setMeta(task);
    renderTimeline(task.steps);
    renderLlmStatus(task);
    if (task.result?.summary?.summary) {
      const el = $('summary-text');
      el.textContent = task.result.summary.summary;
      el.classList.remove('placeholder');
    }
    renderReport(task);
    await loadKnowledgeGraph(task);
    if (task.status === 'completed' || task.status === 'failed') {
      resetBtn();
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      if (task.status === 'failed') clearKnowledgeGraphPolling();
      if (task.status === 'failed') showToast(task.error || '任务执行失败');
      else showToast('审计已完成', 'success');
    }
  }

  async function copyJsonOutput() {
    const content = $('json-output').textContent || '{}';
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
      } else {
        const range = document.createRange();
        range.selectNodeContents($('json-output'));
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        document.execCommand('copy');
        selection.removeAllRanges();
      }
      showToast('原始数据已复制', 'success');
    } catch (err) {
      showToast('复制失败，请手动选择内容后复制');
    }
  }

  function getDownloadFilename(response, fallback = 'geo-audit-report.md') {
    const disposition = response.headers.get('content-disposition') || '';
    const match = disposition.match(/filename="?([^";]+)"?/i);
    return match?.[1] || fallback;
  }

  function triggerDownload(blob, filename) {
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
  }

  async function exportCurrentReport() {
    if (!demoTokenVerified) {
      showToast('请先输入并验证 demo token');
      return;
    }
    if (!currentTaskId || currentTaskStatus !== 'completed') {
      showToast('任务尚未完成，暂时无法导出报告。');
      return;
    }
    if (currentTask?.task_type === 'site_content_audit') {
      showToast('当前内容审计暂不支持导出 Markdown 报告。');
      return;
    }
    try {
      const response = await demoApiFetch(`${DEMO_API_PREFIX}/tasks/${currentTaskId}/report`);
      if (!response.ok) {
        throw new Error(await readErrorMessage(response, '报告导出失败'));
      }
      const blob = await response.blob();
      triggerDownload(blob, getDownloadFilename(response));
      showToast('报告导出成功', 'success');
    } catch (err) {
      showToast(err?.message || '报告导出失败');
    }
  }

  /* ── Start audit ── */
  async function startAudit() {
    if (!demoTokenVerified) {
      showToast('请先输入并验证 demo token');
      return;
    }
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    clearKnowledgeGraphPolling();

    setSubmitBusy('提交中…');
    const taskType = getSelectedTaskType();
    const isContentAudit = taskType === 'site_content_audit';
    currentTask = { task_type: taskType, status: 'queued' };
    currentKnowledgeGraph = null;
    currentTaskId = null;
    currentTaskStatus = 'queued';
    knowledgeGraphLoading = false;
    applyTaskTypeUi(taskType);

    const summaryEl = $('summary-text');
    summaryEl.textContent = isContentAudit
      ? '任务已创建，等待后台返回内容审计结果……'
      : '任务已创建，等待后台返回各阶段结果……';
    summaryEl.classList.add('placeholder');
    summaryEl.className = 'report-empty placeholder';
    summaryEl.innerHTML = isContentAudit
      ? '任务已创建，等待后台返回内容审计结果……<br />报告将在结果完成后自动生成。'
      : '任务已创建，等待后台返回各阶段结果……<br />报告将在结果完成后自动生成。';
    $('llm-notes').textContent = '等待会员增强状态。';
    setKnowledgeGraphPlaceholder(currentTask);
    $('export-btn').disabled = true;
    renderTimeline({});

    const mode = $('mode').value;
    const body = {
      task_type: taskType,
      url: $('url').value.trim(),
      mode,
      force_refresh: $('force').checked,
      full_audit: !isContentAudit && $('full-audit').checked,
      feedback_lang: $('feedback-lang').value,
      build_knowledge_graph: $('build-knowledge-graph').checked
    };
    const targetLocale = $('target-locale')?.value || '';
    if (targetLocale) body.target_locale = targetLocale;
    if (!isContentAudit && $('full-audit').checked) {
      const parsedPages = Number($('max-pages').value || 12);
      body.max_pages = Math.max(5, Math.min(10000, Number.isFinite(parsedPages) ? parsedPages : 12));
    }
    if (mode === 'premium') {
      body.llm = { provider: 'openrouter' };
      const model = $('model').value.trim();
      if (model) body.llm.model = model;
    }

    try {
      const res     = await demoApiFetch(`${DEMO_API_PREFIX}/tasks/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const payload = await res.json();
      if (!payload.success) throw new Error(payload.message || '创建任务失败');

      const task = payload.data;
      setSubmitBusy('审计中…');
      setMeta(task);
      renderTimeline(task.steps);
      renderLlmStatus(task);
      renderReport(task);
      await loadKnowledgeGraph(task);

      if (task.status === 'completed') {
        resetBtn();
        if (task.result?.summary?.summary) {
          summaryEl.textContent = task.result.summary.summary;
          summaryEl.classList.remove('placeholder');
        }
        renderReport(task);
        showToast('审计已完成', 'success');
        return;
      }

      ensureKnowledgeGraphPolling(task);
      pollTimer = setInterval(() => {
        pollTask(task.task_id).catch(err => {
          if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
          clearKnowledgeGraphPolling();
          resetBtn();
          showToast(err.message);
        });
      }, 1500);

    } catch (err) {
      resetBtn();
      showToast(err?.message || '创建任务失败');
    }
  }

  /* ── Events ── */
  $('verify-token-btn').addEventListener('click', () => {
    verifyDemoToken().catch(err => {
      showToast(err?.message || 'token 验证失败');
    });
  });
  $('demo-token').addEventListener('input', () => {
    if (!demoTokenRequired) return;
    demoTokenVerified = false;
    saveDemoToken('');
    setVerifyButtonLoading(false);
    setDemoAccessState({
      badgeText: '待验证',
      badgeClass: 'b-default',
      description: '当前 demo 受 token 保护。请先输入 DEMO_ACCESS_TOKEN 对应的值，再开始任务。',
      hint: 'token 输入发生变化后，需要重新点击“验证 Token”。'
    });
    syncSubmitButtonState();
  });
  $('demo-token').addEventListener('keydown', event => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    verifyDemoToken().catch(err => {
      showToast(err?.message || 'token 验证失败');
    });
  });
  $('submit-btn').addEventListener('click', startAudit);
  $('audit-form').addEventListener('submit', e => { e.preventDefault(); startAudit(); });
  $('copy-json-btn').addEventListener('click', copyJsonOutput);
  $('export-btn').addEventListener('click', exportCurrentReport);

  $('mode').addEventListener('change', () => {
    const isPremium = $('mode').value === 'premium';
    $('model').disabled = !isPremium;
    $('model').style.opacity = isPremium ? '1' : '0.45';
  });
  $('task-type').addEventListener('change', () => {
    clearKnowledgeGraphPolling();
    currentTask = { task_type: getSelectedTaskType(), status: 'idle' };
    currentKnowledgeGraph = null;
    currentTaskId = null;
    currentTaskStatus = 'idle';
    knowledgeGraphLoading = false;
    $('task-id').textContent = '—';
    $('current-step').textContent = '—';
    $('progress').textContent = '0%';
    $('prog-fill').style.width = '0%';
    $('cached-flag').textContent = '否';
    $('llm-model-used-flag').textContent = '否';
    $('mode-display').textContent = '—';
    $('storage-backend').textContent = '—';
    $('asset-counts').textContent = '—';
    $('asset-reuse').textContent = '—';
    $('current-mode-display').textContent = '—';
    $('export-btn').disabled = true;
    setStatusBadge('idle');
    applyTaskTypeUi();
    renderTimeline({});
    setKnowledgeGraphPlaceholder(currentTask, tx(getReportLang(currentTask), '等待任务开始后展示知识图谱。', 'Knowledge graph will appear after the task starts.'));
  });
  $('feedback-lang').addEventListener('change', () => {
    applyTaskTypeUi();
    if (!currentTask || currentTask.status !== 'completed') return;
    const selectedLang = $('feedback-lang').value;
    if (currentTask.feedback_lang !== selectedLang) {
      showToast(selectedLang === 'zh' ? '当前任务结果不是中文版本，请重新发起任务以获取中文报告。' : 'The current task is not an English result. Run a new task to get the English report.');
      return;
    }
    renderReport(currentTask);
    renderKnowledgeGraphPanel(currentTask, currentKnowledgeGraph);
    renderRawPayload(currentTask, currentKnowledgeGraph);
  });
  $('full-audit').addEventListener('change', () => {
    const enabled = $('full-audit').checked;
    $('max-pages').disabled = !enabled;
    $('max-pages').style.opacity = enabled ? '1' : '0.45';
  });

  /* ── Init ── */
  applyTaskTypeUi();
  renderTimeline({});
  setKnowledgeGraphPlaceholder(currentTask, tx(getReportLang(currentTask), '等待任务开始后展示知识图谱。', 'Knowledge graph will appear after the task starts.'));
  syncSubmitButtonState();
  initDemoAccess().catch(err => {
    showToast(err?.message || '初始化 demo token 失败');
  });
