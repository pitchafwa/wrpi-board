# WRPI — backlog

Ordered roughly by priority within each group. "Test before implement" = build it on
a branch / offline and only ship if the leave-one-class-out CV improves.

## Priority

- **Scheme / pace adjustment for college production** — normalise dominator & raw
  yards by team pass volume / pass-rate-over-expected (CFBD). Removes Air-Raid
  inflation. *Test before implement.* (test in progress 2026-09-02)

## Data / model (bigger swings)

- **PFF College** (~$40/mo) — **for BOTH WRPI and RUPI, grab in one pass.**
  - WR: YPRR, contested-catch %, separation, drop rate, PFF grade, slot rate.
    Highest ceiling for real predictive gain; the CFBD PPA proxy is still a top-3
    signal.
  - RB: missed tackles forced / attempt, yards after contact / attempt, elusive
    rating, PFF rushing/receiving grade, YPRR, performance vs stacked boxes.
    PFF's own RB model leans hardest on MTF/att (bottom-15th-pct MTF → 1 of 56
    hit top-12). RUPI currently proxies this with CFBD PPA + YPC only.
  - Plan: one subscription month, pull both position histories, re-fit both
    models, ship only the components whose LOCO-CV improves. Held for cost.
- **Curated "available targets / air yards" opportunity** — the mechanical version
  (Y-1 team targets minus returning-roster players) was BACKTESTED 2026-09 and did
  NOT improve the model (delta -0.001; only `vac_ay` had a weak +0.16 partial vs
  pick). A proper analyst projection (4for4-style) might, but no free historical
  source found. Revisit if a historical dataset surfaces or we replicate the
  methodology with FA/cuts/retirement transactions.
- **Consensus big board / "beat the board"** — BACKTESTED 2026-09, NEGATIVE.
  ESPN pre-draft board (grade + overall rank, 2015-2021, n=193) as a proxy for
  analyst consensus. Board rank alone (Spearman +0.50) is a weaker anchor than the
  actual draft pick (+0.61); the reach residual `pick - board_rank` has partial
  corr -0.03 vs outcome; adding board rank/grade/reach to the pick-anchored
  residual moves CV by +0.001. Structural, not a data issue — the real draft
  already contains the board plus private team info. Don't ship. Revisit only if a
  true multi-analyst consensus surfaces AND we find a pre-draft (picks-unknown) use
  for it.

## Coverage gaps

- **Small-school / non-FBS players** — CFBD only reliably covers FBS (+ partial
  FCS). Players from D-II / NAIA / small FCS get `has_college = 0` and land in the
  low-confidence bucket: WR examples from the original PSI work, RB examples incl.
  **Austin Ekeler** (Western State, D-II), Chris Brooks, Jeff Wilson. **Action:**
  research a fill source when this item is picked up — candidates to evaluate:
  Sports Reference / Stathead college pages, School-specific stats crawls,
  NCAA D-II/D-III stat archives, `cfbfastR` FCS coverage, Wikipedia infoboxes as a
  last resort. Need per-season rushing/receiving + team totals to compute
  dominator; even partial (career totals only) would beat a blank profile.

## Board features

- **Compare mode** — select 2–4 players, side-by-side profile table + radar chart.
  Replaces the head-to-head tool. (build in progress 2026-09-02)
- **My board** — drag-reorder, notes, mark players, saved to browser localStorage.
- **Risers & fallers** — each spring, delta from the previous data scrape
  ("who moved after the combine"). Now buildable (auto-update exists).
- **Dominator trajectory sparkline** in each card (year-by-year college share).
  Low priority.

## RUPI-specific

- **Head-to-head tiebreaker for RB** — logistic-on-feature-diffs for RBs drafted
  within ~20 picks, same as WRPI's tool. If compare mode replaces H2H, this may
  be moot — revisit after compare mode ships.

## Done (recent)

- **CFBD data audit (WRPI)** — 2026-09-02. The truncated `cfbd_ppa/usage/
  recruiting.csv` (PPA/usage -43% of rows, recruiting -75%) were RB-critical
  (Barkley + most RBs gone) but **negligible for WRPI**: the `athleteId`-scoped
  joins were mostly intact for WRs; fill rates barely move (final_ppa 98→98%,
  recruit_stars 83→85% on the mature pool), LOCO-apply CV identical to 3dp,
  `wrpi_post` byte-identical. Switched WRPI to `data/cfbd_*_full.csv` anyway
  (strictly more correct, free) — `rebuild_ppa_usage.py` now runs in the shared
  pipeline section for both models. No refit.
- **Auto-update CI** — `update.yml` (self-scheduling) + `refit-review.yml` +
  deploy chain, verified end to end 2026-09-01.
- **RUPI** — model built, renamed from RBPI, RB tab live, similarity comps,
  provisional banner, prospective-UDFA, wired into the pipeline.

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
