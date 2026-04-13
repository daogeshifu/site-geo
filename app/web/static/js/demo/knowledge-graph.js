import { escapeHtml, tx } from './shared.js';

const ENTITY_TONE_CLASS = {
  site: 'tone-site',
  organization: 'tone-organization',
  page: 'tone-page',
  product: 'tone-offering',
  service: 'tone-offering',
  external_profile: 'tone-profile',
  external_source: 'tone-source'
};

function toEntriesSorted(map) {
  return Object.entries(map || {}).sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0));
}

function summarizeUrl(url) {
  const value = String(url || '').trim();
  if (!value) return '-';
  try {
    const parsed = new URL(value);
    return `${parsed.hostname}${parsed.pathname === '/' ? '' : parsed.pathname}`;
  } catch {
    return value;
  }
}

function getEntityToneClass(entityType) {
  return ENTITY_TONE_CLASS[entityType] || 'tone-neutral';
}

function formatEntityMeta(item, lang) {
  const attributes = item?.attributes || {};
  if (item?.entity_type === 'page') {
    return `${attributes.page_type || 'page'} · ${tx(lang, '词数', 'Words')} ${Number(attributes.word_count || 0)}`;
  }
  if (item?.entity_type === 'product' || item?.entity_type === 'service') {
    return `${tx(lang, '来源页面', 'Source page')} · ${summarizeUrl(attributes.page_url || item?.canonical_url)}`;
  }
  if (item?.entity_type === 'external_profile') {
    return tx(lang, '外部身份 / sameAs', 'External identity / sameAs');
  }
  if (item?.entity_type === 'external_source') {
    return tx(lang, '外部引用 / 链接证据', 'External citation / link evidence');
  }
  if (item?.entity_type === 'site') {
    return summarizeUrl(attributes.scope_root_url || item?.canonical_url);
  }
  return summarizeUrl(item?.canonical_url);
}

function renderChipList(map, emptyText) {
  const entries = toEntriesSorted(map);
  if (!entries.length) {
    return `<div class="graph-empty-note">${escapeHtml(emptyText)}</div>`;
  }
  return `
    <div class="graph-chip-list">
      ${entries.map(([key, value]) => `
        <div class="graph-chip">
          <span class="graph-chip-key">${escapeHtml(String(key))}</span>
          <span class="graph-chip-val">${escapeHtml(String(value))}</span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderBarList(map, emptyText, tone = 'entity') {
  const entries = toEntriesSorted(map).slice(0, 6);
  if (!entries.length) {
    return `<div class="graph-empty-note">${escapeHtml(emptyText)}</div>`;
  }
  const maxValue = Math.max(...entries.map(([, value]) => Number(value || 0)), 1);
  return `
    <div class="graph-bar-list">
      ${entries.map(([key, value]) => {
        const ratio = Math.max(8, Math.round((Number(value || 0) / maxValue) * 100));
        return `
          <div class="graph-bar-row">
            <div class="graph-bar-top">
              <span>${escapeHtml(String(key))}</span>
              <strong>${escapeHtml(String(value))}</strong>
            </div>
            <div class="graph-bar-track">
              <div class="graph-bar-fill ${tone}" style="width:${ratio}%"></div>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderEntityCards(entities, lang) {
  const rows = (entities || []).slice(0, 15);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无实体节点。', 'No graph entities available.'))}</div>`;
  }
  const hiddenCount = Math.max(0, (entities || []).length - rows.length);
  return `
    <div class="graph-node-grid">
      ${rows.map(item => `
        <div class="graph-node-card ${getEntityToneClass(item.entity_type)}">
          <div class="graph-node-head">
            <span class="graph-node-type">${escapeHtml(item.entity_type || 'entity')}</span>
            <span class="graph-node-confidence">${escapeHtml(String(item.confidence ?? 0))}</span>
          </div>
          <div class="graph-node-name">${escapeHtml(item.canonical_name || item.canonical_url || item.entity_key || '-')}</div>
          <div class="graph-node-meta">${escapeHtml(formatEntityMeta(item, lang))}</div>
          <div class="graph-node-url">${escapeHtml(item.canonical_url || '-')}</div>
        </div>
      `).join('')}
    </div>
    ${hiddenCount > 0 ? `<div class="graph-footnote">${escapeHtml(tx(lang, `其余 ${hiddenCount} 个实体请查看原始数据 tab。`, `${hiddenCount} additional entities are available in the raw data tab.`))}</div>` : ''}
  `;
}

function renderEdgeRows(edges, lang) {
  const rows = (edges || []).slice(0, 18);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无关系边。', 'No graph edges available.'))}</div>`;
  }
  const hiddenCount = Math.max(0, (edges || []).length - rows.length);
  return `
    <div class="graph-list">
      ${rows.map(item => `
        <div class="graph-relation-card">
          <div class="graph-relation-type">${escapeHtml(item.relation_type || '-')}</div>
          <div class="graph-relation-path">
            <span>${escapeHtml(item.from_entity_name || item.from_entity_key || '-')}</span>
            <span class="graph-arrow">→</span>
            <span>${escapeHtml(item.to_entity_name || item.to_entity_key || '-')}</span>
          </div>
          <div class="graph-relation-meta">
            ${escapeHtml(tx(lang, '证据', 'Evidence'))} ${escapeHtml(String(item.evidence_count ?? 0))}
            · ${escapeHtml(tx(lang, '置信度', 'Confidence'))} ${escapeHtml(String(item.confidence ?? 0))}
          </div>
        </div>
      `).join('')}
    </div>
    ${hiddenCount > 0 ? `<div class="graph-footnote">${escapeHtml(tx(lang, `其余 ${hiddenCount} 条关系请查看原始数据 tab。`, `${hiddenCount} additional edges are available in the raw data tab.`))}</div>` : ''}
  `;
}

