(() => {
  'use strict';

  document.querySelectorAll('[data-api-origin]').forEach((node) => {
    node.textContent = window.location.origin;
  });

  const icon = (name) => {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const use = document.createElementNS(svg.namespaceURI, 'use');
    svg.classList.add('icon');
    svg.setAttribute('aria-hidden', 'true');
    use.setAttribute('href', `#icon-${name}`);
    svg.append(use);
    return svg;
  };

  // Highlight with text nodes so examples remain literal, copyable text.
  document.querySelectorAll('.code-block pre code').forEach((code) => {
    const source = code.textContent;
    const fragment = document.createDocumentFragment();
    const tokens = /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b/g;
    let cursor = 0;
    for (const match of source.matchAll(tokens)) {
      fragment.append(document.createTextNode(source.slice(cursor, match.index)));
      const span = document.createElement('span');
      span.className = match[3] ? 'syntax-literal' : match[2] ? 'syntax-key' : 'syntax-string';
      span.textContent = match[1] || match[3];
      fragment.append(span);
      if (match[2]) fragment.append(document.createTextNode(match[2]));
      cursor = match.index + match[0].length;
    }
    fragment.append(document.createTextNode(source.slice(cursor)));
    code.replaceChildren(fragment);
  });

  const feedback = document.querySelector('.copy-feedback');
  let feedbackTimer;
  function announce(message) {
    clearTimeout(feedbackTimer);
    feedback.textContent = message;
    feedback.classList.add('is-visible');
    feedbackTimer = setTimeout(() => feedback.classList.remove('is-visible'), 2400);
  }

  async function copyText(value) {
    if (navigator.clipboard && window.isSecureContext) {
      try {
        await navigator.clipboard.writeText(value);
        return;
      } catch {
        // HTTP deployments and denied clipboard access use the selection fallback.
      }
    }
    const previousFocus = document.activeElement;
    const selection = window.getSelection();
    const ranges = Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index).cloneRange());
    const buffer = document.createElement('textarea');
    buffer.value = value;
    buffer.readOnly = true;
    buffer.className = 'clipboard-buffer';
    buffer.setAttribute('aria-label', '复制内容');
    document.body.append(buffer);
    try {
      buffer.focus({ preventScroll: true });
      buffer.select();
      if (!document.execCommand('copy')) throw new Error('Copy unavailable');
    } finally {
      buffer.remove();
      if (previousFocus instanceof HTMLElement) previousFocus.focus({ preventScroll: true });
      selection.removeAllRanges();
      ranges.forEach((range) => selection.addRange(range));
    }
  }

  function addCopyButton(container, getText, label, showLabel) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = showLabel ? 'code-copy' : 'endpoint-copy';
    button.setAttribute('aria-label', label);
    button.title = label;
    button.append(icon('copy'));
    const text = document.createElement('span');
    if (showLabel) {
      text.textContent = '复制';
      button.append(text);
    }
    let resetTimer;
    button.addEventListener('click', async () => {
      try {
        await copyText(getText());
        clearTimeout(resetTimer);
        if (showLabel) text.textContent = '已复制';
        announce('已复制到剪贴板');
        resetTimer = setTimeout(() => { text.textContent = '复制'; }, 1600);
      } catch {
        announce('无法自动复制，请选中内容后手动复制。');
      }
    });
    container.append(button);
  }

  document.querySelectorAll('.code-block').forEach((block) => {
    const code = block.querySelector('pre code');
    const toolbar = block.querySelector('.code-toolbar');
    addCopyButton(toolbar, () => code.textContent, `复制${toolbar.firstElementChild.textContent}示例`, true);
  });
  document.querySelectorAll('.endpoint').forEach((endpoint) => {
    const code = endpoint.querySelector('code');
    addCopyButton(endpoint, () => code.textContent, `复制接口路径 ${code.textContent}`, false);
  });

  const sidebar = document.querySelector('.docs-sidebar');
  const menuToggle = document.querySelector('.docs-menu-toggle');
  const mobileCurrent = document.querySelector('#mobile-current');
  const mobile = window.matchMedia('(max-width: 960px)');
  function setMenu(open, restoreFocus = false) {
    menuToggle.setAttribute('aria-expanded', String(open));
    sidebar.classList.toggle('is-open', open);
    if (restoreFocus) menuToggle.focus({ preventScroll: true });
  }
  menuToggle.addEventListener('click', () => setMenu(menuToggle.getAttribute('aria-expanded') !== 'true'));
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && sidebar.classList.contains('is-open')) setMenu(false, true);
  });
  document.addEventListener('click', (event) => {
    if (sidebar.classList.contains('is-open') && !sidebar.contains(event.target) && !menuToggle.contains(event.target)) setMenu(false);
  });
  mobile.addEventListener('change', () => setMenu(false));
  sidebar.querySelectorAll('a').forEach((link) => {
    link.addEventListener('click', () => {
      setMenu(false);
      if (mobile.matches && link.hash) {
        const section = document.querySelector(link.hash);
        section.tabIndex = -1;
        section.focus({ preventScroll: true });
      }
    });
  });
  menuToggle.hidden = false;
  document.documentElement.classList.add('docs-ready');

  const entries = [...document.querySelectorAll('.docs-nav a')].map((link) => ({ link, section: document.querySelector(link.hash) }));
  let activeLink;
  let scrollFrame = 0;
  function updateLocation() {
    scrollFrame = 0;
    let active = entries[0];
    for (const entry of entries) {
      if (entry.section.getBoundingClientRect().top <= 165) active = entry;
    }
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) active = entries.at(-1);
    if (activeLink === active.link) return;
    entries.forEach(({ link }) => link.removeAttribute('aria-current'));
    active.link.setAttribute('aria-current', 'location');
    mobileCurrent.textContent = active.section.querySelector('h2, h3').textContent;
    activeLink = active.link;
    if (!mobile.matches) {
      const linkBounds = active.link.getBoundingClientRect();
      const bounds = sidebar.getBoundingClientRect();
      if (linkBounds.bottom > bounds.bottom - 20) sidebar.scrollTop += linkBounds.bottom - bounds.bottom + 20;
      if (linkBounds.top < bounds.top + 20) sidebar.scrollTop -= bounds.top + 20 - linkBounds.top;
    }
  }
  function scheduleLocationUpdate() {
    if (!scrollFrame) scrollFrame = requestAnimationFrame(updateLocation);
  }
  window.addEventListener('scroll', scheduleLocationUpdate, { passive: true });
  window.addEventListener('resize', scheduleLocationUpdate, { passive: true });
  window.addEventListener('hashchange', scheduleLocationUpdate);
  updateLocation();

  const search = document.querySelector('#checklist-search');
  const dimension = document.querySelector('#checklist-dimension');
  const rows = [...document.querySelectorAll('.checklist-table tbody tr:not(.checklist-empty)')];
  const records = rows.map((row) => ({ row, text: row.textContent.toLocaleLowerCase(), dimension: row.cells[1].textContent.trim() }));
  function filterChecks() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    records.forEach((record) => {
      const matches = record.text.includes(query) && (!dimension.value || record.dimension === dimension.value);
      record.row.hidden = !matches;
      if (matches) visible += 1;
    });
    document.querySelector('.checklist-empty').hidden = visible !== 0;
    document.querySelector('#checklist-count').textContent = visible === rows.length ? `${rows.length} 项检查` : `${visible} / ${rows.length} 项检查`;
  }
  search.addEventListener('input', filterChecks);
  dimension.addEventListener('change', filterChecks);
  document.querySelector('.checklist-controls').hidden = false;
})();
