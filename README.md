# 2026 World Cup Simulator

Simulates FIFA 2026 World Cup matches and full tournaments using the **Elo-Difference Poisson Model**.

## Model

Expected goals for each team are derived from the difference in Elo ratings:

```
λ_A = exp(α + β × (Elo_A − Elo_B))
λ_B = exp(α + β × (Elo_B − Elo_A))
```

| Constant | Value | Meaning |
|---|---|---|
| `α` (alpha) | 0.26 | ln(1.3) — baseline ~1.3 goals/team |
| `β` (beta) | 0.003 | Elo scaling factor |
| Home advantage | +100 Elo | Applied per city: USA teams in USA venues, Mexico in Mexico, Canada in Canada |

Goals are drawn independently from Poisson distributions. Knockout draws are resolved by a 50/50 penalty coin-flip.

## Modules

### `wc26_simulation.py` — core model primitives

```python
from wc26_simulation import calculate_expected_goals, get_match_probabilities, simulate_match_score
import numpy as np

lambda_a, lambda_b = calculate_expected_goals(
    team_a_elo=2100,  # France
    team_b_elo=1800,  # USA
    b_is_host=True,
)

probs = get_match_probabilities(lambda_a, lambda_b)
# {'win_a': 0.742, 'draw': 0.163, 'win_b': 0.094}

rng = np.random.default_rng(42)
score = simulate_match_score(lambda_a, lambda_b, rng=rng)
# (4, 3)
```

Run the built-in demo:

```bash
venv/bin/python wc26_simulation.py
```

### `tournament_simulator.py` — full tournament runner

Loads real fixture data and PELE Elo ratings from `data/`, then simulates the complete 104-match tournament: Group Stage → Round of 32 → Round of 16 → Quarterfinals → Semifinals → Final.

```python
from tournament_simulator import simulate_tournament

# Single run, reproducible
results = simulate_tournament(n=1, seed=42)
print(results[["champion_name", "finalist_code", "third_place_code"]])

# Monte Carlo win probabilities
results = simulate_tournament(n=1000, seed=0)
print(results["champion_code"].value_counts(normalize=True).mul(100).round(1))
```

Run the built-in demo (single bracket + 10-sim probability table):

```bash
venv/bin/python tournament_simulator.py
```

### `run_simulations.py` — run and save simulation results

Runs 1 000 Monte Carlo simulations and saves raw per-run results to
`sim_results.json`, including per-team per-round opponent probability data
used by the flow diagram. Run this once, or whenever you want fresh numbers.

```bash
venv/bin/python run_simulations.py
```

### `generate_results.py` — static results webpage

Reads `sim_results.json` and writes a self-contained `index.html`. No server
required — open directly in a browser.

```bash
venv/bin/python generate_results.py
open index.html          # or double-click in Finder / Explorer
```

The page has two views:

**Probability table** — all 48 teams ranked by win probability with sortable
columns (Win %, Finalist %, Top 3 %) and a filter box.

**Team flow diagram** — click any team name to see a stage-by-stage flow
diagram of their tournament path. Group opponents are shown at 100%; each
knockout round shows all possible opponents with bezier curve thickness
proportional to the probability of facing them. Each opponent box includes a small segmented bar showing head-to-head
probabilities computed analytically from Elo ratings (neutral ground): group
stage boxes show win (green) / draw (gray) / loss (red); knockout boxes show
only win / loss with the draw probability folded 50/50 into each side
(reflecting the penalty shootout tiebreaker). Click any opponent in the
diagram to switch to that team's view.

## Data files (`data/`)

| File | Contents |
|---|---|
| `teams.csv` | 48 qualified teams with FIFA codes and group assignments |
| `matches.csv` | Full 104-match schedule with stage, city, and opponent labels |
| `host_cities.csv` | 16 venues across USA, Mexico, and Canada |
| `tournament_stages.csv` | Stage names (Group Stage through Final) |
| `data-4oVop.csv` | PELE Elo ratings for ~200 nations, current and historical |

## API — `wc26_simulation.py`

### `calculate_expected_goals(team_a_elo, team_b_elo, a_is_host, b_is_host) -> (λ_a, λ_b)`

Returns expected goals after applying any home advantage.

### `get_match_probabilities(lambda_a, lambda_b, max_goals=10) -> dict`

Returns `{"win_a": float, "draw": float, "win_b": float}` via a vectorised Poisson scoreline matrix (`numpy.tril` / `numpy.trace` / `numpy.triu` — no loops).

### `simulate_match_score(lambda_a, lambda_b, rng=None) -> (goals_a, goals_b)`

Draws a random scoreline. Pass `np.random.default_rng(seed)` for reproducibility.

## API — `tournament_simulator.py`

### `simulate_tournament(n, seed) -> pd.DataFrame`

Runs `n` full simulations. Returns one row per run: `sim_id`, `champion_code`, `champion_name`, `finalist_code`, `third_place_code`.

### `load_tournament_data() -> dict[str, pd.DataFrame]`

Loads all CSVs from `data/`.

### `build_elo_map(teams_df, elo_df) -> dict[int, float]`

Maps team ID → current PELE Elo. Falls back to 1750 for unresolved playoff slots and 1650 for any qualifier absent from the ratings file.

## Requirements

```
numpy
scipy
pandas
```

```bash
venv/bin/pip install numpy scipy pandas
```
