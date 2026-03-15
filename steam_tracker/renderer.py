"""HTML renderer: turns a list of GameRecords into a self-contained page."""
from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .models import GameRecord, NewsItem

if TYPE_CHECKING:
    from .i18n import Translator

# ─── Shared JavaScript (injected into both HTML templates) ───────────────────
_SHARED_JS = """\
// --- Shared utilities ---
function checkPtFilter(pt, el) {
  if (pt === 'all') return true;
  const p = parseInt(el.dataset.playtime) || 0;
  if (pt === '0')   return p === 0;
  if (pt === '60')  return p > 0 && p < 60;
  if (pt === '600') return p >= 60 && p <= 600;
  if (pt === '601') return p > 600;
  return true;
}

function checkRecentFilter(recent, el) {
  if (recent === 'all') return true;
  const ts = parseInt(el.dataset.lastPatchTs) || 0;
  if (ts === 0) return false;
  const days = parseInt(recent);
  return ts * 1000 > Date.now() - days * 86400000;
}

function activateBtn(selector, dataAttr, value) {
  let found = false;
  document.querySelectorAll(selector).forEach(b => {
    const match = b.dataset[dataAttr] === value;
    b.classList.toggle('active', match);
    if (match) found = true;
  });
  if (!found) { const first = document.querySelector(selector); if (first) first.classList.add('active'); }
}

function updateResetBtn() {
  document.getElementById('resetBtn').classList.toggle('show', !isDefaultState());
  updateFilterBadge();
}

// Filter panel toggle
document.getElementById('filtersToggle').addEventListener('click', () => {
  document.getElementById('toolbarFilters').classList.toggle('open');
});

// Scroll-to-top
const scrollBtn = document.getElementById('scrollTop');
window.addEventListener('scroll', () => {
  scrollBtn.classList.toggle('visible', window.scrollY > 400);
}, {passive: true});
scrollBtn.addEventListener('click', () => {
  window.scrollTo({top: 0, behavior: 'smooth'});
});

// Theme toggle
const themeBtn = document.getElementById('themeToggle');
function applyTheme(light) {
  document.documentElement.classList.toggle('light', light);
  themeBtn.textContent = light ? '🌙' : '☀️';
  try { localStorage.setItem('sp-theme', light ? 'light' : 'dark'); } catch(e) {}
}
themeBtn.addEventListener('click', () => {
  applyTheme(!document.documentElement.classList.contains('light'));
});
try { if (localStorage.getItem('sp-theme') === 'light') applyTheme(true); } catch(e) {}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
    if (e.key === 'Escape') { e.target.blur(); document.getElementById('resetBtn').click(); }
    return;
  }
  if (e.key === '/' || (e.ctrlKey && e.key === 'k')) {
    e.preventDefault();
    document.getElementById('search').focus();
  }
  if (e.key === 'Escape') {
    document.getElementById('resetBtn').click();
  }
});"""