function renderEvidenceRows(evidence, lang) {
  const rows = (evidence || []).slice(0, 12);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无证据记录。', 'No graph evidence available.'))}</div>`;
  }
  const hiddenCount = Math.max(0, (evidence || []).length - rows.length);
  return `
    <div class="graph-evidence-grid">
      ${rows.map(item => `
        <div class="graph-evidence-card">
          <div class="graph-evidence-type">${escapeHtml(item.evidence_type || '-')}</div>
          <div class="graph-evidence-field">${escapeHtml(item.evidence_field || item.selector_or_path || '-')}</div>
          <div class="graph-evidence-text">${escapeHtml(item.evidence_text || '-')}</div>
        </div>
      `).join('')}
    </div>
    ${hiddenCount > 0 ? `<div class="graph-footnote">${escapeHtml(tx(lang, `其余 ${hiddenCount} 条证据请查看原始数据 tab。`, `${hiddenCount} additional evidence rows are available in the raw data tab.`))}</div>` : ''}
  `;
}

function renderSourcePages(sourcePages, lang) {
  const rows = (sourcePages || []).slice(0, 8);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无来源页面。', 'No source pages available.'))}</div>`;
  }
  return `
    <div class="graph-page-grid">
      ${rows.map(item => `
        <div class="graph-page-card">
          <div class="graph-page-card-top">
            <span class="graph-page-type">${escapeHtml(item.page_type || 'page')}</span>
            <span class="graph-page-words">${escapeHtml(tx(lang, '词数', 'Words'))} ${escapeHtml(String(item.word_count ?? 0))}</span>
          </div>
          <div class="graph-page-title">${escapeHtml(item.canonical_name || item.canonical_url || '-')}</div>
          <div class="graph-page-url">${escapeHtml(item.canonical_url || '-')}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function buildStageNodes(items, lang, fallbackTitle, fallbackMeta) {
  const nodes = (items || []).slice(0, 4).map(item => ({
    title: item.canonical_name || item.canonical_url || item.entity_key || fallbackTitle,
    meta: formatEntityMeta(item, lang),
    tone: getEntityToneClass(item.entity_type)
  }));
  if (nodes.length) return nodes;
  return [{ title: fallbackTitle, meta: fallbackMeta, tone: 'tone-neutral', empty: true }];
}

