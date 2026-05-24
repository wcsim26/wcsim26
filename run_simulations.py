"""
run_simulations.py
------------------
Runs Monte Carlo tournament simulations and saves results to sim_results.json,
including per-team per-round opponent probability data used by the flow diagram,
per-game data for the All Matches page, and entropy-based importance scores.

Usage:
    venv/bin/python run_simulations.py
"""

import json
from collections import Counter, defaultdict
from math import log2
from pathlib import Path

from tournament_simulator import build_elo_map, load_tournament_data, simulate_tournament
from wc26_simulation import calculate_expected_goals, get_match_probabilities

N = 1000
SEED = 0
OUT = Path(__file__).parent / "sim_results.json"

STAGE_KEY = {2: "r32", 3: "r16", 4: "qf", 5: "sf", 7: "final"}
STAGE_NAME = {1: "Group Stage", 2: "Round of 32", 3: "Round of 16",
              4: "Quarterfinals", 5: "Semifinals", 6: "Third Place", 7: "Final"}


def compute_entropy(codes):
    n = len(codes)
    counts = Counter(codes)
    return -sum((c / n) * log2(c / n) for c in counts.values() if c > 0)


def build_team_flows(all_matchups, teams_df, matches_df, id_to_code, id_to_name):
    group_opps: dict[int, list[int]] = defaultdict(list)
    for _, m in matches_df[matches_df["stage_id"] == 1].iterrows():
        h, a = int(m["home_team_id"]), int(m["away_team_id"])
        group_opps[h].append(a)
        group_opps[a].append(h)

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


def build_games(all_group_results, all_matchups, champion_codes,
                matches_df, teams_df, elo_df, id_to_code, id_to_name):
    H = compute_entropy(champion_codes)
    importances: dict[int, float] = {}

    # Group stage importance
    match_to_pairs: dict[int, list] = defaultdict(list)
    for gs_results, champ in zip(all_group_results, champion_codes):
        for r in gs_results:
            match_to_pairs[r["match_number"]].append((r["result"], champ))

    for mn, pairs in match_to_pairs.items():
        by_outcome: dict[str, list] = defaultdict(list)
        for result, champ in pairs:
            by_outcome[result].append(champ)
        cond_H = sum(len(v) / N * compute_entropy(v) for v in by_outcome.values())
        importances[mn] = round((H - cond_H) / H * 100, 3)

    # Knockout importance and top-team win counts
    ko_match_pairs: dict[int, list] = defaultdict(list)
    ko_win_counts: dict[int, Counter] = defaultdict(Counter)
    for sim_matchups, champ in zip(all_matchups, champion_codes):
        for mu in sim_matchups:
            mn = mu["match_number"]
            winner_code = id_to_code[mu["team_a_id"]]
            ko_match_pairs[mn].append((winner_code, champ))
            ko_win_counts[mn][winner_code] += 1

    for mn, pairs in ko_match_pairs.items():
        by_winner: dict[str, list] = defaultdict(list)
        for winner, champ in pairs:
            by_winner[winner].append(champ)
        cond_H = sum(len(v) / N * compute_entropy(v) for v in by_winner.values())
        importances[mn] = round((H - cond_H) / H * 100, 3)

    # Build Elo lookup for analytic group-stage outcome probabilities
    elo_map = build_elo_map(teams_df, elo_df)
    code_to_elo = {row["fifa_code"]: elo_map[int(row["id"])] for _, row in teams_df.iterrows()}
    fallback_elo = 1650.0

    games = []
    for _, row in matches_df.sort_values("match_number").iterrows():
        mn = int(row["match_number"])
        stage_id = int(row["stage_id"])

        game: dict = {
            "match_number": mn,
            "stage_id": stage_id,
            "stage_name": STAGE_NAME.get(stage_id, ""),
            "kickoff": str(row["kickoff_at"]),
            "importance": importances.get(mn, 0.0),
        }

        if stage_id == 1:
            home_code = id_to_code[int(row["home_team_id"])]
            away_code = id_to_code[int(row["away_team_id"])]
            home_elo = code_to_elo.get(home_code, fallback_elo)
            away_elo = code_to_elo.get(away_code, fallback_elo)
            lam_a, lam_b = calculate_expected_goals(home_elo, away_elo)
            probs = get_match_probabilities(lam_a, lam_b)
            game.update({
                "home_code": home_code,
                "home_name": id_to_name[int(row["home_team_id"])],
                "away_code": away_code,
                "away_name": id_to_name[int(row["away_team_id"])],
                "win_prob":  round(probs["win_a"], 4),
                "draw_prob": round(probs["draw"],  4),
                "loss_prob": round(probs["win_b"], 4),
            })
        else:
            game["match_label"] = str(row["match_label"])
            game["top_teams"] = [
                {"code": code, "win_prob": round(cnt / N, 4)}
                for code, cnt in ko_win_counts[mn].most_common(5)
            ]

        games.append(game)

    return round(H, 4), games


def main():
    print(f"Running {N} simulations (seed={SEED})…", flush=True)
    results, all_matchups, all_group_results = simulate_tournament(
        n=N, seed=SEED, detailed=True
    )

    data = load_tournament_data()
    teams_df   = data["teams"]
    matches_df = data["matches"]
    id_to_code: dict[int, str] = teams_df.set_index("id")["fifa_code"].to_dict()
    id_to_name: dict[int, str] = teams_df.set_index("id")["team_name"].to_dict()

    champion_codes = results["champion_code"].tolist()

    team_flows = build_team_flows(
        all_matchups, teams_df, matches_df, id_to_code, id_to_name
    )

    H_bits, games = build_games(
        all_group_results, all_matchups, champion_codes,
        matches_df, teams_df, data["elo"], id_to_code, id_to_name,
    )

    payload = {
        "n_simulations": N,
        "seed": SEED,
        "H_bits": H_bits,
        "runs": results.to_dict(orient="records"),
        "team_flows": team_flows,
        "games": games,
    }

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({N} runs, {len(team_flows)} team flow maps)")
    print(f"Tournament winner entropy: {H_bits:.3f} bits (max {log2(48):.3f})")

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