# ─── HTML Template ────────────────────────────────────────────────────────────
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="__T_html_lang__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SteamPulse</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:        #0a0e14;
    --surface:   #111722;
    --surface2:  #1a2233;
    --border:    #1f2d45;
    --accent:    #1db9ff;
    --accent2:   #00e5b0;
    --text:      #c8d8ef;
    --muted:     #5a7199;
    --ea:        #f5a623;
    --released:  #3dd68c;
    --unreleased:#7b7fff;
    --unknown:   #5a7199;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    min-height: 100vh;
  }

  /* HEADER */
  header {
    background: linear-gradient(180deg, #0d1a2e 0%, transparent 100%);
    border-bottom: 1px solid var(--border);
    padding: 28px 40px 20px;
    display: flex;
    align-items: center;
    gap: 20px;
  }
  header svg { flex-shrink: 0; }
  .header-text h1 {
    font-family: 'Rajdhani', sans-serif;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 2px;
    color: #fff;
    text-transform: uppercase;
  }
  .header-text p {
    color: var(--muted);
    font-size: 12px;
    margin-top: 2px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .header-stats {
    margin-left: auto;
    display: flex;
    gap: 28px;
    text-align: center;
  }
  .stat-val {
    font-family: 'Rajdhani', sans-serif;
    font-size: 26px;
    font-weight: 700;
    color: var(--accent);
    line-height: 1;
  }
  .stat-lbl {
    font-size: 10px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-top: 3px;
  }

  /* TOOLBAR */
  .toolbar {
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    position: sticky;
    top: 0;
    z-index: 100;
  }
  .toolbar-main {
    padding: 11px 40px;
    display: flex;
    gap: 10px;
    align-items: center;
    flex-wrap: wrap;
  }
  .toolbar-filters {
    display: none;
    gap: 16px 28px;
    flex-wrap: wrap;
    padding: 14px 40px 18px;
    border-top: 1px solid var(--border);
    background: rgba(0,0,0,.14);
  }
  .toolbar-filters.open { display: flex; }
  .filter-group { display: flex; flex-direction: column; gap: 6px; }
  .filter-group-label {
    font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
  }
  .filter-toggle-btn {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    cursor: pointer;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
  }
  .filter-toggle-btn:hover { border-color: var(--accent); color: var(--accent); }
  .filter-toggle-btn.has-active { border-color: var(--accent); color: var(--accent); background: rgba(29,185,255,.1); }
  .filter-badge {
    display: none;
    align-items: center;
    justify-content: center;
    min-width: 16px; height: 16px;
    border-radius: 8px;
    background: var(--accent);
    color: #000;
    font-size: 10px;
    font-weight: 700;
    padding: 0 4px;
  }
  .filter-badge.show { display: inline-flex; }
  .search-wrap {
    position: relative;
    flex: 1;
    min-width: 200px;
    max-width: 340px;
  }
  .search-wrap input {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px 8px 36px;
    border-radius: 6px;
    font-size: 13px;
    outline: none;
    transition: border-color .2s;
    font-family: inherit;
  }
  .search-wrap input:focus { border-color: var(--accent); }
  .search-wrap .icon {
    position: absolute;
    left: 11px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--muted);
    pointer-events: none;
  }
  select {
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
    outline: none;
    cursor: pointer;
    font-family: inherit;
  }
  select:focus { border-color: var(--accent); }
  .filter-btns { display: flex; gap: 6px; }
  .filter-btn {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    cursor: pointer;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
  }
  .filter-btn:hover { border-color: var(--accent); color: var(--accent); }
  .filter-btn.active { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }
  .tag-btn {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    cursor: pointer;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
  }
  .tag-btn:hover { border-color: var(--accent); color: var(--accent); }
  .tag-btn.active { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }
  .count-label {
    margin-left: auto;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 12px;
    color: var(--muted);
  }
  .nav-link {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 12px;
    text-decoration: none;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
  }
  .nav-link:hover { border-color: var(--accent); color: var(--accent); }

  /* GRID */
  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
    padding: 24px 40px;
  }

  /* CARD */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    transition: transform .18s, border-color .18s, box-shadow .18s;
    cursor: pointer;
  }
  .card:hover {
    transform: translateY(-2px);
    border-color: #2a3f60;
    box-shadow: 0 8px 32px rgba(0,0,0,.4);
  }
  .card-img {
    width: 100%;
    height: 80px;
    object-fit: cover;
    display: block;
    background: var(--surface2);
  }
  .card-img-placeholder {
    width: 100%;
    height: 80px;
    background: linear-gradient(135deg, #0d1a2e, #1a2a45);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .card-body { padding: 14px 16px; }
  .card-top {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin-bottom: 10px;
  }
  .card-title {
    font-family: 'Rajdhani', sans-serif;
    font-size: 17px;
    font-weight: 600;
    color: #fff;
    line-height: 1.2;
    flex: 1;
  }
  .badge {
    flex-shrink: 0;
    padding: 3px 9px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
    text-transform: uppercase;
  }
  .badge-earlyaccess { background: rgba(245,166,35,.15); color: var(--ea); border: 1px solid rgba(245,166,35,.3); }
  .badge-released    { background: rgba(61,214,140,.12); color: var(--released); border: 1px solid rgba(61,214,140,.25); }
  .badge-unreleased  { background: rgba(123,127,255,.12); color: var(--unreleased); border: 1px solid rgba(123,127,255,.25); }
  .badge-unknown     { background: rgba(90,113,153,.12); color: var(--unknown); border: 1px solid rgba(90,113,153,.25); }

  .card-meta {
    display: flex;
    gap: 18px;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 10px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .card-meta span { display: flex; align-items: center; gap: 4px; }

  /* NEWS TIMELINE */
  .news-section { border-top: 1px solid var(--border); margin-top: 4px; padding-top: 10px; }
  .news-title {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--muted);
    margin-bottom: 8px;
    font-family: 'IBM Plex Mono', monospace;
  }
  .news-list { display: none; }
  .card.expanded .news-list { display: block; }
  .card.expanded .news-toggle-icon { transform: rotate(180deg); }

  .news-toggle {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
  }
  .news-toggle-icon {
    transition: transform .2s;
    color: var(--muted);
  }
  .news-item {
    display: flex;
    gap: 10px;
    align-items: flex-start;
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
  }
  .news-item:last-child { border-bottom: none; }
  .news-date {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    white-space: nowrap;
    min-width: 68px;
    padding-top: 2px;
  }
  .news-item-title {
    font-size: 12px;
    color: var(--text);
    line-height: 1.4;
  }
  .news-item-title a {
    color: inherit;
    text-decoration: none;
  }
  .news-item-title a:hover { color: var(--accent); }
  .no-news {
    font-size: 12px;
    color: var(--muted);
    font-style: italic;
  }

  /* GENRE / PLATFORM TAGS */
  .genre-tags { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 9px; }
  .genre-tag {
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
    background: rgba(29,185,255,.1);
    color: var(--accent);
    border: 1px solid rgba(29,185,255,.2);
    letter-spacing: .3px;
  }

  .card-detail {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11px;
    color: var(--muted);
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .dev-name { font-style: italic; }
  .platform-icons { letter-spacing: 2px; font-size: 12px; }
  .price-tag { color: var(--accent2); font-family: 'IBM Plex Mono', monospace; font-size: 11px; }
  .price-free { color: var(--released); font-family: 'IBM Plex Mono', monospace; font-size: 11px; }
  .price-discount { text-decoration: line-through; margin-right: 4px; opacity: .6; }
  .metacritic-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    font-weight: 600;
  }
  .mc-green  { background: rgba(61,214,140,.15); color: var(--released); border: 1px solid rgba(61,214,140,.3); }
  .mc-yellow { background: rgba(245,166,35,.15); color: var(--ea); border: 1px solid rgba(245,166,35,.3); }
  .mc-red    { background: rgba(255,80,80,.15); color: #ff6b6b; border: 1px solid rgba(255,80,80,.3); }

  /* EMPTY */
  .empty {
    grid-column: 1/-1;
    text-align: center;
    padding: 80px 0;
    color: var(--muted);
  }
  .empty p { margin-top: 10px; font-size: 13px; }

  /* FOOTER */
  footer {
    text-align: center;
    padding: 20px;
    color: var(--muted);
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    border-top: 1px solid var(--border);
    margin-top: 10px;
  }

  /* SCROLL TO TOP */
  .scroll-top {
    position: fixed; bottom: 28px; right: 28px; z-index: 200;
    width: 42px; height: 42px; border-radius: 50%;
    background: var(--accent); color: #000; border: none;
    font-size: 20px; cursor: pointer;
    opacity: 0; pointer-events: none;
    transition: opacity .3s, transform .3s;
    transform: translateY(10px);
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
    display: flex; align-items: center; justify-content: center;
  }
  .scroll-top.visible { opacity: 1; pointer-events: auto; transform: translateY(0); }
  .scroll-top:hover { transform: translateY(-2px); box-shadow: 0 6px 24px rgba(29,185,255,.3); }

  /* CARD ANIMATION */
  .card {
    transition: transform .18s, border-color .18s, box-shadow .18s, opacity .25s;
  }
  .card.fade-in { animation: fadeIn .25s ease-out; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

  /* COL wrappers — transparent in grid mode */
  .col-title, .col-detail, .col-genres, .col-meta {
    display: contents;
  }
  .grid.list-view .col-title,
  .grid.list-view .col-detail,
  .grid.list-view .col-genres,
  .grid.list-view .col-meta {
    display: block;
  }

  /* LIST VIEW */
  .grid.list-view {
    grid-template-columns: 1fr;
    gap: 4px;
  }
  .grid.list-view .card {
    display: flex;
    flex-direction: row;
    align-items: stretch;
  }
  .grid.list-view .card-img {
    width: 120px;
    height: auto;
    min-height: 56px;
    border-radius: 10px 0 0 10px;
    flex-shrink: 0;
  }
  .grid.list-view .card-img-placeholder {
    width: 120px;
    height: auto;
    min-height: 56px;
    border-radius: 10px 0 0 10px;
    flex-shrink: 0;
  }
  .grid.list-view .card-body {
    display: flex;
    flex-direction: row;
    align-items: center;
    gap: 0;
    flex: 1;
    padding: 0;
    flex-wrap: nowrap;
    overflow: hidden;
  }
  /* Table columns in list view (wide screens) */
  .grid.list-view .col-title   { flex: 0 0 260px; min-width: 0; padding: 8px 12px; overflow: hidden; }
  .grid.list-view .col-detail  { flex: 0 0 220px; min-width: 0; padding: 8px 12px; overflow: hidden; border-left: 1px solid var(--border); }
  .grid.list-view .col-genres  { flex: 0 0 160px; min-width: 0; padding: 8px 12px; overflow: hidden; border-left: 1px solid var(--border); }
  .grid.list-view .col-meta    { flex: 1; min-width: 0; padding: 8px 12px; overflow: hidden; border-left: 1px solid var(--border); }
  .grid.list-view .card-top    { margin-bottom: 0; }
  .grid.list-view .card-detail { margin-bottom: 0; font-size: 11px; }
  .grid.list-view .genre-tags  { margin-bottom: 0; }
  .grid.list-view .card-meta   { margin-bottom: 0; flex-wrap: wrap; gap: 6px; }
  .grid.list-view .news-section { display: none; }
  .grid.list-view .card-ext-hint { display: none; }
  /* Table header row */
  .list-header {
    display: none;
    border-radius: 6px;
    background: var(--surface2);
    border: 1px solid var(--border);
    font-size: 10px;
    font-family: 'IBM Plex Mono', monospace;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 0 40px 4px;
  }
  .list-header.visible { display: flex; }
  .list-header-img   { flex: 0 0 120px; padding: 6px 12px; }
  .list-header-title { flex: 0 0 260px; padding: 6px 12px; }
  .list-header-detail{ flex: 0 0 220px; padding: 6px 12px; border-left: 1px solid var(--border); }
  .list-header-genres{ flex: 0 0 160px; padding: 6px 12px; border-left: 1px solid var(--border); }
  .list-header-meta  { flex: 1; padding: 6px 12px; border-left: 1px solid var(--border); }

  /* RESET BUTTON */
  .reset-btn {
    padding: 6px 12px;
    border-radius: 20px;
    border: 1px solid rgba(255,80,80,.3);
    background: transparent;
    color: #ff6b6b;
    font-size: 12px;
    cursor: pointer;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
    display: none;
  }
  .reset-btn.show { display: inline-flex; align-items: center; gap: 4px; }
  .reset-btn:hover { background: rgba(255,80,80,.12); border-color: #ff6b6b; }

  /* VIEW TOGGLE */
  .view-toggle {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    cursor: pointer;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
  }
  .view-toggle:hover { border-color: var(--accent); color: var(--accent); }

  /* CARD EXTERNAL LINK HINT */
  .card-ext-hint {
    position: absolute; top: 8px; right: 8px;
    background: rgba(0,0,0,.65); border-radius: 4px;
    padding: 2px 6px; font-size: 10px; color: var(--muted);
    opacity: 0; transition: opacity .2s;
    pointer-events: none;
    font-family: 'IBM Plex Mono', monospace;
  }
  .card:hover .card-ext-hint { opacity: 1; }
  .card { position: relative; }

  /* CONTENT VISIBILITY PERF */
  .card { content-visibility: auto; contain-intrinsic-size: 340px 320px; will-change: transform; }
  .grid.list-view .card { contain-intrinsic-size: auto 56px; }

  /* PLAYTIME FILTER */
  .source-btn {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    background: transparent;
    color: var(--muted);
    font-size: 12px;
    cursor: pointer;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
  }
  .source-btn:hover { border-color: var(--accent); color: var(--accent); }
  .source-btn.active { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }

  /* THEME TOGGLE */
  .theme-toggle {
    position: fixed; bottom: 28px; left: 28px; z-index: 200;
    width: 38px; height: 38px; border-radius: 50%;
    background: var(--surface); border: 1px solid var(--border);
    color: var(--muted); font-size: 16px; cursor: pointer;
    transition: all .2s;
    display: flex; align-items: center; justify-content: center;
  }
  .theme-toggle:hover { border-color: var(--accent); color: var(--accent); }

  /* LIGHT THEME */
  html.light {
    --bg: #f0f2f5;
    --surface: #ffffff;
    --surface2: #e8ecf1;
    --border: #d0d7e0;
    --accent: #0a7cc4;
    --accent2: #00a87d;
    --text: #2c3e50;
    --muted: #6c7a8a;
    --ea: #d4850a;
    --released: #1a9960;
    --unreleased: #5b5fe0;
    --unknown: #6c7a8a;
  }
  html.light .card { box-shadow: 0 1px 4px rgba(0,0,0,.08); }
  html.light .scroll-top { box-shadow: 0 4px 16px rgba(0,0,0,.15); }
  html.light header { background: linear-gradient(180deg, #dfe6ee 0%, transparent 100%); }
  html.light .card-title, html.light .feed-game-name { color: #1a2530; }
  html.light .header-text h1 { color: #1a2530; }

  /* KEYBOARD HINT */
  .kbd-hint {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 10px;
    color: var(--muted);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1px 5px;
    margin-left: 4px;
    opacity: .6;
  }

  /* TABLE VIEW — wide screens only */
  @media (max-width: 1099px) {
    /* Compact list on narrow: revert to flex-wrap */
    .grid.list-view .card-body { flex-wrap: wrap; padding: 8px 12px; gap: 10px; }
    .grid.list-view .col-title,
    .grid.list-view .col-detail,
    .grid.list-view .col-genres,
    .grid.list-view .col-meta { flex: unset; border-left: none; padding: 0; }
    .grid.list-view .col-title { flex: 1 1 180px; }
    .grid.list-view .col-meta  { flex: 0 0 100%; }
    .list-header { display: none !important; }
  }
  @media (max-width: 900px) {
    .header-stats { gap: 14px; }
    .grid { grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
  }
  @media (max-width: 600px) {
    header, .toolbar-main, .toolbar-filters, .grid { padding-left: 16px; padding-right: 16px; }
    .header-stats { gap: 10px; flex-wrap: wrap; justify-content: center; }
    .stat-val { font-size: 20px; }
    .grid { grid-template-columns: 1fr; }
    .toolbar-main { gap: 8px; }
    .search-wrap { max-width: 100%; }
    .grid.list-view .card-img { width: 80px; }
    .scroll-top { bottom: 16px; right: 16px; }
    .theme-toggle { bottom: 16px; left: 16px; }
  }
</style>
</head>
<body>

<header>
  <svg width="44" height="44" viewBox="0 0 44 44" fill="none">
    <circle cx="22" cy="22" r="21" stroke="#1db9ff" stroke-width="1.5" opacity=".4"/>
    <circle cx="22" cy="22" r="10" fill="#1db9ff" opacity=".15"/>
    <circle cx="22" cy="22" r="5" fill="#1db9ff"/>
    <circle cx="22" cy="7"  r="2.5" fill="#1db9ff" opacity=".7"/>
    <circle cx="35" cy="29" r="2.5" fill="#1db9ff" opacity=".7"/>
    <circle cx="9"  cy="29" r="2.5" fill="#1db9ff" opacity=".7"/>
  </svg>
  <div class="header-text">
    <h1>SteamPulse</h1>
    <p>__T_generated_at__ __GENERATED_AT__ · SteamID __STEAM_ID__</p>
  </div>
  <div class="header-stats">
    <div>
      <div class="stat-val">__TOTAL__</div>
      <div class="stat-lbl">__T_stat_total__</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--ea)">__EA__</div>
      <div class="stat-lbl">Early Access</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--released)">__REL__</div>
      <div class="stat-lbl">__T_stat_released__</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--unreleased)">__UNREL__</div>
      <div class="stat-lbl">__T_stat_unreleased__</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--accent2)">__PLAYTIME__</div>
      <div class="stat-lbl">__T_stat_hours__</div>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-main">
    <div class="search-wrap">
      <span class="icon">⌕</span>
      <input type="text" id="search" placeholder="__T_search_placeholder__">
    </div>
    <select id="sortBy">
      <option value="name">__T_sort_name_asc__</option>
      <option value="name_desc">__T_sort_name_desc__</option>
      <option value="playtime">__T_sort_playtime__</option>
      <option value="release">__T_sort_release__</option>
      <option value="lastupdate">__T_sort_lastupdate__</option>
      <option value="metacritic">__T_sort_metacritic__</option>
    </select>
    <button class="filter-toggle-btn" id="filtersToggle" title="__T_title_btn_filters__">⚙ __T_btn_filters__<span class="filter-badge" id="filterBadge"></span></button>
    <button class="reset-btn" id="resetBtn" title="__T_title_btn_reset__">✕ __T_btn_reset__</button>
    <button class="view-toggle" id="viewToggle" title="__T_title_view_toggle__">☰ __T_btn_list_view__</button>
    <span class="count-label" id="countLabel"></span>
    <a class="nav-link" href="__NEWS_HREF__">🗞 __T_link_news__</a>
  </div>
  <div class="toolbar-filters" id="toolbarFilters">
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_status__</div>
      <div class="filter-btns" id="filterBtns">
        <button class="filter-btn active" data-filter="all">__T_lbl_all__</button>
        <button class="filter-btn" data-filter="earlyaccess">Early Access</button>
        <button class="filter-btn" data-filter="released">__T_lbl_released__</button>
        <button class="filter-btn" data-filter="unreleased">__T_lbl_upcoming__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_source__</div>
      <div class="filter-btns" id="sourceBtns">
        <button class="source-btn active" data-source="all">🎮 __T_lbl_all__</button>
        <button class="source-btn" data-source="owned">__T_lbl_owned__</button>
        <button class="source-btn" data-source="wishlist">🎁 Wishlist</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_news_type__</div>
      <div class="filter-btns" id="tagBtns">
        <button class="tag-btn active" data-tag="all">__T_lbl_all_types__</button>
        <button class="tag-btn" data-tag="patchnotes">📋 Patch notes</button>
        <button class="tag-btn" data-tag="other">📰 News</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_playtime__</div>
      <div class="filter-btns" id="playtimeBtns">
        <button class="filter-btn active" data-pt="all">__T_lbl_all__</button>
        <button class="filter-btn" data-pt="0">__T_lbl_never_played__</button>
        <button class="filter-btn" data-pt="60">< 1h</button>
        <button class="filter-btn" data-pt="600">1-10h</button>
        <button class="filter-btn" data-pt="601">> 10h</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_metacritic__</div>
      <div class="filter-btns" id="mcBtns">
        <button class="filter-btn active" data-mc="all">__T_lbl_all__</button>
        <button class="filter-btn" data-mc="none">__T_lbl_no_score__</button>
        <button class="filter-btn" data-mc="bad">< 50</button>
        <button class="filter-btn" data-mc="mid">50–75</button>
        <button class="filter-btn" data-mc="good">> 75</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_recent__</div>
      <div class="filter-btns" id="recentBtns">
        <button class="filter-btn active" data-recent="all">__T_lbl_all__</button>
        <button class="filter-btn" data-recent="2">__T_lbl_2_days__</button>
        <button class="filter-btn" data-recent="5">__T_lbl_5_days__</button>
        <button class="filter-btn" data-recent="15">__T_lbl_15_days__</button>
        <button class="filter-btn" data-recent="30">__T_lbl_30_days__</button>
      </div>
    </div>
  </div>
</div>

<div class="list-header" id="listHeader">
  <div class="list-header-img"></div>
  <div class="list-header-title">__T_col_game__</div>
  <div class="list-header-detail">__T_col_dev_score__</div>
  <div class="list-header-genres">Genres</div>
  <div class="list-header-meta">__T_col_playtime_date__</div>
</div>
<div class="grid" id="grid">
__CARDS__
</div>

<footer>__T_footer__</footer>

<button class="scroll-top" id="scrollTop" title="__T_title_scroll_top__">↑</button>
<button class="theme-toggle" id="themeToggle" title="__T_title_theme__">🌙</button>

<script>
__I18N_JS__
const allCards = Array.from(document.querySelectorAll('.card'));
__SHARED_JS__
function getFilter()    { return document.querySelector('#filterBtns .filter-btn.active').dataset.filter; }
function getSrcFilter() { return document.querySelector('#sourceBtns .source-btn.active').dataset.source; }
function getTagFilter() { return document.querySelector('#tagBtns .tag-btn.active').dataset.tag; }
function getPtFilter()  { return document.querySelector('#playtimeBtns .filter-btn.active').dataset.pt; }
function getMcFilter()  { return document.querySelector('#mcBtns .filter-btn.active').dataset.mc; }
function getRecentFilter() { return document.querySelector('#recentBtns .filter-btn.active').dataset.recent; }
function getSearch()    { return document.getElementById('search').value.toLowerCase().trim(); }
function getSort()      { return document.getElementById('sortBy').value; }

function checkMcFilter(mc, card) {
  if (mc === 'all') return true;
  const s = parseInt(card.dataset.metacritic) || 0;
  if (mc === 'none') return s <= 0;
  if (mc === 'bad')  return s > 0 && s < 50;
  if (mc === 'mid')  return s >= 50 && s <= 75;
  if (mc === 'good') return s > 75;
  return true;
}

function isDefaultState() {
  return getFilter() === 'all' && getSrcFilter() === 'all' && getTagFilter() === 'all'
    && getPtFilter() === 'all' && getMcFilter() === 'all' && getRecentFilter() === 'all'
    && !getSearch() && getSort() === 'name';
}

function updateFilterBadge() {
  let n = 0;
  if (getFilter() !== 'all')       n++;
  if (getSrcFilter() !== 'all')    n++;
  if (getTagFilter() !== 'all')    n++;
  if (getPtFilter() !== 'all')     n++;
  if (getMcFilter() !== 'all')     n++;
  if (getRecentFilter() !== 'all') n++;
  const badge = document.getElementById('filterBadge');
  badge.textContent = n;
  badge.classList.toggle('show', n > 0);
  document.getElementById('filtersToggle').classList.toggle('has-active', n > 0);
}

function saveStateToHash() {
  const s = {};
  if (getFilter() !== 'all')    s.status = getFilter();
  if (getSrcFilter() !== 'all') s.source = getSrcFilter();
  if (getTagFilter() !== 'all') s.tag = getTagFilter();
  if (getPtFilter() !== 'all')  s.pt = getPtFilter();
  if (getMcFilter() !== 'all')    s.mc = getMcFilter();
  if (getRecentFilter() !== 'all') s.recent = getRecentFilter();
  if (getSearch())                 s.q = getSearch();
  if (getSort() !== 'name')     s.sort = getSort();
  const grid = document.getElementById('grid');
  if (grid.classList.contains('list-view')) s.view = 'list';
  const h = new URLSearchParams(s).toString();
  history.replaceState(null, '', h ? '#' + h : location.pathname);
  // Persist view mode for page refresh
  try {
    const shared = grid.classList.contains('list-view') ? {view: 'list'} : {};
    localStorage.setItem('sp-shared', JSON.stringify(shared));
  } catch(e) {}
  // Update nav link to carry compatible filters to news page
  const navLink = document.querySelector('.nav-link[href^="steam_news"]');
  if (navLink) {
    const nf = {};
    if (getFilter() !== 'all')       nf.status = getFilter();
    if (getSrcFilter() !== 'all')    nf.source = getSrcFilter();
    if (getTagFilter() !== 'all')    nf.tag = getTagFilter();
    if (getRecentFilter() !== 'all') nf.recent = getRecentFilter();
    const nh = new URLSearchParams(nf).toString();
    navLink.href = 'steam_news.html' + (nh ? '#' + nh : '');
  }
}

function loadStateFromHash() {
  // Restore cross-page shared state (view mode) from localStorage if no hash
  try {
    const shared = JSON.parse(localStorage.getItem('sp-shared') || '{}');
    if (!location.hash && shared.view === 'list') {
      document.getElementById('grid').classList.add('list-view');
      document.getElementById('viewToggle').textContent = '⊞ ' + I18N.grid_view;
      document.getElementById('listHeader').classList.add('visible');
    }
  } catch(e) {}
  const h = location.hash.slice(1);
  if (!h) return;
  const p = new URLSearchParams(h);
  if (p.get('status')) { activateBtn('#filterBtns .filter-btn', 'filter', p.get('status')); }
  if (p.get('source')) { activateBtn('#sourceBtns .source-btn', 'source', p.get('source')); }
  if (p.get('tag'))    { activateBtn('#tagBtns .tag-btn', 'tag', p.get('tag')); }
  if (p.get('pt'))     { activateBtn('#playtimeBtns .filter-btn', 'pt', p.get('pt')); }
  if (p.get('mc'))     { activateBtn('#mcBtns .filter-btn', 'mc', p.get('mc')); }
  if (p.get('recent')) { activateBtn('#recentBtns .filter-btn', 'recent', p.get('recent')); }
  if (p.get('q'))      { document.getElementById('search').value = p.get('q'); }
  if (p.get('sort'))   { document.getElementById('sortBy').value = p.get('sort'); }
  if (p.get('view') === 'list') {
    document.getElementById('grid').classList.add('list-view');
    document.getElementById('viewToggle').textContent = '⊞ ' + I18N.grid_view;
    document.getElementById('listHeader').classList.add('visible');
  }
  // Auto-open filter panel if any filter is active
  if (!isDefaultState()) {
    document.getElementById('toolbarFilters').classList.add('open');
  }
}

function updateGrid() {
  const filter    = getFilter();
  const srcFilter = getSrcFilter();
  const tagFilter = getTagFilter();
  const ptFilter  = getPtFilter();
  const search    = getSearch();
  const sort      = getSort();

  const mcFilter     = getMcFilter();
  const recentFilter  = getRecentFilter();
  let visible = allCards.filter(c => {
    const badgeOk   = filter === 'all' || c.dataset.status === filter;
    const srcOk     = srcFilter === 'all' || c.dataset.source === srcFilter;
    const searchOk  = !search || c.dataset.name.includes(search);
    const ptOk      = checkPtFilter(ptFilter, c);
    const mcOk      = checkMcFilter(mcFilter, c);
    const recentOk  = checkRecentFilter(recentFilter, c);
    return badgeOk && srcOk && searchOk && ptOk && mcOk && recentOk;
  });

  visible.sort((a, b) => {
    if (sort === 'name')       return a.dataset.name.localeCompare(b.dataset.name);
    if (sort === 'name_desc')  return b.dataset.name.localeCompare(a.dataset.name);
    if (sort === 'playtime')   return parseInt(b.dataset.playtime) - parseInt(a.dataset.playtime);
    if (sort === 'release')    return parseInt(b.dataset.releaseTs) - parseInt(a.dataset.releaseTs);
    if (sort === 'metacritic') return parseInt(b.dataset.metacritic || 0) - parseInt(a.dataset.metacritic || 0);
    if (sort === 'lastupdate') {
      const tsA = tagFilter === 'patchnotes' ? parseInt(a.dataset.lastPatchTs) || 0
                : tagFilter === 'other'      ? parseInt(a.dataset.lastOtherTs) || 0
                : parseInt(a.dataset.lastUpdate) || 0;
      const tsB = tagFilter === 'patchnotes' ? parseInt(b.dataset.lastPatchTs) || 0
                : tagFilter === 'other'      ? parseInt(b.dataset.lastOtherTs) || 0
                : parseInt(b.dataset.lastUpdate) || 0;
      return tsB - tsA;
    }
    return 0;
  });

  const grid = document.getElementById('grid');
  allCards.forEach(c => c.style.display = 'none');
  const frag = document.createDocumentFragment();
  visible.forEach(c => {
    c.style.display = '';
    c.classList.remove('fade-in');
    frag.appendChild(c);
  });
  grid.appendChild(frag);
  requestAnimationFrame(() => {
    visible.forEach(c => c.classList.add('fade-in'));
  });

  allCards.forEach(c => {
    c.querySelectorAll('.news-item').forEach(item => {
      item.style.display = (tagFilter === 'all' || item.dataset.newsTag === tagFilter) ? '' : 'none';
    });
    const dateSpan = c.querySelector('.news-date-display');
    if (dateSpan) {
      const d = tagFilter === 'patchnotes' ? dateSpan.dataset.datePatch
              : tagFilter === 'other'      ? dateSpan.dataset.dateOther
              : dateSpan.dataset.dateAll;
      dateSpan.textContent = d ? '📰 ' + d : '📰 —';
    }
    const lbl = c.querySelector('.news-title');
    if (lbl) {
      const n = Array.from(c.querySelectorAll('.news-item')).filter(el => el.style.display !== 'none').length;
      lbl.textContent = n > 0 ? '🗞 ' + (n === 1 ? I18N.news_1 : I18N.news_n.replace('{n}', n)) : '🗞 ' + I18N.news_0;
    }
  });

  let empty = document.getElementById('emptyMsg');
  if (visible.length === 0) {
    if (!empty) {
      empty = document.createElement('div');
      empty.id = 'emptyMsg';
      empty.className = 'empty';
      empty.innerHTML = '<div style="font-size:32px">🔍</div><p>' + I18N.no_match_games + '</p>';
      grid.appendChild(empty);
    }
    empty.style.display = '';
  } else if (empty) {
    empty.style.display = 'none';
  }

  document.getElementById('countLabel').textContent = visible.length === 1 ? I18N.count_game_1 : I18N.count_game_n.replace('{n}', visible.length);
  updateResetBtn();
  saveStateToHash();
}

// --- Event listeners ---
let _searchTimer;
document.getElementById('search').addEventListener('input', () => {
  clearTimeout(_searchTimer);
  _searchTimer = setTimeout(updateGrid, 120);
});
document.getElementById('sortBy').addEventListener('change', updateGrid);

function setupFilterGroup(selector, callback) {
  document.querySelectorAll(selector).forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.filter-btns').querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      callback ? callback() : updateGrid();
    });
  });
}
setupFilterGroup('#filterBtns .filter-btn');
setupFilterGroup('#sourceBtns .source-btn');
setupFilterGroup('#tagBtns .tag-btn');
setupFilterGroup('#playtimeBtns .filter-btn');
setupFilterGroup('#mcBtns .filter-btn');
setupFilterGroup('#recentBtns .filter-btn');

// Reset
document.getElementById('resetBtn').addEventListener('click', () => {
  document.getElementById('search').value = '';
  document.getElementById('sortBy').value = 'name';
  ['#filterBtns .filter-btn', '#sourceBtns .source-btn', '#tagBtns .tag-btn', '#playtimeBtns .filter-btn', '#mcBtns .filter-btn', '#recentBtns .filter-btn'].forEach(sel => {
    document.querySelectorAll(sel).forEach(b => b.classList.remove('active'));
    const first = document.querySelector(sel);
    if (first) first.classList.add('active');
  });
  updateGrid();
});

// View toggle
document.getElementById('viewToggle').addEventListener('click', () => {
  const grid = document.getElementById('grid');
  const btn = document.getElementById('viewToggle');
  const header = document.getElementById('listHeader');
  grid.classList.toggle('list-view');
  const isListView = grid.classList.contains('list-view');
  btn.textContent = isListView ? '⊞ ' + I18N.grid_view : '☰ ' + I18N.list_view;
  header.classList.toggle('visible', isListView);
  saveStateToHash();
});

// Expand/collapse news
document.querySelectorAll('.news-toggle').forEach(toggle => {
  toggle.addEventListener('click', e => {
    e.stopPropagation();
    toggle.closest('.card').classList.toggle('expanded');
  });
});

// Open Steam store on card click
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('click', e => {
    if (e.target.closest('.news-toggle') || e.target.closest('.news-list')) return;
    const appid = card.dataset.appid;
    if (appid) window.open('https://store.steampowered.com/app/' + appid, '_blank');
  });
});

