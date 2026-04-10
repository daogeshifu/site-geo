import { renderContentAuditReport } from './content-report.js';
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
let currentTaskId = null;
let currentTaskStatus = 'idle';
let currentTask = null;
const REPORT_CACHE_PREFIX = 'geo-audit-report:';

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
    $('export-btn').disabled = currentTask.status !== 'completed' || config.exportable === false;
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
    $('export-btn').disabled = task.status !== 'completed' || getTaskTypeConfig(task.task_type).exportable === false;
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
    const res     = await fetch(`/api/v1/tasks/${taskId}`);
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
    $('json-output').textContent = JSON.stringify(task.result || task, null, 2);
    if (task.status === 'completed' || task.status === 'failed') {
      resetBtn();
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
      if (task.status === 'failed') showToast(task.error || '任务执行失败');
      else showToast('审计已完成', 'success');
    }
  }

  /* ── Reset button ── */
  function resetBtn() {
    const btn = $('submit-btn');
    btn.disabled = false;
    btn.innerHTML = '开始审计';
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

  /* ── Start audit ── */
  async function startAudit() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }

    const btn = $('submit-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spin"></div> 提交中…';
    const taskType = getSelectedTaskType();
    const isContentAudit = taskType === 'site_content_audit';
    currentTask = { task_type: taskType, status: 'queued' };
    currentTaskId = null;
    currentTaskStatus = 'queued';
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
    $('json-output').textContent = '{}';
    $('export-btn').disabled = true;
    renderTimeline({});

    const mode = $('mode').value;
    const body = {
      task_type: taskType,
      url: $('url').value.trim(),
      mode,
      force_refresh: $('force').checked,
      full_audit: !isContentAudit && $('full-audit').checked,
      feedback_lang: $('feedback-lang').value
    };
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
      const res     = await fetch('/api/v1/tasks/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const payload = await res.json();
      if (!payload.success) throw new Error(payload.message || '创建任务失败');

      const task = payload.data;
      btn.innerHTML = '<div class="spin"></div> 审计中…';
      setMeta(task);
      renderTimeline(task.steps);
      renderLlmStatus(task);
      renderReport(task);
      $('json-output').textContent = JSON.stringify(task.result || task, null, 2);

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

      pollTimer = setInterval(() => {
        pollTask(task.task_id).catch(err => {
          if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
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
  $('submit-btn').addEventListener('click', startAudit);
  $('audit-form').addEventListener('submit', e => { e.preventDefault(); startAudit(); });
  $('copy-json-btn').addEventListener('click', copyJsonOutput);

  $('export-btn').addEventListener('click', () => {
    if (!currentTaskId || currentTaskStatus !== 'completed') {
      showToast('任务尚未完成，暂时无法导出报告。');
      return;
    }
    if (currentTask?.task_type === 'site_content_audit') {
      showToast('当前内容审计暂不支持导出 Markdown 报告。');
      return;
    }
    window.open(`/api/v1/tasks/${currentTaskId}/report`, '_blank');
  });

  $('mode').addEventListener('change', () => {
    const isPremium = $('mode').value === 'premium';
    $('model').disabled = !isPremium;
    $('model').style.opacity = isPremium ? '1' : '0.45';
  });
  $('task-type').addEventListener('change', () => {
    currentTask = { task_type: getSelectedTaskType(), status: 'idle' };
    currentTaskId = null;
    currentTaskStatus = 'idle';
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
  });
  $('full-audit').addEventListener('change', () => {
    const enabled = $('full-audit').checked;
    $('max-pages').disabled = !enabled;
    $('max-pages').style.opacity = enabled ? '1' : '0.45';
  });

  /* ── Init ── */
  applyTaskTypeUi();
  renderTimeline({});
