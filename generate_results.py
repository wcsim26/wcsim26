"""
generate_results.py
-------------------
Reads sim_results.json (produced by run_simulations.py) and writes a
self-contained index.html with the win-probability table and per-team
flow diagrams embedded as inline JSON. Fast — no simulation is performed.

Usage:
    venv/bin/python run_simulations.py   # run once to generate sim_results.json
    venv/bin/python generate_results.py  # rebuild index.html any time
    open index.html
"""

import json
import sys
from pathlib import Path

from tournament_simulator import load_tournament_data

SIM_FILE = Path(__file__).parent / "sim_results.json"
OUT = Path(__file__).parent / "index.html"


def compute_team_stats(results, teams_df, n):
    champion_counts = results["champion_code"].value_counts()
    finalist_counts = results["finalist_code"].value_counts()
    third_counts    = results["third_place_code"].value_counts()

    rows = []
    for _, team in teams_df.iterrows():
        code = team["fifa_code"]
        wins     = champion_counts.get(code, 0)
        finals   = finalist_counts.get(code, 0)
        thirds   = third_counts.get(code, 0)
        rows.append({
            "code":         code,
            "name":         team["team_name"],
            "group":        team["group_letter"],
            "placeholder":  bool(team["is_placeholder"]),
            "win_pct":      round(wins / n * 100, 1),
            "finalist_pct": round((wins + finals) / n * 100, 1),
            "top3_pct":     round((wins + finals + thirds) / n * 100, 1),
        })

    rows.sort(key=lambda r: (-r["win_pct"], -r["finalist_pct"], r["name"]))
    return rows


HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>2026 FIFA World Cup Simulator</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: system-ui, -apple-system, sans-serif;
    background: #0d1117;
    color: #e6edf3;
    min-height: 100vh;
  }

  header {
    background: linear-gradient(135deg, #1a3a1a 0%, #0d2b0d 100%);
    border-bottom: 2px solid #2ea043;
    padding: 2rem 1.5rem 1.5rem;
    text-align: center;
  }

  header h1 {
    font-size: 1.9rem;
    font-weight: 700;
    letter-spacing: -0.5px;
    color: #fff;
  }

  header h1 span { color: #2ea043; }

  .subtitle {
    margin-top: 0.4rem;
    font-size: 0.85rem;
    color: #8b949e;
  }

  /* ── Main table view ── */

  #main-view main {
    max-width: 860px;
    margin: 2rem auto;
    padding: 0 1rem;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }

  .controls label { font-size: 0.85rem; color: #8b949e; }

  .controls input[type=text] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e6edf3;
    font-size: 0.85rem;
    padding: 0.35rem 0.6rem;
    width: 160px;
  }

  .controls input[type=text]::placeholder { color: #484f58; }

  .table-wrap {
    overflow-x: auto;
    border-radius: 8px;
    border: 1px solid #21262d;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.875rem;
  }

  thead {
    background: #161b22;
    position: sticky;
    top: 0;
    z-index: 1;
  }

  th {
    padding: 0.65rem 0.75rem;
    text-align: left;
    font-weight: 600;
    color: #8b949e;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
    border-bottom: 1px solid #21262d;
  }

  th:hover { color: #e6edf3; }
  th.sort-asc::after  { content: " ↑"; color: #2ea043; }
  th.sort-desc::after { content: " ↓"; color: #2ea043; }

  th.num, td.num { text-align: right; }

  tbody tr {
    border-bottom: 1px solid #21262d;
    transition: background 0.1s;
  }

  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: #1c2128; }

  td { padding: 0.55rem 0.75rem; vertical-align: middle; }

  .rank { color: #484f58; font-size: 0.8rem; width: 2.5rem; }

  .team-link {
    text-decoration: none;
    color: inherit;
    display: flex;
    align-items: baseline;
    gap: 0.35rem;
  }
  .team-link:hover .team-name { color: #2ea043; text-decoration: underline; }

  .team-name { font-weight: 500; }
  .team-code { font-size: 0.75rem; color: #8b949e; }

  .group-badge {
    display: inline-block;
    background: #21262d;
    border-radius: 4px;
    padding: 0.1rem 0.45rem;
    font-size: 0.75rem;
    color: #8b949e;
    font-weight: 600;
  }

  .placeholder .team-name { color: #484f58; font-style: italic; }

  .bar-cell { min-width: 120px; }

  .bar-wrap {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .bar-track {
    flex: 1;
    height: 6px;
    background: #21262d;
    border-radius: 3px;
    overflow: hidden;
  }

  .bar-fill {
    height: 100%;
    background: #2ea043;
    border-radius: 3px;
    transition: width 0.2s;
  }

  .bar-label {
    min-width: 3.2rem;
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: #e6edf3;
  }

  .pct { font-variant-numeric: tabular-nums; color: #8b949e; }
  .pct.nonzero { color: #e6edf3; }

  /* ── Team detail view ── */

  #team-view {
    max-width: 1300px;
    margin: 0 auto;
    padding: 1.5rem 1rem 2rem;
  }

  .back-link {
    display: inline-block;
    color: #8b949e;
    text-decoration: none;
    font-size: 0.85rem;
    margin-bottom: 1.25rem;
  }
  .back-link:hover { color: #2ea043; }

  .team-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    flex-wrap: wrap;
    margin-bottom: 1.25rem;
  }

  .team-header h2 {
    font-size: 1.5rem;
    font-weight: 700;
  }

  .team-stats-row {
    display: flex;
    gap: 1.5rem;
    margin-bottom: 1.75rem;
    flex-wrap: wrap;
  }

  .stat-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 8px;
    padding: 0.75rem 1.25rem;
    text-align: center;
    min-width: 110px;
  }

  .stat-card .stat-val {
    font-size: 1.5rem;
    font-weight: 700;
    color: #2ea043;
    font-variant-numeric: tabular-nums;
  }

  .stat-card .stat-lbl {
    font-size: 0.75rem;
    color: #8b949e;
    margin-top: 0.2rem;
  }

  .flow-section-title {
    font-size: 0.8rem;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.75rem;
    font-weight: 600;
  }

  .flow-wrap {
    overflow-x: auto;
    border: 1px solid #21262d;
    border-radius: 8px;
    background: #0d1117;
    padding: 1rem 0.5rem;
  }

  /* ── Footer ── */

  footer {
    text-align: center;
    padding: 2rem 1rem;
    font-size: 0.78rem;
    color: #484f58;
    border-top: 1px solid #21262d;
    margin-top: 2rem;
  }

  footer code {
    background: #161b22;
    border-radius: 3px;
    padding: 0.1rem 0.3rem;
    font-size: 0.78rem;
    color: #8b949e;
  }

  @media (max-width: 600px) {
    header h1 { font-size: 1.4rem; }
    .bar-cell { min-width: 90px; }
  }
</style>
</head>
<body>

<header>
  <h1>2026 FIFA World Cup <span>Simulator</span></h1>
  <p class="subtitle">
    Elo-Difference Poisson model &nbsp;&middot;&nbsp;
    <strong id="n-sims"></strong> simulations &nbsp;&middot;&nbsp;
    seed = <span id="seed-val"></span>
  </p>
</header>

<!-- ═══ Main view: probability table ═══ -->
<div id="main-view">
  <main>
    <div class="controls">
      <label for="search">Filter team:</label>
      <input type="text" id="search" placeholder="name or code&hellip;">
    </div>

    <div class="table-wrap">
      <table id="results-table">
        <thead>
          <tr>
            <th class="num" data-col="rank">Rank</th>
            <th data-col="name">Team</th>
            <th data-col="group">Grp</th>
            <th class="num bar-cell" data-col="win_pct">Win %</th>
            <th class="num" data-col="finalist_pct">Final %</th>
            <th class="num" data-col="top3_pct">Top 3 %</th>
          </tr>
        </thead>
        <tbody id="table-body"></tbody>
      </table>
    </div>
  </main>
</div>

<!-- ═══ Team detail view ═══ -->
<div id="team-view" style="display:none">
  <a class="back-link" id="back-link" href="#">&larr; All teams</a>

  <div class="team-header">
    <h2 id="team-title"></h2>
    <span class="group-badge" id="team-group-badge"></span>
  </div>

  <div class="team-stats-row">
    <div class="stat-card">
      <div class="stat-val" id="sv-win"></div>
      <div class="stat-lbl">Win</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" id="sv-final"></div>
      <div class="stat-lbl">Reach Final</div>
    </div>
    <div class="stat-card">
      <div class="stat-val" id="sv-top3"></div>
      <div class="stat-lbl">Top 3</div>
    </div>
  </div>

  <p class="flow-section-title">Opponent probability by round</p>
  <div class="flow-wrap">
    <svg id="flow-svg" style="display:block;"></svg>
  </div>
</div>

<footer>
  Model constants: &alpha; = <code>0.26</code> (ln 1.3), &beta; = <code>0.003</code>,
  home advantage <code>+100 Elo</code> for USA / Mexico / Canada in their own venues.
  Knockout draws resolved by 50/50 penalty coin-flip.
  Click any team to see their tournament flow diagram.
</footer>

<script>
const DATA  = __DATA_PLACEHOLDER__;
const FLOWS = __FLOWS_PLACEHOLDER__;

(function () {
  // ── Shared state ──────────────────────────────────────────────────────────
  document.getElementById("n-sims").textContent = DATA.n_simulations.toLocaleString();
  document.getElementById("seed-val").textContent = DATA.seed;

  const teams = DATA.teams;
  const maxWin = Math.max(...teams.map(t => t.win_pct));

  const teamByCode = {};
  teams.forEach(t => { teamByCode[t.code] = t; });

  // ── Routing ───────────────────────────────────────────────────────────────
  function route() {
    const hash = window.location.hash.replace("#", "");
    if (hash && teamByCode[hash]) {
      showTeam(hash);
    } else {
      showMain();
    }
  }

  function showMain() {
    document.getElementById("main-view").style.display = "";
    document.getElementById("team-view").style.display = "none";
    document.title = "2026 FIFA World Cup Simulator";
    refresh();
  }

  function showTeam(code) {
    const team = teamByCode[code];
    document.getElementById("main-view").style.display = "none";
    document.getElementById("team-view").style.display = "";

    document.getElementById("team-title").textContent = team.name;
    document.getElementById("team-group-badge").textContent = "Group " + team.group;
    document.getElementById("sv-win").textContent   = team.win_pct.toFixed(1) + "%";
    document.getElementById("sv-final").textContent = team.finalist_pct.toFixed(1) + "%";
    document.getElementById("sv-top3").textContent  = team.top3_pct.toFixed(1) + "%";
    document.getElementById("back-link").href = window.location.pathname + window.location.search;

    renderFlowDiagram(document.getElementById("flow-svg"), code, FLOWS[code] || {});
    document.title = team.name + " – WC2026 Simulator";
    window.scrollTo(0, 0);
  }

  window.addEventListener("hashchange", route);

  // ── Main table rendering ──────────────────────────────────────────────────
  let sortCol = "rank";
  let sortAsc = true;

  function renderTable(rows) {
    const tbody = document.getElementById("table-body");
    tbody.innerHTML = "";
    rows.forEach((t, i) => {
      const tr = document.createElement("tr");
      if (t.placeholder) tr.classList.add("placeholder");

      const barWidth = maxWin > 0 ? Math.round(t.win_pct / maxWin * 100) : 0;

      tr.innerHTML = `
        <td class="num rank">${i + 1}</td>
        <td>
          <a class="team-link" href="#${t.code}">
            <span class="team-name">${t.name}</span>
            <span class="team-code">${t.code}</span>
          </a>
        </td>
        <td><span class="group-badge">${t.group}</span></td>
        <td class="num bar-cell">
          <div class="bar-wrap">
            <div class="bar-track"><div class="bar-fill" style="width:${barWidth}%"></div></div>
            <span class="bar-label">${t.win_pct.toFixed(1)}</span>
          </div>
        </td>
        <td class="num pct ${t.finalist_pct > 0 ? "nonzero" : ""}">${t.finalist_pct.toFixed(1)}</td>
        <td class="num pct ${t.top3_pct > 0 ? "nonzero" : ""}">${t.top3_pct.toFixed(1)}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  function getSortedRows(filter) {
    let rows = teams.slice();
    if (filter) {
      const q = filter.toLowerCase();
      rows = rows.filter(t =>
        t.name.toLowerCase().includes(q) || t.code.toLowerCase().includes(q)
      );
    }
    rows.sort((a, b) => {
      let av, bv;
      if (sortCol === "rank") {
        av = a.win_pct; bv = b.win_pct;
        return sortAsc ? bv - av : av - bv;
      }
      if (sortCol === "name")          { av = a.name;          bv = b.name; }
      if (sortCol === "group")         { av = a.group;         bv = b.group; }
      if (sortCol === "win_pct")       { av = a.win_pct;       bv = b.win_pct; }
      if (sortCol === "finalist_pct")  { av = a.finalist_pct;  bv = b.finalist_pct; }
      if (sortCol === "top3_pct")      { av = a.top3_pct;      bv = b.top3_pct; }
      if (typeof av === "string") return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortAsc ? av - bv : bv - av;
    });
    return rows;
  }

  function updateHeaders() {
    document.querySelectorAll("th[data-col]").forEach(th => {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.dataset.col === sortCol) th.classList.add(sortAsc ? "sort-asc" : "sort-desc");
    });
  }

  function refresh() {
    const q = document.getElementById("search").value.trim();
    renderTable(getSortedRows(q));
    updateHeaders();
  }

  document.querySelectorAll("th[data-col]").forEach(th => {
    th.addEventListener("click", () => {
      if (sortCol === th.dataset.col) {
        sortAsc = !sortAsc;
      } else {
        sortCol = th.dataset.col;
        sortAsc = sortCol === "name" || sortCol === "group";
      }
      refresh();
    });
  });

  document.getElementById("search").addEventListener("input", refresh);

  // ── SVG flow diagram ──────────────────────────────────────────────────────
  function renderFlowDiagram(svgEl, code, flows) {
    const STAGES      = ["group", "r32", "r16", "qf", "sf", "final"];
    const LABELS      = ["Group", "Round of 32", "Round of 16", "Quarters", "Semis", "Final"];
    const BOX_W       = 128;
    const COL_GAP     = 68;
    const STEP        = BOX_W + COL_GAP;
    const BOX_GAP     = 5;
    const GROUP_H     = 44;
    const PX_PER_PCT  = 4.2;
    const MIN_KO_H    = 26;
    const HEADER_H    = 22;
    const PAD_TOP     = HEADER_H + 14;
    const PAD_BOT     = 16;
    const TEAM_W      = 64;
    const TEAM_GAP    = 48;
    const X0          = TEAM_W + TEAM_GAP;

    // Compute box layout for each stage column
    const cols = STAGES.map((stage, i) => {
      const opps = (flows[stage] || []).slice(0, 24);
      let y = PAD_TOP;
      const boxes = opps.map(opp => {
        const h = stage === "group"
          ? GROUP_H
          : Math.max(MIN_KO_H, opp.prob * 100 * PX_PER_PCT);
        const box = { code: opp.code, name: opp.name, prob: opp.prob, y, h };
        y += h + BOX_GAP;
        return box;
      });
      return { stage, label: LABELS[i], x: X0 + i * STEP, boxes, colH: y };
    });

    const svgH = Math.max(180, ...cols.map(c => c.colH)) + PAD_BOT;
    const svgW = X0 + STAGES.length * STEP - COL_GAP + 12;

    svgEl.setAttribute("viewBox", `0 0 ${svgW} ${svgH}`);
    svgEl.setAttribute("width",  svgW);
    svgEl.setAttribute("height", svgH);
    svgEl.innerHTML = "";

    const NS = "http://www.w3.org/2000/svg";
    function mk(tag, attrs) {
      const e = document.createElementNS(NS, tag);
      if (attrs) for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
      return e;
    }
    function txt(tag, attrs, content) {
      const e = mk(tag, attrs);
      e.textContent = content;
      return e;
    }

    // Weighted centroid Y of a column (for bezier source)
    function centY(col) {
      if (!col.boxes.length) return svgH / 2;
      let num = 0, den = 0;
      for (const b of col.boxes) {
        const w = b.prob;
        num += w * (b.y + b.h / 2);
        den += w;
      }
      return den > 0 ? num / den : svgH / 2;
    }

    // Team label box on far left
    const teamCY = centY(cols[0]);
    const teamBH = 34;
    const teamBY = Math.max(PAD_TOP, teamCY - teamBH / 2);
    svgEl.appendChild(mk("rect", {
      x: 0, y: teamBY, width: TEAM_W, height: teamBH,
      rx: 4, fill: "#2ea043",
    }));
    svgEl.appendChild(txt("text", {
      x: TEAM_W / 2, y: teamBY + teamBH / 2,
      "text-anchor": "middle", "dominant-baseline": "middle",
      "font-size": "12", "font-weight": "bold",
      fill: "#fff", "font-family": "system-ui,sans-serif",
    }, code));

    // Stage headers
    cols.forEach(col => {
      svgEl.appendChild(txt("text", {
        x: col.x + BOX_W / 2, y: HEADER_H,
        "text-anchor": "middle",
        "font-size": "10", "font-weight": "600", "letter-spacing": "0.04em",
        fill: "#8b949e", "font-family": "system-ui,sans-serif",
      }, col.label.toUpperCase()));
    });

    // Draw bezier curves (rendered before boxes so boxes sit on top)
    // Source for first column: right edge of team label box at centroid Y
    let srcX = TEAM_W;
    let srcY = teamCY;

    cols.forEach((col, i) => {
      const dstX = col.x;
      col.boxes.forEach(box => {
        const dstY = box.y + box.h / 2;
        const isGroup = i === 0;
        const sw = isGroup ? 3 : Math.max(1.5, box.prob * 100 * 0.22);
        const op = isGroup ? 0.55 : Math.min(0.88, 0.18 + box.prob * 3.5);
        const cpx = srcX + (dstX - srcX) * 0.5;
        svgEl.appendChild(mk("path", {
          d: `M ${srcX} ${srcY} C ${cpx} ${srcY} ${cpx} ${dstY} ${dstX} ${dstY}`,
          stroke: "#2ea043", "stroke-width": sw, "stroke-opacity": op,
          fill: "none", "stroke-linecap": "round",
        }));
      });
      srcX = col.x + BOX_W;
      srcY = centY(col);
    });

    // Draw opponent boxes (on top of curves)
    cols.forEach((col, i) => {
      const isGroup = i === 0;
      col.boxes.forEach(box => {
        const pct = isGroup ? "100%" : (box.prob * 100).toFixed(1) + "%";
        const bStroke = isGroup
          ? "#30363d"
          : `rgba(46,160,67,${Math.min(0.9, 0.25 + box.prob * 4)})`;
        const bStrokeW = isGroup ? 1 : Math.max(1, 0.6 + box.prob * 100 * 0.04);

        const g = document.createElementNS(NS, "g");
        g.style.cursor = "pointer";
        g.setAttribute("role", "button");
        const targetCode = box.code;
        g.addEventListener("click", () => { window.location.hash = targetCode; });

        g.appendChild(mk("rect", {
          x: col.x, y: box.y, width: BOX_W, height: box.h,
          rx: 3, fill: "#161b22", stroke: bStroke, "stroke-width": bStrokeW,
        }));

        // Truncate name to fit
        const maxChars = 15;
        const name = box.name.length > maxChars
          ? box.name.slice(0, maxChars - 1) + "…"
          : box.name;

        if (box.h >= 34) {
          // Two-line label
          g.appendChild(txt("text", {
            x: col.x + 6, y: box.y + box.h / 2 - 5,
            "font-size": "11", fill: "#e6edf3",
            "font-family": "system-ui,sans-serif",
          }, name));
          g.appendChild(txt("text", {
            x: col.x + 6, y: box.y + box.h / 2 + 9,
            "font-size": "10", fill: "#2ea043",
            "font-family": "system-ui,sans-serif",
          }, pct));
        } else {
          g.appendChild(txt("text", {
            x: col.x + 5, y: box.y + box.h / 2,
            "dominant-baseline": "middle",
            "font-size": "10", fill: "#e6edf3",
            "font-family": "system-ui,sans-serif",
          }, name + " " + pct));
        }

        svgEl.appendChild(g);
      });
    });
  }

  // ── Boot ──────────────────────────────────────────────────────────────────
  route();
})();
</script>
</body>
</html>
"""


def main():
    if not SIM_FILE.exists():
        sys.exit(
            f"Error: {SIM_FILE} not found.\n"
            "Run `venv/bin/python run_simulations.py` first."
        )

    sim_data = json.loads(SIM_FILE.read_text(encoding="utf-8"))
    n = sim_data["n_simulations"]
    team_flows = sim_data.get("team_flows", {})

    import pandas as pd
    results = pd.DataFrame(sim_data["runs"])

    data = load_tournament_data()
    teams_df = data["teams"]

    rows = compute_team_stats(results, teams_df, n)

    data_json  = json.dumps({"n_simulations": n, "seed": sim_data["seed"], "teams": rows})
    flows_json = json.dumps(team_flows)

    html = HTML_TEMPLATE \
        .replace("__DATA_PLACEHOLDER__",  data_json) \
        .replace("__FLOWS_PLACEHOLDER__", flows_json)

    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({len(rows)} teams, {n} simulations, {len(team_flows)} flow maps)")


if __name__ == "__main__":
    main()