function renderTopologyStage(title, count, nodes, lang) {
  return `
    <div class="graph-topology-stage">
      <div class="graph-topology-stage-head">
        <div>
          <div class="graph-topology-label">${escapeHtml(title)}</div>
          <div class="graph-topology-count">${escapeHtml(String(count))}</div>
        </div>
      </div>
      <div class="graph-topology-stack">
        ${nodes.map(node => `
          <div class="graph-topology-node ${escapeHtml(node.tone || 'tone-neutral')} ${node.empty ? 'is-empty' : ''}">
            <div class="graph-topology-node-title">${escapeHtml(node.title)}</div>
            <div class="graph-topology-node-meta">${escapeHtml(node.meta)}</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderTopologyLink(title, relationEntries, lang) {
  const entries = relationEntries.filter(([, value]) => Number(value || 0) > 0);
  return `
    <div class="graph-topology-link">
      <div class="graph-topology-link-label">${escapeHtml(title)}</div>
      <div class="graph-topology-link-pills">
        ${entries.length ? entries.map(([key, value]) => `
          <span class="graph-topology-pill">${escapeHtml(key)} · ${escapeHtml(String(value))}</span>
        `).join('') : `<span class="graph-topology-pill muted">${escapeHtml(tx(lang, '暂无关系', 'No relation yet'))}</span>`}
      </div>
    </div>
  `;
}

function renderTopology(payload, task, lang) {
  const summary = payload.summary || {};
  const relationCounts = summary.relation_type_counts || {};
  const entities = payload.entities || [];
  const sourcePages = payload.source_pages || [];

  const siteEntities = entities.filter(item => item.entity_type === 'site');
  const orgEntities = entities.filter(item => item.entity_type === 'organization');
  const offeringEntities = entities.filter(item => item.entity_type === 'product' || item.entity_type === 'service');
  const externalEntities = entities.filter(item => item.entity_type === 'external_profile' || item.entity_type === 'external_source');

  const siteFallback = {
    canonical_name: (payload.site || {}).domain || task?.domain || '-',
    canonical_url: (payload.site || {}).scope_root_url || task?.normalized_url || task?.url || '-',
    entity_type: 'site',
    attributes: { scope_root_url: (payload.site || {}).scope_root_url || task?.normalized_url || task?.url || '-' }
  };

  return `
    <div class="graph-topology">
      ${renderTopologyStage(
        tx(lang, '站点核心', 'Site core'),
        siteEntities.length + orgEntities.length || 1,
        buildStageNodes([...siteEntities, ...orgEntities], lang, siteFallback.canonical_name, summarizeUrl(siteFallback.canonical_url)),
        lang
      )}
      ${renderTopologyLink(tx(lang, '身份关系', 'Identity links'), [
        ['represents', relationCounts.represents || 0],
        ['entity_home', relationCounts.entity_home || 0],
        ['about', relationCounts.about || 0]
      ], lang)}
      ${renderTopologyStage(
        tx(lang, '页面资产', 'Page layer'),
        sourcePages.length,
        buildStageNodes(
          sourcePages.map(item => ({
            canonical_name: item.canonical_name,
            canonical_url: item.canonical_url,
            entity_type: 'page',
            attributes: { page_type: item.page_type, word_count: item.word_count }
          })),
          lang,
          tx(lang, '暂无页面节点', 'No page nodes yet'),
          tx(lang, '等待页面快照', 'Waiting for page snapshots')
        ),
        lang
      )}
      ${renderTopologyLink(tx(lang, '内容与供给', 'Content & offers'), [
        ['has_page', relationCounts.has_page || 0],
        ['offers', relationCounts.offers || 0],
        ['links_to', relationCounts.links_to || 0]
      ], lang)}
      ${renderTopologyStage(
        tx(lang, '产品与服务', 'Offerings'),
        offeringEntities.length,
        buildStageNodes(
          offeringEntities,
          lang,
          tx(lang, '暂无产品/服务实体', 'No product or service entities'),
          tx(lang, '当前投影未识别 offer 实体', 'The current projection did not detect offer entities')
        ),
        lang
      )}
      ${renderTopologyLink(tx(lang, '外部信号', 'External signals'), [
        ['same_as', relationCounts.same_as || 0],
        ['cites', relationCounts.cites || 0],
        ['references', relationCounts.references || 0]
      ], lang)}
      ${renderTopologyStage(
        tx(lang, '外部身份与来源', 'External identities & sources'),
        externalEntities.length,
        buildStageNodes(
          externalEntities,
          lang,
          tx(lang, '暂无外部信号', 'No external signals yet'),
          tx(lang, '等待 sameAs / 引用 / 外链证据', 'Waiting for sameAs, citations, and external-link evidence')
        ),
        lang
      )}
    </div>
  `;
}

function renderInsightTiles(payload, lang) {
  const summary = payload.summary || {};
  const entityTypeCounts = summary.entity_type_counts || {};
  const relationCounts = summary.relation_type_counts || {};
  const offeringCount = Number(entityTypeCounts.product || 0) + Number(entityTypeCounts.service || 0);
  const externalSignalCount = Number(entityTypeCounts.external_profile || 0) + Number(entityTypeCounts.external_source || 0);

  const cards = [
    {
      label: tx(lang, '实体覆盖', 'Entity coverage'),
      value: summary.entity_count ?? 0,
      note: tx(lang, '当前站点被投影成多少个可追踪实体。', 'How many trackable entities were projected for this site.')
    },
    {
      label: tx(lang, '内容深度', 'Content depth'),
      value: summary.source_snapshot_count ?? 0,
      note: tx(lang, '参与构建的页面快照数量，决定图谱覆盖面。', 'The number of source page snapshots feeding the projection.')
    },
    {
      label: tx(lang, '供给实体', 'Offer entities'),
      value: offeringCount,
      note: tx(lang, '识别到的产品与服务实体，用于表达站点“卖什么”。', 'Detected product and service entities that express what the site offers.')
    },
    {
      label: tx(lang, '外部信号', 'External signals'),
      value: externalSignalCount,
      note: tx(lang, 'sameAs、外部引用与来源链接的聚合结果。', 'The combined external-profile, citation, and source-link signals.')
    },
    {
      label: tx(lang, '关系强度', 'Relation density'),
      value: summary.edge_count ?? 0,
      note: tx(lang, '实体之间建立了多少条结构化关系。', 'How many structured relations connect the projected entities.')
    },
    {
      label: tx(lang, '证据支撑', 'Evidence coverage'),
      value: summary.evidence_count ?? 0,
      note: relationCounts.same_as
        ? tx(lang, 'sameAs 与引用证据已进入图谱，可帮助 AI 建立身份一致性。', 'sameAs and citation evidence are present, which helps AI systems build identity consistency.')
        : tx(lang, '当前证据主要来自页面快照、链接锚文本与启发式判断。', 'The current evidence mostly comes from page snapshots, anchors, and heuristics.')
    }
  ];

  return `
    <div class="graph-insight-grid">
      ${cards.map(card => `
        <div class="graph-insight-card">
          <span class="graph-insight-label">${escapeHtml(card.label)}</span>
          <span class="graph-insight-value">${escapeHtml(String(card.value))}</span>
          <p>${escapeHtml(card.note)}</p>
        </div>
      `).join('')}
    </div>
  `;
}

function renderMetaGrid(payload, task, lang, requestedTaskId, snapshotTaskId, showSnapshotTaskId) {
  const items = [
    ['task_id', requestedTaskId],
    ...(showSnapshotTaskId ? [['snapshot_task_id', snapshotTaskId]] : []),
    ['site_id', String(payload.site_id ?? payload.task?.site_id ?? '-')],
    [tx(lang, '任务状态', 'Task status'), (payload.task || {}).status || task?.status || '-'],
    ['scope root', (payload.site || {}).scope_root_url || '-'],
    ['site root', (payload.site || {}).site_root_url || '-'],
    [tx(lang, '业务类型', 'Business type'), (payload.site || {}).business_type || '-'],
    [tx(lang, '构建时间', 'Built at'), payload.built_at || '-']
  ];
  return `
    <div class="graph-meta-grid">
      ${items.map(([label, value]) => `
        <div class="graph-meta-card">
          <div class="graph-meta-label">${escapeHtml(label)}</div>
          <div class="graph-meta-value">${escapeHtml(value || '-')}</div>
        </div>
      `).join('')}
    </div>
  `;
}

export function renderKnowledgeGraph({ task, graph, host, lang }) {
  const payload = graph || {};
  const summary = payload.summary || {};
  const built = payload.built === true;
  const entities = payload.entities || [];
  const edges = payload.edges || [];
  const evidence = payload.evidence || [];
  const sourcePages = payload.source_pages || [];
  const requestedTaskId = payload.task_id || task?.task_id || '-';
  const snapshotTaskId = payload.snapshot_task_id || '-';
  const showSnapshotTaskId = Boolean(payload.snapshot_task_id) && payload.snapshot_task_id !== payload.task_id;

  if (!built && !entities.length && !edges.length && !evidence.length) {
    host.className = 'report-empty placeholder';
    host.textContent = payload.note || (
      task?.build_knowledge_graph === false
        ? tx(lang, '当前任务未开启知识图谱构建。', 'Knowledge graph build is disabled for this task.')
        : tx(lang, '等待任务完成后生成知识图谱。', 'Waiting for the task to finish before generating the knowledge graph.')
    );
    return;
  }

  host.className = 'graph-shell';
  host.innerHTML = `
    <div class="graph-hero">
      <div class="graph-hero-copy">
        <div class="graph-kicker">${escapeHtml(tx(lang, '站点知识图谱', 'Site Knowledge Graph'))}</div>
        <h3>${escapeHtml((payload.site || {}).domain || task?.domain || '-')}</h3>
        <p>${escapeHtml(payload.note || tx(lang, '基于页面快照、结构化数据、sameAs、内外链与证据线索，整理站点的实体与关系视图。', 'Built from page snapshots, structured data, sameAs, internal/external links, and evidence signals to summarize the site entity graph.'))}</p>
      </div>
      <div class="graph-status-card">
        <div class="graph-status-label">${escapeHtml(tx(lang, '图谱状态', 'Graph status'))}</div>
        <div class="graph-status-value">${escapeHtml(built ? tx(lang, '已构建', 'Built') : tx(lang, '待构建', 'Pending'))}</div>
        <div class="graph-status-meta">${escapeHtml(tx(lang, '版本', 'Version'))} · ${escapeHtml(payload.graph_version || 'site-graph-v1')}</div>
        <div class="graph-status-meta">${escapeHtml(tx(lang, '构建时间', 'Built at'))} · ${escapeHtml(payload.built_at || '-')}</div>
      </div>
    </div>

    <div class="graph-stat-grid">
      <div class="graph-stat-card"><span class="lbl">${escapeHtml(tx(lang, '实体数', 'Entities'))}</span><span class="val">${escapeHtml(String(summary.entity_count ?? 0))}</span></div>
      <div class="graph-stat-card"><span class="lbl">${escapeHtml(tx(lang, '关系数', 'Edges'))}</span><span class="val">${escapeHtml(String(summary.edge_count ?? 0))}</span></div>
      <div class="graph-stat-card"><span class="lbl">${escapeHtml(tx(lang, '证据数', 'Evidence'))}</span><span class="val">${escapeHtml(String(summary.evidence_count ?? 0))}</span></div>
      <div class="graph-stat-card"><span class="lbl">${escapeHtml(tx(lang, '来源快照', 'Source snapshots'))}</span><span class="val">${escapeHtml(String(summary.source_snapshot_count ?? 0))}</span></div>
    </div>

    <div class="graph-overview-grid">
      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '拓扑总览', 'Topology overview'))}</h4>
          <span>${escapeHtml(tx(lang, '用站点 → 页面 → 供给 → 外部信号的顺序快速理解图谱', 'Read the graph from site to pages, offerings, and external signals'))}</span>
        </div>
        <div class="graph-section-body">
          ${renderTopology(payload, task, lang)}
        </div>
      </section>

      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '图谱脉搏', 'Graph pulse'))}</h4>
          <span>${escapeHtml(tx(lang, '看实体构成、关系分布和证据支撑是否健康', 'Inspect the mix of entities, relations, and evidence'))}</span>
        </div>
        <div class="graph-section-body">
          <div class="graph-subsection">
            <div class="graph-subtitle">${escapeHtml(tx(lang, '实体类型分布', 'Entity type mix'))}</div>
            ${renderBarList(summary.entity_type_counts, tx(lang, '暂无实体类型分布。', 'No entity type distribution.'), 'entity')}
          </div>
          <div class="graph-subsection">
            <div class="graph-subtitle">${escapeHtml(tx(lang, '关系类型分布', 'Relation type mix'))}</div>
            ${renderBarList(summary.relation_type_counts, tx(lang, '暂无关系类型分布。', 'No relation type distribution.'), 'relation')}
          </div>
          <div class="graph-subsection">
            <div class="graph-subtitle">${escapeHtml(tx(lang, '关键洞察', 'Key insights'))}</div>
            ${renderInsightTiles(payload, lang)}
          </div>
        </div>
      </section>
    </div>

    <div class="graph-grid-2">
      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '任务与站点上下文', 'Task and site context'))}</h4>
          <span>${escapeHtml(tx(lang, '确认这份图谱来自哪个任务、作用域和站点', 'Verify which task, scope, and site produced this graph'))}</span>
        </div>
        <div class="graph-section-body">
          ${renderMetaGrid(payload, task, lang, requestedTaskId, snapshotTaskId, showSnapshotTaskId)}
        </div>
      </section>

      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '来源页面', 'Source pages'))}</h4>
          <span>${escapeHtml(tx(lang, '这些页面是当前知识图谱的主要输入层', 'These pages are the main inputs feeding the graph'))}</span>
        </div>
        <div class="graph-section-body">${renderSourcePages(sourcePages, lang)}</div>
      </section>
    </div>

    <section class="graph-section">
      <div class="graph-section-hdr">
        <h4>${escapeHtml(tx(lang, '实体样本', 'Entity sample'))}</h4>
        <span>${escapeHtml(tx(lang, '抽样展示当前图谱中的关键实体节点', 'A sampled view of the most important projected entities'))}</span>
      </div>
      <div class="graph-section-body">${renderEntityCards(entities, lang)}</div>
    </section>

    <div class="graph-grid-2">
      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '关系样本', 'Relation sample'))}</h4>
          <span>${escapeHtml(tx(lang, '帮助判断站点内部与外部信号的连接方式', 'See how internal and external entities are connected'))}</span>
        </div>
        <div class="graph-section-body">${renderEdgeRows(edges, lang)}</div>
      </section>

      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '证据样本', 'Evidence sample'))}</h4>
          <span>${escapeHtml(tx(lang, '展示 sameAs、锚文本、inventory 与启发式证据', 'Shows sameAs, anchors, inventory entries, and heuristic evidence'))}</span>
        </div>
        <div class="graph-section-body">${renderEvidenceRows(evidence, lang)}</div>
      </section>
    </div>

    <section class="graph-section">
      <div class="graph-section-hdr">
        <h4>${escapeHtml(tx(lang, '分布速览', 'Distribution snapshot'))}</h4>
        <span>${escapeHtml(tx(lang, '保留类型计数的平面视图，便于快速核对', 'A flat view of the type counts for quick verification'))}</span>
      </div>
      <div class="graph-section-body">
        <div class="graph-subsection">
          <div class="graph-subtitle">${escapeHtml(tx(lang, '实体类型', 'Entity types'))}</div>
          ${renderChipList(summary.entity_type_counts, tx(lang, '暂无实体类型分布。', 'No entity type distribution.'))}
        </div>
        <div class="graph-subsection">
          <div class="graph-subtitle">${escapeHtml(tx(lang, '关系类型', 'Relation types'))}</div>
          ${renderChipList(summary.relation_type_counts, tx(lang, '暂无关系类型分布。', 'No relation type distribution.'))}
        </div>
      </div>
    </section>
  `;
}
