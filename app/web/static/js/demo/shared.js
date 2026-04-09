export const $ = id => document.getElementById(id);

export function tx(lang, zhText, enText) {
  return lang === 'zh' ? zhText : enText;
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

export function scoreToStatus(score) {
  const n = Number(score ?? 0);
  if (n <= 24) return 'critical';
  if (n <= 44) return 'poor';
  if (n <= 64) return 'fair';
  if (n <= 84) return 'good';
  return 'strong';
}

export function statusTone(status) {
  if (status === 'strong' || status === 'good' || status === 'completed') return 'success';
  if (status === 'fair' || status === 'running' || status === 'pending') return 'warn';
  if (status === 'poor' || status === 'critical' || status === 'failed') return 'danger';
  return '';
}

export function formatStatus(status, lang = 'zh') {
  const map = lang === 'zh'
    ? {
        critical: '严重',
        poor: '较弱',
        fair: '一般',
        good: '良好',
        strong: '强',
        completed: '已完成',
        running: '进行中',
        pending: '待执行',
        failed: '失败',
        high: '高优先级',
        medium: '中优先级',
        low: '低优先级'
      }
    : {
        critical: 'Critical',
        poor: 'Poor',
        fair: 'Fair',
        good: 'Good',
        strong: 'Strong',
        completed: 'Completed',
        running: 'Running',
        pending: 'Pending',
        failed: 'Failed',
        high: 'High',
        medium: 'Medium',
        low: 'Low'
      };
  return map[status] || status || '-';
}

export function formatBool(val, yes = '是', no = '否') {
  return val ? yes : no;
}

export function formatList(items, fallback, limit = 5) {
  const list = [...new Set((items || []).filter(Boolean))].slice(0, limit);
  if (!list.length) return `<div class="report-list-item">${escapeHtml(fallback)}</div>`;
  return list.map((item, idx) => `<div class="report-list-item"><strong>${idx + 1}.</strong> ${escapeHtml(item)}</div>`).join('');
}
