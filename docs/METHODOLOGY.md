# Methodology 方法论

## 1. One number: single-game win probability `p`

Every prediction starts from the probability that a side wins **one game/map**. It comes from a logistic rating comparison:

```
p = 1 / (1 + 10^(-(R_a - R_b + side_adv) / scale))
```

- `R_a`, `R_b` — the two sides' strengths.
- `side_adv` — first-pick / blue-side / radiant advantage where it exists (else 0).
- `scale` — 400 (a 400-point gap ≈ 10× odds).
- an optional `shrink` pulls probabilities toward 0.5 to fix over-confidence.

## 2. Ratings (the engine)

Online Elo, updated game by game. A side is a **list of entities** plus a team id, so one engine covers three modes by config:

- **team-only** (`w = 1`, entity = the team) — CS2, Dota 2, R6, Overwatch, KoG, MLBB, CoD, Valorant.
- **player + team blend** (`w = 0.7`) — LoL: strength = 0.7 · mean(player ratings) + 0.3 · team rating, so roster changes move strength by the delta of the swapped players.
- **1v1** (entity = the player) — StarCraft II & Brood War.

New entities get a higher provisional K until they have enough games; ratings mean-revert across seasons.

## 3. Series math → 4 markets

Given `p` and the best-of `N`, the whole series distribution is a negative-binomial expansion. From it:

- **Series winner** — sum of all scorelines the side wins.
- **First game/map** — `p` itself.
- **Handicap** (−1.5 etc.) — probability the map/game margin exceeds the line.
- **Total maps/games** over/under — the distribution over series length.

This layer is title-agnostic and lives in `core/series.py`.

## 4. Validation (walk-forward)

We never score a match the model has already trained on. We sort games by time, warm ratings on the earlier portion, then predict each later game **before** updating on it. We report:

- **Accuracy** — hit rate of the favourite.
- **Brier** and **LogLoss** — probability quality (lower is better; 0.25 / 0.693 = coin flip).
- a **calibration table** — do "70% predictions" win ~70% of the time?

Series-winner accuracy is naturally higher than single-game, because a best-of series amplifies the stronger side.

## 5. Honest limits

- Accuracy is bounded by each title's intrinsic variance; ~55–75% pre-match is the realistic band. Numbers above ~85% in the literature almost always leak in-game information — this framework is strictly **pre-match**.
- The model uses ratings only. Draft/ban, patch/meta, map pool and roster news are not yet modelled (documented next steps).
- Snapshots are as fresh as the last data pull; a scheduled refresh keeps them current.

> Predictions are pre-match statistical estimates and do not constitute betting or investment advice.
