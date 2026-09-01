# WRPI — Wide Receiver Prospect Indicator

A production-and-age model for NFL wide receiver draft prospects, **reverse-engineered
from the 2010–2022 "Prospect Success Indicator"** percentile database, then re-fit and
frozen on 2014–2022.

**Board:** https://pitchafwa.github.io/wrpi-board/

## What it does

Each prospect earns points across six inputs, then the raw total is era-detrended and
ranked against a frozen 2014–2022 reference class to give a percentile and decile tier.

| Input | Shape | ~share of pre-draft score |
|---|---|---|
| NFL entry age | ramp, ~8 pts per year under 24 (cap 28) | ~30% |
| Alpha WR (college team's #1 by yards) | 16 / 0 | ~17% |
| Weighted dominator (best college season) | 35%+ = 15, 20–35% = 9, <20% = 0 | ~16% |
| Breakout age | ramp, 8 × (22 − age), cap 11 | ~12% |
| SWRM combine hits | ~1.4 pts per drill passed, 0–8 | ~10% |
| Bench press ≥ 10 reps | 2 / 0 | ~3% |
| **Draft capital** (post-draft only) | log curve on pick, cap ~40 | ~⅓ of post-draft |

**SWRM is scored conservatively:** a drill a prospect *didn't run* counts as a miss,
because prospects skip drills they expect to test poorly in. The **what-if ceiling**
flips this (every skipped drill = pass) to bound the optimistic case.

Fit quality (5-fold CV on 2014–2022): Spearman **0.86 pre-draft / 0.91 post-draft**.
Reproduces the original PSI ranking at **0.91** on 326 held-out historical players.

## Repo layout

```
wrpi_score.py            frozen scoring function (single source of truth)
data/wrpi_params_*.json   fitted point values
data/wrpi_reference.json  frozen reference distribution + drift-monitor baseline
data/historical_2015_2022.csv   pre-scored historical feature table
data/wrpi_database.csv    full scored board 2015–2025  (regenerated each run)
dashboard/                the board (static site + scores.json)

fetch_sources.py    pull nflverse + array-carpenter feeds
build_cfbd.py       (re)build college production from CollegeFootballData
build_pool.py       assemble the current prospect pool
score.py            featurize + score + write dashboard/scores.json
wrpi_refit.py       re-fit the model (only if you deliberately want to move it)
```

## Running locally

```bash
pip install -r requirements.txt
export CFBD_KEY=...        # free: https://collegefootballdata.com/key
python fetch_sources.py && python build_cfbd.py && python build_pool.py && python score.py
python -m http.server -d dashboard 4177   # open http://localhost:4177
```

## Auto-update

`.github/workflows/update.yml` runs weekly (and on demand): refreshes every feed,
rescoring the whole board and redeploying Pages. Needs a repo secret **`CFBD_KEY`**.

## Caveats

- The model has no route-running / separation / hands input — it's production + age +
  athletic-testing only. Elite producers with scouting red flags will still score high.
- ~40 Division II / NAIA prospects a year fall out of CollegeFootballData and are
  **flagged, not scored**.
- The −0.69 pts/year era detrend is an assumption; the drift monitor on the board
  flags if a new class drifts out of the expected band.

Data: [nflverse](https://github.com/nflverse/nflverse-data) ·
[array-carpenter/nfl-draft-data](https://github.com/array-carpenter/nfl-draft-data) ·
[CollegeFootballData](https://collegefootballdata.com)
