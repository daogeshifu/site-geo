from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["demo"])


HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>GEO Audit Console</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --bg: #f1f3f5;
      --surface: #ffffff;
      --border: #e2e6ea;
      --text: #111827;
      --muted: #6b7280;
      --subtle: #9ca3af;
      --accent: #10b981;
      --accent-dim: rgba(16,185,129,0.1);
      --accent-dark: #059669;
      --warn: #f59e0b;
      --warn-dim: rgba(245,158,11,0.1);
      --danger: #ef4444;
      --danger-dim: rgba(239,68,68,0.1);
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      font-size: 14px;
      line-height: 1.5;
    }

    /* ── Header ── */
    .hdr {
      height: 52px;
      background: #0d1117;
      display: flex;
      align-items: center;
      padding: 0 24px;
      gap: 10px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .hdr-logo {
      width: 26px; height: 26px;
      background: linear-gradient(135deg, #10b981 0%, #059669 100%);
      border-radius: 7px;
      display: flex; align-items: center; justify-content: center;
      color: #fff; font-weight: 800; font-size: 12px; letter-spacing: -0.5px;
    }
    .hdr-name { color: #f1f5f9; font-weight: 600; font-size: 14.5px; }
    .hdr-sep { color: rgba(255,255,255,0.18); margin: 0 6px; }
    .hdr-sub { color: #94a3b8; font-size: 13px; }
    .hdr-pill {
      margin-left: auto;
      padding: 2px 9px;
      background: rgba(16,185,129,0.18);
      color: #34d399;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.02em;
    }

    /* ── Layout ── */
    .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 56px; }

    .page-title { margin-bottom: 22px; }
    .page-title h1 { font-size: 20px; font-weight: 700; margin-bottom: 3px; }
    .page-title p { color: var(--muted); font-size: 13px; }

    .grid-top {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      gap: 14px;
      margin-bottom: 14px;
    }

    /* ── Card ── */
    .card {
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.04);
    }
    .card-hdr {
      padding: 16px 20px 13px;
      border-bottom: 1px solid var(--border);
      display: flex; align-items: center; justify-content: space-between;
    }
    .card-ttl {
      font-size: 13.5px; font-weight: 600;
      display: flex; align-items: center; gap: 8px;
    }
    .card-ico {
      width: 22px; height: 22px;
      background: var(--accent-dim);
      border-radius: 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px;
    }
    .card-body { padding: 20px; }

    /* ── Form ── */
    .field { margin-bottom: 14px; }
    .field:last-child { margin-bottom: 0; }
    .field > label {
      display: block;
      font-size: 11.5px; font-weight: 600;
      color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.05em;
      margin-bottom: 6px;
    }
    .inp-wrap { position: relative; }
    .inp-icon {
      position: absolute; left: 11px; top: 50%;
      transform: translateY(-50%);
      font-size: 13px; color: var(--subtle);
      pointer-events: none;
    }
    input[type="text"], select {
      width: 100%; height: 40px;
      padding: 0 12px;
      border: 1px solid var(--border); border-radius: 9px;
      font-size: 13.5px; color: var(--text);
      background: var(--surface);
      transition: border-color 0.15s, box-shadow 0.15s;
      -webkit-appearance: none; appearance: none;
    }
    input[type="text"].has-icon { padding-left: 30px; }
    input[type="text"]:focus, select:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(16,185,129,0.13);
    }
    input:disabled, select:disabled {
      background: #f9fafb; color: var(--subtle); cursor: not-allowed;
    }
    select {
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='7'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%236b7280' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 12px center;
      padding-right: 32px;
    }
    .row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

    .toggle-wrap {
      display: flex; align-items: center; gap: 9px;
      height: 40px; padding: 0 14px;
      border: 1px solid var(--border); border-radius: 9px;
      cursor: pointer; user-select: none;
      transition: border-color 0.15s, background 0.15s;
    }
    .toggle-wrap:hover { background: #f9fafb; border-color: #c8ced4; }
    .toggle-wrap input[type="checkbox"] {
      width: 14px; height: 14px; accent-color: var(--accent); cursor: pointer; flex-shrink: 0;
    }
    .toggle-lbl { font-size: 13.5px; color: var(--text); }
    .toggle-hint { margin-left: auto; font-size: 11.5px; color: var(--subtle); }

    /* ── Buttons ── */
    .btn {
      height: 40px; padding: 0 18px; border: none; border-radius: 9px;
      font-size: 13.5px; font-weight: 600; cursor: pointer;
      display: inline-flex; align-items: center; gap: 6px;
      transition: all 0.15s;
      white-space: nowrap;
    }
    .btn-primary { background: var(--accent); color: #fff; }
    .btn-primary:hover:not(:disabled) {
      background: var(--accent-dark);
      box-shadow: 0 4px 14px rgba(16,185,129,0.32);
    }
    .btn-primary:active:not(:disabled) { transform: scale(0.97); }
    .btn-ghost {
      background: var(--surface); color: var(--text);
      border: 1px solid var(--border);
    }
    .btn-ghost:hover:not(:disabled) { background: var(--bg); }
    .btn:disabled { opacity: 0.42; cursor: not-allowed; }
    .btn-row { display: flex; gap: 10px; padding-top: 6px; }

    /* ── Status meta grid ── */
    .meta-grid {
      display: grid; grid-template-columns: 1fr 1fr;
      gap: 1px; background: var(--border);
      border-radius: 10px; overflow: hidden; margin-bottom: 16px;
    }
    .meta-cell { background: var(--surface); padding: 11px 14px; }
    .meta-cell:first-child { border-radius: 10px 0 0 0; }
    .meta-cell:nth-child(2) { border-radius: 0 10px 0 0; }
    .meta-cell:nth-last-child(2) { border-radius: 0 0 0 10px; }
    .meta-cell:last-child { border-radius: 0 0 10px 0; }
    .meta-lbl { font-size: 10.5px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 3px; }
    .meta-val { font-size: 13px; font-weight: 600; color: var(--text); word-break: break-all; }

    /* ── Progress ── */
    .prog-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 7px; }
    .prog-label { font-size: 11.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
    .prog-pct { font-size: 12.5px; font-weight: 700; color: var(--text); }
    .prog-track { height: 5px; background: var(--border); border-radius: 999px; overflow: hidden; margin-bottom: 18px; }
    .prog-fill {
      height: 100%;
      background: linear-gradient(90deg, #10b981, #34d399);
      border-radius: 999px; width: 0%;
      transition: width 0.55s cubic-bezier(0.4,0,0.2,1);
    }

    /* ── Timeline ── */
    .tl-label { font-size: 11.5px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 10px; }
    .timeline { display: flex; flex-direction: column; }
    .tl-item { display: flex; gap: 11px; position: relative; }
    .tl-item:not(:last-child)::before {
      content: ''; position: absolute;
      left: 14px; top: 28px; width: 1.5px;
      height: calc(100% - 14px); background: var(--border);
    }
    .tl-dot {
      width: 28px; height: 28px; border-radius: 50%; flex-shrink: 0; z-index: 1;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 700;
      border: 1.5px solid var(--border);
      background: var(--surface); color: var(--subtle);
      transition: all 0.3s;
    }
    .tl-dot.running  { border-color: var(--warn);   color: var(--warn);   background: var(--warn-dim);   animation: glow-warn 1.5s ease-in-out infinite; }
    .tl-dot.completed{ border-color: var(--accent);  color: var(--accent);  background: var(--accent-dim); }
    .tl-dot.failed   { border-color: var(--danger); color: var(--danger); background: var(--danger-dim); }
    @keyframes glow-warn {
      0%,100% { box-shadow: 0 0 0 0 rgba(245,158,11,0.45); }
      50%      { box-shadow: 0 0 0 4px rgba(245,158,11,0); }
    }
    .tl-body { padding: 4px 0 15px; flex: 1; min-width: 0; }
    .tl-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 2px; }
    .tl-name { font-size: 12.5px; font-weight: 600; }
    .tl-st   { font-size: 11px; font-weight: 500; }
    .s-pending   { color: var(--subtle); }
    .s-running   { color: var(--warn); }
    .s-completed { color: var(--accent); }
    .s-failed    { color: var(--danger); }
    .tl-preview { font-size: 11.5px; color: var(--muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px; }

    /* ── Tabs ── */
    .tabs-bar {
      display: flex; gap: 2px;
      background: var(--surface);
      border: 1px solid var(--border);
      border-bottom: none; border-radius: 13px 13px 0 0;
      padding: 7px 7px 0;
    }
    .tab-btn {
      padding: 8px 16px; border: none; background: none;
      border-radius: 8px 8px 0 0;
      font-size: 13px; font-weight: 500; color: var(--muted);
      cursor: pointer; transition: all 0.15s;
    }
    .tab-btn:hover { color: var(--text); background: rgba(0,0,0,0.03); }
    .tab-btn.active { color: var(--accent); background: var(--bg); font-weight: 600; }
    .tabs-body {
      background: var(--surface);
      border: 1px solid var(--border);
      border-top: none; border-radius: 0 0 13px 13px;
    }
    .tab-panel { display: none; padding: 22px; }
    .tab-panel.active { display: block; }

    /* ── Summary tab ── */
    .summary-content { font-size: 14px; line-height: 1.75; min-height: 72px; }
    .placeholder { color: var(--muted); font-style: italic; }

    /* ── LLM tab ── */
    .llm-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
    .stat-box { padding: 14px 16px; border: 1px solid var(--border); border-radius: 10px; background: var(--bg); }
    .stat-lbl { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); margin-bottom: 7px; }
    .stat-big { font-size: 24px; font-weight: 700; margin-bottom: 2px; }
    .stat-hint { font-size: 11.5px; color: var(--muted); }
    .llm-notes-box {
      padding: 14px 16px; border-radius: 9px;
      background: var(--bg); border: 1px solid var(--border);
      font-size: 13px; color: var(--muted); line-height: 1.65; white-space: pre-wrap;
    }

    /* ── Compare tab ── */
    .cmp-table { width: 100%; border-collapse: collapse; }
    .cmp-table th {
      text-align: left; padding: 10px 14px;
      font-size: 11.5px; font-weight: 600; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.05em;
      border-bottom: 1px solid var(--border);
    }
    .cmp-table td { padding: 10px 14px; font-size: 13px; border-bottom: 1px solid var(--border); vertical-align: middle; }
    .cmp-table tr:last-child td { border-bottom: none; }
    .cmp-table code { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 12px; background: var(--bg); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border); }

    /* ── JSON tab ── */
    .json-shell { background: #0d1117; border-radius: 9px; padding: 16px; overflow: hidden; }
    pre.json-out {
      margin: 0; padding: 0;
      font-family: 'SFMono-Regular', Consolas, monospace;
      font-size: 12px; line-height: 1.65;
      color: #8ec89a; background: none;
      overflow: auto; max-height: 480px;
    }

    /* ── Badges ── */
    .badge {
      display: inline-flex; align-items: center; gap: 4px;
      padding: 3px 9px; border-radius: 999px;
      font-size: 11.5px; font-weight: 600;
    }
    .b-default { background: var(--bg); color: var(--muted); border: 1px solid var(--border); }
    .b-success  { background: var(--accent-dim); color: var(--accent); }
    .b-warn     { background: var(--warn-dim); color: var(--warn); }
    .b-danger   { background: var(--danger-dim); color: var(--danger); }

    /* ── Toast ── */
    .toast {
      position: fixed; bottom: 22px; right: 22px;
      max-width: 380px; padding: 11px 16px;
      border-radius: 10px; background: #1c2430; color: #f1f5f9;
      font-size: 13px; line-height: 1.45;
      box-shadow: 0 8px 28px rgba(0,0,0,0.22);
      z-index: 9999;
      display: flex; align-items: flex-start; gap: 9px;
      transform: translateY(80px); opacity: 0;
      transition: transform 0.28s cubic-bezier(0.4,0,0.2,1), opacity 0.28s;
    }
    .toast.show { transform: translateY(0); opacity: 1; }
    .toast.t-error   { border-left: 3px solid var(--danger); }
    .toast.t-success { border-left: 3px solid var(--accent); }
    .toast-icon { font-size: 14px; flex-shrink: 0; margin-top: 1px; }
    .toast-close {
      margin-left: auto; flex-shrink: 0; cursor: pointer;
      color: #64748b; font-size: 15px; line-height: 1;
      background: none; border: none; padding: 0;
    }
    .toast-close:hover { color: #f1f5f9; }

    /* ── Spinner ── */
    .spin {
      width: 13px; height: 13px; border-radius: 50%;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: #fff;
      animation: spin 0.55s linear infinite; flex-shrink: 0;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* ── Bottom sections ── */
    .section-divider {
      margin: 32px 0 0;
      border: none; border-top: 1px solid var(--border);
    }
    .section-hdr {
      display: flex; align-items: baseline; gap: 10px; margin-bottom: 16px;
    }
    .section-hdr h2 { font-size: 15px; font-weight: 700; }
    .section-hdr span { font-size: 12.5px; color: var(--muted); }

    /* scoring dimensions */
    .dim-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 10px;
      margin-bottom: 14px;
    }
    .dim-card {
      border: 1px solid var(--border); border-radius: 11px;
      padding: 13px 14px; background: var(--surface);
    }
    .dim-head {
      display: flex; align-items: center; justify-content: space-between;
      margin-bottom: 9px;
    }
    .dim-name { font-size: 12.5px; font-weight: 700; }
    .dim-score { font-size: 11px; font-weight: 700; color: var(--accent); background: var(--accent-dim); padding: 2px 7px; border-radius: 999px; }
    .dim-rows { display: flex; flex-direction: column; gap: 5px; }
    .dim-row {
      display: flex; justify-content: space-between; align-items: center;
      font-size: 11.5px; gap: 8px;
    }
    .dim-row-label { color: var(--muted); flex: 1; min-width: 0; }
    .dim-row-val { font-weight: 600; white-space: nowrap; flex-shrink: 0; }
    .score-table {
      display: inline-flex; gap: 0;
      border: 1px solid var(--border); border-radius: 9px; overflow: hidden;
    }
    .score-cell {
      padding: 6px 14px; font-size: 12px; text-align: center;
      border-right: 1px solid var(--border);
    }
    .score-cell:last-child { border-right: none; }
    .score-cell .sc-range { font-weight: 700; font-size: 13px; display: block; }
    .score-cell .sc-lbl { color: var(--muted); font-size: 10.5px; margin-top: 1px; }
    .sc-critical { color: #dc2626; }
    .sc-poor     { color: #ea580c; }
    .sc-fair     { color: var(--warn); }
    .sc-good     { color: #16a34a; }
    .sc-strong   { color: var(--accent); }

    /* business notes */
    .biz-grid {
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;
    }
    .biz-card {
      border: 1px solid var(--border); border-radius: 11px;
      padding: 14px 15px; background: var(--surface);
    }
    .biz-card h4 { font-size: 12.5px; font-weight: 700; margin-bottom: 7px; }
    .biz-card ul { padding-left: 16px; display: flex; flex-direction: column; gap: 4px; }
    .biz-card li { font-size: 12px; color: var(--muted); line-height: 1.5; }
    .biz-card li strong { color: var(--text); }

    /* API steps */
    .api-steps { display: flex; flex-direction: column; gap: 12px; }
    .api-step {
      border: 1px solid var(--border); border-radius: 11px;
      background: var(--surface); overflow: hidden;
    }
    .api-step-hdr {
      display: flex; align-items: center; gap: 10px;
      padding: 12px 16px; border-bottom: 1px solid var(--border);
      background: #fafbfc;
    }
    .api-num {
      width: 22px; height: 22px; border-radius: 50%;
      background: #0d1117; color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 11px; font-weight: 700; flex-shrink: 0;
    }
    .api-step-title { font-size: 13px; font-weight: 600; }
    .api-step-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
    .api-endpoint {
      display: inline-flex; align-items: center; gap: 8px;
      background: #0d1117; color: #f1f5f9;
      padding: 7px 14px; border-radius: 8px; font-size: 12.5px;
      font-family: 'SFMono-Regular', Consolas, monospace;
    }
    .method { padding: 2px 7px; border-radius: 5px; font-size: 10.5px; font-weight: 700; }
    .m-post { background: rgba(245,158,11,0.25); color: #f59e0b; }
    .m-get  { background: rgba(16,185,129,0.25); color: #10b981; }
    .api-desc { font-size: 12.5px; color: var(--muted); line-height: 1.55; }
    .api-params { display: flex; flex-direction: column; gap: 4px; }
    .param-row { display: flex; gap: 8px; align-items: baseline; font-size: 12px; }
    .param-key { font-family: 'SFMono-Regular', Consolas, monospace; background: var(--bg); padding: 1px 6px; border-radius: 4px; border: 1px solid var(--border); color: var(--text); font-size: 11.5px; flex-shrink: 0; }
    .param-type { color: #6366f1; font-size: 11px; flex-shrink: 0; }
    .param-desc { color: var(--muted); }
    .param-req { color: var(--danger); font-size: 10.5px; font-weight: 600; flex-shrink: 0; }
    .code-snippet {
      background: #0d1117; border-radius: 8px; padding: 12px 14px; overflow: auto;
    }
    .code-snippet pre {
      margin: 0; font-size: 11.5px; line-height: 1.65;
      font-family: 'SFMono-Regular', Consolas, monospace;
      color: #8ec89a;
    }

    /* ── Responsive ── */
    @media (max-width: 1100px) { .dim-grid { grid-template-columns: repeat(3, 1fr); } }
    @media (max-width: 860px) {
      .grid-top { grid-template-columns: 1fr; }
      .row-2 { grid-template-columns: 1fr; }
      .llm-stats { grid-template-columns: 1fr; }
      .dim-grid { grid-template-columns: repeat(2, 1fr); }
      .biz-grid { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 640px) {
      .dim-grid { grid-template-columns: 1fr; }
      .biz-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .meta-grid { grid-template-columns: 1fr; }
      .meta-cell:first-child  { border-radius: 10px 10px 0 0; }
      .meta-cell:nth-child(2) { border-radius: 0; }
      .meta-cell:nth-last-child(2) { border-radius: 0; }
      .meta-cell:last-child   { border-radius: 0 0 10px 10px; }
    }
  </style>
</head>
<body>

<header class="hdr">
  <div class="hdr-logo">G</div>
  <span class="hdr-name">GEO Audit</span>
  <span class="hdr-sep">/</span>
  <span class="hdr-sub">审计控制台</span>
  <span class="hdr-pill">Beta</span>
</header>

<div class="wrap">
  <div class="page-title">
    <h1>网站 GEO 审计</h1>
    <p>提交目标 URL 创建后台任务，实时追踪各模块执行进度，查看规则分析与 AI 增强结果。</p>
  </div>

  <div class="grid-top">

    <!-- 配置卡 -->
    <div class="card">
      <div class="card-hdr">
        <div class="card-ttl">
          <div class="card-ico">⚙️</div>
          审计配置
        </div>
      </div>
      <div class="card-body">
        <form id="audit-form">
          <div class="field">
            <label>目标 URL</label>
            <div class="inp-wrap">
              <span class="inp-icon">🌐</span>
              <input id="url" type="text" class="has-icon" placeholder="https://example.com" required />
            </div>
          </div>
          <div class="row-2">
            <div class="field">
              <label>审计模式</label>
              <select id="mode">
                <option value="standard">普通版（规则）</option>
                <option value="premium">会员版（规则 + AI）</option>
              </select>
            </div>
            <div class="field">
              <label>OpenRouter 模型</label>
              <select id="model" disabled>
                <option value="openai/gpt-4.1">openai / gpt-4.1</option>
                <option value="deepseek/deepseek-v3.2">deepseek / deepseek-v3.2</option>
                <option value="anthropic/claude-sonnet-4.6">anthropic / claude-sonnet-4.6</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label for="force" class="toggle-wrap" style="margin-bottom:0;border:none;padding-left:0;display:flex;align-items:center">
              <input id="force" type="checkbox" />
              <span class="toggle-lbl">强制刷新缓存</span>
              <span class="toggle-hint">忽略一周内的历史结果</span>
            </label>
          </div>
          <div class="btn-row">
            <button id="submit-btn" type="button" class="btn btn-primary">开始审计</button>
            <button id="export-btn" type="button" class="btn btn-ghost" disabled>导出报告</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 状态卡 -->
    <div class="card">
      <div class="card-hdr">
        <div class="card-ttl">
          <div class="card-ico">📡</div>
          任务状态
        </div>
        <span id="status-badge" class="badge b-default">空闲</span>
      </div>
      <div class="card-body">
        <div class="meta-grid">
          <div class="meta-cell">
            <div class="meta-lbl">任务 ID</div>
            <div class="meta-val" id="task-id">—</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">当前步骤</div>
            <div class="meta-val" id="current-step">—</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">缓存命中</div>
            <div class="meta-val" id="cached-flag">否</div>
          </div>
          <div class="meta-cell">
            <div class="meta-lbl">执行模式</div>
            <div class="meta-val" id="mode-display">—</div>
          </div>
        </div>

        <div class="prog-row">
          <span class="prog-label">进度</span>
          <span class="prog-pct" id="progress">0%</span>
        </div>
        <div class="prog-track">
          <div id="prog-fill" class="prog-fill"></div>
        </div>

        <div class="tl-label">各模块状态</div>
        <div id="timeline" class="timeline"></div>
      </div>
    </div>

  </div><!-- /grid-top -->

  <!-- 结果区 -->
  <div class="tabs-bar">
    <button class="tab-btn active" data-tab="summary">摘要</button>
    <button class="tab-btn" data-tab="llm">AI 增强</button>
    <button class="tab-btn" data-tab="compare">版本对比</button>
    <button class="tab-btn" data-tab="json">原始数据</button>
  </div>
  <div class="tabs-body">

    <div id="tab-summary" class="tab-panel active">
      <div id="summary-text" class="summary-content placeholder">等待任务完成后展示摘要。</div>
    </div>

    <div id="tab-llm" class="tab-panel">
      <div class="llm-stats">
        <div class="stat-box">
          <div class="stat-lbl">LLM 增强状态</div>
          <div id="llm-status"><span class="badge b-default">未判断</span></div>
          <div class="stat-hint" style="margin-top:6px">会员版专属</div>
        </div>
        <div class="stat-box">
          <div class="stat-lbl">已增强模块数</div>
          <div class="stat-big" id="llm-count">0</div>
          <div class="stat-hint">visibility · content · platform · summary</div>
        </div>
      </div>
      <div id="llm-notes" class="llm-notes-box">等待任务开始。</div>
    </div>

    <div id="tab-compare" class="tab-panel">
      <table class="cmp-table">
        <thead>
          <tr>
            <th>维度</th>
            <th>普通版</th>
            <th>会员版</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>分析方式</td>
            <td>规则判断</td>
            <td>规则 + OpenRouter 语义增强</td>
          </tr>
          <tr>
            <td>输出内容</td>
            <td>基础结构化结果</td>
            <td>含 visibility / content / platform / summary 语义增强</td>
          </tr>
          <tr>
            <td>LLM 调用</td>
            <td><span class="badge b-default">不调用</span></td>
            <td><span class="badge b-success">OpenRouter 统一接入</span></td>
          </tr>
          <tr>
            <td>判定依据</td>
            <td colspan="2">以响应中 <code>llm_enhanced=true</code> 字段为准</td>
          </tr>
          <tr>
            <td>当前选择</td>
            <td colspan="2"><strong id="current-mode-display">—</strong></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div id="tab-json" class="tab-panel">
      <div class="json-shell">
        <pre id="json-output" class="json-out">{}</pre>
      </div>
    </div>

  </div><!-- /tabs-body -->

  <!-- ═══ 打分维度说明 ═══ -->
  <hr class="section-divider" style="margin-top:36px" />
  <div style="margin-top:28px">
    <div class="section-hdr">
      <h2>打分维度与规则</h2>
      <span>各模块关键指标及权重，满分均为 100 分</span>
    </div>

    <div class="dim-grid">
      <!-- Visibility -->
      <div class="dim-card">
        <div class="dim-head">
          <span class="dim-name">👁 AI 可见性</span>
          <span class="dim-score">visibility</span>
        </div>
        <div class="dim-rows">
          <div class="dim-row"><span class="dim-row-label">AI 爬虫访问率</span><span class="dim-row-val">×0.35</span></div>
          <div class="dim-row"><span class="dim-row-label">可引用性得分</span><span class="dim-row-val">×0.35</span></div>
          <div class="dim-row"><span class="dim-row-label">llms.txt 存在</span><span class="dim-row-val">×0.15</span></div>
          <div class="dim-row"><span class="dim-row-label">品牌权威信号</span><span class="dim-row-val">×0.15</span></div>
          <div class="dim-row" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--border)">
            <span class="dim-row-label" style="color:var(--subtle);font-size:11px">llms.txt：有=100 / 无=20</span>
          </div>
        </div>
      </div>
      <!-- Technical -->
      <div class="dim-card">
        <div class="dim-head">
          <span class="dim-name">⚙️ 技术基础</span>
          <span class="dim-score">technical</span>
        </div>
        <div class="dim-rows">
          <div class="dim-row"><span class="dim-row-label">安全响应头</span><span class="dim-row-val">18 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">HTTPS 强制</span><span class="dim-row-val">10 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">SSR 信号</span><span class="dim-row-val">10 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">图片优化</span><span class="dim-row-val">10 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">Sitemap 存在</span><span class="dim-row-val">8 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">Meta/Canonical/OG…</span><span class="dim-row-val">其余</span></div>
        </div>
      </div>
      <!-- Content -->
      <div class="dim-card">
        <div class="dim-head">
          <span class="dim-name">📝 内容质量</span>
          <span class="dim-score">content</span>
        </div>
        <div class="dim-rows">
          <div class="dim-row"><span class="dim-row-label">文章页词数 ≥800</span><span class="dim-row-val">20 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">标题层级质量</span><span class="dim-row-val">15 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">服务页词数 ≥400</span><span class="dim-row-val">15 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">FAQ / 作者 / 日期</span><span class="dim-row-val">各 10 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">量化数据 / 先答后述</span><span class="dim-row-val">各 10 pts</span></div>
        </div>
      </div>
      <!-- Schema -->
      <div class="dim-card">
        <div class="dim-head">
          <span class="dim-name">🏷️ 结构化数据</span>
          <span class="dim-score">schema</span>
        </div>
        <div class="dim-rows">
          <div class="dim-row"><span class="dim-row-label">JSON-LD 存在</span><span class="dim-row-val">20 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">Organization</span><span class="dim-row-val">20 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">Article</span><span class="dim-row-val">15 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">LocalBusiness / FAQ</span><span class="dim-row-val">各 10 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">Service / WebSite</span><span class="dim-row-val">各 10 pts</span></div>
          <div class="dim-row"><span class="dim-row-label">sameAs 链接</span><span class="dim-row-val">5 pts</span></div>
        </div>
      </div>
      <!-- Platform -->
      <div class="dim-card">
        <div class="dim-head">
          <span class="dim-name">🌐 平台适配</span>
          <span class="dim-score">platform</span>
        </div>
        <div class="dim-rows">
          <div class="dim-row"><span class="dim-row-label">Google AI Overviews</span><span class="dim-row-val" style="font-size:10.5px">引用×0.35+Schema×0.35</span></div>
          <div class="dim-row"><span class="dim-row-label">ChatGPT Web Search</span><span class="dim-row-val" style="font-size:10.5px">爬虫×0.40+llms×0.25</span></div>
          <div class="dim-row"><span class="dim-row-label">Perplexity / Gemini</span><span class="dim-row-val" style="font-size:10.5px">引用+权威组合</span></div>
          <div class="dim-row"><span class="dim-row-label">Bing Copilot</span><span class="dim-row-val" style="font-size:10.5px">元数据+爬虫</span></div>
        </div>
      </div>
    </div>

    <!-- Score range legend -->
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
      <span style="font-size:12px;color:var(--muted);font-weight:500">分级标准：</span>
      <div class="score-table">
        <div class="score-cell"><span class="sc-range sc-critical">0–24</span><span class="sc-lbl">critical</span></div>
        <div class="score-cell"><span class="sc-range sc-poor">25–44</span><span class="sc-lbl">poor</span></div>
        <div class="score-cell"><span class="sc-range sc-fair">45–64</span><span class="sc-lbl">fair</span></div>
        <div class="score-cell"><span class="sc-range sc-good">65–84</span><span class="sc-lbl">good</span></div>
        <div class="score-cell"><span class="sc-range sc-strong">85–100</span><span class="sc-lbl">strong</span></div>
      </div>
    </div>
  </div>

  <!-- ═══ 业务落成说明 ═══ -->
  <hr class="section-divider" style="margin-top:32px" />
  <div style="margin-top:28px">
    <div class="section-hdr">
      <h2>计算维度业务落成</h2>
      <span>各维度数据来源与业务接入要点</span>
    </div>
    <div class="biz-grid">
      <div class="biz-card">
        <h4>👁 AI 可见性 · 数据来源</h4>
        <ul>
          <li><strong>爬虫访问</strong>：抓取 <code>robots.txt</code>，统计 GPTBot / PerplexityBot / Google-Extended 等主流 AI 爬虫的 Allow 比例</li>
          <li><strong>可引用性</strong>：解析首页 HTML，检测 meta description、OG 标签、标题层级、内容深度等启发式信号</li>
          <li><strong>llms.txt</strong>：请求 <code>/llms.txt</code>，200 即有效；无文件得 20 分基础分</li>
          <li><strong>品牌权威</strong>：检测 About 页、联系方式、社交 sameAs 链接等站内品牌信号</li>
        </ul>
      </div>
      <div class="biz-card">
        <h4>⚙️ 技术基础 · 数据来源</h4>
        <ul>
          <li><strong>HTTPS / SSR</strong>：检查最终跳转 URL 协议；通过 HTML 长度与词数比判断服务端渲染</li>
          <li><strong>安全响应头</strong>：检测 HSTS / CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy</li>
          <li><strong>图片优化</strong>：统计 <code>loading=lazy</code> 比例 + 显式 width/height 比例，各占 50 分</li>
          <li><strong>Sitemap</strong>：robots.txt 中的 Sitemap 指令 + 直接请求 <code>/sitemap.xml</code></li>
        </ul>
      </div>
      <div class="biz-card">
        <h4>📝 内容质量 · 数据来源</h4>
        <ul>
          <li><strong>多页面采样</strong>：Discovery 阶段自动发现 service / article / about / case_study 页面，逐页抓取分析</li>
          <li><strong>E-E-A-T 信号</strong>：正则检测作者署名、发布日期、数字/百分比（量化数据）</li>
          <li><strong>先答后述</strong>：检测正文前 200 字是否包含答案性内容</li>
          <li><strong>标题质量</strong>：评估 H1–H3 层级完整度、关键词分布与唯一性</li>
        </ul>
      </div>
      <div class="biz-card">
        <h4>🏷️ 结构化数据 · 数据来源</h4>
        <ul>
          <li><strong>多页抽取</strong>：首页 + key_pages（service / article / about）的所有 <code>&lt;script type="application/ld+json"&gt;</code></li>
          <li><strong>类型识别</strong>：提取 @type 字段，匹配 Organization / LocalBusiness / Article / FAQPage / Service / WebSite</li>
          <li><strong>sameAs</strong>：计数 Organization/LocalBusiness 下的 sameAs 数组条目</li>
        </ul>
      </div>
      <div class="biz-card">
        <h4>🌐 平台适配 · 计算逻辑</h4>
        <ul>
          <li><strong>复用上游结果</strong>：platform 模块不做额外爬取，直接复用 discovery、visibility、schema 的信号量</li>
          <li><strong>平台差异权重</strong>：Google AI Overviews 侧重 Schema+FAQ；ChatGPT 侧重爬虫准入+llms.txt；Perplexity 侧重引用性+权威</li>
          <li><strong>Gap 判定</strong>：各平台独立输出 <code>primary_gap</code> + <code>key_recommendations</code>（最多 3 条）</li>
        </ul>
      </div>
      <div class="biz-card">
        <h4>🤖 会员 AI 增强 · 机制说明</h4>
        <ul>
          <li><strong>触发条件</strong>：<code>mode=premium</code> + 有效 OpenRouter API Key</li>
          <li><strong>增强模块</strong>：visibility / content / platform / summary 四个模块支持 LLM 语义增强</li>
          <li><strong>回退保障</strong>：LLM 调用失败时自动降级为规则结果，<code>llm_enhanced=false</code></li>
          <li><strong>缓存策略</strong>：同域名结果缓存 7 天（按 URL 规范化后哈希），<code>force_refresh=true</code> 可强制刷新</li>
        </ul>
      </div>
    </div>
  </div>

  <!-- ═══ API 调用说明 ═══ -->
  <hr class="section-divider" style="margin-top:32px" />
  <div style="margin-top:28px;margin-bottom:48px">
    <div class="section-hdr">
      <h2>API 调用步骤</h2>
      <span>异步任务模式（推荐）及单模块直调两种方式</span>
    </div>
    <div class="api-steps">

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">1</div>
          <span class="api-step-title">创建审计任务</span>
        </div>
        <div class="api-step-body">
          <div class="api-endpoint"><span class="method m-post">POST</span>/api/v1/tasks/audit</div>
          <div class="api-desc">提交目标 URL，后台异步启动 discovery → visibility → technical → content → schema → platform → summary 流水线，立即返回 <code>task_id</code>。</div>
          <div class="api-params">
            <div class="param-row"><span class="param-key">url</span><span class="param-type">string</span><span class="param-req">必填</span><span class="param-desc">目标网站 URL（自动规范化）</span></div>
            <div class="param-row"><span class="param-key">mode</span><span class="param-type">string</span><span class="param-desc"><code>"standard"</code>（默认）或 <code>"premium"</code>（启用 LLM 增强）</span></div>
            <div class="param-row"><span class="param-key">force_refresh</span><span class="param-type">boolean</span><span class="param-desc">true 则跳过 7 天缓存强制重新审计</span></div>
            <div class="param-row"><span class="param-key">llm.provider</span><span class="param-type">string</span><span class="param-desc">premium 模式下固定 <code>"openrouter"</code></span></div>
            <div class="param-row"><span class="param-key">llm.model</span><span class="param-type">string</span><span class="param-desc">如 <code>"openai/gpt-4.1"</code>、<code>"anthropic/claude-sonnet-4.6"</code></span></div>
          </div>
          <div class="code-snippet"><pre>{
  "url": "https://example.com",
  "mode": "premium",
  "force_refresh": false,
  "llm": { "provider": "openrouter", "model": "openai/gpt-4.1" }
}</pre></div>
        </div>
      </div>

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">2</div>
          <span class="api-step-title">轮询任务状态</span>
        </div>
        <div class="api-step-body">
          <div class="api-endpoint"><span class="method m-get">GET</span>/api/v1/tasks/{task_id}</div>
          <div class="api-desc">每隔 1–2 秒轮询一次。<code>status</code> 为 <code>"completed"</code> 或 <code>"failed"</code> 时停止。<code>steps</code> 字段实时反映各模块状态（pending / running / completed / failed）。</div>
          <div class="api-params">
            <div class="param-row"><span class="param-key">status</span><span class="param-type">string</span><span class="param-desc">queued → running → completed | failed</span></div>
            <div class="param-row"><span class="param-key">progress_percent</span><span class="param-type">int</span><span class="param-desc">0–100，按完成步骤数计算</span></div>
            <div class="param-row"><span class="param-key">cached</span><span class="param-type">boolean</span><span class="param-desc">命中缓存时为 true，直接返回历史结果</span></div>
            <div class="param-row"><span class="param-key">result</span><span class="param-type">object</span><span class="param-desc">completed 后包含完整的 visibility / technical / content / schema / platform / summary</span></div>
          </div>
          <div class="code-snippet"><pre>// 响应结构示意
{
  "success": true,
  "data": {
    "task_id": "abc123",
    "status": "completed",          // queued | running | completed | failed
    "progress_percent": 100,
    "cached": false,
    "steps": { "discovery": { "status": "completed", "data": {...} }, ... },
    "result": {
      "visibility": { "score": 72, "status": "good", "llm_enhanced": true, ... },
      "technical":  { "score": 85, ... },
      "content":    { "score": 60, ... },
      "schema":     { "score": 45, ... },
      "platform":   { "google_ai_overviews": { "platform_score": 68 }, ... },
      "summary":    { "score": 70, "summary": "...", ... }
    }
  }
}</pre></div>
        </div>
      </div>

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">3</div>
          <span class="api-step-title">导出 HTML 报告（可选）</span>
        </div>
        <div class="api-step-body">
          <div class="api-endpoint"><span class="method m-get">GET</span>/api/v1/tasks/{task_id}/report</div>
          <div class="api-desc">任务完成后可拉取完整 HTML 报告，直接在浏览器渲染或保存为文件。仅在 <code>status=completed</code> 时有效。</div>
        </div>
      </div>

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">4</div>
          <span class="api-step-title">单模块直调（高级用法）</span>
        </div>
        <div class="api-step-body">
          <div class="api-desc">无需走任务队列，直接同步调用单个审计模块，适合实时集成或调试。</div>
          <div class="api-params">
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/visibility</code><span class="param-desc" style="margin-left:4px">AI 可见性模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/technical</code><span class="param-desc" style="margin-left:4px">技术基础模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/content</code><span class="param-desc" style="margin-left:4px">内容质量模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/schema</code><span class="param-desc" style="margin-left:4px">结构化数据模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/platform</code><span class="param-desc" style="margin-left:4px">平台适配模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/full</code><span class="param-desc" style="margin-left:4px">全量同步审计（含 summary，无缓存）</span></div>
          </div>
          <div class="code-snippet"><pre>// 单模块请求体（Body 字段相同）
{ "url": "https://example.com", "mode": "standard" }

// premium 模式下可附加 LLM 配置
{ "url": "https://example.com", "mode": "premium",
  "llm": { "provider": "openrouter", "model": "openai/gpt-4.1" } }</pre></div>
        </div>
      </div>

    </div><!-- /api-steps -->
  </div>

</div><!-- /wrap -->

<!-- Toast -->
<div id="toast" class="toast">
  <span class="toast-icon" id="toast-icon"></span>
  <span id="toast-msg"></span>
  <button class="toast-close" id="toast-close">✕</button>
</div>

<script>
  const $ = id => document.getElementById(id);

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

  /* ── Step config ── */
  const STEP_ORDER = ['discovery', 'visibility', 'technical', 'content', 'schema', 'platform', 'summary'];
  const STEP_ICON  = { discovery:'🔍', visibility:'👁', technical:'⚙️', content:'📝', schema:'🏷️', platform:'🌐', summary:'📊' };

  /* ── State ── */
  let pollTimer = null;
  let currentTaskId = null;
  let currentTaskStatus = 'idle';

  /* ── Render timeline ── */
  function renderTimeline(steps) {
    const el = $('timeline');
    el.innerHTML = '';
    STEP_ORDER.forEach((name, i) => {
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
    currentTaskId     = task.task_id || null;
    currentTaskStatus = task.status  || 'idle';
    const shortId = task.task_id ? task.task_id.slice(0, 10) + '…' : '—';
    $('task-id').textContent     = shortId;
    $('current-step').textContent = task.current_step || '—';
    const pct = task.progress_percent || 0;
    $('progress').textContent   = `${pct}%`;
    $('prog-fill').style.width  = `${pct}%`;
    $('cached-flag').textContent = task.cached ? '是 ✓' : '否';
    $('mode-display').textContent = task.mode === 'premium' ? '会员版' : (task.mode ? '普通版' : '—');
    $('current-mode-display').textContent = task.mode === 'premium'
      ? '会员版（规则 + OpenRouter）'
      : (task.mode ? '普通版（规则）' : '—');
    setStatusBadge(task.status || 'idle');
    $('export-btn').disabled = task.status !== 'completed';
  }

  /* ── LLM status panel ── */
  function renderLlmStatus(task) {
    const result  = task.result || {};
    const modules = ['visibility', 'content', 'platform', 'summary'];
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
      notesEl.textContent = '会员版已提交，等待 visibility / content / platform / summary 返回增强结果。';
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

  /* ── Start audit ── */
  async function startAudit() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }

    const btn = $('submit-btn');
    btn.disabled = true;
    btn.innerHTML = '<div class="spin"></div> 提交中…';

    const summaryEl = $('summary-text');
    summaryEl.textContent = '任务已创建，等待后台返回各阶段结果……';
    summaryEl.classList.add('placeholder');
    $('llm-notes').textContent = '等待会员增强状态。';
    $('json-output').textContent = '{}';
    $('export-btn').disabled = true;
    renderTimeline({});

    const mode = $('mode').value;
    const body = {
      url: $('url').value.trim(),
      mode,
      force_refresh: $('force').checked
    };
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
      $('json-output').textContent = JSON.stringify(task.result || task, null, 2);

      if (task.status === 'completed') {
        resetBtn();
        if (task.result?.summary?.summary) {
          summaryEl.textContent = task.result.summary.summary;
          summaryEl.classList.remove('placeholder');
        }
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

  $('export-btn').addEventListener('click', () => {
    if (!currentTaskId || currentTaskStatus !== 'completed') {
      showToast('任务尚未完成，暂时无法导出报告。');
      return;
    }
    window.open(`/api/v1/tasks/${currentTaskId}/report`, '_blank');
  });

  $('mode').addEventListener('change', () => {
    const isPremium = $('mode').value === 'premium';
    $('model').disabled = !isPremium;
    $('model').style.opacity = isPremium ? '1' : '0.45';
  });

  /* ── Init ── */
  renderTimeline({});
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def demo_page() -> HTMLResponse:
    return HTMLResponse(HTML)
