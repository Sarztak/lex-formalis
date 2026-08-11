"""
Statute annotation tool.

Serves a local web UI for reading scraped IRC section trees and writing
per-node annotations. Annotations saved to data/{section}_annotations.json.

Usage:
    python tools/annotate.py
    python tools/annotate.py --port 8765

Then open http://localhost:8765
"""

import argparse
import glob
import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def sections():
    paths = sorted(glob.glob(os.path.join(DATA_DIR, "*_tree.json")))
    return [os.path.basename(p).replace("_tree.json", "") for p in paths]


def load_tree(section):
    path = os.path.join(DATA_DIR, f"{section}_tree.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_annotations(section):
    path = os.path.join(DATA_DIR, f"{section}_annotations.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_annotations(section, data):
    path = os.path.join(DATA_DIR, f"{section}_annotations.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def flatten_tree(node, depth=0, result=None):
    if result is None:
        result = []
    result.append({
        "id": node["id"],
        "depth": depth,
        "header": node.get("header", ""),
        "chapeau": node.get("chapeau", ""),
        "body": node.get("body", ""),
        "continuation": node.get("continuation", ""),
        "num": node.get("num", ""),
    })
    for child in node.get("children", []):
        flatten_tree(child, depth + 1, result)
    return result


HTML = r"""<!doctype html>
<meta charset="utf-8">
<title>IRC Annotator</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #f7f7f5;
    --panel: #ffffff;
    --border: #e0ddd8;
    --text: #1a1a1a;
    --dim: #6b6b6b;
    --accent: #2563eb;
    --accent-bg: #eff6ff;
    --selected: #dbeafe;
    --annotated: #fef9c3;
    --save-ok: #16a34a;
    --mono: 'JetBrains Mono', 'Fira Mono', 'Cascadia Code', monospace;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #18181b;
      --panel: #1f1f23;
      --border: #3f3f46;
      --text: #e4e4e7;
      --dim: #a1a1aa;
      --accent: #60a5fa;
      --accent-bg: #1e3a5f;
      --selected: #1e3a5f;
      --annotated: #3d3200;
      --save-ok: #4ade80;
    }
  }
  html, body { height: 100%; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; font-size: 14px; }
  #app { display: flex; height: 100vh; }

  /* LEFT PANEL */
  #left { width: 320px; min-width: 220px; max-width: 420px; display: flex; flex-direction: column; border-right: 1px solid var(--border); background: var(--panel); resize: horizontal; overflow: hidden; }
  #section-bar { padding: 10px; border-bottom: 1px solid var(--border); display: flex; gap: 6px; align-items: center; }
  #section-select { flex: 1; padding: 5px 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text); font-size: 13px; }
  #search-wrap { padding: 6px 10px; border-bottom: 1px solid var(--border); }
  #search-input { width: 100%; padding: 5px 8px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text); font-size: 13px; }
  #search-input:focus { outline: none; border-color: var(--accent); }
  #search-count { font-size: 11px; color: var(--dim); text-align: right; padding: 2px 10px 3px; min-height: 18px; }
  mark { background: var(--accent-bg); color: var(--accent); font-weight: 700; border-radius: 2px; padding: 0 1px; }
  #node-list { flex: 1; overflow-y: auto; }
  .node-item { padding: 5px 8px; cursor: pointer; border-bottom: 1px solid var(--border); line-height: 1.4; user-select: none; }
  .node-item:hover { background: var(--accent-bg); }
  .node-item.selected { background: var(--selected); }
  .node-item.annotated { border-left: 3px solid #ca8a04; }
  .node-item.selected.annotated { border-left: 3px solid var(--accent); }
  .node-id { font-family: var(--mono); font-size: 11px; color: var(--dim); }
  .node-hdr { font-size: 12px; font-weight: 600; color: var(--text); }
  .node-preview { font-size: 11px; color: var(--dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* RIGHT PANEL */
  #right { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #topbar { padding: 8px 14px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 10px; background: var(--panel); }
  #node-title { font-family: var(--mono); font-size: 13px; font-weight: 600; }
  #nav-btns { display: flex; gap: 4px; margin-left: auto; }
  #nav-btns button, #save-btn { padding: 4px 10px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text); cursor: pointer; font-size: 12px; }
  #nav-btns button:hover, #save-btn:hover { background: var(--accent-bg); }
  #save-status { font-size: 11px; color: var(--save-ok); min-width: 60px; }

  #content-area { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #statute-text { flex: 1; overflow-y: auto; padding: 16px 20px; line-height: 1.7; }
  #statute-text .field-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; color: var(--dim); margin-top: 14px; margin-bottom: 2px; }
  #statute-text .field-label:first-child { margin-top: 0; }
  #statute-text .field-text { font-size: 14px; }

  #annotation-area { border-top: 1px solid var(--border); padding: 12px 16px; background: var(--panel); display: flex; flex-direction: column; gap: 8px; }
  #annotation-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--dim); }
  #annotation-input { width: 100%; min-height: 100px; max-height: 220px; resize: vertical; padding: 8px 10px; border: 1px solid var(--border); border-radius: 4px; background: var(--bg); color: var(--text); font-size: 13px; font-family: inherit; line-height: 1.5; }
  #annotation-input:focus { outline: none; border-color: var(--accent); }

  #empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--dim); font-size: 15px; }
</style>

<div id="app">
  <div id="left">
    <div id="section-bar">
      <select id="section-select"><option>loading…</option></select>
    </div>
    <div id="search-wrap">
      <input id="search-input" type="text" placeholder="Search nodes… (press /)">
    </div>
    <div id="search-count"></div>
    <div id="node-list"></div>
  </div>
  <div id="right">
    <div id="topbar">
      <span id="node-title">—</span>
      <div id="nav-btns">
        <button id="prev-btn" title="Previous node (Alt+↑)">↑</button>
        <button id="next-btn" title="Next node (Alt+↓)">↓</button>
      </div>
      <span id="save-status"></span>
    </div>
    <div id="content-area">
      <div id="empty-state">Select a node to read</div>
      <div id="statute-text" style="display:none"></div>
      <div id="annotation-area" style="display:none">
        <div id="annotation-label">Notes <span style="font-weight:400;color:var(--dim)">(Ctrl+S to save)</span></div>
        <textarea id="annotation-input" placeholder="Observations, edge types, questions…"></textarea>
      </div>
    </div>
  </div>
</div>

<script src="/static/fzf.umd.js"></script>
<script>
let nodes = [];
let annotations = {};
let currentSection = null;
let currentIdx = -1;
let saveTimer = null;
let filterQuery = '';

const sectionSelect = document.getElementById('section-select');
const nodeList = document.getElementById('node-list');
const searchInput = document.getElementById('search-input');
const searchCount = document.getElementById('search-count');
const nodeTitle = document.getElementById('node-title');
const statuteText = document.getElementById('statute-text');
const annotationArea = document.getElementById('annotation-area');
const annotationInput = document.getElementById('annotation-input');
const emptyState = document.getElementById('empty-state');
const saveStatus = document.getElementById('save-status');

async function api(path, opts) {
  const r = await fetch(path, opts);
  return r.json();
}

async function loadSections() {
  const secs = await api('/api/sections');
  sectionSelect.innerHTML = secs.map(s => `<option value="${s}">§${s}</option>`).join('');
  if (secs.length) loadSection(secs[0]);
}

async function loadSection(section) {
  currentSection = section;
  currentIdx = -1;
  filterQuery = '';
  searchInput.value = '';
  searchCount.textContent = '';
  const [flat, ann] = await Promise.all([
    api(`/api/tree/${section}`),
    api(`/api/annotations/${section}`)
  ]);
  nodes = flat;
  annotations = ann;
  rebuildFzf();
  renderList();
  showNode(-1);
}

let fzfInst = null;

function rebuildFzf() {
  const Fzf = window.fzf && window.fzf.Fzf;
  if (!Fzf) { console.error('fzf not loaded'); return; }
  // Selector: id + header concatenated; track idLen to split positions back per field.
  const items = nodes.map((n, i) => ({
    idx: i,
    idLen: n.id.length,
    target: n.id + ' ' + (n.header || ''),
  }));
  fzfInst = new Fzf(items, { selector: item => item.target });
}

function highlightPositions(text, positions) {
  if (!text) return '';
  let result = '', inMark = false;
  for (let i = 0; i < text.length; i++) {
    const m = positions.has(i);
    if (m && !inMark)  { result += '<mark>'; inMark = true; }
    if (!m && inMark)  { result += '</mark>'; inMark = false; }
    const c = text[i];
    result += c === '&' ? '&amp;' : c === '<' ? '&lt;' : c === '>' ? '&gt;' : c;
  }
  if (inMark) result += '</mark>';
  return result;
}

function nextVisible(from, dir) {
  let i = from + dir;
  while (i >= 0 && i < nodes.length) {
    const el = nodeList.querySelector(`[data-idx="${i}"]`);
    if (el && el.style.display !== 'none') return i;
    i += dir;
  }
  return -1;
}

function renderList() {
  const q = filterQuery.trim();
  let matchMap = null;

  if (q && fzfInst) {
    matchMap = new Map();
    for (const r of fzfInst.find(q)) {
      matchMap.set(r.item.idx, { item: r.item, positions: r.positions });
    }
  }

  let matchCount = 0;
  nodeList.innerHTML = nodes.map((n, i) => {
    const visible = !q || (matchMap !== null && matchMap.has(i));
    if (visible) matchCount++;
    const indent = n.depth * 12;
    const hasAnn = !!annotations[n.id];
    let idHl, hdrHl;
    if (matchMap && matchMap.has(i)) {
      const { item, positions } = matchMap.get(i);
      // positions are indices into item.target = id + ' ' + header
      const idPositions = new Set([...positions].filter(p => p < item.idLen));
      const hdrOffset = item.idLen + 1;
      const hdrPositions = new Set([...positions].filter(p => p >= hdrOffset).map(p => p - hdrOffset));
      idHl  = highlightPositions(n.id, idPositions);
      hdrHl = highlightPositions(n.header || '', hdrPositions);
    } else {
      idHl  = esc(n.id);
      hdrHl = esc(n.header || '');
    }
    const preview = esc((n.chapeau || n.body || '').slice(0, 60));
    return `<div class="node-item${hasAnn ? ' annotated' : ''}${i === currentIdx ? ' selected' : ''}" data-idx="${i}" style="padding-left:${8 + indent}px${visible ? '' : ';display:none'}">
      <div class="node-id">${idHl}</div>
      ${n.header ? `<div class="node-hdr">${hdrHl}</div>` : ''}
      ${preview ? `<div class="node-preview">${preview}</div>` : ''}
    </div>`;
  }).join('');
  nodeList.querySelectorAll('.node-item').forEach(el => {
    el.addEventListener('click', () => selectIdx(+el.dataset.idx));
  });
  searchCount.textContent = q ? `${matchCount} / ${nodes.length} nodes` : '';
}

function selectIdx(idx) {
  if (idx < 0 || idx >= nodes.length) return;
  currentIdx = idx;
  nodeList.querySelectorAll('.node-item').forEach((el, i) => {
    el.classList.toggle('selected', i === idx);
  });
  const el = nodeList.querySelector('.selected');
  if (el) el.scrollIntoView({ block: 'nearest' });
  showNode(idx);
}

function showNode(idx) {
  if (idx < 0 || idx >= nodes.length) {
    emptyState.style.display = 'flex';
    statuteText.style.display = 'none';
    annotationArea.style.display = 'none';
    return;
  }
  const n = nodes[idx];
  emptyState.style.display = 'none';
  statuteText.style.display = 'block';
  annotationArea.style.display = 'flex';

  nodeTitle.textContent = n.id + (n.header ? '  ' + n.header : '');

  let html = '';
  if (n.chapeau) html += `<div class="field-label">Chapeau</div><div class="field-text">${esc(n.chapeau)}</div>`;
  if (n.body)    html += `<div class="field-label">Body</div><div class="field-text">${esc(n.body)}</div>`;
  if (n.continuation) html += `<div class="field-label">Continuation</div><div class="field-text">${esc(n.continuation)}</div>`;
  if (!html) html = '<span style="color:var(--dim)">No text (container node)</span>';
  statuteText.innerHTML = html;

  annotationInput.value = annotations[n.id] || '';
  clearSaveStatus();
}

function esc(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

async function saveCurrentAnnotation() {
  if (currentIdx < 0) return;
  const n = nodes[currentIdx];
  const text = annotationInput.value.trim();
  if (text) {
    annotations[n.id] = text;
  } else {
    delete annotations[n.id];
  }
  renderList();
  await api(`/api/annotations/${currentSection}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(annotations)
  });
  saveStatus.textContent = 'saved';
  setTimeout(() => saveStatus.textContent = '', 1500);
  // re-mark annotated
  nodeList.querySelectorAll('.node-item').forEach((el, i) => {
    el.classList.toggle('annotated', !!annotations[nodes[i].id]);
    el.classList.toggle('selected', i === currentIdx);
  });
}

function clearSaveStatus() { saveStatus.textContent = ''; }

// auto-save debounced
annotationInput.addEventListener('input', () => {
  saveStatus.textContent = '…';
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveCurrentAnnotation, 800);
});

// keyboard nav
document.addEventListener('keydown', e => {
  if (e.target === annotationInput) {
    if (e.ctrlKey && e.key === 's') { e.preventDefault(); saveCurrentAnnotation(); }
    return;
  }
  if (e.target === searchInput) return;
  if (e.key === '/') { e.preventDefault(); searchInput.focus(); searchInput.select(); return; }
  if (e.altKey && e.key === 'ArrowDown') { e.preventDefault(); const n = nextVisible(currentIdx, 1);  if (n >= 0) selectIdx(n); }
  if (e.altKey && e.key === 'ArrowUp')   { e.preventDefault(); const n = nextVisible(currentIdx, -1); if (n >= 0) selectIdx(n); }
  if (e.key === 'ArrowDown') { const n = nextVisible(currentIdx, 1);  if (n >= 0) selectIdx(n); }
  if (e.key === 'ArrowUp')   { const n = nextVisible(currentIdx, -1); if (n >= 0) selectIdx(n); }
  if (e.key === 'Enter' && currentIdx >= 0) annotationInput.focus();
});

searchInput.addEventListener('input', () => {
  filterQuery = searchInput.value;
  renderList();
  if (filterQuery) {
    const first = nodeList.querySelector('.node-item:not([style*="display:none"])');
    if (first) selectIdx(+first.dataset.idx);
  } else {
    const sel = nodeList.querySelector('.selected');
    if (sel) sel.scrollIntoView({ block: 'nearest' });
  }
});
searchInput.addEventListener('keydown', e => {
  if (e.key === 'Escape') { searchInput.value = ''; filterQuery = ''; renderList(); searchInput.blur(); const sel = nodeList.querySelector('.selected'); if (sel) sel.scrollIntoView({ block: 'nearest' }); }
  if (e.key === 'ArrowDown') { e.preventDefault(); const n = nextVisible(currentIdx, 1);  if (n >= 0) selectIdx(n); }
  if (e.key === 'ArrowUp')   { e.preventDefault(); const n = nextVisible(currentIdx, -1); if (n >= 0) selectIdx(n); }
  if (e.key === 'Enter') { const el = nodeList.querySelector('.node-item:not([style*="display:none"])'); if (el) { selectIdx(+el.dataset.idx); searchInput.blur(); } }
});

document.getElementById('prev-btn').addEventListener('click', () => { const n = nextVisible(currentIdx, -1); if (n >= 0) selectIdx(n); });
document.getElementById('next-btn').addEventListener('click', () => { const n = nextVisible(currentIdx, 1);  if (n >= 0) selectIdx(n); });
sectionSelect.addEventListener('change', e => loadSection(e.target.value));

loadSections();
</script>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence access log

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "":
            self.send_html(HTML)

        elif path == "/static/fzf.umd.js":
            fzf_path = os.path.join(os.path.dirname(__file__), "fzf.umd.js")
            with open(fzf_path, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif path == "/api/sections":
            self.send_json(sections())

        elif m := re.match(r"^/api/tree/(\w+)$", path):
            section = m.group(1)
            try:
                tree = load_tree(section)
                self.send_json(flatten_tree(tree))
            except FileNotFoundError:
                self.send_json({"error": "not found"}, 404)

        elif m := re.match(r"^/api/annotations/(\w+)$", path):
            self.send_json(load_annotations(m.group(1)))

        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if m := re.match(r"^/api/annotations/(\w+)$", path):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            save_annotations(m.group(1), data)
            self.send_json({"ok": True})
        else:
            self.send_json({"error": "not found"}, 404)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    os.chdir(os.path.join(os.path.dirname(__file__), ".."))

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Annotator running at http://localhost:{args.port}")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
