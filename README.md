# 2026 World Cup Match Simulator

Simulates FIFA 2026 World Cup match outcomes using the **Elo-Difference Poisson Model**.

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
| Home advantage | +100 Elo | Applied to host nations: USA, Mexico, Canada |

Goals for each team are drawn independently from Poisson distributions with the computed λ values.

## Usage

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

## API

### `calculate_expected_goals(team_a_elo, team_b_elo, a_is_host, b_is_host) -> (λ_a, λ_b)`

Returns expected goals for each team after applying any home advantage.

### `get_match_probabilities(lambda_a, lambda_b, max_goals=10) -> dict`

Returns `{"win_a": float, "draw": float, "win_b": float}` by building a Poisson scoreline probability matrix and summing via `numpy.tril`, `numpy.trace`, and `numpy.triu` (no loops).

### `simulate_match_score(lambda_a, lambda_b, rng=None) -> (goals_a, goals_b)`

Draws a random scoreline. Pass `np.random.default_rng(seed)` for reproducible results.

### `build_teams_dataframe() -> pd.DataFrame`

Returns a sample DataFrame with columns `team`, `elo`, `is_host`.

## Requirements

```
numpy
scipy
pandas
```

Install into the project venv:

```bash
venv/bin/pip install numpy scipy pandas
```
