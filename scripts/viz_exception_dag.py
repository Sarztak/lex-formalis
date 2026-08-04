"""
Generate exception DAG visualization for §7701(b)(3).
Output: demo/exception_dag.html
"""

import os

OUT_FILE = "demo/exception_dag.html"

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>§7701(b)(3) — Exception DAG</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #ffffff;
  color: #1a1a1a;
  font-family: 'Courier New', monospace;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 100vh;
  padding: 32px 24px 40px;
}
h1 {
  font-size: 13px;
  color: #999;
  letter-spacing: 1px;
  margin-bottom: 6px;
  text-transform: uppercase;
}
h2 {
  font-size: 18px;
  color: #222;
  margin-bottom: 8px;
  font-weight: normal;
}
.subtitle {
  font-size: 11px;
  color: #aaa;
  margin-bottom: 40px;
  letter-spacing: 0.5px;
}

/* ── DAG diagram ─────────────────────────────────────── */
.dag {
  display: grid;
  grid-template-columns: 1fr 60px 1fr 60px 1fr;
  grid-template-rows: auto 40px auto;
  align-items: center;
  width: 100%;
  max-width: 960px;
  margin-bottom: 48px;
}

.node {
  border-radius: 6px;
  padding: 16px 18px;
  border-left: 4px solid;
  position: relative;
}
.node-id {
  font-size: 11px;
  font-weight: bold;
  letter-spacing: 1px;
  margin-bottom: 4px;
}
.node-role {
  font-size: 10px;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  opacity: 0.7;
}
.node-header {
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 6px;
  line-height: 1.4;
}
.node-text {
  font-size: 10px;
  line-height: 1.6;
  color: #555;
}

