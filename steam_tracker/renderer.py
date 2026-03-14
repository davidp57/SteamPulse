"""HTML renderer: turns a list of GameRecords into a self-contained page."""
from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from pathlib import Path

from .models import GameRecord, NewsItem

# ─── HTML Template ────────────────────────────────────────────────────────────
_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
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
    padding: 16px 40px;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--border);
    background: var(--surface);
    position: sticky;
    top: 0;
    z-index: 100;
  }
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

  @media (max-width: 600px) {
    header, .toolbar, .grid { padding-left: 16px; padding-right: 16px; }
    .header-stats { gap: 16px; }
    .stat-val { font-size: 20px; }
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
    <p>Généré le __GENERATED_AT__ · SteamID __STEAM_ID__</p>
  </div>
  <div class="header-stats">
    <div>
      <div class="stat-val">__TOTAL__</div>
      <div class="stat-lbl">Jeux total</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--ea)">__EA__</div>
      <div class="stat-lbl">Early Access</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--released)">__REL__</div>
      <div class="stat-lbl">Sortis 1.0</div>
    </div>
    <div>
      <div class="stat-val" style="color:var(--unreleased)">__UNREL__</div>
      <div class="stat-lbl">Pas sortis</div>
    </div>
  </div>
</header>

<div class="toolbar">
  <div class="search-wrap">
    <span class="icon">⌕</span>
    <input type="text" id="search" placeholder="Rechercher un jeu...">
  </div>
  <select id="sortBy">
    <option value="name">Trier : Nom A→Z</option>
    <option value="name_desc">Trier : Nom Z→A</option>
    <option value="playtime">Trier : Temps de jeu ↓</option>
    <option value="release">Trier : Date de sortie ↓</option>
    <option value="lastupdate">Trier : Dernière MàJ ↓</option>
  </select>
  <div class="filter-btns" id="filterBtns">
    <button class="filter-btn active" data-filter="all">Tous</button>
    <button class="filter-btn" data-filter="earlyaccess">Early Access</button>
    <button class="filter-btn" data-filter="released">Sortis</button>
    <button class="filter-btn" data-filter="unreleased">À venir</button>
  </div>
  <div class="filter-btns" id="sourceBtns">
    <button class="source-btn active" data-source="all">🎮 Tout</button>
    <button class="source-btn" data-source="owned">Possédés</button>
    <button class="source-btn" data-source="wishlist">🎁 Wishlist</button>
  </div>
  <div class="filter-btns" id="tagBtns">
    <button class="tag-btn active" data-tag="all">Tous types</button>
    <button class="tag-btn" data-tag="patchnotes">📋 Patch notes</button>
    <button class="tag-btn" data-tag="other">📰 News</button>
  </div>
  <span class="count-label" id="countLabel"></span>
  <a class="nav-link" href="__NEWS_HREF__">🗞 News</a>
</div>

<div class="grid" id="grid">
__CARDS__
</div>

<footer>SteamPulse · Données via Steam Web API &amp; Store API · Non affilié à Valve</footer>

<script>
const allCards = Array.from(document.querySelectorAll('.card'));

function getFilter()    { return document.querySelector('#filterBtns .filter-btn.active').dataset.filter; }
function getSrcFilter() { return document.querySelector('#sourceBtns .source-btn.active').dataset.source; }
function getTagFilter() { return document.querySelector('#tagBtns .tag-btn.active').dataset.tag; }
function getSearch()    { return document.getElementById('search').value.toLowerCase().trim(); }
function getSort()      { return document.getElementById('sortBy').value; }

