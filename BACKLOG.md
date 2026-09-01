# WRPI — backlog

Ordered roughly by priority within each group. "Test before implement" = build it on
a branch / offline and only ship if the leave-one-class-out CV improves.

## Priority

- **Compare mode** — select 2–4 players, side-by-side profile table + radar chart.
  Multi-way extension of the head-to-head tool ("I have picks 1.03 and 1.07, rank
  these 5"). Bigger UI lift.
- **Scheme / pace adjustment for college production** — normalise dominator & raw
  yards by team pass volume / pass-rate-over-expected (CFBD). Removes Air-Raid
  inflation. *Test before implement.*

## Data / model (bigger swings)

- **PFF College** (~$40/mo) — YPRR, contested-catch %, separation, drop rate, PFF
  grade, slot rate. Highest ceiling for real predictive gain; my CFBD PPA proxy is
  still a top-3 signal. Held for cost.
- **Curated "available targets / air yards" opportunity** — the mechanical version
  (Y-1 team targets minus returning-roster players) was BACKTESTED 2026-09 and did
  NOT improve the model (delta -0.001; only `vac_ay` had a weak +0.16 partial vs
  pick). A proper analyst projection (4for4-style) might, but no free historical
  source found. Revisit if a historical dataset surfaces or we replicate the
  methodology with FA/cuts/retirement transactions.

## Board features

- **My board** — drag-reorder, notes, mark players, saved to browser localStorage.
- **Risers & fallers** — each spring, delta from the previous data scrape
  ("who moved after the combine"). Depends on auto-update.
- **Dominator trajectory sparkline** in each card (year-by-year college share).
  Low priority.

## Infrastructure

- **Auto-update CI** — rebuild `update.yml` for the v2 pipeline so the board
  refreshes itself. Held until the model/feature set is settled.

## Done (recent)

- 2025 NFL season added; refit on complete outcomes through 2025
- data audit + fixes (ages, draft picks, dominator artifacts, name-join errors)
- diamond-in-the-rough index + ◆ flag
- star-potential ★ flag (95th pctl)
- low-confidence ⚠ flag
- head-to-head tiebreaker tool + score
- profile similarity / closest comps (body-type weighted)
- mobile card layout
- "How it works" tab with calibration table
- sort by raw WRPI score
