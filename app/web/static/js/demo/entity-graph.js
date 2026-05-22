import { escapeHtml, tx } from './shared.js';

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

function byType(entities, entityType) {
  return (entities || []).filter(item => item.entity_type === entityType);
}

function renderStatCards(summary, lang) {
  return `
    <div class="entity-stat-grid">
      <div class="entity-stat-card"><span class="lbl">${escapeHtml(tx(lang, '实体数', 'Entities'))}</span><span class="val">${escapeHtml(String(summary.entity_count ?? 0))}</span></div>
      <div class="entity-stat-card"><span class="lbl">${escapeHtml(tx(lang, '关系数', 'Edges'))}</span><span class="val">${escapeHtml(String(summary.edge_count ?? 0))}</span></div>
      <div class="entity-stat-card"><span class="lbl">${escapeHtml(tx(lang, '证据数', 'Evidence'))}</span><span class="val">${escapeHtml(String(summary.evidence_count ?? 0))}</span></div>
      <div class="entity-stat-card"><span class="lbl">${escapeHtml(tx(lang, '来源页面', 'Source pages'))}</span><span class="val">${escapeHtml(String(summary.source_snapshot_count ?? 0))}</span></div>
    </div>
  `;
}

function renderTypeBars(summary, lang) {
  const entries = toEntriesSorted(summary.entity_type_counts).slice(0, 8);
  if (!entries.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无实体类型分布。', 'No entity type distribution yet.'))}</div>`;
  }
  const maxValue = Math.max(...entries.map(([, value]) => Number(value || 0)), 1);
  return `
    <div class="entity-type-bars">
      ${entries.map(([key, value]) => {
        const width = Math.max(8, Math.round((Number(value || 0) / maxValue) * 100));
        return `
          <div class="entity-type-row">
            <div class="entity-type-top">
              <span>${escapeHtml(String(key))}</span>
              <strong>${escapeHtml(String(value))}</strong>
            </div>
            <div class="entity-type-track">
              <div class="entity-type-fill" style="width:${width}%"></div>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

function renderLane(title, subtitle, items, lang, toneClass = '') {
  if (!items.length) {
    return `
      <div class="entity-lane ${toneClass}">
        <div class="entity-lane-head">
          <div class="entity-lane-title">${escapeHtml(title)}</div>
          <div class="entity-lane-sub">${escapeHtml(subtitle)}</div>
        </div>
        <div class="graph-empty-note">${escapeHtml(tx(lang, '当前还没有投影到这类实体。', 'No entities of this type have been projected yet.'))}</div>
      </div>
    `;
  }
  return `
    <div class="entity-lane ${toneClass}">
      <div class="entity-lane-head">
        <div class="entity-lane-title">${escapeHtml(title)}</div>
        <div class="entity-lane-sub">${escapeHtml(subtitle)}</div>
      </div>
      <div class="entity-pill-list">
        ${items.slice(0, 8).map(item => `
          <div class="entity-pill">
            <div class="entity-pill-title">${escapeHtml(item.canonical_name || item.canonical_url || '-')}</div>
            <div class="entity-pill-meta">${escapeHtml(summarizeUrl(item.canonical_url || (item.attributes || {}).page_url || ''))}</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderEntityNarrative(graph, lang) {
  const entities = graph.entities || [];
  const brands = byType(entities, 'brand');
  const products = byType(entities, 'product_model');
  const services = byType(entities, 'service_offer');
  const features = byType(entities, 'feature');
  const specs = byType(entities, 'specification');
  const useCases = byType(entities, 'use_case');
  const claims = byType(entities, 'sentiment_claim');
  const offerings = [...products, ...services];

  return `
    <div class="entity-flow">
      ${renderLane(tx(lang, '品牌主体', 'Brand core'), tx(lang, '站点文本里被识别为品牌或组织的中心实体', 'The central brand or organization recognized in site content'), brands, lang, 'tone-brand')}
      <div class="entity-flow-arrow">→</div>
      ${renderLane(tx(lang, '产品 / 服务', 'Products / services'), tx(lang, '从产品页、服务页、落地页标题与正文抽出的供给实体', 'Offer entities projected from product, service, and landing pages'), offerings, lang, 'tone-offer')}
      <div class="entity-flow-arrow">→</div>
      ${renderLane(tx(lang, '特性 / 规格 / 场景', 'Features / specs / use cases'), tx(lang, '页面正文中可复用的卖点、参数与适用场景', 'Reusable selling points, specs, and use cases from body text'), [...features, ...specs, ...useCases], lang, 'tone-detail')}
      <div class="entity-flow-arrow">→</div>
      ${renderLane(tx(lang, '评价与感知', 'Claims & sentiment'), tx(lang, '用户评价、可信度表述与营销语句线索', 'Review, trust, and sentiment statements found in text'), claims, lang, 'tone-claim')}
    </div>
  `;
}

function splitSvgLabel(value, maxChars = 16, maxLines = 2) {
  const text = String(value || '-').trim();
  if (!text) return ['-'];
  const words = text.split(/\s+/);
  const lines = [];
  let current = '';
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
    if (lines.length >= maxLines - 1) break;
  }
  if (current && lines.length < maxLines) lines.push(current);
  if (lines.length === 0) lines.push(text.slice(0, maxChars));
  if (text.length > lines.join(' ').length) {
    lines[lines.length - 1] = `${lines[lines.length - 1].slice(0, Math.max(3, maxChars - 1))}…`;
  }
  return lines.slice(0, maxLines);
}

function renderEntitySvgNode(node, index) {
  const lines = splitSvgLabel(node.label, node.maxChars || 15, 2);
  return `
    <g class="entity-map-node ${escapeHtml(node.tone)}">
      <circle cx="${node.x}" cy="${node.y}" r="${node.r}"></circle>
      <text x="${node.x}" y="${node.y - 8}" text-anchor="middle" class="entity-map-kicker">${escapeHtml(node.kicker)}</text>
      ${lines.map((line, lineIndex) => `
        <text x="${node.x}" y="${node.y + 12 + (lineIndex * 14)}" text-anchor="middle" class="entity-map-label">${escapeHtml(line)}</text>
      `).join('')}
      <text x="${node.x}" y="${node.y - node.r + 18}" text-anchor="middle" class="entity-map-index">${index + 1}</text>
    </g>
  `;
}

function renderEntitySvgEdge(edge) {
  return `
    <g class="entity-map-edge">
      <line x1="${edge.x1}" y1="${edge.y1}" x2="${edge.x2}" y2="${edge.y2}" marker-end="url(#entity-map-arrow)"></line>
      <text x="${edge.labelX}" y="${edge.labelY}" class="entity-map-edge-label">${escapeHtml(edge.label)}</text>
    </g>
  `;
}

function buildEntityGraphMap(graph, lang) {
  const entities = graph.entities || [];
  const brand = byType(entities, 'brand')[0];
  const offerings = [...byType(entities, 'product_model'), ...byType(entities, 'service_offer')].slice(0, 4);
  const details = [...byType(entities, 'feature'), ...byType(entities, 'specification')].slice(0, 4);
  const useCases = byType(entities, 'use_case').slice(0, 3);
  const claims = byType(entities, 'sentiment_claim').slice(0, 3);
  const width = 960;
  const height = 520;
  const center = {
    x: 480,
    y: 250,
    r: 66,
    label: brand?.canonical_name || (graph.site || {}).brand_name || (graph.site || {}).domain || '-',
    kicker: tx(lang, '品牌', 'Brand'),
    tone: 'tone-brand',
    maxChars: 18,
  };
  const nodes = [center];
  const edges = [];
  const offerPositions = [
    { x: 700, y: 120 },
    { x: 760, y: 250 },
    { x: 700, y: 380 },
    { x: 610, y: 460 },
  ];
  offerings.forEach((item, index) => {
    const pos = offerPositions[index];
    const node = {
      ...pos,
      r: 50,
      label: item.canonical_name || '-',
      kicker: item.entity_type === 'product_model' ? tx(lang, '产品', 'Product') : tx(lang, '服务', 'Service'),
      tone: 'tone-offer',
      maxChars: 14,
    };
    nodes.push(node);
    edges.push({
      x1: center.x + 48,
      y1: center.y + ((index - 1.5) * 10),
      x2: node.x - 44,
      y2: node.y,
      labelX: (center.x + node.x) / 2 - 8,
      labelY: (center.y + node.y) / 2 - 8,
      label: index === 0 ? tx(lang, 'offers', 'offers') : '',
    });
  });
  const detailPositions = [
    { x: 270, y: 410 },
    { x: 395, y: 460 },
    { x: 535, y: 470 },
    { x: 665, y: 430 },
  ];
  details.forEach((item, index) => {
    const pos = detailPositions[index];
    const node = {
      ...pos,
      r: 42,
      label: item.canonical_name || '-',
      kicker: item.entity_type === 'feature' ? tx(lang, '特性', 'Feature') : tx(lang, '规格', 'Spec'),
      tone: 'tone-detail',
      maxChars: 13,
    };
    nodes.push(node);
    const sourceOffer = offerings[index % Math.max(offerings.length, 1)];
    const sourcePos = offerPositions[index % Math.max(offerPositions.length, 1)];
    edges.push({
      x1: sourceOffer ? sourcePos.x - 18 : center.x - 20,
      y1: sourceOffer ? sourcePos.y + 26 : center.y + 30,
      x2: node.x,
      y2: node.y - 38,
      labelX: sourceOffer ? (sourcePos.x + node.x) / 2 : (center.x + node.x) / 2,
      labelY: sourceOffer ? (sourcePos.y + node.y) / 2 : (center.y + node.y) / 2,
      label: index === 0 ? tx(lang, 'has_feature/spec', 'has_feature/spec') : '',
    });
  });
  const useCasePositions = [
    { x: 210, y: 135 },
    { x: 170, y: 250 },
    { x: 210, y: 365 },
  ];
  useCases.forEach((item, index) => {
    const pos = useCasePositions[index];
    const node = {
      ...pos,
      r: 42,
      label: item.canonical_name || '-',
      kicker: tx(lang, '场景', 'Use case'),
      tone: 'tone-case',
      maxChars: 13,
    };
    nodes.push(node);
    edges.push({
      x1: center.x - 54,
      y1: center.y + ((index - 1) * 12),
      x2: node.x + 36,
      y2: node.y,
      labelX: (center.x + node.x) / 2 - 4,
      labelY: (center.y + node.y) / 2 - 8,
      label: index === 0 ? tx(lang, 'suited_for', 'suited_for') : '',
    });
  });
  const claimPositions = [
    { x: 360, y: 78 },
    { x: 490, y: 54 },
    { x: 620, y: 84 },
  ];
  claims.forEach((item, index) => {
    const pos = claimPositions[index];
    const node = {
      ...pos,
      r: 38,
      label: item.canonical_name || '-',
      kicker: tx(lang, '评价', 'Claim'),
      tone: 'tone-claim',
      maxChars: 12,
    };
    nodes.push(node);
    edges.push({
      x1: center.x + ((index - 1) * 18),
      y1: center.y - 58,
      x2: node.x,
      y2: node.y + 34,
      labelX: (center.x + node.x) / 2,
      labelY: (center.y + node.y) / 2 - 10,
      label: index === 0 ? tx(lang, 'claim', 'claim') : '',
    });
  });
  if (!nodes.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无可视化实体节点。', 'No entity nodes are available for the map yet.'))}</div>`;
  }
  return `
    <div class="entity-map-shell">
      <svg class="entity-map-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(tx(lang, '实体图谱关系图', 'Entity graph relationship map'))}">
        <defs>
          <marker id="entity-map-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z"></path>
          </marker>
        </defs>
        ${edges.map(renderEntitySvgEdge).join('')}
        ${nodes.map(renderEntitySvgNode).join('')}
      </svg>
    </div>
  `;
}

function renderSourcePages(sourcePages, lang) {
  const rows = (sourcePages || []).slice(0, 8);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无来源页面。', 'No source pages available.'))}</div>`;
  }
  return `
    <div class="entity-source-grid">
      ${rows.map(item => `
        <div class="entity-source-card">
          <div class="entity-source-top">
            <span class="entity-source-type">${escapeHtml(item.page_type || 'page')}</span>
            <span class="entity-source-words">${escapeHtml(tx(lang, '词数', 'Words'))} ${escapeHtml(String(item.word_count ?? 0))}</span>
          </div>
          <div class="entity-source-title">${escapeHtml(item.canonical_name || '-')}</div>
          <div class="entity-source-url">${escapeHtml(item.canonical_url || '-')}</div>
          <div class="entity-source-excerpt">${escapeHtml(item.text_excerpt || tx(lang, '未保留摘要，实体主要来自标题、heading 与正文片段。', 'No excerpt stored; entities were mainly projected from titles, headings, and body text.'))}</div>
        </div>
      `).join('')}
    </div>
  `;
}