/* colors */
.base    { background: #eff6ff; border-color: #3b82f6; }
.base .node-id { color: #1d4ed8; }
.base .node-role { color: #3b82f6; }

.exc1    { background: #fffbeb; border-color: #f59e0b; }
.exc1 .node-id { color: #b45309; }
.exc1 .node-role { color: #f59e0b; }

.exc2    { background: #fff1f2; border-color: #ef4444; }
.exc2 .node-id { color: #b91c1c; }
.exc2 .node-role { color: #ef4444; }

/* arrows */
.arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 4px;
  color: #444;
  font-size: 10px;
  text-align: center;
}
.arrow-line {
  display: flex;
  align-items: center;
  width: 100%;
}
.arrow-line .shaft {
  flex: 1;
  height: 1px;
  background: #bbb;
}
.arrow-line .head {
  width: 0; height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 8px solid #bbb;
}
.arrow-label {
  color: #aaa;
  font-size: 9px;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

/* D node separate row */
.d-row {
  grid-column: 1;
  grid-row: 3;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}
.d-row .node { width: 100%; }
.d-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0;
}
.d-connector .vert-line {
  width: 1px;
  height: 24px;
  background: #444;
}
.d-connector .horiz-row {
  display: flex;
  align-items: center;
  width: 100%;
}
.d-connector .horiz-line {
  flex: 1;
  height: 1px;
  background: #444;
}
.d-connector .arrowhead {
  width: 0; height: 0;
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 8px solid #444;
}
.d-label {
  font-size: 9px;
  color: #555;
  margin-top: 4px;
}

/* ── Priority legend ─────────────────────────────────── */
.priority-box {
  width: 100%;
  max-width: 960px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 20px 24px;
  margin-bottom: 32px;
}
.priority-box h3 {
  font-size: 10px;
  color: #999;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 14px;
}
.priority-chain {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.p-node {
  padding: 4px 12px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: bold;
}
.p-arrow { color: #aaa; font-size: 14px; }
.p-note { font-size: 10px; color: #888; margin-top: 8px; line-height: 1.7; }

/* ── Evaluation table ────────────────────────────────── */
.eval-box {
  width: 100%;
  max-width: 960px;
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 20px 24px;
}
.eval-box h3 {
  font-size: 10px;
  color: #999;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 16px;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
}
th {
  text-align: left;
  color: #999;
  font-weight: normal;
  padding: 0 12px 8px 0;
  border-bottom: 1px solid #e5e7eb;
}
td {
  padding: 8px 12px 8px 0;
  border-bottom: 1px solid #f0f0f0;
  vertical-align: top;
  line-height: 1.5;
}
td:first-child { color: #555; white-space: nowrap; }
.win { color: #15803d; font-weight: bold; }
.lose { color: #bbb; text-decoration: line-through; }
.na { color: #ccc; }
</style>
</head>
<body>

<h1>Exception DAG</h1>
<h2>26 USC § 7701(b)(3) — Substantial Presence Test</h2>
<p class="subtitle">arrows indicate override direction · higher-priority rule silences lower-priority rule</p>

<!-- Main DAG -->
<div class="dag">

  <!-- Row 1: C → B → A -->
  <div class="node exc2" style="grid-column:1; grid-row:1;">
    <div class="node-id">§ 7701(b)(3)(C)</div>
    <div class="node-role">Exception to B</div>
    <div class="node-header">B not to apply in certain cases</div>
    <div class="node-text">
      B shall not apply if at any time during the year the individual had a pending LPR application
      or took steps to apply for lawful permanent resident status.
    </div>
  </div>

  <div class="arrow" style="grid-column:2; grid-row:1;">
    <div class="arrow-line"><div class="shaft"></div><div class="head"></div></div>
    <div class="arrow-label">overrides</div>
  </div>

  <div class="node exc1" style="grid-column:3; grid-row:1;">
    <div class="node-id">§ 7701(b)(3)(B)</div>
    <div class="node-role">Exception to A</div>
    <div class="node-header">Closer connection exception</div>
    <div class="node-text">
      Individual shall <em>not</em> meet the substantial presence test if present fewer than 183 days
      and has a tax home in a foreign country with a closer connection to that country than to the US.
    </div>
  </div>

  <div class="arrow" style="grid-column:4; grid-row:1;">
    <div class="arrow-line"><div class="shaft"></div><div class="head"></div></div>
    <div class="arrow-label">overrides</div>
  </div>

  <div class="node base" style="grid-column:5; grid-row:1;">
    <div class="node-id">§ 7701(b)(3)(A)</div>
    <div class="node-role">Base rule</div>
    <div class="node-header">Substantial presence test</div>
    <div class="node-text">
      Individual meets the test if present ≥ 31 days in the current year and the weighted
      3-year day count (1 × current + ⅓ × prior + ⅙ × two years prior) ≥ 183 days.
    </div>
  </div>

  <!-- D node below A, arrow pointing up toward A -->
  <div style="grid-column:5; grid-row:2 / span 2; display:flex; flex-direction:column; align-items:center;">
    <!-- arrowhead pointing up toward A -->
    <div style="display:flex; flex-direction:column; align-items:center; margin-bottom:0;">
      <div style="width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:8px solid #bbb;"></div>
      <div style="width:1px; height:20px; background:#bbb;"></div>
      <div style="font-size:9px; color:#aaa; margin-bottom:4px;">overrides</div>
    </div>
    <div class="node exc1" style="width:100%;">
      <div class="node-id">§ 7701(b)(3)(D)</div>
      <div class="node-role">Exception to A (independent)</div>
      <div class="node-header">Exempt individuals / medical conditions</div>
      <div class="node-text">
        Days when the individual is an exempt individual, or was unable to leave due to a medical
        condition that arose while present in the US, do not count toward A's day totals.
      </div>
    </div>
  </div>

</div>

<!-- Priority chain -->
<div class="priority-box">
  <h3>Priority order — highest wins</h3>
  <div class="priority-chain">
    <span class="p-node" style="background:#fff1f2; color:#b91c1c;">C</span>
    <span class="p-arrow">&gt;</span>
    <span class="p-node" style="background:#fffbeb; color:#b45309;">B</span>
    <span class="p-arrow">&gt;</span>
    <span class="p-node" style="background:#eff6ff; color:#1d4ed8;">A</span>
    <span style="margin-left:20px; color:#bbb;">|</span>
    <span class="p-node" style="background:#fffbeb; color:#b45309; margin-left:20px;">D</span>
    <span class="p-arrow">&gt;</span>
    <span class="p-node" style="background:#eff6ff; color:#1d4ed8;">A</span>
    <span style="margin-left:8px; font-size:10px; color:#aaa;">(independent chain)</span>
  </div>
  <p class="p-note">
    The DAG evaluator walks from the base rule upward. If a higher-priority rule's condition fires,
    it returns that rule's value and silences the rules it overrides.
    If two rules at the same priority level fire simultaneously → <span style="color:#b91c1c;">ConflictError</span>.
    If no rule fires → <span style="color:#b91c1c;">GapError</span>.
  </p>
</div>

<!-- Evaluation examples -->
<div class="eval-box">
  <h3>Example evaluations</h3>
  <table>
    <thead>
      <tr>
        <th>Scenario</th>
        <th>D fires?</th>
        <th>B fires?</th>
        <th>C fires?</th>
        <th>Result</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>200 days, no foreign home, no LPR steps</td>
        <td class="na">—</td>
        <td class="lose">No (&gt;183 days)</td>
        <td class="na">—</td>
        <td class="win">A applies → resident alien</td>
      </tr>
      <tr>
        <td>150 days, foreign tax home, closer connection</td>
        <td class="na">—</td>
        <td class="win">Yes</td>
        <td class="lose">No (no LPR steps)</td>
        <td class="win">B overrides A → not resident</td>
      </tr>
      <tr>
        <td>150 days, foreign tax home, but pending LPR application</td>
        <td class="na">—</td>
        <td class="lose">Yes (but silenced)</td>
        <td class="win">Yes</td>
        <td class="win">C overrides B → A applies → resident alien</td>
      </tr>
      <tr>
        <td>200 days but 40 days as diplomat (exempt)</td>
        <td class="win">Yes (40 days removed)</td>
        <td class="na">—</td>
        <td class="na">—</td>
        <td class="win">D modifies A's count → 160 effective days → re-evaluate A</td>
      </tr>
    </tbody>
  </table>
</div>

</body>
</html>
"""


def main():
    os.makedirs("demo", exist_ok=True)
    with open(OUT_FILE, "w") as f:
        f.write(HTML)
    print(f"Written: {OUT_FILE}")


if __name__ == "__main__":
    main()
