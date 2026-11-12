const TASK_ID_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;

export function buildReportShareUrl(task, baseUrl) {
  if (task?.status !== 'completed' || !task.result || !TASK_ID_PATTERN.test(task.task_id || '')) return null;
  const url = new URL('/', baseUrl);
  if (!['http:', 'https:'].includes(url.protocol)) return null;
  // A saved report needs only its ID. Never forward audit options or credentials.
  url.searchParams.set('task_id', task.task_id);
  return url.href;
}
