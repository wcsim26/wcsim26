"""
tournament_simulator.py
-----------------------
Full 2026 FIFA World Cup tournament simulator using real fixture data
and current PELE Elo ratings. Simulates the Group Stage through the Final,
then reports win probabilities across many runs.

Reuses the core Elo-Difference Poisson model from wc26_simulation.py.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from wc26_simulation import calculate_expected_goals, simulate_match_score

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent / "data"

FALLBACK_ELO_QUALIFIED: float = 1650.0    # WC qualifier absent from Elo dataset
FALLBACK_ELO_PLACEHOLDER: float = 1750.0  # Unresolved playoff winner slot

# Nations that earned co-host status (venue country → team name must match)
HOST_NATIONS: frozenset[str] = frozenset({"USA", "Mexico", "Canada"})

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_tournament_data() -> dict[str, pd.DataFrame]:
    """Load all tournament CSVs from data/ and return them in a dict."""
    return {
        "teams":   pd.read_csv(DATA_DIR / "teams.csv"),
        "matches": pd.read_csv(DATA_DIR / "matches.csv"),
        "cities":  pd.read_csv(DATA_DIR / "host_cities.csv"),
        "stages":  pd.read_csv(DATA_DIR / "tournament_stages.csv"),
        "elo":     pd.read_csv(DATA_DIR / "data-4oVop.csv"),
    }

# ---------------------------------------------------------------------------
# Lookup maps
# ---------------------------------------------------------------------------


def build_elo_map(teams_df: pd.DataFrame, elo_df: pd.DataFrame) -> dict[int, float]:
    """
    Return {team_id: current_elo} using the PELE column from the Elo dataset.
    Placeholder teams (unresolved playoffs) receive FALLBACK_ELO_PLACEHOLDER;
    qualified teams not found in the dataset receive FALLBACK_ELO_QUALIFIED.
    """
    pele: dict[str, float] = elo_df.set_index("Code")["PELE"].to_dict()
    elo_map: dict[int, float] = {}
    for _, row in teams_df.iterrows():
        tid = int(row["id"])
        if bool(row["is_placeholder"]):
            elo_map[tid] = FALLBACK_ELO_PLACEHOLDER
        else:
            elo_map[tid] = float(pele.get(str(row["fifa_code"]), FALLBACK_ELO_QUALIFIED))
    return elo_map


def build_host_map(cities_df: pd.DataFrame) -> dict[int, str]:
    """Return {city_id: nation} for the three co-host countries."""
    return {
        int(row["id"]): row["country"]
        for _, row in cities_df.iterrows()
        if row["country"] in HOST_NATIONS
    }


def build_nation_map(teams_df: pd.DataFrame) -> dict[int, str]:
    """
    Return {team_id: nation_name} for USA, Mexico, and Canada only.
    A team earns home advantage only when playing in a city from their own nation.
    """
    return {
        int(row["id"]): row["team_name"]
        for _, row in teams_df.iterrows()
        if row["team_name"] in HOST_NATIONS
    }

# ---------------------------------------------------------------------------
# Group stage
# ---------------------------------------------------------------------------


def simulate_group_stage(
    matches_df: pd.DataFrame,
    elo_map: dict[int, float],
    host_map: dict[int, str],
    nation_map: dict[int, str],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Simulate all 72 group stage matches (stage_id == 1).

    Returns
    -------
    DataFrame with columns: match_number, home_id, away_id, home_goals, away_goals.
    """
    records = []
    for _, m in matches_df[matches_df["stage_id"] == 1].iterrows():
        home_id = int(m["home_team_id"])
        away_id = int(m["away_team_id"])
        city_id = int(m["city_id"])

        city_nation = host_map.get(city_id, "")
        home_is_host = city_nation != "" and nation_map.get(home_id, "") == city_nation
        away_is_host = city_nation != "" and nation_map.get(away_id, "") == city_nation

        la, lb = calculate_expected_goals(
            elo_map[home_id], elo_map[away_id],
            a_is_host=home_is_host,
            b_is_host=away_is_host,
        )
        hg, ag = simulate_match_score(la, lb, rng=rng)
        records.append({
            "match_number": int(m["match_number"]),
            "home_id":      home_id,
            "away_id":      away_id,
            "home_goals":   hg,
            "away_goals":   ag,
        })
    return pd.DataFrame(records)


