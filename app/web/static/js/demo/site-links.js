import { escapeHtml as esc } from './shared.js';

const number = value => value == null ? '—' : Number(value).toLocaleString('zh-CN');
const date = value => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未记录';
const display = value => value == null || value === '' ? '未记录' : String(value);
const safeUrl = value => { try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : '#'; } catch { return '#'; } };
const status = page => page.status_code ? String(page.status_code) : page.has_snapshot ? '未记录' : '未采样';
const tone = page => page.status_code >= 400 ? 'danger' : page.status_code >= 300 ? 'warn' : page.status_code >= 200 ? 'success' : 'neutral';
const sourceNames = { discovery: '关键页发现', seo_sample: 'SEO 采样', full_audit: '扩展采样', sitemap: 'Sitemap', internal_link: '站内链接' };
const row = (label, value) => `<div><dt>${esc(label)}</dt><dd>${esc(display(value))}</dd></div>`;

export function createSiteLinksExplorer({ host, fetchApi }) {
  let task = null, pages = [], query = '', filter = 'all', pageIndex = 0, loadedVersion = '', loading = false, generation = 0;
  const pageSize = 25;
  host.innerHTML = `<div class="links-intro"><div><span class="workspace-kicker">PAGE INVENTORY</span><h3>站点链接</h3><p>从每一个 URL，了解内容与抓取质量。</p></div><span id="links-total" class="inventory-total">0 个链接</span></div>
    <div class="links-toolbar"><label class="links-search"><span>⌕</span><input type="search" id="links-search" placeholder="搜索 URL 或页面标题" aria-label="搜索站点链接"></label><select id="links-filter" aria-label="筛选抓取状态"><option value="all">全部链接</option><option value="sampled">已采样</option><option value="error">HTTP 异常</option><option value="pending">未采样</option></select><button type="button" class="btn btn-ghost" id="links-refresh">刷新</button></div>
    <p class="links-note">显示本次任务发现的链接；未采样页面不具有字数、状态码和抓取时间。</p><div id="links-list" aria-live="polite"></div><div id="links-pagination" class="links-pagination"></div>`;
  const list = host.querySelector('#links-list');

  function render() {
    const filtered = pages.filter(page => (!query || `${page.url} ${page.title || ''}`.toLowerCase().includes(query)) && (filter === 'all' || filter === 'sampled' && page.has_snapshot || filter === 'error' && page.status_code >= 400 || filter === 'pending' && !page.has_snapshot));
    pageIndex = Math.min(pageIndex, Math.max(0, Math.ceil(filtered.length / pageSize) - 1));
    host.querySelector('#links-total').textContent = `${pages.length} 个链接 · ${pages.filter(page => page.has_snapshot).length} 已采样`;
    document.getElementById('site-links-count').textContent = pages.length;
    if (!filtered.length) {
      list.innerHTML = `<div class="inventory-empty"><span>⌕</span><h4>${pages.length ? '没有匹配的链接' : '站点链接即将在这里呈现'}</h4><p>${pages.length ? '试试其他关键词或抓取状态。' : '开始审计后，查看页面内容、抓取详情与原始 HTML。'}</p></div>`;
    } else {
      list.innerHTML = `<div class="page-columns"><span>页面 / URL</span><span>状态码</span><span>内容字数</span><span>抓取时间</span><span></span></div>` + filtered.slice(pageIndex * pageSize, (pageIndex + 1) * pageSize).map(page => `<details class="page-record" data-page-id="${esc(page.id)}"><summary><div class="page-url"><strong>${esc(page.title || page.url)}</strong><small>${esc(page.url)}</small></div><span class="http-status ${tone(page)}">${esc(status(page))}</span><span class="page-words">${number(page.word_count)}</span><time>${esc(date(page.fetched_at))}</time><span class="page-chevron">⌄</span></summary><div class="page-detail"><div class="page-detail-heading"><span>${esc(sourceNames[page.discovery_source] || page.discovery_source)}</span><a href="${esc(safeUrl(page.final_url || page.url))}" target="_blank" rel="noopener noreferrer">打开页面 ↗</a></div><div class="detail-tabs" role="tablist" aria-label="页面详情"><button role="tab" aria-selected="true" data-detail="basic">基础信息</button><button role="tab" aria-selected="false" data-detail="fetch">抓取信息</button><button role="tab" aria-selected="false" data-detail="source">HTML 源代码</button></div><div class="detail-content" role="tabpanel">${basic(page)}</div></div></details>`).join('');
    }
    host.querySelector('#links-pagination').innerHTML = filtered.length ? `<span>显示 ${pageIndex * pageSize + 1}–${Math.min((pageIndex + 1) * pageSize, filtered.length)} / ${filtered.length}</span><div><button class="btn btn-ghost" data-page-step="-1" ${pageIndex === 0 ? 'disabled' : ''}>上一页</button><button class="btn btn-ghost" data-page-step="1" ${(pageIndex + 1) * pageSize >= filtered.length ? 'disabled' : ''}>下一页</button></div>` : '';
  }

  function basic(page) {
    const h1 = page.h1_count ?? (page.headings ? page.headings.filter(item => item.level === 'h1').length : null);
    return `<dl class="page-kv">${row('页面标题', page.title)}${row('Meta Description', page.meta_description)}${row('页面类型', page.page_type)}${row('语言', page.lang)}${row('内容字数', page.word_count)}${row('H1 数量', h1)}${row('Canonical', page.canonical)}${row('最终 URL', page.final_url)}${row('图片数量', page.image_count)}${row('Noindex', page.noindex_detected == null ? null : page.noindex_detected ? '是' : '否')}</dl>${page.text_excerpt ? `<div class="page-excerpt"><h4>正文摘要</h4><p>${esc(page.text_excerpt)}</p></div>` : ''}`;
  }

  function fetchDetails(page) {
    return `<dl class="page-kv">${row('请求 URL', page.url)}${row('最终 URL', page.final_url)}${row('HTTP 状态码', page.status_code || null)}${row('抓取时间（本地时区）', date(page.fetched_at))}${row('响应耗时', page.response_time_ms == null ? null : `${page.response_time_ms} ms`)}${row('HTML 字符数', page.html_length)}${row('发现来源', sourceNames[page.discovery_source] || page.discovery_source)}${row('源码保存', page.source_available ? '已保存' : '未保存')}</dl><h4 class="headers-heading">响应头</h4><dl class="page-kv">${Object.entries(page.response_headers || {}).map(([key, value]) => row(key, value)).join('') || row('响应头', null)}</dl>`;
  }

  async function load(force = false) {
    if (!task?.task_id) { render(); return; }
    const version = `${task.task_id}:${task.updated_at}`;
    if (loading || (!force && loadedVersion === version)) return;
    const requestGeneration = generation;
    loading = true;
    list.setAttribute('aria-busy', 'true');
    try {
      const response = await fetchApi(`/api/v1/demo/tasks/${encodeURIComponent(task.task_id)}/pages`);
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.message || '链接加载失败');
      if (generation !== requestGeneration) return;
      pages = payload.data.pages || [];
      loadedVersion = version;
      render();
    } catch (error) {
      if (generation === requestGeneration) list.innerHTML = `<div class="inventory-empty"><h4>暂时无法加载链接</h4><p>${esc(error.message)}</p><p>请点击上方“刷新”重试。</p></div>`;
    } finally {
      if (generation === requestGeneration) { loading = false; list.removeAttribute('aria-busy'); }
    }
  }

  host.addEventListener('click', async event => {
    const pageButton = event.target.closest('[data-page-step]');
    if (pageButton) { pageIndex += Number(pageButton.dataset.pageStep); render(); return; }
    const button = event.target.closest('[data-detail]');
    if (!button) return;
    const record = button.closest('[data-page-id]');
    const page = pages.find(page => page.id === record.dataset.pageId);
    const content = record.querySelector('.detail-content');
    record.querySelectorAll('[data-detail]').forEach(tab => tab.setAttribute('aria-selected', String(tab === button)));
    if (button.dataset.detail === 'basic') { content.innerHTML = basic(page); return; }
    if (button.dataset.detail === 'fetch') { content.innerHTML = fetchDetails(page); return; }
    content.innerHTML = '<p class="source-notice">正在读取抓取时保存的 HTML…</p>';
    if (!page.source_available) { content.innerHTML = '<p class="source-notice">本次记录未保存 HTML 源代码。新审计会保存采样页面源码；历史缓存可通过强制刷新重新抓取。</p>'; return; }
    const currentId = task.task_id;
    try {
      const response = await fetchApi(`/api/v1/demo/tasks/${encodeURIComponent(currentId)}/pages/${page.id}/source`);
      const payload = await response.json();
      if (!response.ok || !payload.success) throw new Error(payload.message || '源码加载失败');
      if (button.getAttribute('aria-selected') !== 'true' || task?.task_id !== currentId) return;
      const data = payload.data;
      if (data.html == null) { content.innerHTML = '<p class="source-notice">源码缓存已不可用，请强制刷新后重新审计。</p>'; return; }
      content.innerHTML = `<div class="source-toolbar"><span>HTML · ${esc(date(data.fetched_at))}${data.truncated ? ' · 仅保留前 2 MB' : ''}</span><span>只读快照</span></div><pre class="page-source" tabindex="0" aria-label="抓取的 HTML 源代码"></pre>`;
      content.querySelector('pre').textContent = data.html;
    } catch (error) { if (button.getAttribute('aria-selected') === 'true') content.innerHTML = `<p class="source-notice">${esc(error.message)}，点击“HTML 源代码”重试。</p>`; }
  });
  host.querySelector('#links-search').addEventListener('input', event => { query = event.target.value.trim().toLowerCase(); pageIndex = 0; render(); });
  host.querySelector('#links-filter').addEventListener('change', event => { filter = event.target.value; pageIndex = 0; render(); });
  host.querySelector('#links-refresh').addEventListener('click', () => load(true));
  render();
  return {
    load,
    setTask(value) {
      if (task?.task_id !== value?.task_id) {
        generation++; pages = []; loadedVersion = ''; loading = false; pageIndex = 0;
        task = value; render();
      } else task = value;
      if (task?.status === 'completed' || document.getElementById('tab-site-links').classList.contains('active')) load();
    }
  };
}
