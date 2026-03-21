"""HTML renderer: turns a list of GameRecords into a self-contained page."""
from __future__ import annotations

import contextlib
import html
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from .models import Alert, GameRecord

if TYPE_CHECKING:
    from .i18n import Translator

# ─── Shared Filter CSS (injected into both HTML templates) ───────────────────
_SHARED_FILTER_CSS = """\
  .toolbar-filters { display:none; gap:16px 28px; flex-wrap:wrap; padding:14px 40px 18px; border-top:1px solid var(--border); background:rgba(0,0,0,.14); }
  .toolbar-filters.open { display:flex; }
  .filter-group { display:flex; flex-direction:column; gap:6px; }
  .filter-group-label { font-size:10px; font-family:'IBM Plex Mono',monospace; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }
  .filter-btns { display:flex; gap:6px; flex-wrap:wrap; }
  .filter-btn { padding:6px 14px; border-radius:20px; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:12px; cursor:pointer; transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; }
  .filter-btn:hover { border-color:var(--accent); color:var(--accent); }
  .filter-btn.active { background:var(--accent); border-color:var(--accent); color:#000; font-weight:500; }
  .store-btn { padding:6px 14px; border-radius:20px; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:12px; cursor:pointer; transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; }
  .store-btn:hover { border-color:var(--accent); color:var(--accent); }
  .store-btn.active { background:var(--accent); border-color:var(--accent); color:#000; font-weight:500; }
  .tag-btn { padding:6px 14px; border-radius:20px; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:12px; cursor:pointer; transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; }
  .tag-btn:hover { border-color:var(--accent); color:var(--accent); }
  .tag-btn.active { background:var(--accent); border-color:var(--accent); color:#000; font-weight:500; }
  .filter-toggle-btn { padding:6px 14px; border-radius:20px; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:12px; cursor:pointer; transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; display:inline-flex; align-items:center; gap:5px; }
  .filter-toggle-btn:hover { border-color:var(--accent); color:var(--accent); }
  .filter-toggle-btn.has-active { border-color:var(--accent); color:var(--accent); background:rgba(29,185,255,.1); }
  .filter-badge { display:none; align-items:center; justify-content:center; min-width:16px; height:16px; border-radius:8px; background:var(--accent); color:#000; font-size:10px; font-weight:700; padding:0 4px; }
  .filter-badge.show { display:inline-flex; }
  .reset-btn { padding:6px 12px; border-radius:20px; border:1px solid rgba(255,80,80,.3); background:transparent; color:#ff6b6b; font-size:12px; cursor:pointer; transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; display:none; }
  .reset-btn.show { display:inline-flex; align-items:center; gap:4px; }
  .reset-btn:hover { background:rgba(255,80,80,.12); border-color:#ff6b6b; }
  .filter-panel-close { display:none; align-items:center; justify-content:space-between; position:sticky; top:0; background:var(--bg); border:none; border-bottom:1px solid var(--border); padding:16px 0 12px; font-size:14px; font-weight:600; color:var(--text); cursor:pointer; width:100%; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; }
  .filter-panel-close:hover { color:var(--accent); }
  [data-tooltip] { position:relative; }
  [data-tooltip]::after { content:attr(data-tooltip); position:absolute; bottom:calc(100% + 6px); left:50%; transform:translateX(-50%); background:rgba(10,14,20,.97); border:1px solid var(--border); border-radius:5px; padding:5px 10px; font-size:11px; white-space:nowrap; color:var(--text); pointer-events:none; z-index:300; font-family:'IBM Plex Mono',monospace; box-shadow:0 3px 10px rgba(0,0,0,.3); opacity:0; transition:opacity .15s; }
  [data-tooltip]:hover::after { opacity:1; }
  .search-wrap { position:relative; flex:1; min-width:200px; max-width:340px; }
  .search-wrap input { width:100%; background:var(--bg); border:1px solid var(--border); color:var(--text); padding:8px 12px 8px 36px; border-radius:6px; font-size:13px; outline:none; transition:border-color .2s; font-family:inherit; }
  .search-wrap input:focus { border-color:var(--accent); }
  .search-wrap .icon { position:absolute; left:11px; top:50%; transform:translateY(-50%); color:var(--muted); pointer-events:none; }
  select { background:var(--bg); border:1px solid var(--border); color:var(--text); padding:8px 12px; border-radius:6px; font-size:13px; outline:none; cursor:pointer; font-family:inherit; }
  select:focus { border-color:var(--accent); }
"""

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
  if (typeof isDefaultState === 'function') {
    document.getElementById('resetBtn').classList.toggle('show', !isDefaultState());
  }
  if (typeof updateFilterBadge === 'function') updateFilterBadge();
}

// Filter panel toggle
document.getElementById('filtersToggle').addEventListener('click', () => {
  document.getElementById('toolbarFilters').classList.toggle('open');
});
// Mobile filter close button
const _filterClose = document.getElementById('filterPanelClose');
if (_filterClose) {
  _filterClose.addEventListener('click', () => {
    document.getElementById('toolbarFilters').classList.remove('open');
  });
}

// Scroll-to-top + auto-hide toolbar on mobile
const scrollBtn = document.getElementById('scrollTop');
const _toolbar = document.querySelector('.toolbar');
let _lastY = window.scrollY;
if (scrollBtn) {
  window.addEventListener('scroll', () => {
    const y = window.scrollY;
    scrollBtn.classList.toggle('visible', y > 400);
    if (_toolbar && window.innerWidth <= 600) {
      if (y > _lastY && y > 80) _toolbar.classList.add('toolbar-hidden');
      else _toolbar.classList.remove('toolbar-hidden');
    }
    _lastY = y;
  }, {passive: true});
  scrollBtn.addEventListener('click', () => {
    window.scrollTo({top: 0, behavior: 'smooth'});
  });
}

// Theme toggle
const themeBtn = document.getElementById('themeToggle');
function applyTheme(light) {
  document.documentElement.classList.toggle('light', light);
  if (themeBtn) themeBtn.textContent = light ? '🌙' : '☀️';
  try { localStorage.setItem('sp-theme', light ? 'light' : 'dark'); } catch(e) {}
}
if (themeBtn) {
  themeBtn.addEventListener('click', () => {
    applyTheme(!document.documentElement.classList.contains('light'));
  });
}
try { if (localStorage.getItem('sp-theme') === 'light') applyTheme(true); } catch(e) {}

// Keyboard shortcuts
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') {
    if (e.key === 'Escape') { e.target.blur(); document.getElementById('resetBtn').click(); }
    return;
  }
  const searchBox = document.getElementById('search');
  if (searchBox && (e.key === '/' || (e.ctrlKey && e.key === 'k'))) {
    e.preventDefault();
    searchBox.focus();
  }
  if (e.key === 'Escape') {
    document.getElementById('resetBtn').click();
  }
});

// --- Store + collection filter helpers (shared by library and alerts pages) ---
function getActiveStores() {
  const active = Array.from(document.querySelectorAll('#storeBtns .store-btn.active')).map(b => b.dataset.store);
  // Fallback: if crafted URL produced no active store, treat all as active
  if (active.length === 0) {
    return new Set(Array.from(document.querySelectorAll('#storeBtns .store-btn')).map(b => b.dataset.store));
  }
  return new Set(active);
}
function allStoresActive() { const all = document.querySelectorAll('#storeBtns .store-btn'); return Array.from(all).every(b => b.classList.contains('active')); }
function getLibStatusFilter() { return document.querySelector('#libStatusBtns .filter-btn.active').dataset.libStatus; }
// Safe getters for filter groups (return 'all' when element is absent)
function getStatusFilter() { var b = document.querySelector('#filterBtns .filter-btn.active'); return b ? b.dataset.filter : 'all'; }
function getTagFilter()    { var b = document.querySelector('#tagBtns .tag-btn.active'); return b ? b.dataset.tag : 'all'; }
function getPtFilter()     { var b = document.querySelector('#playtimeBtns .filter-btn.active'); return b ? b.dataset.pt : 'all'; }
function getMcFilter()     { var b = document.querySelector('#mcBtns .filter-btn.active'); return b ? b.dataset.mc : 'all'; }
function getRecentFilter() { var b = document.querySelector('#recentBtns .filter-btn.active'); return b ? b.dataset.recent : 'all'; }
function checkMcFilter(mc, card) {
  if (mc === 'all') return true;
  var s = parseInt(card.dataset.metacritic) || 0;
  if (mc === 'none') return s <= 0;
  if (mc === 'bad')  return s > 0 && s < 50;
  if (mc === 'mid')  return s >= 50 && s <= 75;
  if (mc === 'good') return s > 75;
  return true;
}
function setupStoreFilter(updateFn) {
  document.querySelectorAll('#storeBtns .store-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const active = document.querySelectorAll('#storeBtns .store-btn.active');
      if (active.length === 1 && btn.classList.contains('active')) return;
      btn.classList.toggle('active');
      updateFn();
    });
  });
}
// Load stores state from URL hash; also handles legacy source= parameter.
function loadStoreHash(p) {
  if (p.get('stores')) {
    const storeSet = new Set(p.get('stores').split(',').filter(Boolean));
    document.querySelectorAll('#storeBtns .store-btn').forEach(b => {
      b.classList.toggle('active', storeSet.has(b.dataset.store));
    });
  } else if (p.get('source')) {
    // Backward compat: map old source= values to new store+lib filters.
    const src = p.get('source');
    if (src === 'epic') {
      document.querySelectorAll('#storeBtns .store-btn').forEach(b => {
        b.classList.toggle('active', b.dataset.store === 'epic');
      });
    } else if (src !== 'all') {
      activateBtn('#libStatusBtns .filter-btn', 'libStatus', src);
    }
  }
}

