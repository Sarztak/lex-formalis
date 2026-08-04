"""
Generate an interactive collapsible tree visualization of 7701_tree.json.
Nodes are color-coded by classify tag. Output: demo/tree.html
"""

import glob
import json
import os

TREE_FILE = "data/7701_tree.json"
CLASSIFY_GLOB = "logs/classify/classify_rules_*.json"
OUT_FILE = "demo/tree.html"

TAG_PRIORITY = [
    "exception",
    "definition",
    "scope_rule",
    "scope_def",
    "structure",
    "container_intro",
    "container_bare",
    "leaf",
]

TAG_COLOR = {
    "exception": "#e05252",
    "definition": "#5b8dd9",
    "scope_rule": "#52b788",
    "scope_def": "#40b4b4",
    "structure": "#c77dff",
    "container_intro": "#f4a261",
    "container_bare": "#adb5bd",
    "leaf": "#ced4da",
}
DEFAULT_COLOR = "#ced4da"


def load_tags():
    files = sorted(glob.glob(CLASSIFY_GLOB))
    if not files:
        print("No classify log found — nodes will be unstyled")
        return {}
    with open(files[-1]) as f:
        data = json.load(f)
    tag_map = {}
    for entry in data["results"]:
        tags = [t["construct"] for t in entry.get("tags", [])]
        tag_map[entry["id"]] = tags
    return tag_map


def pick_color(tags):
    for t in TAG_PRIORITY:
        if t in tags:
            return TAG_COLOR[t]
    return DEFAULT_COLOR


def pick_label(tags):
    for t in TAG_PRIORITY:
        if t in tags:
            return t
    return ""


