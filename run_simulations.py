"""
run_simulations.py
------------------
Runs Monte Carlo tournament simulations and saves results to sim_results.json,
including per-team per-round opponent probability data used by the flow diagram.

Usage:
    venv/bin/python run_simulations.py
"""

import json
from collections import defaultdict
from pathlib import Path

from tournament_simulator import load_tournament_data, simulate_tournament

N = 1000
SEED = 0
OUT = Path(__file__).parent / "sim_results.json"

STAGE_KEY = {2: "r32", 3: "r16", 4: "qf", 5: "sf", 7: "final"}


def build_team_flows(all_matchups, teams_df, matches_df, id_to_code, id_to_name):
    # Group opponents are fixed — find them from matches_df
    group_opps: dict[int, list[int]] = defaultdict(list)
    for _, m in matches_df[matches_df["stage_id"] == 1].iterrows():
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        group_opps[h].append(a)
        group_opps[a].append(h)

    # Count knockout opponent appearances per team per stage across all sims
    ko_counts: dict[int, dict[str, dict[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for sim_matchups in all_matchups:
        for mu in sim_matchups:
            key = STAGE_KEY.get(mu["stage_id"])
            if key:
                ta, tb = mu["team_a_id"], mu["team_b_id"]
                ko_counts[ta][key][tb] += 1
                ko_counts[tb][key][ta] += 1

    team_flows: dict[str, dict] = {}
    for _, team in teams_df.iterrows():
        tid = int(team["id"])
        code = team["fifa_code"]

        group = sorted(
            [
                {"code": id_to_code[oid], "name": id_to_name[oid], "prob": 1.0}
                for oid in group_opps[tid]
            ],
            key=lambda x: x["name"],
        )

        flows: dict[str, list] = {"group": group}
        for stage_key in ["r32", "r16", "qf", "sf", "final"]:
            opp_counts = ko_counts[tid][stage_key]
            flows[stage_key] = sorted(
                [
                    {
                        "code": id_to_code[oid],
                        "name": id_to_name[oid],
                        "prob": round(cnt / N, 4),
                    }
                    for oid, cnt in opp_counts.items()
                    if cnt > 0
                ],
                key=lambda x: -x["prob"],
            )

        team_flows[code] = flows

    return team_flows


def main():
    print(f"Running {N} simulations (seed={SEED})…", flush=True)
    results, all_matchups = simulate_tournament(n=N, seed=SEED, detailed=True)

    data = load_tournament_data()
    teams_df = data["teams"]
    matches_df = data["matches"]
    id_to_code: dict[int, str] = teams_df.set_index("id")["fifa_code"].to_dict()
    id_to_name: dict[int, str] = teams_df.set_index("id")["team_name"].to_dict()

    team_flows = build_team_flows(
        all_matchups, teams_df, matches_df, id_to_code, id_to_name
    )

    payload = {
        "n_simulations": N,
        "seed": SEED,
        "runs": results.to_dict(orient="records"),
        "team_flows": team_flows,
    }

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({N} runs, {len(team_flows)} team flow maps)")

    top5 = (
        results["champion_code"]
        .value_counts()
        .head(5)
        .mul(100 / N)
        .round(1)
    )
    print("\nTop 5 by win %:")
    for code, pct in top5.items():
        name = results.loc[results["champion_code"] == code, "champion_name"].iloc[0]
        print(f"  {code:5s} {name:<25s} {pct:.1f}%")


if __name__ == "__main__":
    main()