// --- Cross-page filter persistence ---
// window.name persists across same-tab navigations (works with file://)
// localStorage is a fallback for HTTP contexts (shared across tabs)
var SP_FILTER_KEY = 'sp-filters';
var SP_WIN_PREFIX = 'sp:';
function saveFilterState() {
  try {
    var state = {};
    if (!allStoresActive()) {
      state.stores = Array.from(getActiveStores()).join(',');
    }
    if (getLibStatusFilter() !== 'all') state.lib = getLibStatusFilter();
    if (getStatusFilter() !== 'all') state.status = getStatusFilter();
    if (getPtFilter() !== 'all') state.pt = getPtFilter();
    if (getMcFilter() !== 'all') state.mc = getMcFilter();
    if (getRecentFilter() !== 'all') state.recent = getRecentFilter();
    if (getTagFilter() !== 'all') state.tag = getTagFilter();
    var json = JSON.stringify(state);
    window.name = SP_WIN_PREFIX + json;
    try { localStorage.setItem(SP_FILTER_KEY, json); } catch(e2) {}
  } catch(e) {}
}
function loadFilterState() {
  try {
    var raw = null;
    if (window.name && window.name.indexOf(SP_WIN_PREFIX) === 0) {
      raw = window.name.substring(SP_WIN_PREFIX.length);
    }
    if (!raw) {
      try { raw = localStorage.getItem(SP_FILTER_KEY); } catch(e2) {}
    }
    if (!raw) return;
    var state = JSON.parse(raw);
    if (state.stores) {
      var storeSet = new Set(state.stores.split(',').filter(Boolean));
      document.querySelectorAll('#storeBtns .store-btn').forEach(function(b) {
        b.classList.toggle('active', storeSet.has(b.dataset.store));
      });
    }
    if (state.lib) {
      activateBtn('#libStatusBtns .filter-btn', 'libStatus', state.lib);
    }
    if (state.status) {
      activateBtn('#filterBtns .filter-btn', 'filter', state.status);
    }
    if (state.pt) {
      activateBtn('#playtimeBtns .filter-btn', 'pt', state.pt);
    }
    if (state.mc) {
      activateBtn('#mcBtns .filter-btn', 'mc', state.mc);
    }
    if (state.recent) {
      activateBtn('#recentBtns .filter-btn', 'recent', state.recent);
    }
    if (state.tag) {
      activateBtn('#tagBtns .tag-btn', 'tag', state.tag);
    }
  } catch(e) {}
}"""

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
    transition: transform .3s ease;
  }
  .toolbar.toolbar-hidden { transform: translateY(-100%); }
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
    aspect-ratio: 460 / 215;
    object-fit: cover;
    display: block;
    background: var(--surface2);
    border-radius: 10px 10px 0 0;
  }
  .card-img-placeholder {
    width: 100%;
    aspect-ratio: 460 / 215;
    background: linear-gradient(135deg, #0d1a2e, #1a2a45);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--muted);
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    border-radius: 10px 10px 0 0;
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

  /* NEWS OVERLAY — expanded card floats above grid */
  .card.expanded {
    overflow: visible;
    content-visibility: visible;
    z-index: 50;
    border-color: var(--accent) !important;
    box-shadow: 0 8px 40px rgba(0,0,0,.75), 0 0 0 1px var(--accent);
  }
  .card.expanded .news-list {
    display: block;
    position: absolute;
    left: -1px; right: -1px;
    top: calc(100% - 1px);
    background: var(--surface);
    border: 1px solid var(--accent);
    border-top: 1px solid var(--border);
    border-radius: 0 0 10px 10px;
    padding: 12px 16px 14px;
    z-index: 50;
    box-shadow: 0 16px 40px rgba(0,0,0,.6);
  }
  /* Dim + blur all other cards when one is expanded */
  .grid.has-expanded .card:not(.expanded) {
    opacity: 0.3;
    filter: blur(1.5px);
    transform: scale(0.975);
    pointer-events: none;
    transition: opacity .25s, filter .25s, transform .25s;
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

  /* METACRITIC TOOLTIP */
  .mc-tt-wrap { position: relative; display: inline-flex; align-items: center; }
  .mc-tt {
    position: absolute;
    bottom: calc(100% + 8px); left: 50%;
    transform: translateX(-50%);
    min-width: 130px;
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 7px;
    padding: 8px 12px;
    text-align: center;
    font-size: 11px;
    font-family: 'IBM Plex Mono', monospace;
    color: var(--text);
    opacity: 0;
    pointer-events: none;
    transition: opacity .15s;
    z-index: 300;
    white-space: nowrap;
    box-shadow: 0 4px 16px rgba(0,0,0,.4);
  }
  .mc-tt::after {
    content: ''; position: absolute;
    top: 100%; left: 50%; transform: translateX(-50%);
    border: 5px solid transparent;
    border-top-color: var(--border);
  }
  .mc-tt-score { display: block; font-size: 15px; font-weight: 600; color: var(--accent); margin-bottom: 3px; }
  .mc-tt-label { display: block; font-size: 10px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); }
  .mc-tt-wrap:hover .mc-tt { opacity: 1; }

  /* GENERIC TOOLTIP via data-tooltip attribute */
  [data-tooltip] { position: relative; }
  [data-tooltip]::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: calc(100% + 6px); left: 50%;
    transform: translateX(-50%);
    background: rgba(10,14,20,.97);
    border: 1px solid var(--border);
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 11px;
    white-space: nowrap;
    color: var(--text);
    pointer-events: none;
    z-index: 300;
    font-family: 'IBM Plex Mono', monospace;
    box-shadow: 0 3px 10px rgba(0,0,0,.3);
    opacity: 0;
    transition: opacity .15s;
  }
  [data-tooltip]:hover::after { opacity: 1; }

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

  /* STORE FILTER (multi-select toggle) */
  .store-btn {
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
  .store-btn:hover { border-color: var(--accent); color: var(--accent); }
  .store-btn.active { background: var(--accent); border-color: var(--accent); color: #000; font-weight: 500; }

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

  /* FILTER PANEL CLOSE BUTTON (mobile only by default) */
  .filter-panel-close {
    display: none;
    align-items: center;
    justify-content: space-between;
    position: sticky; top: 0;
    background: var(--bg);
    border: none;
    border-bottom: 1px solid var(--border);
    padding: 16px 0 12px;
    font-size: 14px;
    font-weight: 600;
    color: var(--text);
    cursor: pointer;
    width: 100%;
    font-family: 'IBM Plex Mono', monospace;
    letter-spacing: .5px;
  }
  .filter-panel-close:hover { color: var(--accent); }

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
    header { padding: 16px 16px 12px; gap: 12px; }
    header svg { display: none; }
    .header-text h1 { font-size: 22px; letter-spacing: 1px; }
    .header-stats { gap: 8px 16px; flex-wrap: wrap; justify-content: center; }
    .stat-val { font-size: 18px; }
    .stat-lbl { font-size: 9px; }
    .toolbar-main { gap: 6px; padding-top: 8px; padding-bottom: 8px; }
    .search-wrap { max-width: 100%; min-width: 0; flex: 1 1 100%; }
    select { font-size: 12px; padding: 6px 8px; }
    .view-toggle, .filter-toggle-btn, .nav-link { font-size: 11px; padding: 5px 10px; }
    .count-label { font-size: 10px; }
    .grid { grid-template-columns: 1fr; }
    .grid.list-view .card-img { width: 80px; }
    .scroll-top { bottom: 16px; right: 16px; }
    .theme-toggle { bottom: 16px; left: 16px; }
    /* Mobile filter overlay */
    #toolbarFilters.open {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      z-index: 1000;
      overflow-y: auto;
      background: var(--bg);
      display: flex !important;
      flex-direction: column;
      padding: 0 20px 40px;
      border-top: none;
      gap: 20px;
    }
    .filter-panel-close { display: flex; }
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
    <a class="nav-link" href="__ALERTS_HREF__">🔔 __T_link_alerts__</a>
  </div>
  <div class="toolbar-filters" id="toolbarFilters">
    <button type="button" class="filter-panel-close" id="filterPanelClose">__T_btn_filters__ <span>✕</span></button>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_status__</div>
      <div class="filter-btns" id="filterBtns">
        <button class="filter-btn active" data-filter="all">__T_lbl_all__</button>
        <button class="filter-btn" data-filter="earlyaccess" data-tooltip="__T_tt_filter_earlyaccess__">Early Access</button>
        <button class="filter-btn" data-filter="released" data-tooltip="__T_tt_filter_released__">__T_lbl_released__</button>
        <button class="filter-btn" data-filter="unreleased" data-tooltip="__T_tt_filter_unreleased__">__T_lbl_upcoming__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_store__</div>
      <div class="filter-btns" id="storeBtns">
        <button class="store-btn active" data-store="steam">🎮 Steam</button>
        <button class="store-btn active" data-store="epic">⚡ Epic</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_collection__</div>
      <div class="filter-btns" id="libStatusBtns">
        <button class="filter-btn active" data-lib-status="all">__T_lbl_all__</button>
        <button class="filter-btn" data-lib-status="owned" data-tooltip="__T_tt_filter_lib_owned__">__T_lbl_owned__</button>
        <button class="filter-btn" data-lib-status="wishlist" data-tooltip="__T_tt_filter_lib_wishlist__">🎁 Wishlist</button>
        <button class="filter-btn" data-lib-status="followed" data-tooltip="__T_tt_filter_lib_followed__">👁 __T_lbl_followed__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_news_type__</div>
      <div class="filter-btns" id="tagBtns">
        <button class="tag-btn active" data-tag="all">__T_lbl_all_types__</button>
        <button class="tag-btn" data-tag="patchnotes" data-tooltip="__T_tt_filter_tag_patch__">📋 Patch notes</button>
        <button class="tag-btn" data-tag="other" data-tooltip="__T_tt_filter_tag_news__">📰 News</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_playtime__</div>
      <div class="filter-btns" id="playtimeBtns">
        <button class="filter-btn active" data-pt="all">__T_lbl_all__</button>
        <button class="filter-btn" data-pt="0" data-tooltip="__T_tt_filter_pt_0__">__T_lbl_never_played__</button>
        <button class="filter-btn" data-pt="60" data-tooltip="__T_tt_filter_pt_60__">&lt; 1h</button>
        <button class="filter-btn" data-pt="600" data-tooltip="__T_tt_filter_pt_600__">1-10h</button>
        <button class="filter-btn" data-pt="601" data-tooltip="__T_tt_filter_pt_601__">&gt; 10h</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_metacritic__</div>
      <div class="filter-btns" id="mcBtns">
        <button class="filter-btn active" data-mc="all">__T_lbl_all__</button>
        <button class="filter-btn" data-mc="none" data-tooltip="__T_tt_filter_mc_none__">__T_lbl_no_score__</button>
        <button class="filter-btn" data-mc="bad" data-tooltip="__T_tt_filter_mc_bad__">&lt; 50</button>
        <button class="filter-btn" data-mc="mid" data-tooltip="__T_tt_filter_mc_mid__">50–75</button>
        <button class="filter-btn" data-mc="good" data-tooltip="__T_tt_filter_mc_good__">&gt; 75</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_recent__</div>
      <div class="filter-btns" id="recentBtns">
        <button class="filter-btn active" data-recent="all">__T_lbl_all__</button>
        <button class="filter-btn" data-recent="2" data-tooltip="__T_tt_filter_recent_2__">__T_lbl_2_days__</button>
        <button class="filter-btn" data-recent="5" data-tooltip="__T_tt_filter_recent_5__">__T_lbl_5_days__</button>
        <button class="filter-btn" data-recent="15" data-tooltip="__T_tt_filter_recent_15__">__T_lbl_15_days__</button>
        <button class="filter-btn" data-recent="30" data-tooltip="__T_tt_filter_recent_30__">__T_lbl_30_days__</button>
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
function getSearch()    { return document.getElementById('search').value.toLowerCase().trim(); }
function getSort()      { return document.getElementById('sortBy').value; }

function isDefaultState() {
  return getStatusFilter() === 'all' && allStoresActive() && getLibStatusFilter() === 'all' && getTagFilter() === 'all'
    && getPtFilter() === 'all' && getMcFilter() === 'all' && getRecentFilter() === 'all'
    && !getSearch() && getSort() === 'name';
}

function updateFilterBadge() {
  let n = 0;
  if (getStatusFilter() !== 'all')   n++;
  if (!allStoresActive())             n++;
  if (getLibStatusFilter() !== 'all') n++;
  if (getTagFilter() !== 'all')      n++;
  if (getPtFilter() !== 'all')       n++;
  if (getMcFilter() !== 'all')       n++;
  if (getRecentFilter() !== 'all')   n++;
  const badge = document.getElementById('filterBadge');
  badge.textContent = n;
  badge.classList.toggle('show', n > 0);
  document.getElementById('filtersToggle').classList.toggle('has-active', n > 0);
}

function saveStateToHash() {
  const s = {};
  if (getStatusFilter() !== 'all')    s.status = getStatusFilter();
  if (!allStoresActive())             s.stores = Array.from(getActiveStores()).join(',');
  if (getLibStatusFilter() !== 'all') s.lib = getLibStatusFilter();
  if (getTagFilter() !== 'all')       s.tag = getTagFilter();
  if (getPtFilter() !== 'all')        s.pt = getPtFilter();
  if (getMcFilter() !== 'all')        s.mc = getMcFilter();
  if (getRecentFilter() !== 'all')    s.recent = getRecentFilter();
  if (getSearch())                    s.q = getSearch();
  if (getSort() !== 'name')           s.sort = getSort();
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
  const navLink = document.querySelector('.nav-link[href^="steam_alerts"]');
  if (navLink) {
    const nf = {};
    if (getStatusFilter() !== 'all')    nf.status = getStatusFilter();
    if (!allStoresActive())             nf.stores = Array.from(getActiveStores()).join(',');
    if (getLibStatusFilter() !== 'all') nf.lib = getLibStatusFilter();
    if (getTagFilter() !== 'all')       nf.tag = getTagFilter();
    if (getPtFilter() !== 'all')        nf.pt = getPtFilter();
    if (getMcFilter() !== 'all')        nf.mc = getMcFilter();
    if (getRecentFilter() !== 'all')    nf.recent = getRecentFilter();
    if (getSearch())                    nf.q = getSearch();
    if (getSort() !== 'name')           nf.sort = getSort();
    const nh = new URLSearchParams(nf).toString();
    navLink.href = 'steam_alerts.html' + (nh ? '#' + nh : '');
  }
  saveFilterState();
}

function loadStateFromHash() {
  // Load cross-page filter state (stores + lib-status) from localStorage
  loadFilterState();
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
  loadStoreHash(p);
  if (p.get('lib'))    { activateBtn('#libStatusBtns .filter-btn', 'libStatus', p.get('lib')); }
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
  const filter          = getStatusFilter();
  const activeStores    = getActiveStores();
  const libStatusFilter = getLibStatusFilter();
  const tagFilter       = getTagFilter();
  const ptFilter        = getPtFilter();
  const search          = getSearch();
  const sort            = getSort();

  const mcFilter     = getMcFilter();
  const recentFilter  = getRecentFilter();
  let visible = allCards.filter(c => {
    const badgeOk     = filter === 'all' || c.dataset.status === filter;
    const storeOk     = activeStores.has(c.dataset.store);
    const libStatusOk = libStatusFilter === 'all' || c.dataset.libStatus === libStatusFilter;
    const searchOk    = !search || c.dataset.name.includes(search);
    const ptOk        = checkPtFilter(ptFilter, c);
    const mcOk        = checkMcFilter(mcFilter, c);
    const recentOk    = checkRecentFilter(recentFilter, c);
    return badgeOk && storeOk && libStatusOk && searchOk && ptOk && mcOk && recentOk;
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
setupStoreFilter(updateGrid);
setupFilterGroup('#libStatusBtns .filter-btn');
setupFilterGroup('#tagBtns .tag-btn');
setupFilterGroup('#playtimeBtns .filter-btn');
setupFilterGroup('#mcBtns .filter-btn');
setupFilterGroup('#recentBtns .filter-btn');

// Reset
document.getElementById('resetBtn').addEventListener('click', () => {
  document.getElementById('search').value = '';
  document.getElementById('sortBy').value = 'name';
  document.querySelectorAll('#storeBtns .store-btn').forEach(b => b.classList.add('active'));
  ['#filterBtns .filter-btn', '#libStatusBtns .filter-btn', '#tagBtns .tag-btn', '#playtimeBtns .filter-btn', '#mcBtns .filter-btn', '#recentBtns .filter-btn'].forEach(sel => {
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

// Expand/collapse news — single open at a time, overlay mode
document.querySelectorAll('.news-toggle').forEach(toggle => {
  toggle.addEventListener('click', e => {
    e.stopPropagation();
    const card = toggle.closest('.card');
    const grid = document.getElementById('grid');
    const wasExpanded = card.classList.contains('expanded');
    document.querySelectorAll('.card.expanded').forEach(c => c.classList.remove('expanded'));
    if (!wasExpanded) card.classList.add('expanded');
    grid.classList.toggle('has-expanded', !wasExpanded);
  });
});
// Close expanded card when clicking outside
document.addEventListener('click', e => {
  if (!e.target.closest('.card.expanded')) {
    document.querySelectorAll('.card.expanded').forEach(c => c.classList.remove('expanded'));
    document.getElementById('grid').classList.remove('has-expanded');
  }
});

// Open Steam store on card click
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('click', e => {
    if (e.target.closest('.news-toggle') || e.target.closest('.news-list')) return;
    const appid = card.dataset.appid;
    if (appid) { var w = window.open('https://store.steampowered.com/app/' + appid, '_blank', 'noopener,noreferrer'); if (w) w.opener = null; }
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



def _build_i18n_js(t: Translator) -> str:
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


def _apply_html_t(s: str, t: Translator) -> str:
    """Replace all ``__T_key__`` placeholders in *s* with translated values."""
    import re
    for key in re.findall(r"__T_(\w+)__", s):
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
    if m := re.search(r"\b((?:19|20)\d{2})\b", s):
        with contextlib.suppress(ValueError):
            return int(datetime(int(m.group()), 1, 1, tzinfo=UTC).timestamp())
    return 0


def _metacritic_html(score: int, url: str, t: Translator | None = None) -> str:
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator()
    if score <= 0:
        return ""
    if score >= 75:
        cls = "mc-green"
        label = t("tt_mc_favorable")
    elif score >= 50:
        cls = "mc-yellow"
        label = t("tt_mc_mixed")
    else:
        cls = "mc-red"
        label = t("tt_mc_negative")
    badge = f'<span class="metacritic-badge {cls}">MC {score}</span>'
    tooltip = (
        f'<span class="mc-tt">'
        f'<span class="mc-tt-score">{score}\u00a0/\u00a0100</span>'
        f'<span class="mc-tt-label">{html.escape(label)}</span>'
        f'</span>'
    )
    if url:
        safe_url = html.escape(url)
        inner = f'<a href="{safe_url}" target="_blank" rel="noopener" style="text-decoration:none">{badge}</a>'
    else:
        inner = badge
    return f'<span class="mc-tt-wrap">{inner}{tooltip}</span>'


def _price_html(details: object, t: Translator | None = None) -> str:
    from .models import AppDetails  # local import to avoid circular
    if not isinstance(details, AppDetails):
        return ""
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator()
    price_free_lbl = t("price_free")
    price_tip = html.escape(t("tt_price"))
    if details.is_free:
        return f'<span class="price-free" data-tooltip="{price_tip}">{price_free_lbl}</span>'
    if details.price_final <= 0:
        return ""
    currency = html.escape(details.price_currency)
    final = f"{details.price_final / 100:.2f} {currency}"
    if details.price_discount_pct > 0:
        original = f"{details.price_initial / 100:.2f} {currency}"
        return (
            f'<span class="price-tag" data-tooltip="{price_tip}">'
            f'<span class="price-discount">{original}</span>'
            f" {final} (-{details.price_discount_pct}%)"
            f"</span>"
        )
    return f'<span class="price-tag" data-tooltip="{price_tip}">{final}</span>'


def _platform_html(details: object, t: Translator | None = None) -> str:
    from .models import AppDetails
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator()
    if not isinstance(details, AppDetails):
        return ""
    icons = []
    if details.platform_windows:
        icons.append(f'<span data-tooltip="{html.escape(t("tt_platform_windows"))}">🪟</span>')
    if details.platform_mac:
        icons.append(f'<span data-tooltip="{html.escape(t("tt_platform_mac"))}">🍎</span>')
    if details.platform_linux:
        icons.append(f'<span data-tooltip="{html.escape(t("tt_platform_linux"))}">🐧</span>')
    return f'<span class="platform-icons">{"".join(icons)}</span>' if icons else ""


def make_card(record: GameRecord, t: Translator | None = None) -> str:
    """Return the HTML string for a single game card."""
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator()
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

    # ── element tooltips ────────────────────────────────────────────────────
    _tt_badge = html.escape(t(f"tt_badge_{status.badge}"))
    _tt_dev = html.escape(t("tt_developer"))
    _tt_rel = html.escape(t("tt_release_date"))
    _tt_news = html.escape(t("tt_last_news"))
    _tt_pt = html.escape(t("tt_playtime"))

    # ── developer / platform / metacritic / price row ──────────────────────
    detail_parts: list[str] = []
    if details and details.developers:
        detail_parts.append(
            f'<span class="dev-name" data-tooltip="{_tt_dev}">{html.escape(details.developers[0])}</span>'
        )
    plat = _platform_html(details, t) if details else ""
    if plat:
        detail_parts.append(plat)
    mc = _metacritic_html(details.metacritic_score, details.metacritic_url, t) if details else ""
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

    news_section_html = (
        f'    <div class="news-section">\n'
        f'      <div class="news-toggle">\n'
        f'        <div class="news-title">\U0001f5de {html.escape(toggle_lbl)}</div>\n'
        f'        <span class="news-toggle-icon">\u25bc</span>\n'
        f"      </div>\n"
        f"    </div>\n"
    ) if nc > 0 else ""
    news_list_html = (
        f'  <div class="news-list">\n'
        f"    {news_html}\n"
        f"  </div>\n"
    ) if nc > 0 else ""

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
        elif _ts > last_other_ts:
            last_other_ts = _ts
            last_other_date = _n.date.strftime("%d/%m/%Y")
    placeholder = html.escape(game.name[:2].upper())
    store_tag = "epic" if game.source == "epic" else "steam"
    lib_status_tag = "owned" if game.source in ("owned", "epic") else game.source
    if game.source == "wishlist":
        pt_display = t("source_wishlist")
    elif game.source == "followed":
        pt_display = t("source_followed")
    elif game.source == "epic":
        pt_display = t("source_epic")
    else:
        pt_display = f"🕹 {pt_fmt}"
    metacritic_score = details.metacritic_score if details else 0
    store_hint = "🎮 Epic" if game.source == "epic" else "↗ Steam"
    _pt_attr = f' data-tooltip="{_tt_pt}"' if game.source == "owned" else ""
    return (
        f'<div class="card" data-appid="{appid}" data-status="{status.badge}" '
        f'data-store="{store_tag}" data-lib-status="{lib_status_tag}" data-name="{name.lower()}" '
        f'data-playtime="{game.playtime_forever}" '
        f'data-metacritic="{metacritic_score}" '
        f'data-release="{rel_date}" data-release-ts="{release_ts}" '
        f'data-last-update="{last_update_ts}" '
        f'data-last-patch-ts="{last_patch_ts}" data-last-other-ts="{last_other_ts}">\n'
        f'  <span class="card-ext-hint">{store_hint}</span>\n'
        f'  <img class="card-img" src="{html.escape(img_url)}" alt="" loading="lazy"'
        f"    onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">\n"
        f'  <div class="card-img-placeholder" style="display:none">{placeholder}</div>\n'
        f'  <div class="card-body">\n'
        f'    <div class="col-title">\n'
        f'    <div class="card-top">\n'
        f'      <div class="card-title">{name}</div>\n'
        f'      <span class="{html.escape(badge_cls)}" data-tooltip="{_tt_badge}">{html.escape(badge_label)}</span>\n'
        f"    </div>\n"
        f"    </div>\n"
        f'    <div class="col-detail">{detail_row}</div>\n'
        f'    <div class="col-genres">{genres_html}</div>\n'
        f'    <div class="col-meta">\n'
        f'    <div class="card-meta">\n'
        f'      <span data-tooltip="{_tt_rel}">📅 {rel_date}</span>\n'
        f'      <span class="news-date-display" data-tooltip="{_tt_news}"'
        f' data-date-all="{html.escape(last_all_date)}"'
        f' data-date-patch="{html.escape(last_patch_date)}"'
        f' data-date-other="{html.escape(last_other_date)}">'
        f'\U0001f4f0 {html.escape(last_all_date) or "—"}</span>\n'
        f'      <span{_pt_attr}>{pt_display}</span>\n'
        f"    </div>\n"
        f"    </div>\n"
        f"{news_section_html}"
        f"  </div>\n"
        f"{news_list_html}"
        f"</div>"
    )


def generate_html(
    records: list[GameRecord],
    steam_id: str,
    alerts_href: str = "steam_alerts.html",
    lang: str | None = None,
) -> str:
    """Render the full HTML page from a list of game records."""
    from .i18n import get_translator  # noqa: PLC0415
    t = get_translator(lang)
    cards_html = "\n".join(make_card(r, t) for r in records)
    total = len(records)
    ea = sum(r.status.badge == "earlyaccess" for r in records)
    released = sum(r.status.badge == "released" for r in records)
    unrel = sum(r.status.badge == "unreleased" for r in records)
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
        .replace("__ALERTS_HREF__", html.escape(alerts_href)),
        t,
    )


def write_html(
    records: list[GameRecord],
    steam_id: str,
    output_path: Path,
    alerts_href: str = "steam_alerts.html",
    lang: str | None = None,
) -> None:
    """Write the rendered HTML page to *output_path*."""
    output_path.write_text(generate_html(records, steam_id, alerts_href, lang), encoding="utf-8")



def make_alert_card(
    alert: Alert, record: GameRecord | None = None, t: Translator | None = None
) -> str:
    """Return the HTML for a single alert card.

    Args:
        alert: The :class:`~steam_tracker.models.Alert` to render.
        record: Optional :class:`~steam_tracker.models.GameRecord` for the game
            (used for the thumbnail image).
        t: Translation callable.  If ``None``, falls back to English.

    Returns:
        HTML string for one ``.alert-card`` element.
    """
    if t is None:
        from .i18n import get_translator  # noqa: PLC0415
        t = get_translator()

    details = record.details if record else None
    game = record.game if record else None
    img_url = (
        details.header_image
        if details and details.header_image
        else f"https://cdn.akamai.steamstatic.com/steam/apps/{alert.appid}/header.jpg"
    )
    ts = int(alert.timestamp.timestamp()) if alert.timestamp else 0
    date_str = alert.timestamp.strftime("%d/%m/%Y") if alert.timestamp else "—"
    title_html = (
        f'<a href="{html.escape(alert.url)}" target="_blank" rel="noopener">'
        f"{html.escape(alert.title)}</a>"
        if alert.url
        else html.escape(alert.title)
    )
    details_html = (
        f'<p class="alert-details">{html.escape(alert.details)}</p>' if alert.details else ""
    )
    # Store & collection data attributes for filtering
    store_tag = "epic" if game and game.source == "epic" else "steam"
    collection_tag = (
        ("owned" if game.source in ("owned", "epic") else game.source)
        if game
        else "owned"
    )
    # Game-level data attributes for shared filters
    status_tag = record.status.badge if record else "released"
    playtime_val = game.playtime_forever if game else 0
    metacritic_val = details.metacritic_score if details and details.metacritic_score else 0
    # Compute last_patch_ts from game news (same logic as library page)
    last_patch_ts = 0
    if record and record.news:
        for _n in record.news:
            _primary = _n.tags[0].lower() if _n.tags else ""
            if _primary == "patchnotes":
                _ts = int(_n.date.timestamp())
                if _ts > last_patch_ts:
                    last_patch_ts = _ts
    # Buildid badge
    buildid = details.buildid if details and details.buildid else 0
    buildid_html = (
        f'      <span class="alert-buildid">build {buildid}</span>\n'
        if buildid
        else ""
    )
    # Tag for news-type filter: match alert to its NewsItem via source_id/gid
    tag_val = "other"
    if alert.source_type == "news" and record and record.news:
        news_item = next(
            (n for n in record.news if str(n.gid) == alert.source_id), None,
        )
        if news_item and any(t.lower() == "patchnotes" for t in news_item.tags):
            tag_val = "patchnotes"
    store_url = f"https://store.steampowered.com/app/{alert.appid}"
    news_url_attr = f' data-news-url="{html.escape(alert.url)}"' if alert.url else ""
    return (
        f'<div class="alert-card" data-id="{html.escape(alert.id)}" '
        f'data-rule="{html.escape(alert.rule_name)}" '
        f'data-game="{html.escape(alert.game_name)}" '
        f'data-name="{html.escape(alert.game_name.lower())}" '
        f'data-appid="{alert.appid}" data-ts="{ts}" '
        f'data-source="{html.escape(alert.source_type)}" '
        f'data-store="{store_tag}" data-lib-status="{collection_tag}" '
        f'data-status="{status_tag}" data-playtime="{playtime_val}" '
        f'data-metacritic="{metacritic_val}" data-last-patch-ts="{last_patch_ts}" '
        f'data-tag="{tag_val}" data-store-url="{html.escape(store_url)}"'
        f'{news_url_attr}>\n'
        f'  <a class="alert-thumb-link" href="{html.escape(store_url)}" target="_blank" rel="noopener">'
        f'<img class="alert-thumb" src="{html.escape(img_url)}" alt="" loading="lazy"></a>\n'
        f'  <div class="alert-body">\n'
        f'    <div class="alert-meta">\n'
        f'      <span class="alert-icon">{html.escape(alert.rule_icon)}</span>'
        f'      <span class="alert-rule">{html.escape(alert.rule_name)}</span>'
        f'      <a class="alert-game" href="{html.escape(store_url)}" target="_blank" rel="noopener">{html.escape(alert.game_name)}</a>'
        f'      <span class="alert-date">{date_str}</span>\n'
        f"{buildid_html}"
        f"    </div>\n"
        f'    <div class="alert-title">{title_html}</div>\n'
        f"{details_html}"
        f"  </div>\n"
        f'  <button class="mark-read-btn" data-id="{html.escape(alert.id)}" '
        f'title="__T_btn_mark_read__">✓</button>\n'
        f"</div>"
    )


_ALERTS_TEMPLATE = """\
<!DOCTYPE html>
<html lang="__T_html_lang__">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SteamPulse — __T_alert_page_title__</title>
<link href="https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:#0a0e14; --surface:#111722; --border:#1f2d45;
    --accent:#1db9ff; --text:#c8d8ef; --muted:#5a7199;
    --unread:#f5a623; --read-op:0.45;
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
  .nav-link { padding:6px 14px; border-radius:20px; border:1px solid var(--border); color:var(--muted); font-size:12px; text-decoration:none; transition:all .2s; font-family:'IBM Plex Mono',monospace; letter-spacing:.5px; }
  .nav-link:hover { border-color:var(--accent); color:var(--accent); }
  .toolbar { border-bottom:1px solid var(--border); background:var(--surface); position:sticky; top:0; z-index:100; transition:transform .3s ease; }
  .toolbar.toolbar-hidden { transform:translateY(-100%); }
  .toolbar-main { padding:11px 40px; display:flex; gap:10px; align-items:center; flex-wrap:wrap; }
  .view-btn { padding:5px 14px; border-radius:16px; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:12px; cursor:pointer; transition:all .2s; font-family:'IBM Plex Mono',monospace; }
  .view-btn:hover, .view-btn.active { border-color:var(--accent); color:var(--accent); background:rgba(29,185,255,.07); }
  .action-btn { padding:5px 14px; border-radius:16px; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:12px; cursor:pointer; transition:all .2s; }
  .action-btn:hover { border-color:var(--text); color:var(--text); }
  .spacer { flex:1; }
  .count-label { font-size:11px; color:var(--muted); font-family:'IBM Plex Mono',monospace; }
  main { padding:28px 40px; max-width:1400px; }
  .section-header { font-family:'Rajdhani',sans-serif; font-size:16px; font-weight:600; color:var(--text); text-transform:uppercase; letter-spacing:1px; padding:12px 0 8px; border-bottom:1px solid var(--border); margin-bottom:12px; margin-top:20px; display:flex; align-items:center; gap:10px; cursor:pointer; user-select:none; transition:color .2s; }
  .section-header:first-child { margin-top:0; }
  .section-header:hover { color:var(--accent); }
  .section-header.collapsed { margin-bottom:0; }
  .section-chevron { display:inline-block; width:14px; font-size:11px; transition:transform .2s; flex-shrink:0; }
  .section-header:not(.collapsed) .section-chevron { transform:rotate(90deg); }
  .section-cards { margin-bottom:0; }
  .section-cards.collapsed { display:none; }
  .group-controls { display:none; align-items:center; gap:8px; }
  .group-controls.visible { display:flex; }
  .section-badge { background:rgba(29,185,255,.12); border:1px solid rgba(29,185,255,.3); color:var(--accent); border-radius:12px; padding:1px 8px; font-size:11px; font-family:'IBM Plex Mono',monospace; }
  .section-header .section-thumb { width:64px; height:30px; object-fit:cover; border-radius:4px; flex-shrink:0; }
  .sub-section-header { font-family:'IBM Plex Mono',monospace; font-size:13px; font-weight:500; color:var(--muted); padding:8px 0 4px 18px; border-bottom:1px solid rgba(31,45,69,.5); margin-bottom:8px; margin-top:12px; display:flex; align-items:center; gap:8px; cursor:pointer; user-select:none; transition:color .2s; }
  .sub-section-header:hover { color:var(--accent); }
  .sub-section-header.collapsed { margin-bottom:0; }
  .sub-section-cards { margin-bottom:0; padding-left:18px; }
  .sub-section-cards.collapsed { display:none; }
  .alert-card { display:flex; align-items:flex-start; gap:12px; padding:12px 16px; border:1px solid var(--border); border-radius:8px; background:var(--surface); margin-bottom:8px; transition:border-color .2s, opacity .2s; }
  .alert-card:hover { border-color:rgba(29,185,255,.35); }
  .alert-card.read { opacity:var(--read-op); }
  .alert-card.hidden { display:none; }
  .alert-thumb-link { flex-shrink:0; line-height:0; }
  .alert-thumb { width:120px; height:56px; object-fit:cover; border-radius:4px; flex-shrink:0; transition:width .2s, height .2s; }
  .grouped-by-game .alert-thumb-link { display:none; }
  .grouped-by-game .alert-game { display:none; }
  .alert-body { flex:1; min-width:0; cursor:default; }
  .alert-meta { display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:4px; }
  .alert-icon { font-size:14px; }
  .alert-rule { font-size:11px; color:var(--accent); font-family:'IBM Plex Mono',monospace; }
  .alert-game { font-size:11px; color:var(--muted); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; text-decoration:none; }
  .alert-game:hover { color:var(--accent); text-decoration:underline; }
  .alert-date { font-size:11px; color:var(--muted); font-family:'IBM Plex Mono',monospace; white-space:nowrap; margin-left:auto; }
  .alert-title { font-size:13px; color:var(--text); line-height:1.4; cursor:pointer; }
  .alert-title a { color:var(--text); text-decoration:none; }
  .alert-title a:hover { color:var(--accent); text-decoration:underline; }
  .alert-details { font-size:12px; color:var(--muted); margin-top:4px; line-height:1.5; cursor:pointer; }
  .mark-read-btn { flex-shrink:0; background:transparent; border:1px solid var(--border); color:var(--muted); border-radius:50%; width:22px; height:22px; font-size:11px; cursor:pointer; line-height:1; display:flex; align-items:center; justify-content:center; transition:all .2s; }
  .mark-read-btn:hover { border-color:#3dd68c; color:#3dd68c; }
  .alert-buildid { font-size:10px; color:var(--muted); font-family:'IBM Plex Mono',monospace; background:rgba(29,185,255,.08); border:1px solid rgba(29,185,255,.2); border-radius:8px; padding:1px 6px; white-space:nowrap; }
  .search-clear { position:absolute; right:8px; top:50%; transform:translateY(-50%); background:none; border:none; color:var(--muted); font-size:14px; cursor:pointer; padding:2px 4px; line-height:1; display:none; }
  .search-clear:hover { color:var(--text); }
  .search-wrap input:not(:placeholder-shown) ~ .search-clear { display:block; }
  .search-wrap .autocomplete-list { position:absolute; top:100%; left:0; right:0; background:var(--surface); border:1px solid var(--border); border-top:none; border-radius:0 0 6px 6px; max-height:220px; overflow-y:auto; z-index:200; display:none; }
  .search-wrap .autocomplete-list.open { display:block; }
  .search-wrap .autocomplete-item { padding:6px 12px 6px 36px; font-size:13px; color:var(--text); cursor:pointer; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .search-wrap .autocomplete-item:hover, .search-wrap .autocomplete-item.selected { background:rgba(29,185,255,.1); color:var(--accent); }
  .font-controls { display:flex; align-items:center; gap:2px; }
  .font-btn { width:26px; height:26px; border-radius:50%; border:1px solid var(--border); background:transparent; color:var(--muted); font-size:14px; cursor:pointer; display:flex; align-items:center; justify-content:center; font-family:'IBM Plex Mono',monospace; transition:all .2s; }
  .font-btn:hover { border-color:var(--accent); color:var(--accent); }
__SHARED_FILTER_CSS__
  .scroll-top { position:fixed; bottom:28px; right:28px; z-index:200; width:42px; height:42px; border-radius:50%; background:var(--accent); color:#000; border:none; font-size:20px; cursor:pointer; opacity:0; pointer-events:none; transition:opacity .3s, transform .3s; transform:translateY(10px); box-shadow:0 4px 16px rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center; }
  .scroll-top.visible { opacity:1; pointer-events:auto; transform:translateY(0); }
  .scroll-top:hover { transform:translateY(-2px); box-shadow:0 6px 24px rgba(29,185,255,.3); }
  .theme-toggle { position:fixed; bottom:28px; left:28px; z-index:200; width:38px; height:38px; border-radius:50%; background:var(--surface); border:1px solid var(--border); color:var(--muted); font-size:16px; cursor:pointer; transition:all .2s; display:flex; align-items:center; justify-content:center; }
  .theme-toggle:hover { border-color:var(--accent); color:var(--accent); }
  html.light { --bg:#f0f2f5; --surface:#ffffff; --border:#d0d7e0; --accent:#0a7cc4; --text:#2c3e50; --muted:#6c7a8a; }
  html.light .scroll-top { box-shadow:0 4px 16px rgba(0,0,0,.15); }
  html.light header { background:linear-gradient(180deg, #dfe6ee 0%, transparent 100%); }
  html.light .header-text h1 { color:#1a2530; }
  .no-alerts { text-align:center; padding:60px 20px; color:var(--muted); font-size:16px; }
  footer { border-top:1px solid var(--border); padding:16px 40px; font-size:11px; color:var(--muted); text-align:center; font-family:'IBM Plex Mono',monospace; }
  @media (max-width:600px) {
    header { padding:16px 16px 12px; }
    .header-text h1 { font-size:22px; letter-spacing:1px; }
    .toolbar-main { gap:6px; padding:8px 16px; }
    .search-wrap { max-width:100%; min-width:0; flex:1 1 100%; }
    .view-btn { padding:4px 10px; font-size:11px; }
    .action-btn { padding:4px 10px; font-size:11px; }
    .group-controls { flex:1 1 100%; }
    .group-controls .search-wrap { flex:1 1 auto; }
    .font-btn { width:28px; height:28px; font-size:12px; }
    .filter-toggle-btn, .nav-link { font-size:11px; padding:5px 10px; }
    .count-label { font-size:10px; }
    main { padding:16px; }
    .scroll-top { bottom:16px; right:16px; }
    .theme-toggle { bottom:16px; left:16px; }
    #toolbarFilters.open { position:fixed; top:0; left:0; right:0; bottom:0; z-index:1000; overflow-y:auto; background:var(--bg); display:flex !important; flex-direction:column; padding:0 20px 40px; border-top:none; gap:20px; }
    .filter-panel-close { display:flex; }
  }
</style>
</head>
<body>
<header>
  <div class="header-text">
    <h1>SteamPulse</h1>
    <p>🔔 __T_alert_page_title__ · __STEAM_ID__ · __T_generated_at__ __GENERATED_AT__</p>
  </div>
</header>
<div class="toolbar">
  <div class="toolbar-main">
    <div class="search-wrap">
      <span class="icon">⌕</span>
      <input type="text" id="search" placeholder="__T_search_placeholder__">
      <button class="search-clear" id="searchClear" type="button">&times;</button>
      <div class="autocomplete-list" id="autocompleteList"></div>
    </div>
    <select id="sortBy">
      <option value="date">__T_sort_lastupdate__</option>
      <option value="name">__T_sort_name_asc__</option>
      <option value="name_desc">__T_sort_name_desc__</option>
      <option value="playtime">__T_sort_playtime__</option>
      <option value="metacritic">__T_sort_metacritic__</option>
    </select>
    <button class="view-btn active" data-view="combined">__T_alert_view_combined__</button>
    <button class="view-btn" data-view="by-rule">__T_alert_view_by_rule__</button>
    <button class="view-btn" data-view="by-game">__T_alert_view_by_game__</button>
    <button class="view-btn" data-view="by-rule-game">__T_alert_view_by_rule_game__</button>
    <div class="group-controls" id="groupControls">
      <div class="search-wrap">
        <span class="icon">⌕</span>
        <input type="text" id="groupSearch" placeholder="__T_alert_group_search__">
        <button class="search-clear" id="groupSearchClear" type="button">&times;</button>
      </div>
      <button class="action-btn" id="toggleAllBtn">__T_alert_expand_all__</button>
    </div>
    <button class="filter-toggle-btn" id="filtersToggle" title="__T_title_btn_filters__">⚙ __T_btn_filters__<span class="filter-badge" id="filterBadge"></span></button>
    <button class="reset-btn" id="resetBtn" title="__T_title_btn_reset__">✕ __T_btn_reset__</button>
    <div class="spacer"></div>
    <button class="action-btn" id="unreadToggle">__T_btn_show_unread_only__</button>
    <button class="action-btn" id="markAllBtn">__T_btn_mark_all_read__</button>
    <div class="font-controls">
      <button class="font-btn" id="fontMinus" title="__T_alert_font_smaller__">A−</button>
      <button class="font-btn" id="fontPlus" title="__T_alert_font_larger__">A+</button>
    </div>
    <span class="count-label" id="countLabel"></span>
    <a class="nav-link" href="__LIB_HREF__">📚 __T_link_library__</a>
  </div>
  <div class="toolbar-filters" id="toolbarFilters">
    <button type="button" class="filter-panel-close" id="filterPanelClose">__T_btn_filters__ <span>✕</span></button>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_status__</div>
      <div class="filter-btns" id="filterBtns">
        <button class="filter-btn active" data-filter="all">__T_lbl_all__</button>
        <button class="filter-btn" data-filter="earlyaccess" data-tooltip="__T_tt_filter_earlyaccess__">Early Access</button>
        <button class="filter-btn" data-filter="released" data-tooltip="__T_tt_filter_released__">__T_lbl_released__</button>
        <button class="filter-btn" data-filter="unreleased" data-tooltip="__T_tt_filter_unreleased__">__T_lbl_upcoming__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_store__</div>
      <div class="filter-btns" id="storeBtns">
        <button class="store-btn active" data-store="steam">🎮 Steam</button>
        <button class="store-btn active" data-store="epic">⚡ Epic</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_collection__</div>
      <div class="filter-btns" id="libStatusBtns">
        <button class="filter-btn active" data-lib-status="all">__T_lbl_all__</button>
        <button class="filter-btn" data-lib-status="owned" data-tooltip="__T_tt_filter_lib_owned__">__T_lbl_owned__</button>
        <button class="filter-btn" data-lib-status="wishlist" data-tooltip="__T_tt_filter_lib_wishlist__">🎁 Wishlist</button>
        <button class="filter-btn" data-lib-status="followed" data-tooltip="__T_tt_filter_lib_followed__">👁 __T_lbl_followed__</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_news_type__</div>
      <div class="filter-btns" id="tagBtns">
        <button class="tag-btn active" data-tag="all">__T_lbl_all_types__</button>
        <button class="tag-btn" data-tag="patchnotes" data-tooltip="__T_tt_filter_tag_patch__">📋 Patch notes</button>
        <button class="tag-btn" data-tag="other" data-tooltip="__T_tt_filter_tag_news__">📰 News</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_playtime__</div>
      <div class="filter-btns" id="playtimeBtns">
        <button class="filter-btn active" data-pt="all">__T_lbl_all__</button>
        <button class="filter-btn" data-pt="0" data-tooltip="__T_tt_filter_pt_0__">__T_lbl_never_played__</button>
        <button class="filter-btn" data-pt="60" data-tooltip="__T_tt_filter_pt_60__">&lt; 1h</button>
        <button class="filter-btn" data-pt="600" data-tooltip="__T_tt_filter_pt_600__">1-10h</button>
        <button class="filter-btn" data-pt="601" data-tooltip="__T_tt_filter_pt_601__">&gt; 10h</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_metacritic__</div>
      <div class="filter-btns" id="mcBtns">
        <button class="filter-btn active" data-mc="all">__T_lbl_all__</button>
        <button class="filter-btn" data-mc="none" data-tooltip="__T_tt_filter_mc_none__">__T_lbl_no_score__</button>
        <button class="filter-btn" data-mc="bad" data-tooltip="__T_tt_filter_mc_bad__">&lt; 50</button>
        <button class="filter-btn" data-mc="mid" data-tooltip="__T_tt_filter_mc_mid__">50–75</button>
        <button class="filter-btn" data-mc="good" data-tooltip="__T_tt_filter_mc_good__">&gt; 75</button>
      </div>
    </div>
    <div class="filter-group">
      <div class="filter-group-label">__T_filter_recent__</div>
      <div class="filter-btns" id="recentBtns">
        <button class="filter-btn active" data-recent="all">__T_lbl_all__</button>
        <button class="filter-btn" data-recent="2" data-tooltip="__T_tt_filter_recent_2__">__T_lbl_2_days__</button>
        <button class="filter-btn" data-recent="5" data-tooltip="__T_tt_filter_recent_5__">__T_lbl_5_days__</button>
        <button class="filter-btn" data-recent="15" data-tooltip="__T_tt_filter_recent_15__">__T_lbl_15_days__</button>
        <button class="filter-btn" data-recent="30" data-tooltip="__T_tt_filter_recent_30__">__T_lbl_30_days__</button>
      </div>
    </div>
  </div>
</div>
<main>
  <div id="alertsContainer">__ALERTS__</div>
  <div class="no-alerts" id="noAlertsMsg" style="display:none">__T_alert_no_alerts__</div>
</main>
<button class="scroll-top" id="scrollTop" title="__T_title_scroll_top__">↑</button>
<button class="theme-toggle" id="themeToggle" title="__T_title_theme__">🌙</button>
<footer>__T_footer__</footer>
<script>
__SHARED_JS__
(function() {
  var READ_KEY = 'steampulse_read_alerts';
  var FONT_KEY = 'steampulse_font_size';
  var I18N = {
    count1: '__I18N_COUNT1__',
    countN: '__I18N_COUNTN__',
    unreadBadge: '__I18N_UNREAD__',
    showAll: '__I18N_SHOW_ALL__',
    showUnread: '__I18N_SHOW_UNREAD__',
    noAlerts: '__I18N_NO_ALERTS__',
    expandAll: '__I18N_EXPAND_ALL__',
    collapseAll: '__I18N_COLLAPSE_ALL__'
  };
  function getRead() {
    try { return new Set(JSON.parse(localStorage.getItem(READ_KEY) || '[]')); }
    catch(e) { return new Set(); }
  }
  function saveRead(s) {
    try { localStorage.setItem(READ_KEY, JSON.stringify(Array.from(s))); } catch(e) {}
  }
  var readSet = getRead();
  var unreadOnly = false;
  var currentView = 'combined';

  /* ── Font size ─────────────────────────────────────────────── */
  var fontSize = 14;
  try { var sf = parseInt(localStorage.getItem(FONT_KEY)); if (sf >= 10 && sf <= 22) fontSize = sf; } catch(e) {}
  function applyFontSize() {
    document.querySelector('main').style.fontSize = fontSize + 'px';
    try { localStorage.setItem(FONT_KEY, fontSize); } catch(e) {}
  }
  applyFontSize();
  document.getElementById('fontPlus').addEventListener('click', function() {
    if (fontSize < 22) { fontSize += 1; applyFontSize(); }
  });
  document.getElementById('fontMinus').addEventListener('click', function() {
    if (fontSize > 10) { fontSize -= 1; applyFontSize(); }
  });

  /* ── Read/unread ───────────────────────────────────────────── */
  function applyRead() {
    document.querySelectorAll('.alert-card').forEach(function(c) {
      var id = c.getAttribute('data-id');
      if (readSet.has(id)) c.classList.add('read');
      else c.classList.remove('read');
    });
  }

  function markCard(id) {
    readSet.add(id);
    saveRead(readSet);
    document.querySelectorAll('[data-id="' + id + '"]').forEach(function(el) {
      if (el.classList.contains('alert-card')) el.classList.add('read');
    });
    applyFilters();
  }

  /* ── Search helpers ────────────────────────────────────────── */
  function getSearch() { var el = document.getElementById('search'); return el ? el.value.toLowerCase().trim() : ''; }
  function getSort()   { var el = document.getElementById('sortBy'); return el ? el.value : 'date'; }
  function getGroupSearch() { var el = document.getElementById('groupSearch'); return el ? el.value.toLowerCase().trim() : ''; }

  function isDefaultState() {
    return getStatusFilter() === 'all' && allStoresActive() && getLibStatusFilter() === 'all'
      && getTagFilter() === 'all' && getPtFilter() === 'all' && getMcFilter() === 'all'
      && getRecentFilter() === 'all' && !getSearch() && getSort() === 'date'
      && !unreadOnly && !getGroupSearch();
  }
  window.isDefaultState = isDefaultState;

  function updateFilterBadge() {
    var n = 0;
    if (getStatusFilter() !== 'all')   n++;
    if (!allStoresActive())             n++;
    if (getLibStatusFilter() !== 'all') n++;
    if (getTagFilter() !== 'all')      n++;
    if (getPtFilter() !== 'all')       n++;
    if (getMcFilter() !== 'all')       n++;
    if (getRecentFilter() !== 'all')   n++;
    var badge = document.getElementById('filterBadge');
    badge.textContent = n;
    badge.classList.toggle('show', n > 0);
    document.getElementById('filtersToggle').classList.toggle('has-active', n > 0);
  }
  window.updateFilterBadge = updateFilterBadge;

  /* ── Search clear buttons ──────────────────────────────────── */
  var searchEl = document.getElementById('search');
  var searchClearBtn = document.getElementById('searchClear');
  if (searchClearBtn && searchEl) {
    searchClearBtn.addEventListener('click', function() {
      searchEl.value = '';
      searchClearBtn.style.display = 'none';
      closeAutocomplete();
      applyFilters();
      searchEl.focus();
    });
    searchEl.addEventListener('input', function() {
      searchClearBtn.style.display = searchEl.value ? 'block' : 'none';
    });
  }
  var groupSearchEl = document.getElementById('groupSearch');
  var groupSearchClearBtn = document.getElementById('groupSearchClear');
  if (groupSearchClearBtn && groupSearchEl) {
    groupSearchClearBtn.addEventListener('click', function() {
      groupSearchEl.value = '';
      groupSearchClearBtn.style.display = 'none';
      updateSections(); updateCount(); updateResetBtn();
      groupSearchEl.focus();
    });
    groupSearchEl.addEventListener('input', function() {
      groupSearchClearBtn.style.display = groupSearchEl.value ? 'block' : 'none';
    });
  }

  /* ── Autocomplete ──────────────────────────────────────────── */
  var acList = document.getElementById('autocompleteList');
  var acIndex = -1;
  function getVisibleGameNames() {
    var names = new Set();
    document.querySelectorAll('.alert-card:not(.hidden)').forEach(function(c) {
      var g = c.getAttribute('data-game');
      if (g) names.add(g);
    });
    return Array.from(names).sort();
  }
  function showAutocomplete(query) {
    if (!acList || !query) { closeAutocomplete(); return; }
    var names = getVisibleGameNames().filter(function(n) { return n.toLowerCase().indexOf(query) !== -1; });
    if (names.length === 0 || (names.length === 1 && names[0].toLowerCase() === query)) { closeAutocomplete(); return; }
    acList.innerHTML = '';
    names.slice(0, 12).forEach(function(n) {
      var item = document.createElement('div');
      item.className = 'autocomplete-item';
      item.textContent = n;
      item.addEventListener('mousedown', function(e) {
        e.preventDefault();
        searchEl.value = n;
        if (searchClearBtn) searchClearBtn.style.display = 'block';
        closeAutocomplete();
        applyFilters();
      });
      acList.appendChild(item);
    });
    acList.classList.add('open');
    acIndex = -1;
  }
  function closeAutocomplete() { if (acList) { acList.classList.remove('open'); acList.innerHTML = ''; acIndex = -1; } }
  if (searchEl) {
    searchEl.addEventListener('input', function() { showAutocomplete(getSearch()); });
    searchEl.addEventListener('blur', function() { setTimeout(closeAutocomplete, 150); });
    searchEl.addEventListener('keydown', function(e) {
      var items = acList ? acList.querySelectorAll('.autocomplete-item') : [];
      if (!items.length) return;
      if (e.key === 'ArrowDown') { e.preventDefault(); acIndex = Math.min(acIndex + 1, items.length - 1); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); acIndex = Math.max(acIndex - 1, 0); }
      else if (e.key === 'Enter' && acIndex >= 0) { e.preventDefault(); items[acIndex].dispatchEvent(new Event('mousedown')); return; }
      else if (e.key === 'Escape') { closeAutocomplete(); return; }
      else return;
      items.forEach(function(it, i) { it.classList.toggle('selected', i === acIndex); });
    });
  }

  /* ── Main filter logic ─────────────────────────────────────── */
  function applyFilters() {
    var stores = getActiveStores();
    var lib = getLibStatusFilter();
    var statusF = getStatusFilter();
    var tagF = getTagFilter();
    var ptF = getPtFilter();
    var mcF = getMcFilter();
    var recentF = getRecentFilter();
    var search = getSearch();
    var sort = getSort();
    var allCards = Array.from(document.querySelectorAll('.alert-card'));
    allCards.forEach(function(c) {
      var isRead = readSet.has(c.getAttribute('data-id'));
      var storeOk = stores.has(c.getAttribute('data-store') || 'steam');
      var collectionOk = lib === 'all' || (c.getAttribute('data-lib-status') || 'owned') === lib;
      var statusOk = statusF === 'all' || (c.getAttribute('data-status') || 'released') === statusF;
      var tagOk = tagF === 'all' || (c.getAttribute('data-tag') || 'other') === tagF;
      var ptOk = checkPtFilter(ptF, c);
      var mcOk = checkMcFilter(mcF, c);
      var recentOk = checkRecentFilter(recentF, c);
      var searchOk = !search || (c.getAttribute('data-name') || '').indexOf(search) !== -1;
      var shouldHide = (unreadOnly && isRead) || !storeOk || !collectionOk || !statusOk || !tagOk || !ptOk || !mcOk || !recentOk || !searchOk;
      c.classList.toggle('hidden', shouldHide);
    });
    if (currentView === 'combined') {
      var container = document.getElementById('alertsContainer');
      allCards.sort(function(a, b) {
        if (sort === 'name')       return (a.getAttribute('data-game') || '').localeCompare(b.getAttribute('data-game') || '');
        if (sort === 'name_desc')  return (b.getAttribute('data-game') || '').localeCompare(a.getAttribute('data-game') || '');
        if (sort === 'playtime')   return (parseInt(b.getAttribute('data-playtime')) || 0) - (parseInt(a.getAttribute('data-playtime')) || 0);
        if (sort === 'metacritic') return (parseInt(b.getAttribute('data-metacritic')) || 0) - (parseInt(a.getAttribute('data-metacritic')) || 0);
        return (parseInt(b.getAttribute('data-ts')) || 0) - (parseInt(a.getAttribute('data-ts')) || 0);
      });
      allCards.forEach(function(c) { container.appendChild(c); });
    }
    updateSections();
    updateCount();
    updateResetBtn();
    saveFilterState();
    var navLink = document.querySelector('.nav-link[href^="steam_library"]');
    if (navLink) {
      var nf = {};
      if (statusF !== 'all') nf.status = statusF;
      if (!allStoresActive()) nf.stores = Array.from(stores).join(',');
      if (lib !== 'all') nf.lib = lib;
      if (tagF !== 'all') nf.tag = tagF;
      if (ptF !== 'all') nf.pt = ptF;
      if (mcF !== 'all') nf.mc = mcF;
      if (recentF !== 'all') nf.recent = recentF;
      var nh = new URLSearchParams(nf).toString();
      navLink.href = 'steam_library.html' + (nh ? '#' + nh : '');
    }
  }

  /* ── Section visibility ────────────────────────────────────── */
  function updateSections() {
    var groupQuery = getGroupSearch();
    document.querySelectorAll('.section-header').forEach(function(h) {
      var cardsDiv = h.nextElementSibling;
      if (!cardsDiv || !cardsDiv.classList.contains('section-cards')) return;
      var visible = 0;
      cardsDiv.querySelectorAll('.alert-card').forEach(function(c) {
        if (!c.classList.contains('hidden')) visible++;
      });
      var badge = h.querySelector('.section-badge');
      if (badge) badge.textContent = visible;
      var nameMatch = !groupQuery || h.textContent.toLowerCase().indexOf(groupQuery) !== -1;
      var shouldHide = visible === 0 || !nameMatch;
      h.style.display = shouldHide ? 'none' : '';
      if (shouldHide) {
        cardsDiv.style.display = 'none';
      } else {
        cardsDiv.style.display = h.classList.contains('collapsed') ? 'none' : '';
      }
    });
    // Sub-sections
    document.querySelectorAll('.sub-section-header').forEach(function(h) {
      var cardsDiv = h.nextElementSibling;
      if (!cardsDiv || !cardsDiv.classList.contains('sub-section-cards')) return;
      var visible = 0;
      cardsDiv.querySelectorAll('.alert-card').forEach(function(c) {
        if (!c.classList.contains('hidden')) visible++;
      });
      var badge = h.querySelector('.section-badge');
      if (badge) badge.textContent = visible;
      h.style.display = visible === 0 ? 'none' : '';
      if (visible === 0) {
        cardsDiv.style.display = 'none';
      } else {
        cardsDiv.style.display = h.classList.contains('collapsed') ? 'none' : '';
      }
    });
  }

  function updateCount() {
    var all = document.querySelectorAll('.alert-card');
    var visible = 0, unread = 0;
    all.forEach(function(c) {
      if (!c.classList.contains('hidden')) visible++;
      if (!readSet.has(c.getAttribute('data-id'))) unread++;
    });
    var lbl = visible === 1 ? I18N.count1 : I18N.countN.replace('{n}', visible);
    if (unread > 0 && !unreadOnly) lbl += '  \\u00b7  ' + I18N.unreadBadge.replace('{n}', unread);
    document.getElementById('countLabel').textContent = lbl;
    var noMsg = document.getElementById('noAlertsMsg');
    if (noMsg) noMsg.style.display = all.length === 0 ? '' : 'none';
  }

  /* ── Section collapse ──────────────────────────────────────── */
  function toggleSection(header) {
    var cardsDiv = header.nextElementSibling;
    var cls = cardsDiv && cardsDiv.classList.contains('section-cards') ? 'section-cards' : 'sub-section-cards';
    if (!cardsDiv || !cardsDiv.classList.contains(cls)) return;
    var collapsed = header.classList.toggle('collapsed');
    cardsDiv.classList.toggle('collapsed', collapsed);
    cardsDiv.style.display = collapsed ? 'none' : '';
  }

  function toggleAllSections(expand) {
    document.querySelectorAll('.section-header, .sub-section-header').forEach(function(h) {
      if (h.style.display === 'none') return;
      var cardsDiv = h.nextElementSibling;
      if (!cardsDiv) return;
      h.classList.toggle('collapsed', !expand);
      cardsDiv.classList.toggle('collapsed', !expand);
      cardsDiv.style.display = expand ? '' : 'none';
    });
    var btn = document.getElementById('toggleAllBtn');
    if (btn) btn.textContent = expand ? I18N.collapseAll : I18N.expandAll;
  }

  /* ── Build grouping views ──────────────────────────────────── */
  function buildView(view) {
    var container = document.getElementById('alertsContainer');
    var allCards = Array.from(container.querySelectorAll('.alert-card'));
    container.querySelectorAll('.section-header, .sub-section-header').forEach(function(h) { h.remove(); });
    container.querySelectorAll('.section-cards, .sub-section-cards').forEach(function(d) { d.remove(); });
    allCards.forEach(function(c) { c.remove(); });
    container.classList.remove('grouped-by-game');
    var gc = document.getElementById('groupControls');
    if (gc) gc.classList.toggle('visible', view !== 'combined');
    var toggleBtn = document.getElementById('toggleAllBtn');
    if (toggleBtn) toggleBtn.textContent = I18N.expandAll;
    var groupSearchEl = document.getElementById('groupSearch');
    if (groupSearchEl) groupSearchEl.value = '';

    if (view === 'combined') {
      allCards.sort(function(a, b) { return parseInt(b.getAttribute('data-ts') || 0) - parseInt(a.getAttribute('data-ts') || 0); });
      allCards.forEach(function(c) { container.appendChild(c); });
    } else if (view === 'by-rule' || view === 'by-game') {
      if (view === 'by-game') container.classList.add('grouped-by-game');
      var key = view === 'by-rule' ? 'data-rule' : 'data-game';
      var groups = {};
      var order = [];
      allCards.forEach(function(c) {
        var k = c.getAttribute(key) || '';
        if (!groups[k]) { groups[k] = []; order.push(k); }
        groups[k].push(c);
      });
      order.forEach(function(k) {
        var h = document.createElement('div');
        h.className = 'section-header collapsed';
        var chevron = document.createElement('span');
        chevron.className = 'section-chevron';
        chevron.textContent = '\\u25B8';
        h.appendChild(chevron);
        // In by-game view, add the game thumbnail in the header
        if (view === 'by-game' && groups[k].length > 0) {
          var firstCard = groups[k][0];
          var thumbLink = firstCard.querySelector('.alert-thumb-link');
          if (thumbLink) {
            var headerThumb = document.createElement('a');
            headerThumb.href = thumbLink.href;
            headerThumb.target = '_blank';
            headerThumb.rel = 'noopener';
            headerThumb.style.lineHeight = '0';
            var img = document.createElement('img');
            img.className = 'section-thumb';
            img.src = thumbLink.querySelector('img').src;
            img.alt = '';
            img.loading = 'lazy';
            headerThumb.appendChild(img);
            h.appendChild(headerThumb);
          }
        }
        h.appendChild(document.createTextNode(' ' + k + ' '));
        var badge = document.createElement('span');
        badge.className = 'section-badge';
        badge.textContent = groups[k].length;
        h.appendChild(badge);
        h.addEventListener('click', function(e) { if (!e.target.closest('a')) toggleSection(h); });
        container.appendChild(h);
        var wrapper = document.createElement('div');
        wrapper.className = 'section-cards collapsed';
        wrapper.style.display = 'none';
        groups[k].sort(function(a, b) { return parseInt(b.getAttribute('data-ts') || 0) - parseInt(a.getAttribute('data-ts') || 0); });
        groups[k].forEach(function(c) { wrapper.appendChild(c); });
        container.appendChild(wrapper);
      });
    } else if (view === 'by-rule-game') {
      /* Two-level grouping: by rule, then by game */
      var ruleGroups = {};
      var ruleOrder = [];
      allCards.forEach(function(c) {
        var r = c.getAttribute('data-rule') || '';
        if (!ruleGroups[r]) { ruleGroups[r] = []; ruleOrder.push(r); }
        ruleGroups[r].push(c);
      });
      ruleOrder.forEach(function(rule) {
        var h = document.createElement('div');
        h.className = 'section-header collapsed';
        var chevron = document.createElement('span');
        chevron.className = 'section-chevron';
        chevron.textContent = '\\u25B8';
        h.appendChild(chevron);
        h.appendChild(document.createTextNode(' ' + rule + ' '));
        var badge = document.createElement('span');
        badge.className = 'section-badge';
        badge.textContent = ruleGroups[rule].length;
        h.appendChild(badge);
        h.addEventListener('click', function() { toggleSection(h); });
        container.appendChild(h);
        var ruleWrapper = document.createElement('div');
        ruleWrapper.className = 'section-cards collapsed';
        ruleWrapper.style.display = 'none';
        /* Sub-group by game */
        var gameGroups = {};
        var gameOrder = [];
        ruleGroups[rule].forEach(function(c) {
          var g = c.getAttribute('data-game') || '';
          if (!gameGroups[g]) { gameGroups[g] = []; gameOrder.push(g); }
          gameGroups[g].push(c);
        });
        gameOrder.forEach(function(game) {
          var sh = document.createElement('div');
          sh.className = 'sub-section-header collapsed';
          var sc = document.createElement('span');
          sc.className = 'section-chevron';
          sc.textContent = '\\u25B8';
          sh.appendChild(sc);
          /* Add game thumbnail */
          if (gameGroups[game].length > 0) {
            var firstCard = gameGroups[game][0];
            var thumbLink = firstCard.querySelector('.alert-thumb-link');
            if (thumbLink) {
              var subImg = document.createElement('img');
              subImg.className = 'section-thumb';
              subImg.src = thumbLink.querySelector('img').src;
              subImg.alt = '';
              subImg.loading = 'lazy';
              sh.appendChild(subImg);
            }
          }
          sh.appendChild(document.createTextNode(' ' + game + ' '));
          var sbadge = document.createElement('span');
          sbadge.className = 'section-badge';
          sbadge.textContent = gameGroups[game].length;
          sh.appendChild(sbadge);
          sh.addEventListener('click', function() { toggleSection(sh); });
          ruleWrapper.appendChild(sh);
          var subWrapper = document.createElement('div');
          subWrapper.className = 'sub-section-cards collapsed';
          subWrapper.style.display = 'none';
          gameGroups[game].sort(function(a, b) { return parseInt(b.getAttribute('data-ts') || 0) - parseInt(a.getAttribute('data-ts') || 0); });
          gameGroups[game].forEach(function(c) { subWrapper.appendChild(c); });
          ruleWrapper.appendChild(subWrapper);
        });
        container.appendChild(ruleWrapper);
      });
    }
    applyFilters();
  }

  /* ── View mode buttons ─────────────────────────────────────── */
  document.querySelectorAll('.view-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('.view-btn').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      currentView = btn.getAttribute('data-view');
      buildView(currentView);
    });
  });

  // Unread toggle
  document.getElementById('unreadToggle').addEventListener('click', function() {
    unreadOnly = !unreadOnly;
    this.textContent = unreadOnly ? I18N.showAll : I18N.showUnread;
    applyFilters();
  });

  // Mark all read
  document.getElementById('markAllBtn').addEventListener('click', function() {
    document.querySelectorAll('.alert-card').forEach(function(c) {
      readSet.add(c.getAttribute('data-id'));
      c.classList.add('read');
    });
    saveRead(readSet);
    applyFilters();
  });

  // Store & all shared filters
  setupStoreFilter(applyFilters);
  ['#filterBtns', '#libStatusBtns', '#playtimeBtns', '#mcBtns', '#recentBtns'].forEach(function(sel) {
    document.querySelectorAll(sel + ' .filter-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        btn.closest('.filter-btns').querySelectorAll('button').forEach(function(b) { b.classList.remove('active'); });
        btn.classList.add('active');
        applyFilters();
      });
    });
  });
  document.querySelectorAll('#tagBtns .tag-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      document.querySelectorAll('#tagBtns .tag-btn').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      applyFilters();
    });
  });
  // Search
  if (searchEl) { searchEl.addEventListener('input', function() { applyFilters(); }); }
  // Sort
  var sortEl = document.getElementById('sortBy');
  if (sortEl) { sortEl.addEventListener('change', function() { applyFilters(); }); }
  // Group search
  if (groupSearchEl) { groupSearchEl.addEventListener('input', function() { updateSections(); updateCount(); updateResetBtn(); }); }
  // Toggle all sections
  var toggleAllBtnEl = document.getElementById('toggleAllBtn');
  if (toggleAllBtnEl) {
    toggleAllBtnEl.addEventListener('click', function() {
      var anyCollapsed = document.querySelector('.section-header.collapsed:not([style*="display: none"]), .sub-section-header.collapsed:not([style*="display: none"])');
      toggleAllSections(!!anyCollapsed);
    });
  }

  // Reset
  document.getElementById('resetBtn').addEventListener('click', function() {
    document.querySelectorAll('#storeBtns .store-btn').forEach(function(b) { b.classList.add('active'); });
    ['#filterBtns', '#libStatusBtns', '#playtimeBtns', '#mcBtns', '#recentBtns'].forEach(function(sel) {
      document.querySelectorAll(sel + ' .filter-btn').forEach(function(b) { b.classList.remove('active'); });
      var first = document.querySelector(sel + ' .filter-btn');
      if (first) first.classList.add('active');
    });
    document.querySelectorAll('#tagBtns .tag-btn').forEach(function(b) { b.classList.remove('active'); });
    var firstTag = document.querySelector('#tagBtns .tag-btn');
    if (firstTag) firstTag.classList.add('active');
    if (searchEl) searchEl.value = '';
    if (searchClearBtn) searchClearBtn.style.display = 'none';
    if (sortEl) sortEl.value = 'date';
    var gSearchEl = document.getElementById('groupSearch');
    if (gSearchEl) gSearchEl.value = '';
    if (groupSearchClearBtn) groupSearchClearBtn.style.display = 'none';
    unreadOnly = false;
    document.getElementById('unreadToggle').textContent = I18N.showUnread;
    closeAutocomplete();
    applyFilters();
  });

  /* ── Click handlers — differentiated zones ─────────────────── */
  // Only the checkmark button marks as read
  document.querySelectorAll('.mark-read-btn').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      markCard(this.getAttribute('data-id'));
    });
  });
  // Clicking the news body (title/details) opens the news URL
  document.querySelectorAll('.alert-card').forEach(function(c) {
    var body = c.querySelector('.alert-body');
    if (!body) return;
    var titleEl = body.querySelector('.alert-title');
    var detailsEl = body.querySelector('.alert-details');
    function openNews(e) {
      e.stopPropagation();
      // Don't intercept clicks on links (they handle themselves)
      if (e.target.closest('a')) return;
      var url = c.getAttribute('data-news-url');
      if (url) { var w = window.open(url, '_blank', 'noopener,noreferrer'); if (w) w.opener = null; }
    }
    if (titleEl) titleEl.addEventListener('click', openNews);
    if (detailsEl) detailsEl.addEventListener('click', openNews);
  });

  // Initialise: load filters from URL hash or window.name
  var h = location.hash.slice(1);
  if (h) {
    var p = new URLSearchParams(h);
    if (p.get('stores')) {
      var storeSet = new Set(p.get('stores').split(',').filter(Boolean));
      document.querySelectorAll('#storeBtns .store-btn').forEach(function(b) {
        b.classList.toggle('active', storeSet.has(b.dataset.store));
      });
    }
    if (p.get('status')) { activateBtn('#filterBtns .filter-btn', 'filter', p.get('status')); }
    if (p.get('lib'))    { activateBtn('#libStatusBtns .filter-btn', 'libStatus', p.get('lib')); }
    if (p.get('tag'))    { activateBtn('#tagBtns .tag-btn', 'tag', p.get('tag')); }
    if (p.get('pt'))     { activateBtn('#playtimeBtns .filter-btn', 'pt', p.get('pt')); }
    if (p.get('mc'))     { activateBtn('#mcBtns .filter-btn', 'mc', p.get('mc')); }
    if (p.get('recent')) { activateBtn('#recentBtns .filter-btn', 'recent', p.get('recent')); }
    if (p.get('q') && searchEl)   { searchEl.value = p.get('q'); }
    if (p.get('sort') && sortEl)  { sortEl.value = p.get('sort'); }
  } else {
    loadFilterState();
  }
  if (!isDefaultState()) {
    document.getElementById('toolbarFilters').classList.add('open');
  }
  applyRead();
  applyFilters();
})();
</script>
</body>
</html>
"""


def generate_alerts_html(
    alerts: list[Alert],
    records: list[GameRecord],
    steam_id: str,
    library_href: str = "steam_library.html",
    lang: str | None = None,
) -> str:
    """Render the alerts page from a list of Alert objects.

    Args:
        alerts: Alerts to display (sorted newest-first by this function).
        records: Game records used for thumbnail images.
        steam_id: The user's SteamID64 (shown in the header).
        library_href: URL of the library page (for the nav link).
        lang: Language code (e.g. ``"fr"``).  Falls back to English.

    Returns:
        A self-contained HTML string.
    """
    from .i18n import get_translator  # noqa: PLC0415

    t = get_translator(lang)
    record_map = {r.game.appid: r for r in records}
    sorted_alerts = sorted(alerts, key=lambda a: a.timestamp, reverse=True)
    cards_html = "\n".join(
        make_alert_card(a, record_map.get(a.appid), t) for a in sorted_alerts
    )
    now_str = datetime.now().strftime("%d/%m/%Y à %H:%M")
    return _apply_html_t(
        _ALERTS_TEMPLATE
        .replace("__SHARED_FILTER_CSS__", _SHARED_FILTER_CSS)
        .replace("__SHARED_JS__", _SHARED_JS)
        .replace("__GENERATED_AT__", now_str)
        .replace("__STEAM_ID__", html.escape(steam_id))
        .replace("__LIB_HREF__", html.escape(library_href))
        .replace("__ALERTS__", cards_html)
        .replace("__I18N_COUNT1__", t("alert_count_1").replace("'", "\\'"))
        .replace("__I18N_COUNTN__", t("alert_count_n").replace("'", "\\'"))
        .replace("__I18N_UNREAD__", t("alert_unread_badge").replace("'", "\\'"))
        .replace("__I18N_SHOW_ALL__", t("btn_show_all").replace("'", "\\'"))
        .replace("__I18N_SHOW_UNREAD__", t("btn_show_unread_only").replace("'", "\\'"))
        .replace("__I18N_NO_ALERTS__", t("alert_no_alerts").replace("'", "\\'"))
        .replace("__I18N_EXPAND_ALL__", t("alert_expand_all").replace("'", "\\'"))
        .replace("__I18N_COLLAPSE_ALL__", t("alert_collapse_all").replace("'", "\\'")),
        t,
    )


def write_alerts_html(
    alerts: list[Alert],
    records: list[GameRecord],
    steam_id: str,
    output_path: Path,
    library_href: str = "steam_library.html",
    lang: str | None = None,
) -> None:
    """Write the rendered alerts page to *output_path*.

    Args:
        alerts: Alerts to render.
        records: Game records for thumbnail images.
        steam_id: User's SteamID64.
        output_path: Destination file path.
        library_href: URL of the library page.
        lang: Language code.
    """
    output_path.write_text(
        generate_alerts_html(alerts, records, steam_id, library_href, lang), encoding="utf-8"
    )
