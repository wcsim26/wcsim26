"""
run_simulations.py
------------------
Runs Monte Carlo tournament simulations and saves raw results to
sim_results.json. Run this once (or whenever you want fresh numbers);
then run generate_results.py to rebuild index.html without re-simulating.

Usage:
    venv/bin/python run_simulations.py
"""

import json
from pathlib import Path

from tournament_simulator import simulate_tournament

N = 1000
SEED = 0
OUT = Path(__file__).parent / "sim_results.json"


def main():
    print(f"Running {N} simulations (seed={SEED})…", flush=True)
    results = simulate_tournament(n=N, seed=SEED)

    payload = {
        "n_simulations": N,
        "seed": SEED,
        "runs": results.to_dict(orient="records"),
    }

    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({N} runs)")

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