function updateGrid() {
  const filter    = getFilter();
  const srcFilter = getSrcFilter();
  const tagFilter = getTagFilter();
  const search    = getSearch();
  const sort      = getSort();

  let visible = allCards.filter(c => {
    const badgeOk  = filter === 'all' || c.dataset.status === filter;
    const srcOk    = srcFilter === 'all' || c.dataset.source === srcFilter;
    const searchOk = !search || c.dataset.name.includes(search);
    return badgeOk && srcOk && searchOk;
  });

  visible.sort((a, b) => {
    if (sort === 'name')       return a.dataset.name.localeCompare(b.dataset.name);
    if (sort === 'name_desc')  return b.dataset.name.localeCompare(a.dataset.name);
    if (sort === 'playtime')   return parseInt(b.dataset.playtime) - parseInt(a.dataset.playtime);
    if (sort === 'release')    return parseInt(b.dataset.releaseTs) - parseInt(a.dataset.releaseTs);
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
  // Hide all, then append sorted visible
  allCards.forEach(c => c.style.display = 'none');
  visible.forEach(c => { c.style.display = ''; grid.appendChild(c); });

  // Update each card: filter news items by tag, refresh date & count display
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
      lbl.textContent = n > 0 ? `🗞 ${n} news / mise${n === 1 ? '' : 's'} à jour` : '🗞 Aucune news';
    }
  });

  let empty = document.getElementById('emptyMsg');
  if (visible.length === 0) {
    if (!empty) {
      empty = document.createElement('div');
      empty.id = 'emptyMsg';
      empty.className = 'empty';
      empty.innerHTML = '<div style="font-size:32px">🔍</div><p>Aucun jeu ne correspond à ta recherche.</p>';
      grid.appendChild(empty);
    }
    empty.style.display = '';
  } else if (empty) {
    empty.style.display = 'none';
  }

  document.getElementById('countLabel').textContent = `${visible.length} jeu${visible.length > 1 ? 'x' : ''}`;
}

document.getElementById('search').addEventListener('input', updateGrid);
document.getElementById('sortBy').addEventListener('change', updateGrid);
document.querySelectorAll('#filterBtns .filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#filterBtns .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateGrid();
  });
});
document.querySelectorAll('#sourceBtns .source-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#sourceBtns .source-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateGrid();
  });
});
document.querySelectorAll('#tagBtns .tag-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#tagBtns .tag-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateGrid();
  });
});

// Expand/collapse news
document.querySelectorAll('.news-toggle').forEach(toggle => {
  toggle.addEventListener('click', e => {
    e.stopPropagation();
    toggle.closest('.card').classList.toggle('expanded');
  });
});

// Open Steam store on card click (not on toggle)
document.querySelectorAll('.card').forEach(card => {
  card.addEventListener('click', e => {
    if (e.target.closest('.news-toggle') || e.target.closest('.news-list')) return;
    const appid = card.dataset.appid;
    if (appid) window.open('https://store.steampowered.com/app/' + appid, '_blank');
  });
});

