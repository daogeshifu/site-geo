from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

# Demo 路由：提供内置的交互式 GEO 审计控制台页面（单页 HTML 应用）
# 挂载在根路径 /，供开发者和演示场景直接在浏览器中使用
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
    input[type="text"], input[type="number"], select {
      width: 100%; height: 40px;
      padding: 0 12px;
      border: 1px solid var(--border); border-radius: 9px;
      font-size: 13.5px; color: var(--text);
      background: var(--surface);
      transition: border-color 0.15s, box-shadow 0.15s;
      -webkit-appearance: none; appearance: none;
    }
    input[type="text"].has-icon { padding-left: 30px; }
    input[type="text"]:focus, input[type="number"]:focus, select:focus {
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
    .meta-sub-row {
      margin-top: 8px;
      padding-top: 8px;
      border-top: 1px dashed var(--border);
      display: flex; align-items: center; justify-content: space-between; gap: 10px;
    }
    .meta-sub-lbl {
      font-size: 10.5px; font-weight: 600;
      color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em;
    }
    .meta-sub-val { font-size: 12.5px; font-weight: 700; color: var(--text); }

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

    /* ── Report tab ── */
    .placeholder { color: var(--muted); font-style: italic; }
    .report-empty {
      min-height: 96px;
      display: flex; align-items: center; justify-content: center;
      text-align: center; padding: 18px;
      border: 1px dashed var(--border); border-radius: 12px;
      background: linear-gradient(180deg, #fbfcfd 0%, #f5f7f8 100%);
      font-size: 13.5px; line-height: 1.8;
    }
    .report-shell { display: flex; flex-direction: column; gap: 16px; }
    .report-hero {
      position: relative; overflow: hidden;
      border: 1px solid #0f172a;
      border-radius: 16px;
      background:
        radial-gradient(circle at top right, rgba(52,211,153,0.22), transparent 34%),
        radial-gradient(circle at bottom left, rgba(16,185,129,0.18), transparent 30%),
        linear-gradient(135deg, #0f172a 0%, #111827 55%, #172554 100%);
      color: #f8fafc;
      padding: 22px;
      display: grid; grid-template-columns: 220px 1fr; gap: 20px;
    }
    .report-score-box {
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 16px;
      background: rgba(255,255,255,0.05);
      backdrop-filter: blur(6px);
      padding: 18px;
      display: flex; flex-direction: column; justify-content: space-between;
      min-height: 198px;
    }
    .report-score-label {
      font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
      text-transform: uppercase; color: rgba(226,232,240,0.72);
    }
    .report-score-value { font-size: 58px; font-weight: 800; line-height: 1; margin: 10px 0 6px; }
    .report-score-sub { font-size: 13px; color: rgba(226,232,240,0.78); }
    .report-hero-main { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
    .report-kicker {
      display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap;
      font-size: 12px; color: rgba(226,232,240,0.86);
    }
    .report-kicker .dot {
      width: 4px; height: 4px; border-radius: 50%;
      background: rgba(226,232,240,0.45);
    }
    .report-hero h3 { font-size: 22px; line-height: 1.3; font-weight: 700; }
    .report-summary {
      font-size: 13.5px; line-height: 1.8; color: rgba(226,232,240,0.88);
      max-width: 1000px;
    }
    .report-badges {
      display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    }
    .r-badge {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 5px 10px; border-radius: 999px; font-size: 11.5px; font-weight: 700;
      border: 1px solid rgba(255,255,255,0.1);
      background: rgba(255,255,255,0.06); color: #f8fafc;
    }
    .r-badge.success { background: rgba(16,185,129,0.14); color: #6ee7b7; }
    .r-badge.warn { background: rgba(245,158,11,0.14); color: #fbbf24; }
    .r-badge.danger { background: rgba(239,68,68,0.14); color: #fca5a5; }
    .report-meta-grid {
      display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px;
    }
    .report-meta-item {
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 12px;
      background: rgba(255,255,255,0.05);
      padding: 12px 13px;
    }
    .report-meta-item .lbl {
      font-size: 10.5px; text-transform: uppercase; letter-spacing: 0.06em;
      color: rgba(226,232,240,0.62); font-weight: 700; margin-bottom: 6px;
    }
    .report-meta-item .val {
      font-size: 13px; line-height: 1.45; color: #f8fafc; font-weight: 600;
      word-break: break-word;
    }
    .report-section {
      border: 1px solid var(--border); border-radius: 14px;
      background: var(--surface);
      box-shadow: 0 1px 4px rgba(0,0,0,0.04);
      overflow: hidden;
    }
    .report-section-hdr {
      display: flex; align-items: baseline; justify-content: space-between; gap: 10px;
      padding: 14px 18px; border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, #fbfcfd 0%, #f8fafc 100%);
    }
    .report-section-hdr h4 { font-size: 14px; font-weight: 700; }
    .report-section-hdr span { font-size: 12px; color: var(--muted); }
    .report-section-body { padding: 18px; }
    .report-dim-grid {
      display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;
    }
    .report-dim-card {
      border: 1px solid var(--border); border-radius: 13px;
      background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
      padding: 14px;
    }
    .report-dim-head {
      display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px;
    }
    .report-dim-name { font-size: 13px; font-weight: 700; }
    .report-dim-pill {
      font-size: 11px; font-weight: 700; color: var(--accent);
      background: var(--accent-dim); border-radius: 999px; padding: 3px 8px;
      white-space: nowrap;
    }
    .report-dim-scoreline {
      display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
      margin-bottom: 8px;
    }
    .report-dim-scoreline .score { font-size: 30px; font-weight: 800; line-height: 1; }
    .report-dim-scoreline .status { font-size: 11.5px; color: var(--muted); font-weight: 700; text-transform: uppercase; }
    .report-dim-kpis {
      display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;
    }
    .report-dim-kpi {
      border: 1px solid var(--border); border-radius: 10px;
      background: #fff; padding: 9px 10px;
    }
    .report-dim-kpi .lbl { font-size: 10.5px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; font-weight: 700; margin-bottom: 4px; }
    .report-dim-kpi .val { font-size: 13px; font-weight: 700; }
    .report-dim-note { font-size: 12px; color: var(--muted); line-height: 1.65; }
    .report-grid-2 {
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px;
    }
    .report-list {
      display: flex; flex-direction: column; gap: 9px;
    }
    .report-list-item {
      border: 1px solid var(--border); border-radius: 11px;
      padding: 11px 12px; background: #fff;
      font-size: 12.5px; line-height: 1.65;
      color:black;
    }
    .report-list-item strong { color: var(--text); }
    .report-action-list {
      display: flex; flex-direction: column; gap: 10px;
    }
    .report-action {
      display: grid; grid-template-columns: 86px 1fr 84px; gap: 12px;
      align-items: start;
      border: 1px solid var(--border); border-radius: 12px;
      background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
      padding: 12px;
    }
    .report-action-priority {
      border-radius: 10px; padding: 8px 10px; text-align: center;
      font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.06em;
      background: var(--bg); color: var(--muted);
    }
    .report-action-priority.high, .report-action-priority.critical { background: rgba(239,68,68,0.1); color: #dc2626; }
    .report-action-priority.medium { background: rgba(245,158,11,0.12); color: #d97706; }
    .report-action-priority.low { background: rgba(16,185,129,0.1); color: #059669; }
    .report-action-main h5 { font-size: 13px; font-weight: 700; margin-bottom: 4px; }
    .report-action-main p { font-size: 12px; color: var(--muted); line-height: 1.65; }
    .report-action-impact {
      font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;
      color: var(--muted); text-align: right;
    }
    .report-action-impact span {
      display: inline-block; margin-top: 6px; padding: 5px 9px; border-radius: 999px;
      background: var(--accent-dim); color: var(--accent);
    }
    .report-platform-grid {
      display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px;
    }
    .platform-card {
      border: 1px solid var(--border); border-radius: 13px;
      padding: 12px; background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
    }
    .platform-card .hd {
      display: flex; align-items: center; justify-content: space-between; gap: 8px;
      margin-bottom: 8px;
    }
    .platform-card .name { font-size: 12px; font-weight: 700; line-height: 1.4; }
    .platform-card .score { font-size: 20px; font-weight: 800; }
    .platform-card .gap { font-size: 11.5px; color: var(--muted); line-height: 1.55; min-height: 52px; }
    .platform-card .reco { margin-top: 8px; font-size: 11.5px; color: var(--text); line-height: 1.55; }
    .report-evidence-grid {
      display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px;
    }
    .evidence-card {
      border: 1px solid var(--border); border-radius: 13px;
      background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
      padding: 14px;
    }
    .evidence-card h5 { font-size: 13px; font-weight: 700; margin-bottom: 10px; }
    .kv-list { display: flex; flex-direction: column; gap: 8px; }
    .kv-row {
      display: flex; align-items: baseline; justify-content: space-between; gap: 12px;
      border-bottom: 1px dashed var(--border); padding-bottom: 8px;
      font-size: 12px;
    }
    .kv-row:last-child { border-bottom: none; padding-bottom: 0; }
    .kv-key { color: var(--muted); flex: 1; min-width: 0; }
    .kv-val { color: var(--text); font-weight: 600; text-align: right; flex: 1; min-width: 0; word-break: break-word; }
    .page-samples { display: flex; flex-direction: column; gap: 9px; }
    .page-sample {
      border: 1px solid var(--border); border-radius: 10px;
      padding: 10px 11px; background: #fff;
    }
    .page-sample .top {
      display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px;
    }
    .page-sample .name { font-size: 12px; font-weight: 700; }
    .page-sample .meta { font-size: 11px; color: var(--muted); line-height: 1.6; }
    .report-note-box {
      border: 1px solid var(--border); border-radius: 13px;
      background: linear-gradient(180deg, #ffffff 0%, #fafbfc 100%);
      padding: 14px 15px;
      font-size: 12.5px; line-height: 1.8; color: var(--muted);
      white-space: pre-wrap;
    }

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
    .json-toolbar {
      display: flex; align-items: center; justify-content: space-between;
      gap: 12px; margin-bottom: 12px;
    }
    .json-title {
      font-size: 11.5px; font-weight: 700; letter-spacing: 0.06em;
      text-transform: uppercase; color: rgba(241,245,249,0.72);
    }
    .btn-json {
      height: 32px; padding: 0 12px; border-radius: 8px;
      border: 1px solid rgba(255,255,255,0.12);
      background: rgba(255,255,255,0.06); color: #f8fafc;
      font-size: 12px; font-weight: 600; cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
    }
    .btn-json:hover { background: rgba(255,255,255,0.11); border-color: rgba(255,255,255,0.2); }
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
      grid-template-columns: repeat(3, 1fr);
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
      .report-hero { grid-template-columns: 1fr; }
      .report-meta-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .report-dim-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .report-grid-2 { grid-template-columns: 1fr; }
      .report-platform-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .report-evidence-grid { grid-template-columns: 1fr; }
      .dim-grid { grid-template-columns: repeat(2, 1fr); }
      .biz-grid { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 640px) {
      .report-meta-grid { grid-template-columns: 1fr; }
      .report-dim-grid { grid-template-columns: 1fr; }
      .report-platform-grid { grid-template-columns: 1fr; }
      .report-action { grid-template-columns: 1fr; }
      .report-action-impact { text-align: left; }
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
  <span class="hdr-pill">v3</span>
</header>

<div class="wrap">
  <div class="page-title">
    <h1>网站 GEO 审计</h1>
    <p>提交目标 URL 创建后台任务，支持可选 full audit、非首页偏差提示与逐页诊断结果。</p>
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
                <option value="deepseek/deepseek-v3.2">deepseek / deepseek-v3.2</option>
                <option value="openai/gpt-4.1">openai / gpt-4.1</option>
                <option value="anthropic/claude-sonnet-4.6">anthropic / claude-sonnet-4.6</option>
              </select>
            </div>
          </div>
          <div class="field">
            <label>反馈语言</label>
            <select id="feedback-lang">
              <option value="en">English</option>
              <option value="zh">简体中文</option>
            </select>
          </div>
          <div class="field">
            <label for="force" class="toggle-wrap" style="margin-bottom:0;border:none;padding-left:0;display:flex;align-items:center">
              <input id="force" type="checkbox" />
              <span class="toggle-lbl">强制刷新缓存</span>
              <span class="toggle-hint">忽略一周内的历史结果</span>
            </label>
          </div>
          <div class="row-2">
            <div class="field">
              <label for="full-audit" class="toggle-wrap" style="margin-bottom:0;border:none;padding-left:0;display:flex;align-items:center">
                <input id="full-audit" type="checkbox" />
                <span class="toggle-lbl">启用 Full Audit</span>
                <span class="toggle-hint">返回逐页诊断</span>
              </label>
            </div>
            <div class="field">
              <label>最大页面数</label>
              <select id="max-pages" disabled>
                <option value="12">12 页</option>
                <option value="20">20 页</option>
                <option value="30">30 页</option>
                <option value="50">50 页</option>
              </select>
            </div>
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
            <div class="meta-sub-row">
              <span class="meta-sub-lbl">LLM 模型生效</span>
              <span class="meta-sub-val" id="llm-model-used-flag">否</span>
            </div>
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
    <button class="tab-btn active" data-tab="summary">报告</button>
    <button class="tab-btn" data-tab="llm">AI 增强</button>
    <button class="tab-btn" data-tab="compare">版本对比</button>
    <button class="tab-btn" data-tab="json">原始数据</button>
  </div>
  <div class="tabs-body">

    <div id="tab-summary" class="tab-panel active">
      <div id="summary-text" class="report-empty placeholder">等待任务完成后生成完整报告。报告将展示综合评分、6 个汇总维度、6 平台适配、可选 Observation Layer、非首页提示、full audit 逐页诊断、关键问题、行动计划与 snapshot 证据。</div>
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
        <div class="json-toolbar">
          <span class="json-title">Raw JSON</span>
          <button id="copy-json-btn" type="button" class="btn-json">复制原始数据</button>
        </div>
        <pre id="json-output" class="json-out">{}</pre>
      </div>
    </div>

  </div><!-- /tabs-body -->

  <!-- ═══ 打分维度说明 ═══ -->

<hr class="section-divider" style="margin-top:36px" />
<div style="margin-top:28px">
  <div class="section-hdr">
    <h2>打分维度与规则</h2>
    <span>按 6 个汇总层展示关键指标、内部公式与综合分权重，单维度原始分满分均为 100 分</span>
  </div>

  <div class="dim-grid">
    <div class="dim-card">
      <div class="dim-head"><span class="dim-name">AI 可见性</span><span class="dim-score">25%</span></div>
      <div class="dim-rows">
        <div class="dim-row"><span class="dim-row-label">AI crawler 放行率</span><span class="dim-row-val">×0.32</span></div>
        <div class="dim-row"><span class="dim-row-label">snapshot citability</span><span class="dim-row-val">×0.40</span></div>
        <div class="dim-row"><span class="dim-row-label">llms.txt 有效性</span><span class="dim-row-val">×0.12</span></div>
        <div class="dim-row"><span class="dim-row-label">基础实体存在</span><span class="dim-row-val">×0.16</span></div>
        <div class="dim-row" style="margin-top:4px;padding-top:4px;border-top:1px solid var(--border)"><span class="dim-row-label" style="color:var(--subtle);font-size:11px">citability 基于 snapshot 中 homepage 与最佳页面的 answer-first、信息密度、数据点、分块结构和 FAQ / 作者 / 日期信号综合评估</span></div>
      </div>
    </div>
    <div class="dim-card">
      <div class="dim-head"><span class="dim-name">品牌权威</span><span class="dim-score">20%</span></div>
      <div class="dim-rows">
        <div class="dim-row"><span class="dim-row-label">外链质量</span><span class="dim-row-val">25%</span></div>
        <div class="dim-row"><span class="dim-row-label">品牌提及覆盖</span><span class="dim-row-val">25%</span></div>
        <div class="dim-row"><span class="dim-row-label">sameAs / Entity 一致性</span><span class="dim-row-val">25%</span></div>
        <div class="dim-row"><span class="dim-row-label">企业信息完整度</span><span class="dim-row-val">25%</span></div>
        <div class="dim-row"><span class="dim-row-label">站外数据源</span><span class="dim-row-val">Semrush Backlinks Overview</span></div>
        <div class="dim-row"><span class="dim-row-label">结构预留</span><span class="dim-row-val">已抽离 BrandAuthorityService 边界</span></div>
      </div>
    </div>
    <div class="dim-card">
      <div class="dim-head"><span class="dim-name">内容与 E-E-A-T</span><span class="dim-score">20%</span></div>
      <div class="dim-rows">
        <div class="dim-row"><span class="dim-row-label">汇总公式</span><span class="dim-row-val">5 个子分均值</span></div>
        <div class="dim-row"><span class="dim-row-label">content_score</span><span class="dim-row-val">字数 / FAQ / 作者 / 日期 / 数据 / 标题 / answer-first</span></div>
        <div class="dim-row"><span class="dim-row-label">experience</span><span class="dim-row-val">案例 / 量化结果 / 服务页深度 / About</span></div>
        <div class="dim-row"><span class="dim-row-label">expertise</span><span class="dim-row-val">服务页深度 / 文章深度 / answer-first / heading quality</span></div>
        <div class="dim-row"><span class="dim-row-label">authority / trust</span><span class="dim-row-val">作者 / 资质 / sameAs / contact / 日期</span></div>
        <div class="dim-row"><span class="dim-row-label">页面来源</span><span class="dim-row-val">page_profiles 中的 service / article / about / case_study</span></div>
      </div>
    </div>
    <div class="dim-card">
      <div class="dim-head"><span class="dim-name">技术基础</span><span class="dim-score">15%</span></div>
      <div class="dim-rows">
        <div class="dim-row"><span class="dim-row-label">安全响应头</span><span class="dim-row-val">16 pts</span></div>
        <div class="dim-row"><span class="dim-row-label">HTTPS / SSR</span><span class="dim-row-val">8 / 10</span></div>
        <div class="dim-row"><span class="dim-row-label">Meta / Canonical</span><span class="dim-row-val">5 / 5</span></div>
        <div class="dim-row"><span class="dim-row-label">Sitemap / robots 指令</span><span class="dim-row-val">8 / 4</span></div>
        <div class="dim-row"><span class="dim-row-label">性能 / 渲染阻塞</span><span class="dim-row-val">8 / 8</span></div>
        <div class="dim-row"><span class="dim-row-label">图片 / OG / Twitter / hreflang</span><span class="dim-row-val">8 / 5 / 3 / 4</span></div>
      </div>
    </div>
    <div class="dim-card">
      <div class="dim-head"><span class="dim-name">结构化数据</span><span class="dim-score">10%</span></div>
      <div class="dim-rows">
        <div class="dim-row"><span class="dim-row-label">JSON-LD / Organization</span><span class="dim-row-val">12 / 14</span></div>
        <div class="dim-row"><span class="dim-row-label">WebSite / Service / Article</span><span class="dim-row-val">10 / 10 / 10</span></div>
        <div class="dim-row"><span class="dim-row-label">FAQPage / Product / DefinedTerm</span><span class="dim-row-val">8 / 10 / 8</span></div>
        <div class="dim-row"><span class="dim-row-label">sameAs</span><span class="dim-row-val">8 pts</span></div>
        <div class="dim-row"><span class="dim-row-label">稳定 @id</span><span class="dim-row-val">5 pts</span></div>
        <div class="dim-row"><span class="dim-row-label">关系丰富度</span><span class="dim-row-val">5 pts</span></div>
      </div>
    </div>
    <div class="dim-card">
      <div class="dim-head"><span class="dim-name">平台适配</span><span class="dim-score">10%</span></div>
      <div class="dim-rows">
        <div class="dim-row"><span class="dim-row-label">汇总方式</span><span class="dim-row-val">战略权重加权</span></div>
        <div class="dim-row"><span class="dim-row-label">ChatGPT</span><span class="dim-row-val" style="font-size:10.5px">22% · crawler + llms + citability + brand</span></div>
        <div class="dim-row"><span class="dim-row-label">Google AI Mode</span><span class="dim-row-val" style="font-size:10.5px">18% · topic breadth + entity graph + schema</span></div>
        <div class="dim-row"><span class="dim-row-label">Google AI Overviews</span><span class="dim-row-val" style="font-size:10.5px">18% · citability + schema + FAQ + metadata</span></div>
        <div class="dim-row"><span class="dim-row-label">Perplexity</span><span class="dim-row-val" style="font-size:10.5px">16% · cited evidence + brand + schema</span></div>
        <div class="dim-row"><span class="dim-row-label">Gemini / Grok</span><span class="dim-row-val" style="font-size:10.5px">13% / 13% · authority / social amplification</span></div>
      </div>
    </div>
  </div>

  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
    <span style="font-size:12px;color:var(--muted);font-weight:500">分级标准：</span>
    <div class="score-table">
      <div class="score-cell"><span class="sc-range sc-critical">0-24</span><span class="sc-lbl">critical</span></div>
      <div class="score-cell"><span class="sc-range sc-poor">25-44</span><span class="sc-lbl">poor</span></div>
      <div class="score-cell"><span class="sc-range sc-fair">45-64</span><span class="sc-lbl">fair</span></div>
      <div class="score-cell"><span class="sc-range sc-good">65-84</span><span class="sc-lbl">good</span></div>
      <div class="score-cell"><span class="sc-range sc-strong">85-100</span><span class="sc-lbl">strong</span></div>
    </div>
  </div>
</div>

<hr class="section-divider" style="margin-top:32px" />
<div style="margin-top:28px">
  <div class="section-hdr">
    <h2>汇总层维度业务落成</h2>
    <span>按 6 个汇总维度展示数据来源、权重比例、计算公式与接入要点</span>
  </div>
  <div class="biz-grid">
    <div class="biz-card"><h4>AI 可见性 · 25%</h4><ul><li><strong>汇总取值</strong>：直接取 <code>visibility.ai_visibility_score</code>，再按 <code>×0.25</code> 计入综合分</li><li><strong>计算公式</strong>：<code>0.32 × AI crawler 放行率 + 0.40 × snapshot citability + 0.12 × llms.txt 有效性 + 0.16 × 基础实体存在</code></li><li><strong>数据来源</strong>：抓取 <code>robots.txt</code>、请求 <code>/llms.txt</code>、构建 snapshot 页面画像，并复用 homepage / about / service / article / case_study 的实体信号</li><li><strong>细项规则</strong>：citability 综合 answer-first、信息密度、数据点、分块结构与 FAQ / 作者 / 日期信号，输出 <code>homepage_citability</code>、<code>best_page_citability</code> 和 <code>citation_probability</code></li></ul></div>
    <div class="biz-card"><h4>品牌权威 · 20%</h4><ul><li><strong>汇总取值</strong>：直接取 <code>visibility.brand_authority_score</code>，再按 <code>×0.20</code> 计入综合分</li><li><strong>计算公式</strong>：<code>0.25 × 外链质量 + 0.25 × 品牌提及覆盖 + 0.25 × sameAs / Entity 一致性 + 0.25 × 企业信息完整度</code></li><li><strong>数据来源</strong>：站内品牌信号 + Schema sameAs + sitemap / canonical 一致性 + Semrush Backlinks Overview</li><li><strong>结构预留</strong>：当前仍由 <code>visibility</code> 产出品牌总分，但代码层已预留 <code>BrandAuthorityService</code> 边界，方便后续独立服务化</li></ul></div>
    <div class="biz-card"><h4>内容与 E-E-A-T · 20%</h4><ul><li><strong>汇总取值</strong>：<code>(content_score + experience + expertise + authoritativeness + trustworthiness) / 5</code> 后，再按 <code>×0.20</code> 计入综合分</li><li><strong>内容总分</strong>：服务页深度、文章页深度、FAQ、作者、日期、量化数据、标题质量、answer-first、信息密度、分块结构共同构成</li><li><strong>E-E-A-T 细项</strong>：Experience 看案例与量化结果；Expertise 看服务页/文章深度与结构；Authority 看作者、资质与 sameAs；Trust 看联系信息与日期</li><li><strong>数据来源</strong>：优先复用 <code>discovery.page_profiles</code>，不再为了内容审计重复抓取这些关键页面</li></ul></div>
    <div class="biz-card"><h4>技术基础 · 15%</h4><ul><li><strong>汇总取值</strong>：直接取 <code>technical.technical_score</code>，再按 <code>×0.15</code> 计入综合分</li><li><strong>计算公式</strong>：<code>HTTPS8 + SSR10 + Meta5 + Canonical5 + lang4 + viewport4 + Sitemap8 + robots 指令4 + 性能8 + 渲染阻塞8 + 安全头16 + 图片8 + OG5 + Twitter3 + hreflang4</code></li><li><strong>数据来源</strong>：最终 URL、首页 HTML、响应头、<code>robots.txt</code>、<code>sitemap.xml</code></li><li><strong>细项说明</strong>：<code>response_time_ms</code> 已纳入正式性能评分；安全头为 5 项等比计分；图片优化由 lazyload 与显式尺寸比例组成</li></ul></div>
    <div class="biz-card"><h4>结构化数据 · 10%</h4><ul><li><strong>汇总取值</strong>：直接取 <code>schema.structured_data_score</code>，再按 <code>×0.10</code> 计入综合分</li><li><strong>计算公式</strong>：<code>JSON-LD + Organization + WebSite + Service + Article + FAQPage + Product + DefinedTerm + sameAs + @id + relation richness</code></li><li><strong>数据来源</strong>：优先复用 snapshot 中各页面的 <code>json_ld_blocks</code>，统一汇总 <code>@type</code>、<code>sameAs</code>、稳定 <code>@id</code> 与实体关系信号</li><li><strong>接入要点</strong>：schema 既参与综合分，也被平台适配模块复用，尤其影响 Google AI Mode、AI Overviews 与 Gemini</li></ul></div>
    <div class="biz-card"><h4>平台适配 · 10%</h4><ul><li><strong>汇总取值</strong>：直接取 <code>platform.platform_optimization_score</code>，按平台战略权重汇总后再按 <code>×0.10</code> 计入综合分</li><li><strong>平台权重</strong>：ChatGPT 22%，Google AI Mode 18%，Google AI Overviews 18%，Perplexity 16%，Gemini 13%，Grok 13%</li><li><strong>数据来源</strong>：不额外抓取，直接复用 discovery snapshot、visibility、schema 与 metadata 结果</li><li><strong>输出结果</strong>：分别产出 <code>chatgpt / google_ai_mode / google_ai_overviews / perplexity / gemini / grok</code> 的分数、优化焦点、主缺口与建议</li></ul></div>
  </div>
  <div class="biz-card" style="margin-top:10px"><h4>发现层与复用机制</h4><ul><li><strong>发现层升级</strong>：当前 discovery 已升级为 <code>snapshot-v3</code>，默认抓取 homepage、about、service、article、case_study；full audit 时继续扩展到更多内部页</li><li><strong>抓取作用域</strong>：按“精确 host + 语言路径前缀”限制范围；例如 <code>www.ecoflow.com/de/</code> 只抓 <code>/de/</code>，不会抓 <code>de.ecoflow.com</code> 或 <code>/fr/</code></li><li><strong>统一画像</strong>：每个页面都输出 title、meta、canonical、lang、headings、word_count、FAQ / 作者 / 日期、JSON-LD 摘要、entity signals 等统一 profile</li><li><strong>复用机制</strong>：<code>audit_full</code> 支持直接传入已有 <code>discovery</code>，存在时复用，不再重复执行 discover</li><li><strong>提示机制</strong>：当输入 URL 不是首页或语言首页时，结果中会增加“非首页，数据可能有偏差”的提示，但不会强制改写输入页</li></ul></div>
  <div class="biz-card" style="margin-top:10px"><h4>Observation Layer · 不计分</h4><ul><li><strong>定位</strong>：可选上传 GA4、日志或人工引用观测，用于展示实际观测结果，不属于 6 个计分维度</li><li><strong>默认行为</strong>：大部分用户只输入 <code>url</code> 即可；未上传 observation 时仍可完成完整审计</li><li><strong>展示内容</strong>：可呈现 AI sessions、来源平台拆分、citation observations 与 measurement maturity</li><li><strong>评分规则</strong>：无论是否上传，<code>composite_geo_score</code> 都不会被 observation 改写</li></ul></div>
  <div class="biz-card" style="margin-top:10px"><h4>会员 AI 增强 · 机制说明</h4><ul><li><strong>单独展示原因</strong>：该部分不属于 6 个汇总维度之一，而是 <code>premium</code> 模式下对规则结果的语义增强与总结补充</li><li><strong>触发条件</strong>：<code>mode=premium</code> + 有效 OpenRouter API Key</li><li><strong>增强范围</strong>：当前覆盖 <code>visibility / content / platform / summary</code> 四个模块；technical 与 schema 仍保持规则制以保证确定性</li><li><strong>回退保障</strong>：LLM 调用失败时自动降级为规则结果，<code>llm_enhanced=false</code>；同域名结果默认缓存 7 天，<code>force_refresh=true</code> 可强制刷新</li></ul></div>
</div>

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
          <div class="api-desc">提交目标 URL，后台异步启动 discovery → visibility → technical → content → schema → platform → observation → summary 流水线；启用 <code>full_audit=true</code> 时会追加逐页诊断结果，且抓取严格限制在当前 URL 的 host 与语言作用域内。</div>
          <div class="api-params">
            <div class="param-row"><span class="param-key">url</span><span class="param-type">string</span><span class="param-req">必填</span><span class="param-desc">目标网站 URL（自动规范化）</span></div>
            <div class="param-row"><span class="param-key">mode</span><span class="param-type">string</span><span class="param-desc"><code>"standard"</code>（默认）或 <code>"premium"</code>（启用 LLM 增强）</span></div>
            <div class="param-row"><span class="param-key">force_refresh</span><span class="param-type">boolean</span><span class="param-desc">true 则跳过 7 天缓存强制重新审计</span></div>
            <div class="param-row"><span class="param-key">feedback_lang</span><span class="param-type">string</span><span class="param-desc"><code>"en"</code>（默认）或 <code>"zh"</code>；选择 <code>zh</code> 时，JSON key 保持英文，问题、建议、摘要、维度展示名和大部分用户可读 value 尽量返回中文</span></div>
            <div class="param-row"><span class="param-key">full_audit</span><span class="param-type">boolean</span><span class="param-desc">可选，启用后扩展抓取更多内部页并返回 <code>page_diagnostics</code></span></div>
            <div class="param-row"><span class="param-key">max_pages</span><span class="param-type">int</span><span class="param-desc">仅 full audit 生效，范围 5-50，默认 12</span></div>
            <div class="param-row"><span class="param-key">observation</span><span class="param-type">object</span><span class="param-desc">可选观测层输入，支持 GA4 / 来源拆分 / 人工引用观测；仅展示，不计分</span></div>
            <div class="param-row"><span class="param-key">llm.provider</span><span class="param-type">string</span><span class="param-desc">premium 模式下固定 <code>"openrouter"</code></span></div>
            <div class="param-row"><span class="param-key">llm.model</span><span class="param-type">string</span><span class="param-desc">如 <code>"openai/gpt-4.1"</code>、<code>"anthropic/claude-sonnet-4.6"</code></span></div>
          </div>
          <div class="code-snippet"><pre>{
  "url": "https://example.com",
  "mode": "premium",
  "feedback_lang": "zh",
  "full_audit": true,
  "max_pages": 12,
  "force_refresh": false,
  "llm": { "provider": "openrouter", "model": "openai/gpt-4.1" }
}</pre></div>
          <div class="api-desc">作用域示例：<code>https://www.ecoflow.com/de/</code> 只抓 <code>www.ecoflow.com/de/</code>；<code>https://de.ecoflow.com/</code> 会作为另一站独立审计。</div>
        </div>
      </div>

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">2</div>
          <span class="api-step-title">轮询任务状态</span>
        </div>
        <div class="api-step-body">
          <div class="api-endpoint"><span class="method m-get">GET</span>/api/v1/tasks/{task_id}</div>
          <div class="api-desc">每隔 1–2 秒轮询一次。<code>status</code> 为 <code>"completed"</code> 或 <code>"failed"</code> 时停止。<code>steps</code> 字段实时反映各模块状态（pending / running / completed / failed）。完成后，<code>summary.ai_perception</code> 还会返回 AI 对站点的认知百分比分布和 4 个认知标签。</div>
          <div class="api-params">
            <div class="param-row"><span class="param-key">status</span><span class="param-type">string</span><span class="param-desc">queued → running → completed | failed</span></div>
            <div class="param-row"><span class="param-key">progress_percent</span><span class="param-type">int</span><span class="param-desc">0–100，按完成步骤数计算</span></div>
            <div class="param-row"><span class="param-key">cached</span><span class="param-type">boolean</span><span class="param-desc">命中缓存时为 true，直接返回历史结果</span></div>
            <div class="param-row"><span class="param-key">llm_model_used</span><span class="param-type">boolean</span><span class="param-desc">只有真正拿到并使用了 llm.model 的增强结果时才为 true；失败降级时为 false</span></div>
            <div class="param-row"><span class="param-key">result</span><span class="param-type">object</span><span class="param-desc">completed 后包含完整的 visibility / technical / content / schema / platform / observation / summary；full audit 时额外返回 <code>page_diagnostics</code>，并在 <code>discovery.scope_root_url</code> 标明抓取边界</span></div>
          </div>
          <div class="code-snippet"><pre>// 响应结构示意
{
  "success": true,
  "data": {
    "task_id": "abc123",
    "status": "completed",          // queued | running | completed | failed
    "progress_percent": 100,
    "cached": false,
    "llm_model_used": true,
    "steps": { "discovery": { "status": "completed", "data": {...} }, ... },
    "result": {
      "visibility": { "score": 72, "status": "good", "llm_enhanced": true, ... },
      "technical":  { "score": 85, ... },
      "content":    { "score": 60, ... },
      "schema":     { "score": 45, ... },
      "platform":   { "chatgpt": { "platform_score": 68 }, ... },
      "discovery":  { "scope_root_url": "https://www.ecoflow.com/de/", ... },
      "page_diagnostics": [ { "page_type": "product", "overall_score": 71, ... } ],
      "observation":{ "provided": false, "scored": false, ... },
      "summary":    {
        "composite_geo_score": 70,
        "summary": "...",
        "ai_perception": {
          "positive_percentage": 58,
          "neutral_percentage": 29,
          "controversial_percentage": 13,
          "cognition_keywords": ["Thought Leader", "Well-structured", "Evidence-led", "Trustworthy"]
        }
      }
    }
  }
}</pre></div>
        </div>
      </div>

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">3</div>
          <span class="api-step-title">导出 Markdown 报告（可选）</span>
        </div>
        <div class="api-step-body">
          <div class="api-endpoint"><span class="method m-get">GET</span>/api/v1/tasks/{task_id}/report</div>
          <div class="api-desc">任务完成后可拉取完整 Markdown 报告，直接在浏览器渲染或保存为文件。仅在 <code>status=completed</code> 时有效。</div>
        </div>
      </div>

      <div class="api-step">
        <div class="api-step-hdr">
          <div class="api-num">4</div>
          <span class="api-step-title">单模块直调（高级用法）</span>
        </div>
        <div class="api-step-body">
          <div class="api-desc">无需走任务队列，直接同步调用单个审计模块，适合实时集成或调试；<code>/api/v1/audit/full</code> 同样支持 full audit 与作用域限制。</div>
          <div class="api-params">
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/visibility</code><span class="param-desc" style="margin-left:4px">AI 可见性模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/technical</code><span class="param-desc" style="margin-left:4px">技术基础模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/content</code><span class="param-desc" style="margin-left:4px">内容质量模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/schema</code><span class="param-desc" style="margin-left:4px">结构化数据模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/platform</code><span class="param-desc" style="margin-left:4px">平台适配模块</span></div>
            <div class="param-row"><span class="method m-post" style="border-radius:4px;font-size:11px">POST</span><code style="font-size:12px">/api/v1/audit/full</code><span class="param-desc" style="margin-left:4px">全量同步审计（含 summary，无缓存）</span></div>
          </div>
          <div class="code-snippet"><pre>// 单模块请求体（Body 字段相同）
{ "url": "https://example.com", "mode": "standard", "feedback_lang": "zh", "full_audit": true, "max_pages": 12 }

// premium 模式下可附加 LLM 配置
{ "url": "https://www.ecoflow.com/de/", "mode": "premium", "feedback_lang": "zh", "full_audit": true, "max_pages": 20,
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
  const STEP_ORDER = ['discovery', 'visibility', 'technical', 'content', 'schema', 'platform', 'observation', 'summary'];
  const STEP_ICON  = { discovery:'🔍', visibility:'👁', technical:'⚙️', content:'📝', schema:'🏷️', platform:'🌐', observation:'📎', summary:'📊' };

  /* ── State ── */
  let pollTimer = null;
  let currentTaskId = null;
  let currentTaskStatus = 'idle';
  let currentTask = null;
  const REPORT_CACHE_PREFIX = 'geo-audit-report:';

  function tx(lang, zhText, enText) {
    return lang === 'zh' ? zhText : enText;
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

  function getDimensionMeta(lang) {
    return [
      {
        key: 'AI Citability & Visibility',
        defaultName: tx(lang, 'AI 可见性', 'AI Citability & Visibility'),
        weight: '25%',
        formula: tx(
          lang,
          '0.32 × crawler + 0.40 × snapshot citability + 0.12 × llms 有效性 + 0.16 × 基础实体存在',
          '0.32 × crawler + 0.40 × snapshot citability + 0.12 × llms quality + 0.16 × baseline entity presence'
        ),
        detail: result => {
          const checks = result?.visibility?.checks || {};
          const citability = result?.visibility?.findings?.citability || {};
          const best = citability.best_page_citability || {};
          return tx(
            lang,
            `${checks.allowed_ai_crawlers ?? 0}/${checks.total_ai_crawlers_checked ?? 0} 个 AI crawler 放行 · 最佳页面 ${best.page_key || 'homepage'} ${best.score ?? 0} · 引用概率 ${citability.citation_probability || 'LOW'}`,
            `${checks.allowed_ai_crawlers ?? 0}/${checks.total_ai_crawlers_checked ?? 0} AI crawlers allowed · Best page ${best.page_key || 'homepage'} ${best.score ?? 0} · Citation probability ${citability.citation_probability || 'LOW'}`
          );
        }
      },
      {
        key: 'Brand Authority Signals',
        defaultName: tx(lang, '品牌权威', 'Brand Authority Signals'),
        weight: '20%',
        formula: tx(
          lang,
          '0.25 × 外链质量 + 0.25 × 品牌提及覆盖 + 0.25 × sameAs/Entity 一致性 + 0.25 × 企业信息完整度',
          '0.25 × backlink quality + 0.25 × brand mention coverage + 0.25 × sameAs/entity consistency + 0.25 × business completeness'
        ),
        detail: result => {
          const brand = result?.visibility?.checks?.brand_signals || {};
          const backlinks = result?.visibility?.checks?.backlinks || {};
          const authority = backlinks.authority_score ?? tx(lang, '未接入', 'Unavailable');
          return tx(
            lang,
            `公司名 ${brand.company_name_detected ? '已识别' : '未识别'} · sameAs ${brand.same_as_detected ? '已配置' : '缺失'} · Semrush AS ${authority}`,
            `Company name ${brand.company_name_detected ? 'detected' : 'missing'} · sameAs ${brand.same_as_detected ? 'present' : 'missing'} · Semrush AS ${authority}`
          );
        }
      },
      {
        key: 'Content Quality & E-E-A-T',
        defaultName: tx(lang, '内容与 E-E-A-T', 'Content Quality & E-E-A-T'),
        weight: '20%',
        formula: tx(
          lang,
          '(content + experience + expertise + authority + trust) / 5，内容层同时吸收信息密度与分块结构',
          '(content + experience + expertise + authority + trust) / 5, with information density and chunk structure folded into the content layer'
        ),
        detail: result => {
          const findings = result?.content?.findings || {};
          const sampled = Number(result?.discovery?.profiled_page_count || Object.keys(result?.discovery?.page_profiles || {}).length || 0);
          return tx(
            lang,
            `snapshot 采样 ${sampled} 页 · FAQ ${findings.has_faq_any ? '有' : '无'} · 标题质量 ${findings.average_heading_quality ?? 0} · 信息密度 ${findings.average_information_density ?? 0}`,
            `Snapshot sampled ${sampled} pages · FAQ ${findings.has_faq_any ? 'yes' : 'no'} · Heading quality ${findings.average_heading_quality ?? 0} · Information density ${findings.average_information_density ?? 0}`
          );
        }
      },
      {
        key: 'Technical Foundations',
        defaultName: tx(lang, '技术基础', 'Technical Foundations'),
        weight: '15%',
        formula: tx(
          lang,
          'HTTPS / SSR / Meta / Canonical / Sitemap / 性能 / 安全头 / 图片 / 渲染阻塞等加权求和',
          'Weighted sum of HTTPS / SSR / meta / canonical / sitemap / performance / security headers / images / render blocking'
        ),
        detail: result => {
          const tech = result?.technical || {};
          return tx(
            lang,
            `响应 ${tech.findings?.response_time_ms ?? '-'}ms · 性能 ${tech.findings?.performance_classification || '-'} · 安全头 ${tech.findings?.security_headers_score ?? 0}`,
            `Response ${tech.findings?.response_time_ms ?? '-'}ms · Performance ${tech.findings?.performance_classification || '-'} · Security headers ${tech.findings?.security_headers_score ?? 0}`
          );
        }
      },
      {
        key: 'Structured Data',
        defaultName: tx(lang, '结构化数据', 'Structured Data'),
        weight: '10%',
        formula: tx(
          lang,
          'JSON-LD + Organization + WebSite + Service + Article + FAQ + Product + DefinedTerm + sameAs + @id + relation richness',
          'JSON-LD + Organization + WebSite + Service + Article + FAQ + Product + DefinedTerm + sameAs + @id + relation richness'
        ),
        detail: result => {
          const findings = result?.schema?.findings || {};
          const sampled = Number(result?.discovery?.profiled_page_count || Object.keys(result?.discovery?.page_profiles || {}).length || 0);
          return tx(
            lang,
            `Schema 类型 ${findings.schema_type_count ?? 0} 项 · sameAs ${findings.same_as_count ?? 0} 项 · @id ${findings.entity_id_count ?? 0} · 关系 ${findings.relation_count ?? 0} · 复用 snapshot ${sampled} 页`,
            `Schema types ${findings.schema_type_count ?? 0} · sameAs ${findings.same_as_count ?? 0} · @id ${findings.entity_id_count ?? 0} · Relations ${findings.relation_count ?? 0} · Reused snapshot pages ${sampled}`
          );
        }
      },
      {
        key: 'Platform Optimization',
        defaultName: tx(lang, '平台适配', 'Platform Optimization'),
        weight: '10%',
        formula: 'ChatGPT 22% + Google AI Mode 18% + AI Overviews 18% + Perplexity 16% + Gemini 13% + Grok 13%',
        detail: result => {
          const scores = Object.entries(result?.platform?.platform_scores || {});
          if (!scores.length) return tx(lang, '等待平台结果', 'Waiting for platform scores');
          scores.sort((a, b) => (a[1]?.platform_score || 0) - (b[1]?.platform_score || 0));
          const low = scores[0];
          const high = scores[scores.length - 1];
          return tx(
            lang,
            `最佳 ${PLATFORM_LABELS[high?.[0]] || high?.[0]} ${high?.[1]?.platform_score ?? 0} · 最弱 ${PLATFORM_LABELS[low?.[0]] || low?.[0]} ${low?.[1]?.platform_score ?? 0}`,
            `Best ${PLATFORM_LABELS[high?.[0]] || high?.[0]} ${high?.[1]?.platform_score ?? 0} · Weakest ${PLATFORM_LABELS[low?.[0]] || low?.[0]} ${low?.[1]?.platform_score ?? 0}`
          );
        }
      }
    ];
  }

  const PLATFORM_LABELS = {
    google_ai_overviews: 'Google AI Overviews',
    google_ai_mode: 'Google AI Mode',
    chatgpt: 'ChatGPT',
    perplexity: 'Perplexity',
    gemini: 'Gemini',
    grok: 'Grok'
  };

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function scoreToStatus(score) {
    const n = Number(score ?? 0);
    if (n <= 24) return 'critical';
    if (n <= 44) return 'poor';
    if (n <= 64) return 'fair';
    if (n <= 84) return 'good';
    return 'strong';
  }

  function statusTone(status) {
    if (status === 'strong' || status === 'good' || status === 'completed') return 'success';
    if (status === 'fair' || status === 'running' || status === 'pending') return 'warn';
    if (status === 'poor' || status === 'critical' || status === 'failed') return 'danger';
    return '';
  }


function formatStatus(status, lang = 'zh') {
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

function formatBool(val, yes = '是', no = '否') {
  return val ? yes : no;
}

function formatList(items, fallback, limit = 5) {
  const list = [...new Set((items || []).filter(Boolean))].slice(0, limit);
  if (!list.length) return `<div class="report-list-item">${escapeHtml(fallback)}</div>`;
  return list.map((item, idx) => `<div class="report-list-item"><strong>${idx + 1}.</strong> ${escapeHtml(item)}</div>`).join('');
}

  function normalizeActions(result, lang = 'zh') {
    const llmPlan = result?.summary?.llm_insights?.prioritized_action_plan;
    if (Array.isArray(llmPlan) && llmPlan.length) {
      return llmPlan.map(item => ({
        priority: (item.priority || 'medium').toLowerCase(),
        action: item.action || tx(lang, '待补充', 'TBD'),
        description: item.description || item.rationale || '',
        impact: item.expected_impact || 'High'
      }));
    }
    return (result?.summary?.prioritized_action_plan || []).map(item => ({
      priority: (item.priority || 'medium').toLowerCase(),
      action: item.action || tx(lang, '待补充', 'TBD'),
      description: item.rationale || tx(lang, `${item.module || '该模块'} 需要优先优化。`, `${item.module || 'This module'} needs priority optimization.`),
      impact: item.priority === 'high' ? 'High' : item.priority === 'low' ? 'Medium' : 'High'
    }));
  }

  function formatKeyPages(keyPages, lang = 'zh') {
    return Object.entries({
      About: keyPages?.about,
      Service: keyPages?.service,
      Contact: keyPages?.contact,
      Article: keyPages?.article,
      'Case Study': keyPages?.case_study
    }).map(([name, value]) => `
      <div class="kv-row">
        <span class="kv-key">${escapeHtml(name)}</span>
        <span class="kv-val">${value ? tx(lang, '已识别', 'Detected') : tx(lang, '缺失', 'Missing')}</span>
      </div>
    `).join('');
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

  const summary = result.summary || {};
  const discovery = result.discovery || {};
  const homepage = discovery.homepage || {};
  const visibility = result.visibility || {};
  const technical = result.technical || {};
  const content = result.content || {};
  const schema = result.schema || {};
  const platform = result.platform || {};
  const labels = {
    noSummary: tx(lang, '暂无摘要。', 'No summary available.'),
    noPageSamples: tx(lang, '暂无可展示的页面采样。', 'No sampled pages available.'),
    contribution: tx(lang, '综合贡献', 'Weighted contribution'),
    rawWeight: tx(lang, '原始权重', 'Weight'),
    formula: tx(lang, '公式', 'Formula'),
    currentSignals: tx(lang, '当前信号', 'Current signals'),
    noPlatformData: tx(lang, '暂无平台数据。', 'No platform data available.'),
    noMetricDefinitions: tx(lang, '暂无指标说明。', 'No metric definitions available.'),
    observationStatus: tx(lang, 'Observation 状态', 'Observation Status'),
    observationSummaryTitle: tx(lang, 'Observation 摘要', 'Observation Summary'),
    provided: tx(lang, '已提供', 'Provided'),
    notProvided: tx(lang, '未提供', 'Not provided'),
    scored: tx(lang, '是', 'Yes'),
    unscored: tx(lang, '否', 'No'),
    maturity: tx(lang, '成熟度', 'Maturity'),
    note: tx(lang, '说明', 'Note'),
    observationNote: tx(lang, 'Observation 仅做展示，不改写综合分', 'Observation is shown for context only and never changes the composite score'),
    noObservationSummary: tx(lang, '未上传 observation 数据，系统仅基于 URL 做 readiness 评分。', 'No observation data was uploaded. Readiness is scored from the URL alone.'),
    noHighlights: tx(lang, '暂无 highlights。', 'No highlights available.'),
    noDataGaps: tx(lang, '暂无数据缺口。', 'No data gaps available.'),
    noNotices: tx(lang, '暂无提示。', 'No notices.'),
    fullAuditMissing: tx(lang, '当前未启用 full audit，未返回逐页诊断。', 'Full audit is not enabled, so no page diagnostics were returned.'),
    noActionPlan: tx(lang, '暂无行动计划。', 'No action plan available.'),
    noIssues: tx(lang, '暂无关键问题', 'No key issues'),
    reportBasis: tx(lang, '报告口径', 'Report basis'),
    compositeGeoScore: 'Composite GEO Score',
    premiumBadge: tx(lang, '会员版 / AI 增强', 'Premium / AI Enriched'),
    standardBadge: tx(lang, '普通版 / 规则版', 'Standard / Rule-based'),
    enhanced: tx(lang, '报告已增强', 'Report Enhanced'),
    ruleSummary: tx(lang, '规则汇总', 'Rule Summary'),
    siteGeoReport: tx(lang, '站点 GEO 报告', 'Site GEO Report'),
    responsePrefix: tx(lang, '响应', 'Response'),
    snapshotLabel: 'Snapshot',
    scopeRootLabel: 'Scope Root',
    aiCrawlLlms: tx(lang, 'AI 抓取 / llms', 'AI Crawl / llms'),
    citationProbability: tx(lang, '引用概率', 'Citation Probability'),
    bestWeakestPlatform: tx(lang, '最佳 / 最弱平台', 'Best / Weakest Platform'),
    observationLabel: 'Observation',
    inputScope: 'Input Scope',
    fullAudit: 'Full Audit',
    aiPerceptionTitle: tx(lang, 'AI 认知快照', 'AI Perception Snapshot'),
    aiPerceptionSubtitle: tx(lang, '根据站点信号估算 AI 对该站点的认知倾向，不参与评分', 'Estimated AI-side perception based on site signals. This does not affect scoring.'),
    positiveLabel: tx(lang, '正面', 'Positive'),
    neutralLabel: tx(lang, '中性', 'Neutral'),
    controversialLabel: tx(lang, '争议', 'Controversial'),
    cognitionKeywordsLabel: tx(lang, '认知标签', 'Perception Keywords'),
    scoredDimensionsTitle: tx(lang, '6 个汇总维度评估', '6 Scored Dimensions'),
    scoredDimensionsSubtitle: tx(lang, '原始分满分 100，按权重折算进入综合分', 'Raw scores are out of 100 and are weighted into the composite score'),
    keyIssuesTitle: tx(lang, '关键问题', 'Key Issues'),
    keyIssuesSubtitle: tx(lang, '优先处理最拖分的约束项', 'Prioritize the constraints hurting the score most'),
    quickWinsTitle: tx(lang, '快速收益项', 'Quick Wins'),
    quickWinsSubtitle: tx(lang, '优先处理投入低、收益快的动作', 'Prioritize low-effort, fast-return actions'),
    actionPlanTitle: tx(lang, '优先行动计划', 'Prioritized Action Plan'),
    actionPlanSubtitle: tx(lang, '结合规则结果与 AI 增强建议生成', 'Generated from rule-based outputs and AI enrichment'),
    platformOverviewTitle: tx(lang, '平台适配概览', 'Platform Readiness Overview'),
    platformOverviewSubtitle: tx(lang, '展示 6 个目标平台的 readiness、优化焦点、主缺口与首要建议', 'Shows readiness, optimization focus, primary gap, and top recommendation across 6 platforms'),
    metricsTitle: tx(lang, '指标说明', 'Metric Definitions'),
    metricsSubtitle: tx(lang, '区分计分维度与 Observation Layer', 'Separates scored dimensions from the Observation Layer'),
    observationTitle: 'Observation Layer',
    observationSubtitle: tx(lang, '可选上传的外部观测数据，仅展示，不计分', 'Optional uploaded observation data, displayed only and not scored'),
    pageDiagnosticsTitle: 'Page Diagnostics',
    pageDiagnosticsSubtitle: tx(lang, '仅 full audit 模式返回，逐页展示可引用性与结构质量', 'Returned only in full audit mode, with page-level extraction and structure diagnostics'),
    snapshotTitle: tx(lang, 'Snapshot 与原始发现', 'Snapshot and Raw Findings'),
    snapshotSubtitle: tx(lang, '基于 discovery snapshot 与各模块 checks / findings 的事实层展示', 'Fact-layer view based on the discovery snapshot and module checks/findings'),
    notesTitle: tx(lang, '说明与备注', 'Notes and Context'),
    notesSubtitle: tx(lang, '发现层版本、处理注释与模式说明', 'Discovery version, processing notes, and mode context'),
    impact: tx(lang, '预计影响', 'Expected impact'),
    pageWordCountSuffix: tx(lang, '词', 'words'),
    pageFaqYes: tx(lang, '有', 'Yes'),
    pageFaqNo: tx(lang, '无', 'No'),
    pageIssueEmpty: tx(lang, '暂无关键问题', 'No key issues'),
    waitReport: tx(lang, '等待平台结果', 'Waiting for platform results'),
    unavailable: tx(lang, '暂无', 'N/A'),
    missingGap: tx(lang, '暂无缺口描述', 'No gap description'),
    preferredSourcesFallback: tx(lang, '暂无偏好信源', 'No preferred sources'),
    recommendationFallback: tx(lang, '暂无建议', 'No recommendation'),
    observationProvidedLine: observation => observation.provided
      ? tx(lang, `已提供 · ${observation.measurement_maturity || 'basic'}`, `Provided · ${observation.measurement_maturity || 'basic'}`)
      : tx(lang, '未提供 · 不计分', 'Not provided · Unscored')
  };
  const executive = summary?.llm_insights?.executive_summary || summary.summary || labels.noSummary;
  const topIssues = summary?.llm_insights?.top_issues || summary.top_issues || [];
  const quickWins = summary?.llm_insights?.quick_wins || summary.quick_wins || [];
  const actions = normalizeActions(result, lang).slice(0, 5);
  const weighted = summary.weighted_scores || {};
  const aiPerception = summary.ai_perception || {};
  const platformScores = platform.platform_scores || {};
  const observation = result.observation || summary.observation || {};
  const metricDefinitions = summary.metric_definitions || [];
  const notices = summary.notices || [];
  const pageDiagnostics = Array.isArray(result.page_diagnostics) ? result.page_diagnostics : [];
  const citability = visibility.findings?.citability || {};
  const homepageCitability = citability.homepage_citability || {};
  const bestPageCitability = citability.best_page_citability || {};
  const citationProbability = citability.citation_probability || 'LOW';
  const citationLabelMap = lang === 'zh'
    ? { LOW: '低', MEDIUM: '中', HIGH: '高' }
    : { LOW: 'Low', MEDIUM: 'Medium', HIGH: 'High' };
  const pageProfiles = Object.entries(discovery.page_profiles || {});
  const additionalProfiles = Array.isArray(discovery.additional_page_profiles) ? discovery.additional_page_profiles : [];
  const fallbackPages = Object.values(content.page_analyses || {});
  const dimensionMeta = getDimensionMeta(lang);
  const pageSamples = pageProfiles.length
    ? [
        ...pageProfiles.map(([key, page]) => ({ key, source: 'core', ...page })),
        ...additionalProfiles.map((page, index) => ({ key: `additional_${index + 1}`, source: 'extended', ...page }))
      ]
    : fallbackPages;
  const pageSampleHtml = pageSamples.length
    ? pageSamples.slice(0, 5).map(page => {
        const schemaTypes = Array.isArray(page.json_ld_summary?.types) ? page.json_ld_summary.types.length : 0;
        return `
          <div class="page-sample">
            <div class="top">
              <span class="name">${escapeHtml(page.page_type || page.key || 'page')}</span>
              <span class="name">${escapeHtml(String(page.word_count || 0))} ${escapeHtml(labels.pageWordCountSuffix)}</span>
            </div>
            <div class="meta">${escapeHtml(tx(lang, '标题质量', 'Heading quality'))} ${escapeHtml(String(page.heading_quality_score || 0))} · ${escapeHtml(tx(lang, '信息密度', 'Information density'))} ${escapeHtml(String(page.information_density_score || 0))} · ${escapeHtml(tx(lang, '分块结构', 'Chunk structure'))} ${escapeHtml(String(page.chunk_structure_score || 0))}</div>
            <div class="meta">FAQ ${page.has_faq ? labels.pageFaqYes : labels.pageFaqNo} · ${escapeHtml(tx(lang, '作者', 'Author'))} ${page.has_author ? labels.pageFaqYes : labels.pageFaqNo} · ${escapeHtml(tx(lang, '日期', 'Date'))} ${page.has_publish_date ? labels.pageFaqYes : labels.pageFaqNo} · answer-first ${page.answer_first ? labels.pageFaqYes : labels.pageFaqNo} · Schema ${schemaTypes}</div>
          </div>
        `;
      }).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noPageSamples)}</div>`;

  const dimensionHtml = dimensionMeta.map(meta => {
    const item = weighted[meta.key] || {};
    const rawScore = Number(item.raw_score ?? 0);
    const status = scoreToStatus(rawScore);
    const displayName = summary.dimensions?.[meta.key]?.display_name || meta.defaultName;
    return `
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(displayName)}</span>
          <span class="report-dim-pill">${escapeHtml(meta.weight)}</span>
        </div>
        <div class="report-dim-scoreline">
          <span class="score">${escapeHtml(String(rawScore))}</span>
          <span class="status">${escapeHtml(formatStatus(status, lang))}</span>
        </div>
        <div class="report-dim-kpis">
          <div class="report-dim-kpi">
            <div class="lbl">${escapeHtml(labels.contribution)}</div>
            <div class="val">${escapeHtml(String(item.weighted_value ?? 0))}</div>
          </div>
          <div class="report-dim-kpi">
            <div class="lbl">${escapeHtml(labels.rawWeight)}</div>
            <div class="val">${escapeHtml(meta.weight)}</div>
          </div>
        </div>
        <div class="report-dim-note"><strong>${escapeHtml(labels.formula)}:</strong> ${escapeHtml(meta.formula)}</div>
        <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(labels.currentSignals)}:</strong> ${escapeHtml(meta.detail(result))}</div>
      </div>
    `;
  }).join('');

  const platformHtml = Object.entries(platformScores).map(([key, item]) => `
    <div class="platform-card">
      <div class="hd">
        <span class="name">${escapeHtml(PLATFORM_LABELS[key] || key)}</span>
        <span class="score">${escapeHtml(String(item.platform_score ?? 0))}</span>
      </div>
      <div class="gap"><strong>${escapeHtml(tx(lang, '优化焦点', 'Optimization Focus'))}:</strong> ${escapeHtml(item.optimization_focus || labels.unavailable)}</div>
      <div class="gap">${escapeHtml(item.primary_gap || labels.missingGap)}</div>
      <div class="reco">${escapeHtml((item.preferred_sources || []).join(' / ') || labels.preferredSourcesFallback)}</div>
      <div class="reco">${escapeHtml((item.key_recommendations || [])[0] || labels.recommendationFallback)}</div>
    </div>
  `).join('');

  const metricHtml = metricDefinitions.length
    ? metricDefinitions.map(item => `
        <div class="report-dim-card">
          <div class="report-dim-head">
            <span class="report-dim-name">${escapeHtml(item.name || '-')}</span>
            <span class="report-dim-pill">${escapeHtml(item.scoring === 'unscored' ? tx(lang, '不计分', 'Unscored') : tx(lang, '计分', 'Scored'))}</span>
          </div>
          <div class="report-dim-note"><strong>${escapeHtml(labels.formula)}:</strong> ${escapeHtml(item.formula || '-')}</div>
          <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(tx(lang, '数据来源', 'Data Source'))}:</strong> ${escapeHtml(item.data_source || '-')}</div>
          <div class="report-dim-note" style="margin-top:6px"><strong>${escapeHtml(tx(lang, '业务意义', 'Why It Matters'))}:</strong> ${escapeHtml(item.why_it_matters || '-')}</div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noMetricDefinitions)}</div>`;

  const observationBreakdown = Array.isArray(observation.platform_breakdown) ? observation.platform_breakdown : [];
  const observationHighlights = Array.isArray(observation.highlights) ? observation.highlights : [];
  const observationGaps = Array.isArray(observation.data_gaps) ? observation.data_gaps : [];
  const observationHtml = `
    <div class="report-grid-2">
      <div class="evidence-card">
        <h5>${escapeHtml(labels.observationStatus)}</h5>
        <div class="kv-list">
          <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '是否提供', 'Provided'))}</span><span class="kv-val">${observation.provided ? labels.provided : labels.notProvided}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '是否计分', 'Scored'))}</span><span class="kv-val">${observation.scored ? labels.scored : labels.unscored}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.maturity)}</span><span class="kv-val">${escapeHtml(observation.measurement_maturity || 'none')}</span></div>
          <div class="kv-row"><span class="kv-key">${escapeHtml(labels.note)}</span><span class="kv-val">${escapeHtml(labels.observationNote)}</span></div>
        </div>
      </div>
      <div class="evidence-card">
        <h5>${escapeHtml(labels.observationSummaryTitle)}</h5>
        <div class="report-note-box">${escapeHtml(observation.summary || labels.noObservationSummary)}</div>
      </div>
    </div>
    ${observationHighlights.length ? `<div class="report-list" style="margin-top:12px">${formatList(observationHighlights, labels.noHighlights)}</div>` : ''}
    ${observationBreakdown.length ? `
      <div class="report-note-box" style="margin-top:12px">
        ${observationBreakdown.map(item => `${escapeHtml(item.platform)}: ${escapeHtml(String(item.sessions ?? '-'))} sessions / ${escapeHtml(String(item.conversions ?? '-'))} conversions / CR ${escapeHtml(String(item.conversion_rate ?? '-'))}`).join('<br />')}
      </div>
    ` : ''}
    ${observationGaps.length ? `<div class="report-list" style="margin-top:12px">${formatList(observationGaps, labels.noDataGaps)}</div>` : ''}
  `;

  const aiPerceptionHtml = `
    <div class="report-grid-2">
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.positiveLabel)}</span>
          <span class="report-dim-pill">%</span>
        </div>
        <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(aiPerception.positive_percentage ?? 0))}</span></div>
      </div>
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.neutralLabel)}</span>
          <span class="report-dim-pill">%</span>
        </div>
        <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(aiPerception.neutral_percentage ?? 0))}</span></div>
      </div>
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.controversialLabel)}</span>
          <span class="report-dim-pill">%</span>
        </div>
        <div class="report-dim-scoreline"><span class="score">${escapeHtml(String(aiPerception.controversial_percentage ?? 0))}</span></div>
      </div>
      <div class="report-dim-card">
        <div class="report-dim-head">
          <span class="report-dim-name">${escapeHtml(labels.cognitionKeywordsLabel)}</span>
          <span class="report-dim-pill">${escapeHtml(String((aiPerception.cognition_keywords || []).length || 0))}</span>
        </div>
        <div class="report-list">${formatList(aiPerception.cognition_keywords || [], tx(lang, '暂无认知标签。', 'No perception keywords.'))}</div>
      </div>
    </div>
  `;

  const noticesHtml = notices.length
    ? `<div class="report-list" style="margin-top:14px">${formatList(notices, labels.noNotices, 8)}</div>`
    : '';

  const pageDiagnosticsHtml = pageDiagnostics.length
    ? `<div class="report-list">${pageDiagnostics.slice(0, 12).map((item, index) => `
        <div class="report-list-item">
          <strong>${index + 1}. ${escapeHtml(item.page_type || 'page')}</strong>
          · ${escapeHtml(item.source || 'core')}
          · ${escapeHtml(tx(lang, '总分', 'Overall'))} ${escapeHtml(String(item.overall_score ?? 0))}
          · Citability ${escapeHtml(String(item.citability_score ?? 0))}
          · Content ${escapeHtml(String(item.content_score ?? 0))}
          · Technical ${escapeHtml(String(item.technical_score ?? 0))}
          · Schema ${escapeHtml(String(item.schema_score ?? 0))}
          <br />
          ${escapeHtml(item.url || '-')}
          <br />
          ${(item.issues || []).length ? escapeHtml((item.issues || []).slice(0, 2).join(' | ')) : labels.pageIssueEmpty}
        </div>
      `).join('')}</div>`
    : `<div class="report-list-item">${escapeHtml(labels.fullAuditMissing)}</div>`;

  const actionHtml = actions.length
    ? actions.map(item => `
        <div class="report-action">
          <div class="report-action-priority ${escapeHtml(item.priority)}">${escapeHtml(formatStatus(item.priority, lang))}</div>
          <div class="report-action-main">
            <h5>${escapeHtml(item.action)}</h5>
            <p>${escapeHtml(item.description || tx(lang, '暂无说明', 'No description'))}</p>
          </div>
          <div class="report-action-impact">${escapeHtml(labels.impact)}<span>${escapeHtml(item.impact || 'High')}</span></div>
        </div>
      `).join('')
    : `<div class="report-list-item">${escapeHtml(labels.noActionPlan)}</div>`;

  const strongestPlatform = Object.entries(platformScores).sort((a, b) => (b[1]?.platform_score || 0) - (a[1]?.platform_score || 0))[0];
  const weakestPlatform = Object.entries(platformScores).sort((a, b) => (a[1]?.platform_score || 0) - (b[1]?.platform_score || 0))[0];
  const noteText = [
    discovery.site_snapshot_version ? tx(lang, `发现层版本：${discovery.site_snapshot_version}，当前 audit_full 支持复用传入 discovery，避免重复抓取。`, `Discovery version: ${discovery.site_snapshot_version}. Current audit_full can reuse a supplied discovery payload to avoid duplicate crawling.`) : '',
    discovery.scope_root_url ? tx(lang, `抓取作用域：${discovery.scope_root_url}`, `Crawl scope: ${discovery.scope_root_url}`) : '',
    discovery.input_scope_warning ? tx(lang, `输入范围提示：${discovery.input_scope_warning}`, `Input scope note: ${discovery.input_scope_warning}`) : '',
    discovery.full_audit_enabled ? tx(lang, `full audit：已启用，累计建模 ${discovery.profiled_page_count || 0} 页，requested max_pages=${discovery.requested_max_pages || 12}。`, `Full audit enabled: profiled ${discovery.profiled_page_count || 0} pages, requested max_pages=${discovery.requested_max_pages || 12}.`) : tx(lang, 'full audit：未启用，默认只输出站点级结果。', 'Full audit disabled: only site-level results are returned by default.'),
    tx(lang, '品牌权威当前仍通过 visibility 输出，但代码层已预留 BrandAuthorityService 边界，便于后续独立服务化。', 'Brand authority is still emitted from visibility for now, but a BrandAuthorityService boundary is reserved for future service separation.'),
    summary.summary ? tx(lang, `报告摘要：${summary.summary}`, `Report summary: ${summary.summary}`) : '',
    summary.score_interpretation?.length ? tx(lang, `评分说明：${summary.score_interpretation.join(' | ')}`, `Score interpretation: ${summary.score_interpretation.join(' | ')}`) : '',
    summary.processing_notes?.length ? tx(lang, `汇总注释：${summary.processing_notes.join(' | ')}`, `Summary notes: ${summary.processing_notes.join(' | ')}`) : '',
    technical.processing_notes?.length ? tx(lang, `技术模块：${technical.processing_notes.join(' | ')}`, `Technical module: ${technical.processing_notes.join(' | ')}`) : '',
    schema.processing_notes?.length ? tx(lang, `结构化数据模块：${schema.processing_notes.join(' | ')}`, `Structured data module: ${schema.processing_notes.join(' | ')}`) : ''
  ].filter(Boolean).join('\\n\\n') || tx(lang, '当前无额外备注。', 'No extra notes.');

  host.className = 'report-shell';
  const html = `
    <section class="report-hero">
      <div class="report-score-box">
        <div>
          <div class="report-score-label">${escapeHtml(labels.compositeGeoScore)}</div>
          <div class="report-score-value">${escapeHtml(String(summary.composite_geo_score ?? 0))}</div>
          <div class="report-score-sub">${escapeHtml(formatStatus(summary.status, lang))} · ${escapeHtml(labels.reportBasis)}</div>
        </div>
        <div class="report-badges">
          <span class="r-badge ${escapeHtml(statusTone(summary.status))}">${escapeHtml(formatStatus(summary.status, lang))}</span>
          <span class="r-badge">${task.mode === 'premium' ? labels.premiumBadge : labels.standardBadge}</span>
          <span class="r-badge ${summary.llm_enhanced ? 'success' : ''}">${summary.llm_enhanced ? labels.enhanced : labels.ruleSummary}</span>
          <span class="r-badge">${escapeHtml(summary.scoring_version || 'geo-audit-v3')}</span>
        </div>
      </div>
      <div class="report-hero-main">
        <div class="report-kicker">
          <span>${escapeHtml(discovery.domain || discovery.normalized_url || task.url || '-')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(discovery.business_type || 'unknown')}</span>
          <span class="dot"></span>
          <span>${escapeHtml(labels.responsePrefix)} ${escapeHtml(String(discovery.fetch?.response_time_ms ?? '-'))} ms</span>
        </div>
        <h3>${escapeHtml(labels.siteGeoReport)}</h3>
        <div class="report-summary">${escapeHtml(executive)}</div>
        <div class="report-meta-grid">
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.snapshotLabel)}</div>
            <div class="val">${escapeHtml(discovery.site_snapshot_version || 'snapshot-v1')} · ${escapeHtml(String(discovery.profiled_page_count || pageSamples.length || 1))} ${escapeHtml(tx(lang, '页画像', 'page profiles'))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.scopeRootLabel)}</div>
            <div class="val">${escapeHtml(discovery.scope_root_url || discovery.site_root_url || '-')}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.aiCrawlLlms)}</div>
            <div class="val">${escapeHtml(String(visibility.checks?.allowed_ai_crawlers ?? 0))} / ${escapeHtml(String(visibility.checks?.total_ai_crawlers_checked ?? 0))} ${escapeHtml(tx(lang, '放行', 'allowed'))} · llms ${escapeHtml(String(visibility.findings?.llms_quality?.score ?? 0))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.citationProbability)}</div>
            <div class="val">${escapeHtml(citationLabelMap[citationProbability] || citationProbability)} · ${escapeHtml(tx(lang, '首页', 'Homepage'))} ${escapeHtml(String(homepageCitability.score ?? 0))} / ${escapeHtml(tx(lang, '最佳页', 'Best page'))} ${escapeHtml(String(bestPageCitability.score ?? 0))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.bestWeakestPlatform)}</div>
            <div class="val">${escapeHtml(PLATFORM_LABELS[strongestPlatform?.[0]] || '-')} ${escapeHtml(String(strongestPlatform?.[1]?.platform_score ?? '-'))} / ${escapeHtml(PLATFORM_LABELS[weakestPlatform?.[0]] || '-')} ${escapeHtml(String(weakestPlatform?.[1]?.platform_score ?? '-'))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.observationLabel)}</div>
            <div class="val">${escapeHtml(labels.observationProvidedLine(observation))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.inputScope)}</div>
            <div class="val">${discovery.input_is_likely_homepage === false ? escapeHtml(tx(lang, '非首页输入 · 结果可能偏差', 'Non-homepage input · results may be biased')) : escapeHtml(tx(lang, '首页 / 语言首页输入', 'Homepage / locale-homepage input'))}</div>
          </div>
          <div class="report-meta-item">
            <div class="lbl">${escapeHtml(labels.fullAudit)}</div>
            <div class="val">${discovery.full_audit_enabled ? `${escapeHtml(tx(lang, '已启用', 'Enabled'))} · ${escapeHtml(String(discovery.profiled_page_count || 0))} ${escapeHtml(tx(lang, '页', 'pages'))}` : escapeHtml(tx(lang, '未启用', 'Disabled'))}</div>
          </div>
        </div>
        ${noticesHtml}
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr">
        <h4>${escapeHtml(labels.scoredDimensionsTitle)}</h4>
        <span>${escapeHtml(labels.scoredDimensionsSubtitle)}</span>
      </div>
      <div class="report-section-body">
        <div class="report-dim-grid">${dimensionHtml}</div>
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr">
        <h4>${escapeHtml(labels.aiPerceptionTitle)}</h4>
        <span>${escapeHtml(labels.aiPerceptionSubtitle)}</span>
      </div>
      <div class="report-section-body">${aiPerceptionHtml}</div>
    </section>

    <div class="report-grid-2">
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(labels.keyIssuesTitle)}</h4><span>${escapeHtml(labels.keyIssuesSubtitle)}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(topIssues, tx(lang, '暂无关键问题。', 'No key issues.'))}</div></div>
      </section>
      <section class="report-section">
        <div class="report-section-hdr"><h4>${escapeHtml(labels.quickWinsTitle)}</h4><span>${escapeHtml(labels.quickWinsSubtitle)}</span></div>
        <div class="report-section-body"><div class="report-list">${formatList(quickWins, tx(lang, '暂无快速收益建议。', 'No quick wins available.'))}</div></div>
      </section>
    </div>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.actionPlanTitle)}</h4><span>${escapeHtml(labels.actionPlanSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-action-list">${actionHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.platformOverviewTitle)}</h4><span>${escapeHtml(labels.platformOverviewSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-platform-grid">${platformHtml || `<div class="report-list-item">${escapeHtml(labels.noPlatformData)}</div>`}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.metricsTitle)}</h4><span>${escapeHtml(labels.metricsSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-dim-grid">${metricHtml}</div></div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.observationTitle)}</h4><span>${escapeHtml(labels.observationSubtitle)}</span></div>
      <div class="report-section-body">${observationHtml}</div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.pageDiagnosticsTitle)}</h4><span>${escapeHtml(labels.pageDiagnosticsSubtitle)}</span></div>
      <div class="report-section-body">${pageDiagnosticsHtml}</div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.snapshotTitle)}</h4><span>${escapeHtml(labels.snapshotSubtitle)}</span></div>
      <div class="report-section-body">
        <div class="report-evidence-grid">
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '站点概况', 'Site Overview'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '规范化 URL', 'Normalized URL'))}</span><span class="kv-val">${escapeHtml(discovery.normalized_url || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页标题', 'Homepage Title'))}</span><span class="kv-val">${escapeHtml(homepage.title || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页 H1', 'Homepage H1'))}</span><span class="kv-val">${escapeHtml(homepage.h1 || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '字数 / 标题数', 'Words / Headings'))}</span><span class="kv-val">${escapeHtml(String(homepage.word_count ?? 0))} / ${escapeHtml(String((homepage.headings || []).length))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '语言 / hreflang', 'Language / hreflang'))}</span><span class="kv-val">${escapeHtml(homepage.lang || '-')} / ${escapeHtml(String((homepage.hreflang || []).length))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '发现层快照', 'Discovery Snapshot'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, 'snapshot 版本', 'Snapshot version'))}</span><span class="kv-val">${escapeHtml(discovery.site_snapshot_version || 'snapshot-v1')}</span></div><div class="kv-row"><span class="kv-key">scope root</span><span class="kv-val">${escapeHtml(discovery.scope_root_url || discovery.site_root_url || '-')}</span></div><div class="kv-row"><span class="kv-key">profiled pages</span><span class="kv-val">${escapeHtml(String(discovery.profiled_page_count || pageSamples.length || 1))} ${escapeHtml(tx(lang, '页', 'pages'))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '关键页面识别', 'Key pages identified'))}</span><span class="kv-val">${escapeHtml(String(Object.values(discovery.key_pages || {}).filter(Boolean).length))} ${escapeHtml(tx(lang, '页', 'pages'))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '首页引用得分', 'Homepage citability'))}</span><span class="kv-val">${escapeHtml(String(homepageCitability.score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '最佳引用页', 'Best citation page'))}</span><span class="kv-val">${escapeHtml(bestPageCitability.page_key || 'homepage')} / ${escapeHtml(String(bestPageCitability.score ?? 0))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '抓取与实体信号', 'Crawl and Entity Signals'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">robots.txt</span><span class="kv-val">${formatBool(discovery.robots?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))}</span></div><div class="kv-row"><span class="kv-key">llms.txt / ${escapeHtml(tx(lang, '有效性', 'Quality'))}</span><span class="kv-val">${formatBool(discovery.llms?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))} / ${escapeHtml(String(visibility.findings?.llms_quality?.score ?? discovery.llms?.effectiveness_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">Sitemap / Semrush AS</span><span class="kv-val">${formatBool(discovery.sitemap?.exists, tx(lang, '存在', 'Present'), tx(lang, '缺失', 'Missing'))} / ${escapeHtml(String(discovery.backlinks?.authority_score ?? tx(lang, '未接入', 'Unavailable')))}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '公司名 / 电话', 'Company / Phone'))}</span><span class="kv-val">${formatBool(discovery.site_signals?.company_name_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.phone_detected, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '地址 / 邮箱 / sameAs', 'Address / Email / sameAs'))}</span><span class="kv-val">${formatBool(discovery.site_signals?.address_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.email_detected, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(discovery.site_signals?.same_as_detected, labels.pageFaqYes, labels.pageFaqNo)}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '技术与结构化快照', 'Technical and Structured Snapshot'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '安全头得分', 'Security headers score'))}</span><span class="kv-val">${escapeHtml(String(technical.findings?.security_headers_score ?? 0))}</span></div><div class="kv-row"><span class="kv-key">SSR / ${escapeHtml(tx(lang, '性能', 'Performance'))}</span><span class="kv-val">${escapeHtml(technical.findings?.ssr_classification || '-')} / ${escapeHtml(technical.findings?.performance_classification || technical.checks?.performance?.classification || '-')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '图片 lazyload / 尺寸', 'Image lazyload / dimensions'))}</span><span class="kv-val">${escapeHtml(String(technical.checks?.image_optimization?.lazyload_ratio ?? 0))} / ${escapeHtml(String(technical.checks?.image_optimization?.dimension_ratio ?? 0))}</span></div><div class="kv-row"><span class="kv-key">Open Graph / Twitter Card</span><span class="kv-val">${formatBool(technical.checks?.open_graph, labels.pageFaqYes, labels.pageFaqNo)} / ${formatBool(technical.checks?.twitter_card, labels.pageFaqYes, labels.pageFaqNo)}</span></div><div class="kv-row"><span class="kv-key">Schema / sameAs</span><span class="kv-val">${escapeHtml(String(schema.findings?.schema_type_count ?? 0))} / ${escapeHtml(String(schema.findings?.same_as_count ?? 0))}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '引用与平台证据', 'Citation and Platform Evidence'))}</h5><div class="kv-list"><div class="kv-row"><span class="kv-key">${escapeHtml(labels.citationProbability)}</span><span class="kv-val">${escapeHtml(citationLabelMap[citationProbability] || citationProbability)}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '最佳页类型', 'Best page type'))}</span><span class="kv-val">${escapeHtml(bestPageCitability.page_type || bestPageCitability.page_key || 'homepage')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(labels.bestWeakestPlatform)}</span><span class="kv-val">${escapeHtml(PLATFORM_LABELS[strongestPlatform?.[0]] || '-')} / ${escapeHtml(PLATFORM_LABELS[weakestPlatform?.[0]] || '-')}</span></div><div class="kv-row"><span class="kv-key">Observation</span><span class="kv-val">${observation.provided ? tx(lang, '已上传，不计分', 'Uploaded, unscored') : tx(lang, '未上传', 'Not uploaded')}</span></div><div class="kv-row"><span class="kv-key">${escapeHtml(tx(lang, '输入范围', 'Input Scope'))}</span><span class="kv-val">${discovery.input_is_likely_homepage === false ? tx(lang, '非首页，可能偏差', 'Non-homepage, may be biased') : tx(lang, '首页/语言首页', 'Homepage/locale homepage')}</span></div></div></div>
          <div class="evidence-card"><h5>${escapeHtml(tx(lang, '关键页面与内容采样', 'Key Pages and Content Samples'))}</h5><div class="kv-list" style="margin-bottom:10px">${formatKeyPages(discovery.key_pages || {}, lang)}</div><div class="page-samples">${pageSampleHtml}</div></div>
        </div>
      </div>
    </section>

    <section class="report-section">
      <div class="report-section-hdr"><h4>${escapeHtml(labels.notesTitle)}</h4><span>${escapeHtml(labels.notesSubtitle)}</span></div>
      <div class="report-section-body"><div class="report-note-box">${escapeHtml(noteText)}</div></div>
    </section>
  `;
  host.innerHTML = html;
  setCachedReportHtml(task, lang, html);
}

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
    currentTask = task || null;
    currentTaskId     = task.task_id || null;
    currentTaskStatus = task.status  || 'idle';
    if (task.feedback_lang && $('feedback-lang').value !== task.feedback_lang) {
      $('feedback-lang').value = task.feedback_lang;
    }
    const shortId = task.task_id ? task.task_id.slice(0, 10) + '…' : '—';
    $('task-id').textContent     = shortId;
    $('current-step').textContent = task.current_step || '—';
    const pct = task.progress_percent || 0;
    $('progress').textContent   = `${pct}%`;
    $('prog-fill').style.width  = `${pct}%`;
    $('cached-flag').textContent = task.cached ? '是 ✓' : '否';
    $('llm-model-used-flag').textContent = task.llm_model_used ? '是 ✓' : '否';
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

    const summaryEl = $('summary-text');
    summaryEl.textContent = '任务已创建，等待后台返回各阶段结果……';
    summaryEl.classList.add('placeholder');
    summaryEl.className = 'report-empty placeholder';
    summaryEl.innerHTML = '任务已创建，等待后台返回各阶段结果……<br />报告将在结果完成后自动生成。';
    $('llm-notes').textContent = '等待会员增强状态。';
    $('json-output').textContent = '{}';
    $('export-btn').disabled = true;
    renderTimeline({});

    const mode = $('mode').value;
    const body = {
      url: $('url').value.trim(),
      mode,
      force_refresh: $('force').checked,
      full_audit: $('full-audit').checked,
      feedback_lang: $('feedback-lang').value
    };
    if ($('full-audit').checked) {
      body.max_pages = Number($('max-pages').value || 12);
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
    window.open(`/api/v1/tasks/${currentTaskId}/report`, '_blank');
  });

  $('mode').addEventListener('change', () => {
    const isPremium = $('mode').value === 'premium';
    $('model').disabled = !isPremium;
    $('model').style.opacity = isPremium ? '1' : '0.45';
  });
  $('feedback-lang').addEventListener('change', () => {
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
  renderTimeline({});
</script>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
async def demo_page() -> HTMLResponse:
    """返回内置的 GEO 审计交互控制台页面

    该页面是一个完整的单页应用（SPA），内嵌在 Python 字符串 HTML 中，
    无需额外静态文件服务。提供以下功能：
    - 输入 URL 触发全量 GEO 审计（调用 /api/v1/tasks/audit）
    - 实时轮询任务进度（步骤时间线展示）
    - 展示各模块审计分数和详情（可折叠卡片）
    - 报告导出和调试面板

    Returns:
        HTMLResponse：包含完整前端界面的 HTML 文档
    """
    return HTMLResponse(HTML)
