"""
Generate cross-reference dependency graph visualization.
Shows only nodes that participate in cross-references, colored by subsection.
Output: demo/dep_graph.html
"""

import json
import os
import sys

sys.path.insert(0, "pipeline")
from resolve_refs import find_refs

TREE_FILE = "data/7701_tree.json"
OUT_FILE = "demo/dep_graph.html"

SUBSECTION_COLORS = {
    "a": "#3b82f6",
    "b": "#10b981",
    "c": "#f59e0b",
    "d": "#ef4444",
    "e": "#8b5cf6",
    "f": "#ec4899",
    "g": "#06b6d4",
    "h": "#f97316",
    "i": "#84cc16",
    "j": "#a78bfa",
    "k": "#fb923c",
    "l": "#34d399",
    "m": "#60a5fa",
    "n": "#f472b6",
    "o": "#facc15",
    "p": "#4ade80",
}
DEFAULT_COLOR = "#94a3b8"


def subsection_color(node_id):
    # "7701(a)(12)(A)" → "a"
    parts = node_id.split("(")
    if len(parts) >= 2:
        sub = parts[1].rstrip(")")
        return SUBSECTION_COLORS.get(sub.lower(), DEFAULT_COLOR)
    return DEFAULT_COLOR


def subsection_label(node_id):
    parts = node_id.split("(")
    if len(parts) >= 2:
        return "§7701(" + parts[1].rstrip(")") + ")"
    return node_id


def walk(node):
    yield node
    for c in node.get("children", []):
        yield from walk(c)