function renderGroupedEntities(graph, lang) {
  const entities = graph.entities || [];
  const groups = [
    ['product_model', tx(lang, '产品实体', 'Product entities')],
    ['service_offer', tx(lang, '服务实体', 'Service entities')],
    ['feature', tx(lang, '产品特性', 'Feature entities')],
    ['specification', tx(lang, '规格参数', 'Specification entities')],
    ['use_case', tx(lang, '使用场景', 'Use-case entities')],
    ['sentiment_claim', tx(lang, '评价语句', 'Sentiment claims')],
  ];
  return groups.map(([entityType, label]) => {
    const rows = byType(entities, entityType).slice(0, 6);
    return `
      <div class="entity-group-card">
        <div class="entity-group-head">
          <h4>${escapeHtml(label)}</h4>
          <span>${escapeHtml(String(byType(entities, entityType).length))}</span>
        </div>
        ${rows.length ? `
          <div class="entity-group-list">
            ${rows.map(item => `
              <div class="entity-group-item">
                <div class="entity-group-name">${escapeHtml(item.canonical_name || '-')}</div>
                <div class="entity-group-meta">${escapeHtml(summarizeUrl(item.canonical_url || (item.attributes || {}).page_url || ''))}</div>
              </div>
            `).join('')}
          </div>
        ` : `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无样本。', 'No samples yet.'))}</div>`}
      </div>
    `;
  }).join('');
}

function renderRelationRows(edges, lang) {
  const rows = (edges || []).slice(0, 16);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无关系边。', 'No entity relations available.'))}</div>`;
  }
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
  `;
}

function renderEvidenceRows(evidence, lang) {
  const rows = (evidence || []).slice(0, 12);
  if (!rows.length) {
    return `<div class="graph-empty-note">${escapeHtml(tx(lang, '暂无证据记录。', 'No evidence records available.'))}</div>`;
  }
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
  `;
}

export function renderEntityGraph({ task, graph, host, lang }) {
  const payload = graph || {};
  const summary = payload.summary || {};
  const built = payload.built === true;
  const hasGraphData = (payload.entities || []).length || (payload.edges || []).length || (payload.evidence || []).length;

  if (!built && !hasGraphData) {
    host.className = 'report-empty placeholder';
    host.textContent = payload.note || (
      task?.build_knowledge_graph === false
        ? tx(lang, '当前任务未开启实体图谱构建。', 'Entity graph build is disabled for this task.')
        : tx(lang, '等待任务完成后生成实体图谱。', 'Waiting for the task to finish before generating the entity graph.')
    );
    return;
  }

  host.className = 'graph-shell entity-shell';
  host.innerHTML = `
    <div class="graph-hero entity-hero">
      <div class="graph-hero-copy">
        <div class="graph-kicker">${escapeHtml(tx(lang, '内容实体图谱', 'Content Entity Graph'))}</div>
        <h3>${escapeHtml((payload.site || {}).brand_name || (payload.site || {}).domain || task?.domain || '-')}</h3>
        <p>${escapeHtml(payload.note || tx(lang, '基于页面标题、heading、正文片段与文本线索，抽取品牌、产品、特性、规格、场景与评价类实体。', 'Built from titles, headings, body text, and textual clues to project brands, products, features, specs, use cases, and sentiment claims.'))}</p>
      </div>
      <div class="graph-status-card">
        <div class="graph-status-label">${escapeHtml(tx(lang, '图谱状态', 'Graph status'))}</div>
        <div class="graph-status-value">${escapeHtml(built ? tx(lang, '已构建', 'Built') : tx(lang, '待构建', 'Pending'))}</div>
        <div class="graph-status-meta">${escapeHtml(tx(lang, '版本', 'Version'))} · ${escapeHtml(payload.graph_version || 'entity-graph-v1')}</div>
        <div class="graph-status-meta">${escapeHtml(tx(lang, '构建时间', 'Built at'))} · ${escapeHtml(payload.built_at || '-')}</div>
      </div>
    </div>

    ${renderStatCards(summary, lang)}

    <section class="graph-section">
      <div class="graph-section-hdr">
        <h4>${escapeHtml(tx(lang, '实体关系图', 'Entity relationship map'))}</h4>
        <span>${escapeHtml(tx(lang, '以品牌为中心，看产品、特性、场景和评价类实体如何展开', 'Read products, attributes, use cases, and claims around the brand hub'))}</span>
      </div>
      <div class="graph-section-body">
        ${buildEntityGraphMap(payload, lang)}
      </div>
    </section>

    <section class="graph-section">
      <div class="graph-section-hdr">
        <h4>${escapeHtml(tx(lang, '实体脉络', 'Entity narrative'))}</h4>
        <span>${escapeHtml(tx(lang, '按品牌 → 供给 → 细节 → 感知的顺序看站点内容表达了什么', 'Read the site narrative from brand to offerings, details, and sentiment'))}</span>
      </div>
      <div class="graph-section-body">
        ${renderEntityNarrative(payload, lang)}
      </div>
    </section>

    <div class="graph-grid-2">
      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '实体类型分布', 'Entity type mix'))}</h4>
          <span>${escapeHtml(tx(lang, '快速判断当前抽取更偏品牌、产品、规格还是评价', 'See whether extraction is leaning toward brands, products, specs, or claims'))}</span>
        </div>
        <div class="graph-section-body">
          ${renderTypeBars(summary, lang)}
        </div>
      </section>

      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '来源页面', 'Source pages'))}</h4>
          <span>${escapeHtml(tx(lang, '这些页面正文为实体抽取提供了主要语料', 'These pages provide the main text corpus for entity extraction'))}</span>
        </div>
        <div class="graph-section-body">
          ${renderSourcePages(payload.source_pages || [], lang)}
        </div>
      </section>
    </div>

    <section class="graph-section">
      <div class="graph-section-hdr">
        <h4>${escapeHtml(tx(lang, '实体分组样本', 'Entity group samples'))}</h4>
        <span>${escapeHtml(tx(lang, '按产品、服务、特性、规格、场景和评价语句分开展示', 'Split the sample by products, services, features, specs, use cases, and sentiment claims'))}</span>
      </div>
      <div class="graph-section-body">
        <div class="entity-group-grid">
          ${renderGroupedEntities(payload, lang)}
        </div>
      </div>
    </section>

    <div class="graph-grid-2">
      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '关系样本', 'Relation sample'))}</h4>
          <span>${escapeHtml(tx(lang, '帮助判断品牌、供给与文本特征之间的连边是否合理', 'Inspect whether brands, offerings, and text-level attributes are connected correctly'))}</span>
        </div>
        <div class="graph-section-body">${renderRelationRows(payload.edges || [], lang)}</div>
      </section>

      <section class="graph-section">
        <div class="graph-section-hdr">
          <h4>${escapeHtml(tx(lang, '证据样本', 'Evidence sample'))}</h4>
          <span>${escapeHtml(tx(lang, '展示标题、heading 与正文片段如何支撑实体抽取', 'Shows how titles, headings, and text snippets support extraction'))}</span>
        </div>
        <div class="graph-section-body">${renderEvidenceRows(payload.evidence || [], lang)}</div>
      </section>
    </div>
  `;
}
