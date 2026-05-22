"""
generate_results.py
-------------------
Reads sim_results.json (produced by run_simulations.py) and writes a
self-contained index.html with the win-probability table embedded as
inline JSON. Fast — no simulation is performed here.

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

  main {
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

  .team-name { font-weight: 500; }
  .team-code {
    font-size: 0.75rem;
    color: #8b949e;
    margin-left: 0.35rem;
  }

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

  .pct {
    font-variant-numeric: tabular-nums;
    color: #8b949e;
  }

  .pct.nonzero { color: #e6edf3; }

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

<footer>
  Model constants: &alpha; = <code>0.26</code> (ln 1.3), &beta; = <code>0.003</code>,
  home advantage <code>+100 Elo</code> for USA / Mexico / Canada in their own venues.
  Knockout draws resolved by 50/50 penalty coin-flip.
</footer>

<script>
const DATA = __JSON_PLACEHOLDER__;

(function () {
  document.getElementById("n-sims").textContent =
    DATA.n_simulations.toLocaleString();
  document.getElementById("seed-val").textContent = DATA.seed;

  const teams = DATA.teams;
  const maxWin = Math.max(...teams.map(t => t.win_pct));

  let sortCol = "rank";
  let sortAsc = true;

  function renderTable(rows) {
    const tbody = document.getElementById("table-body");
    tbody.innerHTML = "";
    rows.forEach((t, i) => {
      const tr = document.createElement("tr");
      if (t.placeholder) tr.classList.add("placeholder");

      const barWidth = maxWin > 0
        ? Math.round(t.win_pct / maxWin * 100)
        : 0;

      tr.innerHTML = `
        <td class="num rank">${i + 1}</td>
        <td>
          <span class="team-name">${t.name}</span>
          <span class="team-code">${t.code}</span>
        </td>
        <td><span class="group-badge">${t.group}</span></td>
        <td class="num bar-cell">
          <div class="bar-wrap">
            <div class="bar-track">
              <div class="bar-fill" style="width:${barWidth}%"></div>
            </div>
            <span class="bar-label">${t.win_pct.toFixed(1)}</span>
          </div>
        </td>
        <td class="num pct ${t.finalist_pct > 0 ? "nonzero" : ""}">
          ${t.finalist_pct.toFixed(1)}
        </td>
        <td class="num pct ${t.top3_pct > 0 ? "nonzero" : ""}">
          ${t.top3_pct.toFixed(1)}
        </td>
      `;
      tbody.appendChild(tr);
    });
  }

  function getSortedRows(filter) {
    let rows = teams.slice();

    if (filter) {
      const q = filter.toLowerCase();
      rows = rows.filter(t =>
        t.name.toLowerCase().includes(q) ||
        t.code.toLowerCase().includes(q)
      );
    }

    rows.sort((a, b) => {
      let av, bv;
      if (sortCol === "rank") {
        av = a.win_pct; bv = b.win_pct;
        const asc = !sortAsc;
        return asc ? av - bv : bv - av;
      }
      if (sortCol === "name")  { av = a.name;  bv = b.name; }
      if (sortCol === "group") { av = a.group; bv = b.group; }
      if (sortCol === "win_pct")      { av = a.win_pct;      bv = b.win_pct; }
      if (sortCol === "finalist_pct") { av = a.finalist_pct; bv = b.finalist_pct; }
      if (sortCol === "top3_pct")     { av = a.top3_pct;     bv = b.top3_pct; }
      if (typeof av === "string") {
        return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      }
      return sortAsc ? av - bv : bv - av;
    });

    return rows;
  }

  function updateHeaders() {
    document.querySelectorAll("th[data-col]").forEach(th => {
      th.classList.remove("sort-asc", "sort-desc");
      if (th.dataset.col === sortCol) {
        th.classList.add(sortAsc ? "sort-asc" : "sort-desc");
      }
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

  refresh();
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

    import pandas as pd
    results = pd.DataFrame(sim_data["runs"])

    data = load_tournament_data()
    teams_df = data["teams"]

    rows = compute_team_stats(results, teams_df, n)

    payload = json.dumps(
        {"n_simulations": n, "seed": sim_data["seed"], "teams": rows},
        indent=2,
    )

    html = HTML_TEMPLATE.replace("__JSON_PLACEHOLDER__", payload)
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({len(rows)} teams, {n} simulations)")


if __name__ == "__main__":
    main()
