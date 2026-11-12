const PREFIX = 'geo-audit-report:v16-report-links:';

const keyFor = (task, lang) => task?.task_id && task.status === 'completed'
  ? `${PREFIX}${task.task_id}:${lang}:${task.updated_at || task.completed_at || task.status}` : null;

export function getCachedReportHtml(storage, task, lang) {
  const key = keyFor(task, lang);
  if (!key) return null;
  try {
    const html = storage.getItem(key);
    // Reject stale HTML even if a caller stored it in the current namespace.
    if (task.result?.sgeo && !html?.includes('data-report-version="diagnostic-report-v3-sgeo"')) return null;
    if (!task.result?.sgeo && (task.result?.geo || task.result?.seo) &&
        !html?.includes('data-report-version="diagnostic-report-v2"')) return null;
    return html;
  } catch {
    return null;
  }
}

export function setCachedReportHtml(storage, task, lang, html) {
  const key = keyFor(task, lang);
  if (!key) return;
  try { storage.setItem(key, html); } catch { /* Storage limits must not hide a report. */ }
}