// Load state from URL hash
loadStateFromHash();
saveStateToHash(); // initialise le lien nav avec l'état courant
updateGrid();
</script>
</body>
</html>
"""

_NEWS_TEMPLATE = r"""<!DOCTYPE html>
<html lang="__T_html_lang__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SteamPulse — News</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0a0e14; --surface:#111722; --border:#1f2d45;
    --accent:#1db9ff; --text:#c8d8ef; --muted:#5a7199;
    --ea:#f5a623; --released:#3dd68c; --unreleased:#7b7fff; --unknown:#5a7199;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  body { background:var(--bg); color:var(--text); font-family:'Inter',sans-serif; font-size:14px; min-height:100vh; }
  header {
    background:linear-gradient(180deg,#0d1a2e 0%,transparent 100%);
    border-bottom:1px solid var(--border);
    padding:24px 40px 18px;
    display:flex; align-items:center; gap:20px;
  }
  .header-text h1 { font-family:'Rajdhani',sans-serif; font-size:28px; font-weight:700; letter-spacing:2px; color:#fff; text-transform:uppercase; }
  .header-text p { color:var(--muted); font-size:12px; margin-top:2px; font-family:'IBM Plex Mono',monospace; }
  .nav-link {
    padding: 6px 14px;
    border-radius: 20px;
    border: 1px solid var(--border);
    color: var(--muted);
    font-size: 12px;
    text-decoration: none;
    transition: all .2s;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
  }
  .nav-link:hover { border-color: var(--accent); color: var(--accent); }
  .toolbar { border-bottom:1px solid var(--border); background:var(--surface); position:sticky; top:0; z-index:100; }
  .toolbar-main { padding:11px 40px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  .toolbar-filters {
    display:none; gap:16px 28px; flex-wrap:wrap;
    padding:14px 40px 18px; border-top:1px solid var(--border);
    background:rgba(0,0,0,.12);
  }
  .toolbar-filters.open { display:flex; }
  .filter-group { display:flex; flex-direction:column; gap:7px; }
  .filter-group-label { font-size:10px; font-family:'IBM Plex Mono',monospace; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }
  .filter-toggle-btn {
    padding:6px 14px; border-radius:20px; border:1px solid var(--border);
    background:transparent; color:var(--muted); font-size:12px; cursor:pointer;
    transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px;
    display:inline-flex; align-items:center; gap:6px;
  }
  .filter-toggle-btn:hover { border-color:var(--accent); color:var(--accent); }
  .filter-toggle-btn.has-active { border-color:var(--accent); color:var(--accent); background:rgba(29,185,255,.1); }
  .filter-badge {
    display:none; align-items:center; justify-content:center;
    min-width:16px; height:16px; border-radius:8px;
    background:var(--accent); color:#000; font-size:10px; font-weight:700; padding:0 4px;
  }
  .filter-badge.show { display:inline-flex; }
  .search-wrap { position:relative; flex:1; min-width:200px; max-width:340px; }
  .search-wrap input {
    width:100%; background:var(--bg); border:1px solid var(--border);
    color:var(--text); padding:8px 12px 8px 36px; border-radius:6px;
    font-size:13px; outline:none; font-family:inherit; transition:border-color .2s;
  }
  .search-wrap input:focus { border-color:var(--accent); }
  .search-wrap .icon { position:absolute; left:11px; top:50%; transform:translateY(-50%); color:var(--muted); pointer-events:none; }
  .filter-btns { display:flex; gap:6px; }
  .filter-btn, .source-btn, .tag-btn {
    padding:6px 14px; border-radius:20px; border:1px solid var(--border);
    background:transparent; color:var(--muted); font-size:12px; cursor:pointer;
    transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px;
  }
  .filter-btn:hover, .source-btn:hover, .tag-btn:hover { border-color:var(--accent); color:var(--accent); }
  .filter-btn.active, .source-btn.active, .tag-btn.active { background:var(--accent); border-color:var(--accent); color:#000; font-weight:500; }
  .feed-tag {
    display:inline-block; padding:1px 6px; border-radius:3px; margin-left:8px; flex-shrink:0;
    font-size:10px; font-weight:600; font-family:'IBM Plex Mono',monospace;
    text-transform:uppercase; letter-spacing:.5px; align-self:center;
  }
  .feed-tag-patchnotes { background:rgba(61,214,140,.12); color:#3dd68c; border:1px solid rgba(61,214,140,.25); }
  .feed-tag-other { background:rgba(90,113,153,.12); color:#5a7199; border:1px solid rgba(90,113,153,.25); }
  .count-label { margin-left:auto; font-family:'IBM Plex Mono',monospace; font-size:12px; color:var(--muted); }
  .badge { padding:2px 7px; border-radius:3px; font-size:10px; font-weight:600; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; text-transform:uppercase; }
  .badge-earlyaccess { background:rgba(245,166,35,.15); color:var(--ea); border:1px solid rgba(245,166,35,.3); }
  .badge-released    { background:rgba(61,214,140,.12); color:var(--released); border:1px solid rgba(61,214,140,.25); }
  .badge-unreleased  { background:rgba(123,127,255,.12); color:var(--unreleased); border:1px solid rgba(123,127,255,.25); }
  .badge-unknown     { background:rgba(90,113,153,.12); color:var(--unknown); border:1px solid rgba(90,113,153,.25); }
  .feed { padding:20px 40px; display:flex; flex-direction:column; gap:6px; }
  .feed-item {
    background:var(--surface); border:1px solid var(--border); border-radius:8px;
    display:flex; align-items:stretch; overflow:hidden; transition:border-color .15s;
  }
  .feed-item:hover { border-color:var(--accent); }
  .feed-thumb { width:107px; height:40px; object-fit:cover; display:block; flex-shrink:0; align-self:center; }
  .feed-game {
    padding:8px 14px; border-right:1px solid var(--border);
    display:flex; flex-direction:column; justify-content:center;
    min-width:180px; max-width:240px;
  }
  .feed-game-name { font-family:'Rajdhani',sans-serif; font-size:13px; font-weight:600; color:#fff; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .feed-game-badge { margin-top:3px; }
  .feed-date {
    padding:0 16px; font-family:'IBM Plex Mono',monospace; font-size:11px;
    color:var(--muted); white-space:nowrap; display:flex; align-items:center;
    border-right:1px solid var(--border); min-width:90px;
  }
  .feed-title { padding:8px 16px; flex:1; display:flex; align-items:center; font-size:13px; }
  .feed-title a { color:var(--text); text-decoration:none; }
  .feed-title a:hover { color:var(--accent); }
  .empty { text-align:center; padding:80px 0; color:var(--muted); }
  .empty p { margin-top:10px; font-size:13px; }
  footer { text-align:center; padding:20px; color:var(--muted); font-size:11px; font-family:'IBM Plex Mono',monospace; border-top:1px solid var(--border); margin-top:10px; }
  .scroll-top {
    position:fixed; bottom:28px; right:28px; z-index:200;
    width:42px; height:42px; border-radius:50%;
    background:var(--accent); color:#000; border:none;
    font-size:20px; cursor:pointer;
    opacity:0; pointer-events:none;
    transition:opacity .3s, transform .3s;
    transform:translateY(10px);
    box-shadow:0 4px 16px rgba(0,0,0,.4);
    display:flex; align-items:center; justify-content:center;
  }
  .scroll-top.visible { opacity:1; pointer-events:auto; transform:translateY(0); }
  .scroll-top:hover { transform:translateY(-2px); }
  .theme-toggle {
    position:fixed; bottom:28px; left:28px; z-index:200;
    width:38px; height:38px; border-radius:50%;
    background:var(--surface); border:1px solid var(--border);
    color:var(--muted); font-size:16px; cursor:pointer;
    transition:all .2s;
    display:flex; align-items:center; justify-content:center;
  }
  .theme-toggle:hover { border-color:var(--accent); color:var(--accent); }
  .reset-btn {
    padding:6px 12px; border-radius:20px; border:1px solid rgba(255,80,80,.3);
    background:transparent; color:#ff6b6b; font-size:12px; cursor:pointer;
    transition:all .2s; font-family:'IBM Plex Mono',monospace; display:none;
  }
  .reset-btn.show { display:inline-flex; align-items:center; gap:4px; }
  .reset-btn:hover { background:rgba(255,80,80,.12); border-color:#ff6b6b; }
  html.light {
    --bg:#f0f2f5; --surface:#ffffff; --surface2:#e8ecf1; --border:#d0d7e0;
    --accent:#0a7cc4; --accent2:#00a87d; --text:#2c3e50; --muted:#6c7a8a;
    --ea:#d4850a; --released:#1a9960; --unreleased:#5b5fe0; --unknown:#6c7a8a;
  }
  html.light header { background:linear-gradient(180deg,#dfe6ee 0%,transparent 100%); }
  html.light .feed-game-name, html.light .header-text h1 { color:#1a2530; }
  html.light .feed-item { box-shadow:0 1px 4px rgba(0,0,0,.08); }
  @media(max-width:600px) { header,.toolbar-main,.toolbar-filters,.feed { padding-left:16px; padding-right:16px; } .feed-game { min-width:130px; max-width:160px; } .scroll-top { bottom:16px; right:16px; } .theme-toggle { bottom:16px; left:16px; } }
</style>
</head>
<body>

<header>
  <svg width="36" height="36" viewBox="0 0 44 44" fill="none" style="flex-shrink:0">
    <circle cx="22" cy="22" r="21" stroke="#1db9ff" stroke-width="1.5" opacity=".4"/>
    <circle cx="22" cy="22" r="10" fill="#1db9ff" opacity=".15"/>
    <circle cx="22" cy="22" r="5" fill="#1db9ff"/>
    <circle cx="22" cy="7"  r="2.5" fill="#1db9ff" opacity=".7"/>
    <circle cx="35" cy="29" r="2.5" fill="#1db9ff" opacity=".7"/>
    <circle cx="9"  cy="29" r="2.5" fill="#1db9ff" opacity=".7"/>
  </svg>
  <div class="header-text">
    <h1>SteamPulse — News</h1>
    <p>__T_generated_at__ __GENERATED_AT__ · SteamID __STEAM_ID__</p>
  </div>
</header>

<div class="toolbar">
  <div class="toolbar-main">
    <div class="search-wrap">
      <span class="icon">⌕</span>
      <input type="text" id="search" placeholder="Rechercher un jeu...">
    </div>
    <button class="filter-toggle-btn" id="filtersToggle" title="__T_title_btn_filters__">⚙ __T_btn_filters__<span class="filter-badge" id="filterBadge"></span></button>
    <button class="reset-btn" id="resetBtn" title="__T_title_btn_reset__">✕ __T_btn_reset__</button>
    <span class="count-label" id="countLabel"></span>
    <a class="nav-link" href="__LIB_HREF__">📚 __T_link_library__</a>
  </div>
  <div class="toolbar-filters" id="toolbarFilters">
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_status__</div>
      <div class="filter-btns" id="statusBtns">
        <button class="filter-btn active" data-filter="all">__T_lbl_all__</button>
        <button class="filter-btn" data-filter="earlyaccess">Early Access</button>
        <button class="filter-btn" data-filter="released">__T_lbl_released__</button>
        <button class="filter-btn" data-filter="unreleased">__T_lbl_upcoming__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_source__</div>
      <div class="filter-btns" id="sourceBtns">
        <button class="source-btn active" data-source="all">🎮 __T_lbl_all__</button>
        <button class="source-btn" data-source="owned">__T_lbl_owned__</button>
        <button class="source-btn" data-source="wishlist">🎁 Wishlist</button>
        <button class="source-btn" data-source="followed">👁 __T_lbl_followed__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_news_type__</div>
      <div class="filter-btns" id="tagBtns">
        <button class="tag-btn active" data-tag="all">__T_lbl_all_types__</button>
        <button class="tag-btn" data-tag="patchnotes">📋 Patch notes</button>
        <button class="tag-btn" data-tag="other">📰 News</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_playtime__</div>
      <div class="filter-btns" id="playtimeBtns">
        <button class="filter-btn active" data-pt="all">__T_lbl_all__</button>
        <button class="filter-btn" data-pt="0">__T_lbl_never_played__</button>
        <button class="filter-btn" data-pt="60">&lt; 1h</button>
        <button class="filter-btn" data-pt="600">1-10h</button>
        <button class="filter-btn" data-pt="601">&gt; 10h</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_metacritic__</div>
      <div class="filter-btns" id="mcBtns">
        <button class="filter-btn active" data-mc="all">__T_lbl_all__</button>
        <button class="filter-btn" data-mc="none">__T_lbl_no_score__</button>
        <button class="filter-btn" data-mc="poor">&lt; 60</button>
        <button class="filter-btn" data-mc="mixed">60–74</button>
        <button class="filter-btn" data-mc="good">75–89</button>
        <button class="filter-btn" data-mc="great">≥ 90</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_recent__</div>
      <div class="filter-btns" id="recentBtns">
        <button class="filter-btn active" data-recent="all">__T_lbl_all__</button>
        <button class="filter-btn" data-recent="2">__T_lbl_2_days__</button>
        <button class="filter-btn" data-recent="5">__T_lbl_5_days__</button>
        <button class="filter-btn" data-recent="15">__T_lbl_15_days__</button>
        <button class="filter-btn" data-recent="30">__T_lbl_30_days__</button>
      </div>
    </div>
  </div>
</div>

<div class="feed" id="feed">
__ROWS__
</div>

<footer>__T_footer__</footer>

<button class="scroll-top" id="scrollTop" title="__T_title_scroll_top__">↑</button>
<button class="theme-toggle" id="themeToggle" title="__T_title_theme__">🌙</button>

<script>
__I18N_JS__
const allRows = Array.from(document.querySelectorAll('.feed-item'));
__SHARED_JS__
// --- Getters ---
function getStatusFilter() { return document.querySelector('#statusBtns .filter-btn.active').dataset.filter; }
function getSrcFilter()    { return document.querySelector('#sourceBtns .source-btn.active').dataset.source; }
function getTagFilter()    { return document.querySelector('#tagBtns .tag-btn.active').dataset.tag; }
function getPtFilter()     { return document.querySelector('#playtimeBtns .filter-btn.active').dataset.pt; }
function getMcFilter()     { return document.querySelector('#mcBtns .filter-btn.active').dataset.mc; }
function getRecentFilter() { return document.querySelector('#recentBtns .filter-btn.active').dataset.recent; }
function getSearch()       { return document.getElementById('search').value.toLowerCase().trim(); }

// --- Check functions ---
function checkMcFilter(mc, row) {
  if (mc === 'all') return true;
  const score = parseInt(row.dataset.metacritic) || 0;
  if (mc === 'none')  return score === 0;
  if (mc === 'poor')  return score > 0 && score < 60;
  if (mc === 'mixed') return score >= 60 && score < 75;
  if (mc === 'good')  return score >= 75 && score < 90;
  if (mc === 'great') return score >= 90;
  return true;
}
function isDefaultState() {
  return getStatusFilter() === 'all' && getSrcFilter() === 'all' && getTagFilter() === 'all'
    && getPtFilter() === 'all' && getMcFilter() === 'all' && getRecentFilter() === 'all'
    && !getSearch();
}

function updateFilterBadge() {
  let n = 0;
  if (getStatusFilter() !== 'all') n++;
  if (getSrcFilter() !== 'all')    n++;
  if (getTagFilter() !== 'all')    n++;
  if (getPtFilter() !== 'all')     n++;
  if (getMcFilter() !== 'all')     n++;
  if (getRecentFilter() !== 'all') n++;
  const badge = document.getElementById('filterBadge');
  badge.textContent = n;
  badge.classList.toggle('show', n > 0);
  document.getElementById('filtersToggle').classList.toggle('has-active', n > 0);
}

function saveStateToHash() {
  const s = {};
  if (getStatusFilter() !== 'all') s.status = getStatusFilter();
  if (getSrcFilter() !== 'all')    s.source = getSrcFilter();
  if (getTagFilter() !== 'all')    s.tag = getTagFilter();
  if (getPtFilter() !== 'all')     s.pt = getPtFilter();
  if (getMcFilter() !== 'all')     s.mc = getMcFilter();
  if (getRecentFilter() !== 'all') s.recent = getRecentFilter();
  if (getSearch())                 s.q = getSearch();
  const h = new URLSearchParams(s).toString();
  history.replaceState(null, '', h ? '#' + h : location.pathname);
  // Update back link to carry compatible filters to library page
  const backLink = document.querySelector('.nav-link[href^="steam_library"]');
  if (backLink) {
    const nf = {};
    if (getStatusFilter() !== 'all') nf.status = getStatusFilter();
    if (getSrcFilter() !== 'all')    nf.source = getSrcFilter();
    if (getTagFilter() !== 'all')    nf.tag = getTagFilter();
    if (getRecentFilter() !== 'all') nf.recent = getRecentFilter();
    const nh = new URLSearchParams(nf).toString();
    backLink.href = 'steam_library.html' + (nh ? '#' + nh : '');
  }
}

function loadStateFromHash() {
  const h = location.hash.slice(1);
  if (!h) return;
  const p = new URLSearchParams(h);
  if (p.get('status')) { activateBtn('#statusBtns .filter-btn', 'filter', p.get('status')); }
  if (p.get('source')) { activateBtn('#sourceBtns .source-btn', 'source', p.get('source')); }
  if (p.get('tag'))    { activateBtn('#tagBtns .tag-btn', 'tag', p.get('tag')); }
  if (p.get('pt'))     { activateBtn('#playtimeBtns .filter-btn', 'pt', p.get('pt')); }
  if (p.get('mc'))     { activateBtn('#mcBtns .filter-btn', 'mc', p.get('mc')); }
  if (p.get('recent')) { activateBtn('#recentBtns .filter-btn', 'recent', p.get('recent')); }
  if (p.get('q'))      { document.getElementById('search').value = p.get('q'); }
  if (!isDefaultState()) {
    document.getElementById('toolbarFilters').classList.add('open');
  }
}

function updateFeed() {
  const statusFilter = getStatusFilter();
  const srcFilter    = getSrcFilter();
  const tagFilter    = getTagFilter();
  const ptFilter     = getPtFilter();
  const mcFilter     = getMcFilter();
  const recentFilter = getRecentFilter();
  const search       = getSearch();
  let visible = allRows.filter(r => {
    const statusOk = statusFilter === 'all' || r.dataset.status === statusFilter;
    const srcOk    = srcFilter === 'all' || r.dataset.source === srcFilter;
    const tagOk    = tagFilter === 'all' || r.dataset.tag === tagFilter;
    const searchOk = !search || r.dataset.name.includes(search);
    const ptOk     = checkPtFilter(ptFilter, r);
    const mcOk     = checkMcFilter(mcFilter, r);
    const recentOk = checkRecentFilter(recentFilter, r);
    return statusOk && srcOk && tagOk && searchOk && ptOk && mcOk && recentOk;
  });
  allRows.forEach(r => r.style.display = 'none');
  visible.forEach(r => r.style.display = '');
  let empty = document.getElementById('emptyMsg');
  if (visible.length === 0) {
    if (!empty) {
      empty = document.createElement('div');
      empty.id = 'emptyMsg'; empty.className = 'empty';
      empty.innerHTML = '<div style="font-size:32px">🔍</div><p>' + I18N.no_match_news + '</p>';
      document.getElementById('feed').appendChild(empty);
    }
    empty.style.display = '';
  } else if (empty) {
    empty.style.display = 'none';
  }
  document.getElementById('countLabel').textContent = I18N.count_news.replace('{n}', visible.length);
  updateResetBtn();
  saveStateToHash();
}

// --- Event listeners ---
let _newsSearchTimer;
document.getElementById('search').addEventListener('input', () => {
  clearTimeout(_newsSearchTimer);
  _newsSearchTimer = setTimeout(updateFeed, 120);
});

function setupFilterGroup(selector, callback) {
  document.querySelectorAll(selector).forEach(btn => {
    btn.addEventListener('click', () => {
      btn.closest('.filter-btns').querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      callback ? callback() : updateFeed();
    });
  });
}
setupFilterGroup('#statusBtns .filter-btn');
setupFilterGroup('#sourceBtns .source-btn');
setupFilterGroup('#tagBtns .tag-btn');
setupFilterGroup('#playtimeBtns .filter-btn');
setupFilterGroup('#mcBtns .filter-btn');
setupFilterGroup('#recentBtns .filter-btn');

// Reset
document.getElementById('resetBtn').addEventListener('click', () => {
  document.getElementById('search').value = '';
  ['#statusBtns .filter-btn', '#sourceBtns .source-btn', '#tagBtns .tag-btn',
   '#playtimeBtns .filter-btn', '#mcBtns .filter-btn', '#recentBtns .filter-btn'].forEach(sel => {
    document.querySelectorAll(sel).forEach(b => b.classList.remove('active'));
    const first = document.querySelector(sel);
    if (first) first.classList.add('active');
  });
  updateFeed();
});

loadStateFromHash();
saveStateToHash(); // initialise le lien nav avec l'état courant
updateFeed();
</script>
</body>
</html>
"""


def _build_i18n_js(t: "Translator") -> str:
    """Return a ``const I18N = {...};`` block for the HTML templates."""
    data = {
        "grid_view":      t("btn_grid_view"),
        "list_view":      t("btn_list_view"),
        "news_0":         t("js_news_0"),
        "news_1":         t("js_news_1"),
        "news_n":         t("js_news_n"),
        "no_match_games": t("js_no_match_games"),
        "count_game_1":   t("js_count_game_1"),
        "count_game_n":   t("js_count_game_n"),
        "no_match_news":  t("js_no_match_news"),
        "count_news":     t("js_count_news"),
    }
    entries = ", ".join(f"{k}: {json.dumps(v)}" for k, v in data.items())
    return f"const I18N = {{{entries}}};"


def _apply_html_t(s: str, t: "Translator") -> str:
    """Replace all ``__T_key__`` placeholders in *s* with translated values."""
    keys = [
        "html_lang", "generated_at", "search_placeholder",
        "btn_filters", "btn_reset", "btn_list_view", "btn_grid_view",
        "title_btn_filters", "title_btn_reset", "title_view_toggle",
        "title_scroll_top", "title_theme",
        "filter_status", "filter_source", "filter_news_type",
        "filter_playtime", "filter_metacritic", "filter_recent",
        "lbl_all", "lbl_released", "lbl_upcoming", "lbl_owned",
        "lbl_followed", "lbl_all_types", "lbl_never_played", "lbl_no_score",
        "lbl_2_days", "lbl_5_days", "lbl_15_days", "lbl_30_days", "footer",
        "stat_total", "stat_released", "stat_unreleased", "stat_hours",
        "sort_name_asc", "sort_name_desc", "sort_playtime",
        "sort_release", "sort_lastupdate", "sort_metacritic",
        "link_news", "col_game", "col_dev_score", "col_playtime_date",
        "link_library",
    ]
    for key in keys:
        s = s.replace(f"__T_{key}__", t(key))
    return s




def format_playtime(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60}h{minutes % 60:02d}"


_FR_MONTHS = {
    "janvier": "Jan", "f\u00e9vrier": "Feb", "mars": "Mar", "avril": "Apr",
    "mai": "May", "juin": "Jun", "juillet": "Jul", "ao\u00fbt": "Aug",
    "septembre": "Sep", "octobre": "Oct", "novembre": "Nov", "d\u00e9cembre": "Dec",
}


def _parse_release_ts(date_str: str) -> int:
    """Convert a Steam release date string (French or English) to a Unix timestamp."""
    s = date_str.strip()
    if not s or s == "\u2014":
        return 0
    s_lower = s.lower()
    for fr, en in _FR_MONTHS.items():
        if fr in s_lower:
            s = s_lower.replace(fr, en)
            break
    for fmt in ("%d %b %Y", "%d %b, %Y", "%b %Y", "%Y"):
        try:
            return int(datetime.strptime(s.strip(), fmt).replace(tzinfo=UTC).timestamp())
        except ValueError:
            continue
    m = re.search(r"\b((?:19|20)\d{2})\b", s)
    if m:
        try:
            return int(datetime(int(m.group()), 1, 1, tzinfo=UTC).timestamp())
        except ValueError:
            pass
    return 0


def _metacritic_html(score: int, url: str) -> str:
    if score <= 0:
        return ""
    cls = "mc-green" if score >= 75 else ("mc-yellow" if score >= 50 else "mc-red")
    safe_url = html.escape(url)
    link_open = f'<a href="{safe_url}" target="_blank" rel="noopener" style="text-decoration:none">' if url else ""
    link_close = "</a>" if url else ""
    return f'{link_open}<span class="metacritic-badge {cls}">MC {score}</span>{link_close}'


def _price_html(details: object, t: "Translator | None" = None) -> str:
    from .models import AppDetails  # local import to avoid circular
    if not isinstance(details, AppDetails):
        return ""
    price_free_lbl = t("price_free") if t else "Free"
    if details.is_free:
        return f'<span class="price-free">{price_free_lbl}</span>'
    if details.price_final <= 0:
        return ""
    currency = html.escape(details.price_currency)
    final = f"{details.price_final / 100:.2f} {currency}"
    if details.price_discount_pct > 0:
        original = f"{details.price_initial / 100:.2f} {currency}"
        return (
            f'<span class="price-tag">'
            f'<span class="price-discount">{original}</span>'
            f" {final} (-{details.price_discount_pct}%)"
            f"</span>"
        )
    return f'<span class="price-tag">{final}</span>'


def _platform_html(details: object) -> str:
    from .models import AppDetails
    if not isinstance(details, AppDetails):
        return ""
    icons = []
    if details.platform_windows:
        icons.append("🪟")
    if details.platform_mac:
        icons.append("🍎")
    if details.platform_linux:
        icons.append("🐧")
    return f'<span class="platform-icons">{"".join(icons)}</span>' if icons else ""


def make_card(record: GameRecord, t: "Translator | None" = None) -> str:
    """Return the HTML string for a single game card."""
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator("en")
    game = record.game
    status = record.status
    news_list = record.news
    details = record.details

    name = html.escape(game.name)
    appid = game.appid

    img_url = (
        details.header_image
        if details and details.header_image
        else f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
    )

    badge_cls = f"badge badge-{status.badge}"
    badge_label = t(f"badge_{status.badge}")
    pt_fmt = format_playtime(game.playtime_forever)
    rel_date = html.escape(status.release_date)

    # ── genre tags (max 3) ──────────────────────────────────────────────────
    genres_html = ""
    if details and details.genres:
        tags = "".join(
            f'<span class="genre-tag">{html.escape(g)}</span>'
            for g in details.genres[:3]
        )
        genres_html = f'<div class="genre-tags">{tags}</div>\n'

    # ── developer / platform / metacritic / price row ──────────────────────
    detail_parts: list[str] = []
    if details and details.developers:
        detail_parts.append(
            f'<span class="dev-name">{html.escape(details.developers[0])}</span>'
        )
    plat = _platform_html(details) if details else ""
    if plat:
        detail_parts.append(plat)
    mc = _metacritic_html(details.metacritic_score, details.metacritic_url) if details else ""
    if mc:
        detail_parts.append(mc)
    price = _price_html(details, t) if details else ""
    if price:
        detail_parts.append(price)
    detail_row = (
        f'<div class="card-detail">{" · ".join(detail_parts)}</div>\n' if detail_parts else ""
    )

    # ── news ────────────────────────────────────────────────────────────────
    if news_list:
        _rows = []
        for n in news_list:
            _ntag = "patchnotes" if n.tags and n.tags[0].lower() == "patchnotes" else "other"
            _rows.append(                f'<div class="news-item" data-news-tag="{_ntag}">'
                f'  <span class="news-date">{html.escape(n.date.strftime("%d/%m/%Y"))}</span>'
                f'  <span class="news-item-title">'
                f'    <a href="{html.escape(n.url)}" target="_blank" rel="noopener">'
                f"{html.escape(n.title)}</a>"
                f"  </span>"
                f"</div>"
            )
        news_html = "\n".join(_rows)
    else:
        news_html = f'<p class="no-news">{html.escape(t("card_no_news_html"))}</p>'

    nc = len(news_list)
    if nc == 0:
        toggle_lbl = t("card_news_toggle_0")
    elif nc == 1:
        toggle_lbl = t("card_news_toggle_1")
    else:
        toggle_lbl = t("card_news_toggle_n", count=nc)

    release_ts = _parse_release_ts(status.release_date)
    last_update_ts = int(news_list[0].date.timestamp()) if news_list else 0
    last_all_date = news_list[0].date.strftime("%d/%m/%Y") if news_list else ""
    last_patch_ts, last_other_ts = 0, 0
    last_patch_date, last_other_date = "", ""
    for _n in news_list:
        _primary = _n.tags[0].lower() if _n.tags else ""
        _ts = int(_n.date.timestamp())
        if _primary == "patchnotes":
            if _ts > last_patch_ts:
                last_patch_ts = _ts
                last_patch_date = _n.date.strftime("%d/%m/%Y")
        else:
            if _ts > last_other_ts:
                last_other_ts = _ts
                last_other_date = _n.date.strftime("%d/%m/%Y")
    placeholder = html.escape(game.name[:2].upper())
    source_tag = html.escape(game.source)
    if game.source == "wishlist":
        pt_display = t("source_wishlist")
    elif game.source == "followed":
        pt_display = t("source_followed")
    else:
        pt_display = f"🕹 {pt_fmt}"
    metacritic_score = details.metacritic_score if details else 0
    return (
        f'<div class="card" data-appid="{appid}" data-status="{status.badge}" '
        f'data-source="{source_tag}" data-name="{name.lower()}" '
        f'data-playtime="{game.playtime_forever}" '
        f'data-metacritic="{metacritic_score}" '
        f'data-release="{rel_date}" data-release-ts="{release_ts}" '
        f'data-last-update="{last_update_ts}" '
        f'data-last-patch-ts="{last_patch_ts}" data-last-other-ts="{last_other_ts}">\n'
        f'  <span class="card-ext-hint">↗ Steam</span>\n'
        f'  <img class="card-img" src="{html.escape(img_url)}" alt="" loading="lazy"'
        f"    onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">\n"
        f'  <div class="card-img-placeholder" style="display:none">{placeholder}</div>\n'
        f'  <div class="card-body">\n'
        f'    <div class="col-title">\n'
        f'    <div class="card-top">\n'
        f'      <div class="card-title">{name}</div>\n'
        f'      <span class="{html.escape(badge_cls)}">{html.escape(badge_label)}</span>\n'
        f"    </div>\n"
        f"    </div>\n"
        f'    <div class="col-detail">{detail_row}</div>\n'
        f'    <div class="col-genres">{genres_html}</div>\n'
        f'    <div class="col-meta">\n'
        f'    <div class="card-meta">\n'
        f"      <span>📅 {rel_date}</span>\n"
        f'      <span class="news-date-display"'
        f' data-date-all="{html.escape(last_all_date)}"'
        f' data-date-patch="{html.escape(last_patch_date)}"'
        f' data-date-other="{html.escape(last_other_date)}">'
        f'\U0001f4f0 {html.escape(last_all_date) or "—"}</span>\n'
        f"      <span>{pt_display}</span>\n"
        f'      <span style="color:#3a5a99">#{appid}</span>\n'
        f"    </div>\n"
        f"    </div>\n"
        f'    <div class="news-section">\n'
        f'      <div class="news-toggle">\n'
        f'        <div class="news-title">🗞 {html.escape(toggle_lbl)}</div>\n'
        f'        <span class="news-toggle-icon">▼</span>\n'
        f"      </div>\n"
        f'      <div class="news-list">\n'
        f"        {news_html}\n"
        f"      </div>\n"
        f"    </div>\n"
        f"  </div>\n"
        f"</div>"
    )


def generate_html(
    records: list[GameRecord],
    steam_id: str,
    news_href: str = "steam_news.html",
    lang: str | None = None,
) -> str:
    """Render the full HTML page from a list of game records."""
    from .i18n import get_translator  # noqa: PLC0415
    t = get_translator(lang)
    cards_html = "\n".join(make_card(r, t) for r in records)
    total = len(records)
    ea = sum(1 for r in records if r.status.badge == "earlyaccess")
    released = sum(1 for r in records if r.status.badge == "released")
    unrel = sum(1 for r in records if r.status.badge == "unreleased")
    total_playtime_min = sum(r.game.playtime_forever for r in records)
    total_playtime_h = total_playtime_min // 60
    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")

    return _apply_html_t(
        _HTML_TEMPLATE.replace("__SHARED_JS__", _SHARED_JS)
        .replace("__I18N_JS__", _build_i18n_js(t))
        .replace("__GENERATED_AT__", now_str)
        .replace("__STEAM_ID__", html.escape(steam_id))
        .replace("__TOTAL__", str(total))
        .replace("__EA__", str(ea))
        .replace("__REL__", str(released))
        .replace("__UNREL__", str(unrel))
        .replace("__PLAYTIME__", f"{total_playtime_h:,}h".replace(",", "\u202f"))
        .replace("__CARDS__", cards_html)
        .replace("__NEWS_HREF__", html.escape(news_href)),
        t,
    )


def write_html(
    records: list[GameRecord],
    steam_id: str,
    output_path: Path,
    news_href: str = "steam_news.html",
    lang: str | None = None,
) -> None:
    """Write the rendered HTML page to *output_path*."""
    output_path.write_text(generate_html(records, steam_id, news_href, lang), encoding="utf-8")


def make_news_row(record: GameRecord, item: NewsItem, t: "Translator | None" = None) -> str:
    """Return an HTML feed-item row for a single news article."""
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator("en")
    game = record.game
    status = record.status
    details = record.details

    appid = game.appid
    name = html.escape(game.name)
    img_url = (
        details.header_image
        if details and details.header_image
        else f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
    )
    badge_cls = f"badge badge-{status.badge}"
    badge_label = t(f"badge_{status.badge}")
    date_str = html.escape(item.date.strftime("%d/%m/%Y"))
    title = html.escape(item.title)
    url = html.escape(item.url)
    primary_tag = item.tags[0].lower() if item.tags else ""
    tag_css = "feed-tag-patchnotes" if primary_tag == "patchnotes" else "feed-tag-other"
    tag_data = primary_tag if primary_tag == "patchnotes" else "other"
    tag_html = (
        f'<span class="feed-tag {tag_css}">{html.escape(primary_tag)}</span>'
        if primary_tag
        else ""
    )

    source_tag = html.escape(game.source)
    playtime = game.playtime_forever
    metacritic_score = details.metacritic_score if details else 0
    last_patch_ts = 0
    for _n in record.news:
        _primary = _n.tags[0].lower() if _n.tags else ""
        if _primary == "patchnotes":
            _ts = int(_n.date.timestamp())
            if _ts > last_patch_ts:
                last_patch_ts = _ts

    return (
        f'<div class="feed-item" data-status="{status.badge}" data-name="{name.lower()}" '
        f'data-tag="{tag_data}" data-source="{source_tag}" '
        f'data-playtime="{playtime}" data-metacritic="{metacritic_score}" '
        f'data-last-patch-ts="{last_patch_ts}">\n'
        f'  <img class="feed-thumb" src="{html.escape(img_url)}" alt="" loading="lazy">\n'
        f'  <div class="feed-game">\n'
        f'    <div class="feed-game-name">{name}</div>\n'
        f'    <div class="feed-game-badge"><span class="{html.escape(badge_cls)}">{html.escape(badge_label)}</span></div>\n'
        f'  </div>\n'
        f'  <div class="feed-date">{date_str}</div>\n'
        f'  <div class="feed-title"><a href="{url}" target="_blank" rel="noopener">{title}</a>{tag_html}</div>\n'
        f"</div>"
    )


def generate_news_html(
    records: list[GameRecord],
    steam_id: str,
    library_href: str = "steam_library.html",
    lang: str | None = None,
) -> str:
    """Render the dedicated news feed page from a list of game records."""
    from .i18n import get_translator  # noqa: PLC0415
    t = get_translator(lang)
    items: list[tuple[int, GameRecord, NewsItem]] = []
    for record in records:
        for item in record.news:
            items.append((int(item.date.timestamp()), record, item))
    items.sort(key=lambda x: x[0], reverse=True)

    rows_html = "\n".join(make_news_row(rec, it, t) for _, rec, it in items)
    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")

    return _apply_html_t(
        _NEWS_TEMPLATE.replace("__SHARED_JS__", _SHARED_JS)
        .replace("__I18N_JS__", _build_i18n_js(t))
        .replace("__GENERATED_AT__", now_str)
        .replace("__STEAM_ID__", html.escape(steam_id))
        .replace("__ROWS__", rows_html)
        .replace("__LIB_HREF__", html.escape(library_href)),
        t,
    )


def write_news_html(
    records: list[GameRecord],
    steam_id: str,
    output_path: Path,
    library_href: str = "steam_library.html",
    lang: str | None = None,
) -> None:
    """Write the rendered news feed page to *output_path*."""
    output_path.write_text(
        generate_news_html(records, steam_id, library_href, lang), encoding="utf-8"
    )