def build_graph(tree):
    all_nodes = list(walk(tree))
    all_ids = {n["id"] for n in all_nodes}
    node_map = {n["id"]: n for n in all_nodes}

    edges = set()
    for node in all_nodes:
        nid = node["id"]
        for field in ("header", "chapeau", "body", "continuation"):
            text = node.get(field) or ""
            for _, target in find_refs(nid, text):
                if target in all_ids and target != nid:
                    edges.add((nid, target))

    # only include nodes that appear in edges
    active_ids = set()
    for src, tgt in edges:
        active_ids.add(src)
        active_ids.add(tgt)

    nodes = [
        {
            "id": nid,
            "label": nid,
            "header": (node_map[nid].get("header") or "")[:80],
            "color": subsection_color(nid),
            "subsection": subsection_label(nid),
        }
        for nid in active_ids
    ]

    links = [{"source": src, "target": tgt} for src, tgt in edges]

    # subsection legend entries
    seen_subs = {}
    for nid in active_ids:
        sub = subsection_label(nid)
        if sub not in seen_subs:
            seen_subs[sub] = subsection_color(nid)
    legend = sorted(seen_subs.items())

    return nodes, links, legend


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>§7701 — Cross-Reference Dependency Graph</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: #f8fafc;
  font-family: 'Courier New', monospace;
  overflow: hidden;
}}
#hud {{
  position: fixed; top: 0; left: 0; width: 100vw;
  z-index: 10; pointer-events: none;
  padding: 12px 20px 8px;
  background: rgba(248,250,252,0.92);
  border-bottom: 1px solid #e2e8f0;
}}
h1 {{
  font-size: 13px; color: #64748b;
  letter-spacing: 1px; text-transform: uppercase;
  margin-bottom: 4px;
}}
h2 {{
  font-size: 16px; color: #1e293b; font-weight: normal;
  margin-bottom: 6px;
}}
.subtitle {{ font-size: 10px; color: #94a3b8; margin-bottom: 8px; }}
#legend {{
  display: flex; flex-wrap: wrap; gap: 8px;
  font-size: 10px; pointer-events: none;
}}
.leg {{ display: flex; align-items: center; gap: 4px; color: #475569; }}
.leg-dot {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
#container {{ width: 100vw; height: 100vh; }}
svg {{ width: 100%; height: 100%; }}
.link {{
  fill: none;
  stroke: #cbd5e1;
  stroke-width: 1px;
  marker-end: url(#arrow);
}}
.node circle {{
  stroke: #fff;
  stroke-width: 1.5px;
  cursor: pointer;
}}
.node text {{
  font-size: 8px;
  fill: #334155;
  pointer-events: none;
}}
#tooltip {{
  position: fixed;
  background: #fff;
  border: 1px solid #e2e8f0;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 11px;
  max-width: 300px;
  pointer-events: none;
  display: none;
  color: #334155;
  line-height: 1.5;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  z-index: 20;
}}
</style>
</head>
<body>
<div id="hud">
  <h1>Dependency Graph</h1>
  <h2>26 USC § 7701 — Cross-Reference Edges</h2>
  <p class="subtitle">{node_count} provisions · {edge_count} cross-references · scroll to zoom · drag to pan · hover for details</p>
  <div id="legend">{legend_html}</div>
</div>
<div id="container"><svg id="graph"></svg></div>
<div id="tooltip"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const NODES = {nodes_json};
const LINKS = {links_json};

const W = window.innerWidth, H = window.innerHeight;

const svg = d3.select("#graph");
const g = svg.append("g");

// arrowhead marker
svg.append("defs").append("marker")
  .attr("id", "arrow")
  .attr("viewBox", "0 -4 8 8")
  .attr("refX", 14).attr("refY", 0)
  .attr("markerWidth", 6).attr("markerHeight", 6)
  .attr("orient", "auto")
  .append("path")
  .attr("d", "M0,-4L8,0L0,4")
  .attr("fill", "#cbd5e1");

svg.call(d3.zoom().scaleExtent([0.1, 6]).on("zoom", e => g.attr("transform", e.transform)));

const sim = d3.forceSimulation(NODES)
  .force("link", d3.forceLink(LINKS).id(d => d.id).distance(90).strength(0.4))
  .force("charge", d3.forceManyBody().strength(-220))
  .force("center", d3.forceCenter(W / 2, H / 2))
  .force("collision", d3.forceCollide(18));

const link = g.append("g").selectAll("line")
  .data(LINKS).join("line").attr("class", "link");

const node = g.append("g").selectAll("g.node")
  .data(NODES).join("g").attr("class", "node")
  .call(d3.drag()
    .on("start", (e, d) => {{ if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
    .on("drag",  (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
    .on("end",   (e, d) => {{ if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }}));

const tooltip = document.getElementById("tooltip");

node.append("circle").attr("r", 7)
  .attr("fill", d => d.color)
  .on("mouseover", (e, d) => {{
    tooltip.style.display = "block";
    tooltip.innerHTML = `<strong>${{d.id}}</strong>`
      + (d.header ? `<br>${{d.header}}` : "")
      + `<br><em style="color:#94a3b8">${{d.subsection}}</em>`;
  }})
  .on("mousemove", e => {{
    tooltip.style.left = (e.clientX + 14) + "px";
    tooltip.style.top  = (e.clientY - 10) + "px";
  }})
  .on("mouseout", () => tooltip.style.display = "none");

node.append("text").attr("dy", "0.31em").attr("x", 10)
  .text(d => d.id.replace("7701", ""));

sim.on("tick", () => {{
  link
    .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
    .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
  node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
}});
</script>
</body>
</html>
"""


def main():
    with open(TREE_FILE) as f:
        tree = json.load(f)

    nodes, links, legend = build_graph(tree)

    legend_html = "".join(
        f'<div class="leg"><div class="leg-dot" style="background:{color}"></div>{sub}</div>'
        for sub, color in legend
    )

    html = HTML_TEMPLATE.format(
        node_count=len(nodes),
        edge_count=len(links),
        legend_html=legend_html,
        nodes_json=json.dumps(nodes),
        links_json=json.dumps(links),
    )

    os.makedirs("demo", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        f.write(html)

    print(f"Written: {OUT_FILE} ({len(nodes)} nodes, {len(links)} edges)")


if __name__ == "__main__":
    main()