updateGrid();
</script>
</body>
</html>
"""

_NEWS_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
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
  .nav-back {
    margin-left:auto; padding:7px 16px; border-radius:6px;
    border:1px solid var(--border); background:transparent;
    color:var(--text); font-size:13px; text-decoration:none; transition:border-color .2s, color .2s;
  }
  .nav-back:hover { border-color:var(--accent); color:var(--accent); }
  .toolbar {
    padding:14px 40px; display:flex; gap:12px; align-items:center; flex-wrap:wrap;
    border-bottom:1px solid var(--border); background:var(--surface);
    position:sticky; top:0; z-index:100;
  }
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
  @media(max-width:600px) { header,.toolbar,.feed { padding-left:16px; padding-right:16px; } .feed-game { min-width:130px; max-width:160px; } }
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
    <p>Généré le __GENERATED_AT__ · SteamID __STEAM_ID__</p>
  </div>
  <a class="nav-back" href="__LIB_HREF__">← Bibliothèque</a>
</header>

<div class="toolbar">
  <div class="search-wrap">
    <span class="icon">⌕</span>
    <input type="text" id="search" placeholder="Rechercher un jeu...">
  </div>
  <div class="filter-btns" id="statusBtns">
    <button class="filter-btn active" data-filter="all">Tous</button>
    <button class="filter-btn" data-filter="earlyaccess">Early Access</button>
    <button class="filter-btn" data-filter="released">Sortis</button>
    <button class="filter-btn" data-filter="unreleased">À venir</button>
  </div>
  <div class="filter-btns" id="tagBtns">
    <button class="tag-btn active" data-tag="all">Tous types</button>
    <button class="tag-btn" data-tag="patchnotes">📋 Patch notes</button>
    <button class="tag-btn" data-tag="other">📰 News</button>
  </div>
  <span class="count-label" id="countLabel"></span>
</div>

<div class="feed" id="feed">
__ROWS__
</div>

<footer>SteamPulse · Données via Steam Web API &amp; Store API · Non affilié à Valve</footer>

<script>
const allRows = Array.from(document.querySelectorAll('.feed-item'));

function updateFeed() {
  const filter = document.querySelector('#statusBtns .filter-btn.active').dataset.filter;
  const tagFilter = document.querySelector('#tagBtns .tag-btn.active').dataset.tag;
  const search = document.getElementById('search').value.toLowerCase().trim();
  let visible = allRows.filter(r => {
    const statusOk = filter === 'all' || r.dataset.status === filter;
    const tagOk = tagFilter === 'all' || r.dataset.tag === tagFilter;
    const searchOk = !search || r.dataset.name.includes(search);
    return statusOk && tagOk && searchOk;
  });
  allRows.forEach(r => r.style.display = 'none');
  visible.forEach(r => r.style.display = '');
  let empty = document.getElementById('emptyMsg');
  if (visible.length === 0) {
    if (!empty) {
      empty = document.createElement('div');
      empty.id = 'emptyMsg'; empty.className = 'empty';
      empty.innerHTML = '<div style="font-size:32px">🔍</div><p>Aucune news ne correspond.</p>';
      document.getElementById('feed').appendChild(empty);
    }
    empty.style.display = '';
  } else if (empty) {
    empty.style.display = 'none';
  }
  document.getElementById('countLabel').textContent = `${visible.length} news`;
}

document.getElementById('search').addEventListener('input', updateFeed);
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#statusBtns .filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateFeed();
  });
});
document.querySelectorAll('.tag-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#tagBtns .tag-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    updateFeed();
  });
});
updateFeed();
</script>
</body>
</html>
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


def _price_html(details: object) -> str:
    from .models import AppDetails  # local import to avoid circular
    if not isinstance(details, AppDetails):
        return ""
    if details.is_free:
        return '<span class="price-free">Gratuit</span>'
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


def make_card(record: GameRecord) -> str:
    """Return the HTML string for a single game card."""
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
    price = _price_html(details) if details else ""
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
            _rows.append(
                f'<div class="news-item" data-news-tag="{_ntag}">'
                f'  <span class="news-date">{html.escape(n.date.strftime("%d/%m/%Y"))}</span>'
                f'  <span class="news-item-title">'
                f'    <a href="{html.escape(n.url)}" target="_blank" rel="noopener">'
                f"{html.escape(n.title)}</a>"
                f"  </span>"
                f"</div>"
            )
        news_html = "\n".join(_rows)
    else:
        news_html = '<p class="no-news">Aucune news disponible</p>'

    nc = len(news_list)
    toggle_lbl = f"{nc} news / mise{'' if nc == 1 else 's'} à jour" if nc else "Aucune news"

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
        pt_display = "🎁 Wishlist"
    elif game.source == "followed":
        pt_display = "👁 Suivi"
    else:
        pt_display = f"🕹 {pt_fmt}"
    return (
        f'<div class="card" data-appid="{appid}" data-status="{status.badge}" '
        f'data-source="{source_tag}" data-name="{name.lower()}" '
        f'data-playtime="{game.playtime_forever}" '
        f'data-release="{rel_date}" data-release-ts="{release_ts}" '
        f'data-last-update="{last_update_ts}" '
        f'data-last-patch-ts="{last_patch_ts}" data-last-other-ts="{last_other_ts}">\n'
        f'  <img class="card-img" src="{html.escape(img_url)}" alt="" loading="lazy"'
        f"    onerror=\"this.style.display='none';this.nextElementSibling.style.display='flex'\">\n"
        f'  <div class="card-img-placeholder" style="display:none">{placeholder}</div>\n'
        f'  <div class="card-body">\n'
        f'    <div class="card-top">\n'
        f'      <div class="card-title">{name}</div>\n'
        f'      <span class="{html.escape(badge_cls)}">{html.escape(status.label)}</span>\n'
        f"    </div>\n"
        f"    {detail_row}"
        f"    {genres_html}"
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
) -> str:
    """Render the full HTML page from a list of game records."""
    cards_html = "\n".join(make_card(r) for r in records)
    total = len(records)
    ea = sum(1 for r in records if r.status.badge == "earlyaccess")
    released = sum(1 for r in records if r.status.badge == "released")
    unrel = sum(1 for r in records if r.status.badge == "unreleased")
    now_str = datetime.now().strftime("%d/%m/%Y \u00e0 %H:%M")

    return (
        _HTML_TEMPLATE.replace("__GENERATED_AT__", now_str)
        .replace("__STEAM_ID__", html.escape(steam_id))
        .replace("__TOTAL__", str(total))
        .replace("__EA__", str(ea))
        .replace("__REL__", str(released))
        .replace("__UNREL__", str(unrel))
        .replace("__CARDS__", cards_html)
        .replace("__NEWS_HREF__", html.escape(news_href))
    )


def write_html(
    records: list[GameRecord],
    steam_id: str,
    output_path: Path,
    news_href: str = "steam_news.html",
) -> None:
    """Write the rendered HTML page to *output_path*."""
    output_path.write_text(generate_html(records, steam_id, news_href), encoding="utf-8")


def make_news_row(record: GameRecord, item: NewsItem) -> str:
    """Return an HTML feed-item row for a single news article."""
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

    return (
        f'<div class="feed-item" data-status="{status.badge}" data-name="{name.lower()}" data-tag="{tag_data}">\n'
        f'  <img class="feed-thumb" src="{html.escape(img_url)}" alt="" loading="lazy">\n'
        f'  <div class="feed-game">\n'
        f'    <div class="feed-game-name">{name}</div>\n'
        f'    <div class="feed-game-badge"><span class="{html.escape(badge_cls)}">{html.escape(status.label)}</span></div>\n'
        f'  </div>\n'
        f'  <div class="feed-date">{date_str}</div>\n'
        f'  <div class="feed-title"><a href="{url}" target="_blank" rel="noopener">{title}</a>{tag_html}</div>\n'
        f"</div>"
    )


def generate_news_html(
    records: list[GameRecord],
    steam_id: str,
    library_href: str = "steam_library.html",
) -> str:
    """Render the dedicated news feed page from a list of game records."""
    items: list[tuple[int, GameRecord, NewsItem]] = []
    for record in records:
        for item in record.news:
            items.append((int(item.date.timestamp()), record, item))
    items.sort(key=lambda t: t[0], reverse=True)

    rows_html = "\n".join(make_news_row(rec, it) for _, rec, it in items)
    now_str = datetime.now().strftime("%d/%m/%Y \u00e0 %H:%M")

    return (
        _NEWS_TEMPLATE.replace("__GENERATED_AT__", now_str)
        .replace("__STEAM_ID__", html.escape(steam_id))
        .replace("__ROWS__", rows_html)
        .replace("__LIB_HREF__", html.escape(library_href))
    )


def write_news_html(
    records: list[GameRecord],
    steam_id: str,
    output_path: Path,
    library_href: str = "steam_library.html",
) -> None:
    """Write the rendered news feed page to *output_path*."""
    output_path.write_text(
        generate_news_html(records, steam_id, library_href), encoding="utf-8"
    )