def convert(node, tag_map):
    nid = node["id"]
    tags = tag_map.get(nid, [])
    header = node.get("header") or ""
    chapeau = (node.get("chapeau") or "")[:120]
    body = (node.get("body") or "")[:120]
    tooltip = header or chapeau or body or nid
    label = pick_label(tags)

    d = {
        "id": nid,
        "name": nid,
        "header": header,
        "tooltip": tooltip,
        "color": pick_color(tags),
        "tag": label,
    }
    children = node.get("children", [])
    if children:
        d["children"] = [convert(c, tag_map) for c in children]
    return d


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>26 USC § 7701 — Provision Tree</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: #f8fafc; color: #1e293b; font-family: monospace; overflow: hidden; }}
  #header {{ text-align: center; padding: 10px 0 4px; font-size: 14px; color: #64748b; letter-spacing: 1px; }}
  #legend {{ display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; padding: 4px 0 8px; font-size: 11px; }}
  .leg {{ display: flex; align-items: center; gap: 5px; color: #475569; }}
  .leg-dot {{ width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }}
  #tree-container {{ position: absolute; top: 0; left: 0; width: 100vw; height: 100vh; }}
  svg {{ width: 100%; height: 100%; }}
  .node circle {{ stroke-width: 1.5px; cursor: pointer; }}
  .node text {{ font-size: 8px; fill: #334155; }}
  .link {{ fill: none; stroke: #cbd5e1; stroke-width: 1px; }}
  #tooltip {{
    position: fixed; background: #fff; border: 1px solid #e2e8f0;
    padding: 8px 12px; border-radius: 4px; font-size: 11px;
    max-width: 320px; pointer-events: none; display: none;
    color: #334155; line-height: 1.5; z-index: 10;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }}
  #hud {{
    position: fixed; top: 0; left: 0; width: 100vw; z-index: 5;
    pointer-events: none;
    background: rgba(248,250,252,0.92);
    border-bottom: 1px solid #e2e8f0;
  }}
</style>
</head>
<body>
<div id="tree-container"><svg id="tree-svg"></svg></div>
<div id="hud">
  <div id="header">26 USC § 7701 — Provision Tree &nbsp;·&nbsp; {node_count} nodes &nbsp;·&nbsp; scroll to zoom · drag to pan · click to collapse</div>
  <div id="legend">{legend_html}</div>
</div>
<div id="tooltip"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const DATA = {tree_json};

const W = window.innerWidth;
const H = window.innerHeight;

const svg = d3.select("#tree-svg");
const g = svg.append("g");

const zoom = d3.zoom().scaleExtent([0.03, 6]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

const root = d3.hierarchy(DATA);
let uid = 0;
root.descendants().forEach(d => {{ d.uid = ++uid; }});

// left-to-right layout: x = vertical position, y = horizontal depth
const treeLayout = d3.tree().nodeSize([14, 160]);
const diagonal = d3.linkHorizontal().x(d => d.y).y(d => d.x);

const tooltip = document.getElementById("tooltip");

function update(source, animate) {{
  treeLayout(root);
  const nodes = root.descendants();
  const links = root.links();

  // fit to screen on first render (x=vertical, y=horizontal in LR layout)
  if (!update.fitted) {{
    update.fitted = true;
    const xs = nodes.map(d => d.x), ys = nodes.map(d => d.y);
    const minX = Math.min(...xs), maxX = Math.max(...xs);
    const minY = Math.min(...ys), maxY = Math.max(...ys);
    const treeW = maxY - minY + 60, treeH = maxX - minX + 40;
    const scale = Math.min(W / treeW, H / treeH) * 0.92;
    const tx = 20 - minY * scale;
    const ty = H / 2 - (minX + maxX) / 2 * scale;
    svg.call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }}

  const dur = animate ? 300 : 0;

  // links
  const link = g.selectAll("path.link").data(links, d => d.target.uid);
  link.enter().insert("path", "g").attr("class", "link")
    .attr("d", () => {{ const o = {{x: source._x0 ?? source.x, y: source._y0 ?? source.y}}; return diagonal({{source: o, target: o}}); }})
    .merge(link).transition().duration(dur).attr("d", diagonal);
  link.exit().transition().duration(dur)
    .attr("d", () => {{ const o = {{x: source.x, y: source.y}}; return diagonal({{source: o, target: o}}); }})
    .remove();

  // nodes
  const node = g.selectAll("g.node").data(nodes, d => d.uid);

  const ne = node.enter().append("g").attr("class", "node")
    .attr("transform", d => `translate(${{source._y0 ?? source.y}},${{source._x0 ?? source.x}})`)
    .on("click", (event, d) => {{
      event.stopPropagation();
      if (d.children) {{ d._children = d.children; d.children = null; }}
      else if (d._children) {{ d.children = d._children; d._children = null; }}
      d._x0 = d.x; d._y0 = d.y;
      update(d, true);
    }})
    .on("mouseover", (_, d) => {{
      const dd = d.data;
      tooltip.style.display = "block";
      tooltip.innerHTML = `<strong>${{dd.id}}</strong>`
        + (dd.header ? `<br>${{dd.header}}` : "")
        + (dd.tooltip && dd.tooltip !== dd.header ? `<br><span style="color:#64748b">${{dd.tooltip}}</span>` : "")
        + (dd.tag ? `<br><em style="color:#94a3b8">${{dd.tag}}</em>` : "");
    }})
    .on("mousemove", ev => {{
      tooltip.style.left = (ev.clientX + 14) + "px";
      tooltip.style.top  = (ev.clientY - 10) + "px";
    }})
    .on("mouseout", () => tooltip.style.display = "none");

  ne.append("circle").attr("r", 4);
  ne.append("text").attr("dy", "0.31em").attr("x", 8).attr("text-anchor", "start");

  const nu = ne.merge(node);
  nu.transition().duration(dur).attr("transform", d => `translate(${{d.y}},${{d.x}})`);
  nu.select("circle")
    .attr("fill", d => d._children ? d3.color(d.data.color).darker(0.6) : d.data.color)
    .attr("stroke", d => d3.color(d.data.color).darker(1));
  nu.select("text").text(d => d.data.name);

  node.exit().transition().duration(dur)
    .attr("transform", `translate(${{source.y}},${{source.x}})`).remove();

  nodes.forEach(d => {{ d._x0 = d.x; d._y0 = d.y; }});
}}

update(root, false);
</script>
</body>
</html>
"""


def main():
    tag_map = load_tags()

    with open(TREE_FILE) as f:
        tree = json.load(f)

    tree_data = convert(tree, tag_map)

    # count nodes
    def count(n):
        return 1 + sum(count(c) for c in n.get("children", []))

    node_count = count(tree_data)

    legend_html = "".join(
        f'<div class="leg"><div class="leg-dot" style="background:{color}"></div>{tag}</div>'
        for tag, color in TAG_COLOR.items()
    )

    tag_colors_json = json.dumps(TAG_COLOR)
    tree_json = json.dumps(tree_data)

    html = HTML_TEMPLATE.format(
        node_count=node_count,
        legend_html=legend_html,
        tree_json=tree_json,
        tag_colors=tag_colors_json,
    )

    os.makedirs("demo", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        f.write(html)

    print(f"Written: {OUT_FILE} ({node_count} nodes)")


if __name__ == "__main__":
    main()