def compute_group_standings(
    results_df: pd.DataFrame,
    teams_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute group standings sorted by pts → GD → GF within each group.

    Returns
    -------
    DataFrame with a rank column (1 = group winner, 4 = bottom of group).
    """
    stats: dict[int, dict[str, int]] = {
        int(t["id"]): {"pts": 0, "gf": 0, "ga": 0}
        for _, t in teams_df.iterrows()
    }

    for _, r in results_df.iterrows():
        hid, aid = int(r["home_id"]), int(r["away_id"])
        hg,  ag  = int(r["home_goals"]), int(r["away_goals"])
        stats[hid]["gf"] += hg;  stats[hid]["ga"] += ag
        stats[aid]["gf"] += ag;  stats[aid]["ga"] += hg
        if hg > ag:
            stats[hid]["pts"] += 3
        elif hg < ag:
            stats[aid]["pts"] += 3
        else:
            stats[hid]["pts"] += 1
            stats[aid]["pts"] += 1

    rows = []
    for _, t in teams_df.iterrows():
        tid = int(t["id"])
        s = stats[tid]
        rows.append({
            "team_id":      tid,
            "team_name":    t["team_name"],
            "fifa_code":    t["fifa_code"],
            "group_letter": t["group_letter"],
            "pts": s["pts"],
            "gf":  s["gf"],
            "ga":  s["ga"],
            "gd":  s["gf"] - s["ga"],
        })

    df = pd.DataFrame(rows)
    df = df.sort_values(
        ["group_letter", "pts", "gd", "gf"],
        ascending=[True, False, False, False],
    )
    df["rank"] = df.groupby("group_letter").cumcount() + 1
    return df.reset_index(drop=True)

# ---------------------------------------------------------------------------
# Qualifier selection
# ---------------------------------------------------------------------------


def get_third_place_qualifiers(standings_df: pd.DataFrame) -> list[int]:
    """Return the 8 best third-place team IDs, ranked by pts → GD → GF."""
    thirds = (
        standings_df[standings_df["rank"] == 3]
        .sort_values(["pts", "gd", "gf"], ascending=False)
    )
    return thirds.head(8)["team_id"].tolist()

# ---------------------------------------------------------------------------
# Round of 32 bracket assignment
# ---------------------------------------------------------------------------


def _team_by_rank_group(standings_df: pd.DataFrame, rank: int, group: str) -> int:
    """Look up the team_id that finished at a given rank in the given group."""
    mask = (standings_df["rank"] == rank) & (standings_df["group_letter"] == group)
    row = standings_df[mask]
    if row.empty:
        raise ValueError(f"No team found: rank={rank}, group={group}")
    return int(row.iloc[0]["team_id"])


def _match_thirds_to_fixtures(
    fixture_eligible: list[tuple[int, list[str]]],
    third_qualifiers: list[int],
    team_group: dict[int, str],
) -> dict[int, int]:
    """
    Solve the bipartite assignment of 3rd-place teams to R32 fixtures using
    DFS augmenting paths (Hopcroft-Karp lite).

    The greedy approach fails when a team needed by a later fixture is
    consumed by an earlier one; bipartite matching avoids this.

    Parameters
    ----------
    fixture_eligible : list of (match_number, eligible_group_letters)
    third_qualifiers : team_ids in ranked order (best first)
    team_group       : {team_id: group_letter} for the 8 qualifiers

    Returns
    -------
    {match_number: team_id}
    """
    n_f = len(fixture_eligible)
    n_t = len(third_qualifiers)

    # Adjacency list: fixture_idx → list of eligible team_indices
    adj: list[list[int]] = []
    for _, eligible in fixture_eligible:
        adj.append([
            t for t, tid in enumerate(third_qualifiers)
            if team_group.get(tid, "") in eligible
        ])

    match_t: list[int] = [-1] * n_t  # team_idx → fixture_idx

    def _augment(f: int, seen: list[bool]) -> bool:
        for t in adj[f]:
            if not seen[t]:
                seen[t] = True
                if match_t[t] == -1 or _augment(match_t[t], seen):
                    match_t[t] = f
                    return True
        return False

    for f in range(n_f):
        _augment(f, [False] * n_t)

    # Invert: fixture_idx → team_id
    f_to_team: dict[int, int] = {}
    for t_idx, f_idx in enumerate(match_t):
        if f_idx >= 0:
            f_to_team[f_idx] = third_qualifiers[t_idx]

    return {fixture_eligible[f_idx][0]: tid for f_idx, tid in f_to_team.items()}


def assign_r32_teams(
    standings_df: pd.DataFrame,
    third_qualifiers: list[int],
    matches_df: pd.DataFrame,
) -> dict[int, tuple[int, int]]:
    """
    Parse R32 match_label strings (e.g. "1C vs 2F", "1E vs 3ABCDF") to resolve
    the two competing team IDs for each of the 16 Round-of-32 fixtures.

    Uses bipartite matching (DFS augmenting paths) for the 8 3rd-place slots
    so that every qualifier lands in exactly one eligible fixture.

    Returns {match_number: (home_team_id, away_team_id)}.
    """
    r32 = matches_df[matches_df["stage_id"] == 2].sort_values("match_number")

    # Build group lookup for the 8 qualified 3rd-place teams
    team_group: dict[int, str] = {
        int(row["team_id"]): row["group_letter"]
        for _, row in standings_df[standings_df["team_id"].isin(third_qualifiers)].iterrows()
    }

    # Collect all fixtures that need a 3rd-place team, with their eligible groups
    third_fixtures: list[tuple[int, list[str]]] = []
    for _, m in r32.iterrows():
        label = str(m["match_label"])
        for side in label.split(" vs "):
            side = side.strip()
            if side[0] == "3":
                third_fixtures.append((int(m["match_number"]), list(side[1:])))

    # Solve the bipartite assignment once for all 3rd-place slots
    third_assignment: dict[int, int] = _match_thirds_to_fixtures(
        third_fixtures, third_qualifiers, team_group
    )

    # Build the full R32 bracket
    assignments: dict[int, tuple[int, int]] = {}
    for _, m in r32.iterrows():
        mn    = int(m["match_number"])
        sides = str(m["match_label"]).split(" vs ")
        if len(sides) != 2:
            continue

        team_ids: list[int] = []
        for side in sides:
            side = side.strip()
            rank = int(side[0])
            rest = side[1:]

            if rank in (1, 2):
                team_ids.append(_team_by_rank_group(standings_df, rank, rest))
            else:
                team_ids.append(third_assignment[mn])

        if len(team_ids) == 2:
            assignments[mn] = (team_ids[0], team_ids[1])

    return assignments

# ---------------------------------------------------------------------------
# Knockout stage simulation
# ---------------------------------------------------------------------------


def _resolve_ref(
    ref: str,
    match_winners: dict[int, int],
    match_losers: dict[int, int],
) -> int | None:
    """Resolve 'W73' (winner) or 'RU101' (runner-up / loser) to a team_id."""
    ref = ref.strip()
    if ref.startswith("RU"):
        return match_losers.get(int(ref[2:]))
    if ref.startswith("W"):
        return match_winners.get(int(ref[1:]))
    return None


def simulate_knockout_stage(
    matches_df: pd.DataFrame,
    r32_assignments: dict[int, tuple[int, int]],
    elo_map: dict[int, float],
    host_map: dict[int, str],
    nation_map: dict[int, str],
    rng: np.random.Generator,
) -> tuple[dict[int, int], dict[int, int]]:
    """
    Simulate all knockout matches (stages 2 through 7), resolving team
    references from previous match results.

    Draws after 90 minutes are decided by a 50/50 penalty coin-flip.

    Returns
    -------
    (match_winners, match_losers) — both map match_number → team_id.
    """
    # Patch a data anomaly: match 100 label incorrectly self-references "W100"
    # instead of the winner of R16 match 96.
    matches_df = matches_df.copy()
    matches_df.loc[matches_df["match_number"] == 100, "match_label"] = "W95 vs W96"

    knockout = matches_df[matches_df["stage_id"] >= 2].sort_values(
        ["stage_id", "match_number"]
    )

    match_winners: dict[int, int] = {}
    match_losers: dict[int, int] = {}

    for _, m in knockout.iterrows():
        mn      = int(m["match_number"])
        city_id = int(m["city_id"])

        # Resolve team IDs from previous results or from the R32 pre-assignment
        if mn in r32_assignments:
            home_id, away_id = r32_assignments[mn]
        else:
            sides = str(m["match_label"]).split(" vs ")
            if len(sides) != 2:
                continue
            home_id = _resolve_ref(sides[0], match_winners, match_losers)
            away_id = _resolve_ref(sides[1], match_winners, match_losers)
            if home_id is None or away_id is None:
                continue

        city_nation = host_map.get(city_id, "")
        home_is_host = city_nation != "" and nation_map.get(home_id, "") == city_nation
        away_is_host = city_nation != "" and nation_map.get(away_id, "") == city_nation

        la, lb = calculate_expected_goals(
            elo_map[home_id], elo_map[away_id],
            a_is_host=home_is_host,
            b_is_host=away_is_host,
        )
        hg, ag = simulate_match_score(la, lb, rng=rng)

        # Penalty shootout (50/50) to resolve draws in knockout rounds
        if hg == ag:
            winner_id = home_id if rng.integers(0, 2) == 0 else away_id
        elif hg > ag:
            winner_id = home_id
        else:
            winner_id = away_id

        loser_id = away_id if winner_id == home_id else home_id
        match_winners[mn] = winner_id
        match_losers[mn]  = loser_id

    return match_winners, match_losers

# ---------------------------------------------------------------------------
# Full tournament runner
# ---------------------------------------------------------------------------


def simulate_tournament(
    n: int = 1,
    seed: int | None = None,
    detailed: bool = False,
) -> "pd.DataFrame | tuple[pd.DataFrame, list]":
    """
    Run n complete tournament simulations from Group Stage through Final.

    Parameters
    ----------
    n        : Number of independent simulations to run.
    seed     : Optional RNG seed for reproducibility.
    detailed : When True, also return per-simulation knockout matchup data as a
               second element: list[list[dict]] where each inner list contains
               {stage_id, team_a_id, team_b_id} dicts for every knockout match
               played (R32/R16/QF/SF/Final; third-place playoff excluded).

    Returns
    -------
    DataFrame (detailed=False) or (DataFrame, matchups_list) (detailed=True).
    DataFrame columns: sim_id, champion_code, champion_name, finalist_code,
    third_place_code.
    """
    data = load_tournament_data()
    teams_df   = data["teams"]
    matches_df = data["matches"]

    elo_map    = build_elo_map(teams_df, data["elo"])
    host_map   = build_host_map(data["cities"])
    nation_map = build_nation_map(teams_df)

    id_to_code: dict[int, str] = teams_df.set_index("id")["fifa_code"].to_dict()
    id_to_name: dict[int, str] = teams_df.set_index("id")["team_name"].to_dict()

    if detailed:
        stage_lookup: dict[int, int] = (
            matches_df.set_index("match_number")["stage_id"].to_dict()
        )

    rng = np.random.default_rng(seed)
    records: list = []
    all_matchups: list = []

    for sim_id in range(n):
        group_results    = simulate_group_stage(matches_df, elo_map, host_map, nation_map, rng)
        standings        = compute_group_standings(group_results, teams_df)
        third_qualifiers = get_third_place_qualifiers(standings)
        r32              = assign_r32_teams(standings, third_qualifiers, matches_df)
        winners, losers  = simulate_knockout_stage(
            matches_df, r32, elo_map, host_map, nation_map, rng
        )

        champion_id = winners.get(104)   # match 104 = Final
        finalist_id = losers.get(104)
        third_id    = winners.get(103)   # match 103 = Third-place playoff

        records.append({
            "sim_id":          sim_id,
            "champion_code":   id_to_code.get(champion_id),
            "champion_name":   id_to_name.get(champion_id),
            "finalist_code":   id_to_code.get(finalist_id),
            "third_place_code": id_to_code.get(third_id),
        })

        if detailed:
            matchups = [
                {
                    "stage_id":   int(stage_lookup[mn]),
                    "team_a_id":  int(winners[mn]),
                    "team_b_id":  int(losers[mn]),
                }
                for mn in winners
                if stage_lookup.get(mn) in (2, 3, 4, 5, 7)
            ]
            all_matchups.append(matchups)

    df = pd.DataFrame(records)
    if detailed:
        return df, all_matchups
    return df

# ---------------------------------------------------------------------------
# Main demonstration
# ---------------------------------------------------------------------------


def main() -> None:
    data       = load_tournament_data()
    teams_df   = data["teams"]
    matches_df = data["matches"]
    stages_df  = data["stages"]

    elo_map    = build_elo_map(teams_df, data["elo"])
    host_map   = build_host_map(data["cities"])
    nation_map = build_nation_map(teams_df)

    id_to_code: dict[int, str] = teams_df.set_index("id")["fifa_code"].to_dict()
    id_to_name: dict[int, str] = teams_df.set_index("id")["team_name"].to_dict()
    stage_name: dict[int, str] = stages_df.set_index("id")["stage_name"].to_dict()

    # ── Single run ──────────────────────────────────────────────────────────
    print("=== Single Tournament Simulation (seed=42) ===\n")
    rng = np.random.default_rng(42)

    group_results    = simulate_group_stage(matches_df, elo_map, host_map, nation_map, rng)
    standings        = compute_group_standings(group_results, teams_df)
    third_qualifiers = get_third_place_qualifiers(standings)
    r32              = assign_r32_teams(standings, third_qualifiers, matches_df)
    winners, losers  = simulate_knockout_stage(
        matches_df, r32, elo_map, host_map, nation_map, rng
    )

    # Print group standings summary
    print("Group stage standings (top 2 per group + 3rd-place qualifiers):")
    for grp in sorted(standings["group_letter"].unique()):
        grp_rows = standings[standings["group_letter"] == grp].sort_values("rank")
        teams_str = "  ".join(
            f"{r['rank']}. {r['fifa_code']}({r['pts']}pts)"
            for _, r in grp_rows.iterrows()
        )
        print(f"  Group {grp}: {teams_str}")

    # Print knockout bracket
    ko_matches = (
        matches_df[matches_df["stage_id"] >= 2]
        .sort_values(["stage_id", "match_number"])
    )
    current_stage_id = None
    for _, m in ko_matches.iterrows():
        mn  = int(m["match_number"])
        sid = int(m["stage_id"])
        if sid != current_stage_id:
            print(f"\n--- {stage_name.get(sid, '')} ---")
            current_stage_id = sid
        winner_id = winners.get(mn)
        loser_id  = losers.get(mn)
        if winner_id and loser_id:
            w = id_to_code.get(winner_id, "???")
            l = id_to_code.get(loser_id,  "???")
            print(f"  Match {mn:3d}: {w:3s} def. {l}")

    champ_id = winners.get(104)
    print(f"\n{'='*44}")
    print(f"  Champion: {id_to_name.get(champ_id, '?')}  ({id_to_code.get(champ_id, '?')})")
    print(f"{'='*44}")

    # ── Monte Carlo win probabilities ───────────────────────────────────────
    print("\n\n=== Win Probability — 10 Simulations ===\n")
    sims = simulate_tournament(n=10, seed=0)

    win_pct = (
        sims["champion_code"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
        .rename("win %")
    )
    final_pct = (
        sims[sims["finalist_code"].notna()]["finalist_code"]
        .value_counts(normalize=True)
        .mul(100)
        .round(2)
        .rename("final %")
    )
    summary = (
        pd.concat([win_pct, final_pct], axis=1)
        .fillna(0.0)
        .sort_values("win %", ascending=False)
        .head(15)
    )
    print(summary.to_string())


if __name__ == "__main__":
    main()
