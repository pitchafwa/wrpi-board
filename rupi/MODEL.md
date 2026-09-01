# RUPI v1 — model card (running back prospect indicator)

Companion to RESEARCH.md. Fills in once fits land.

## Pool & target
- Pool: every drafted RB 2015-2026 (245) + UDFA supplement (44 undrafted RBs with
  >=80 career NFL touches, joined by gsis_id to dodge namesake collisions). 289 total.
- Fit window: 2015-2023 classes (win3_full = 1, i.e. 3 mature NFL seasons). ~183
  drafted with college data.
- Reference percentile pool: 2015-2020 classes.
- Target `rb_top34` = mean of a back's best 2 PPR-PPG seasons within NFL years 1-3.
  Front-loaded for RB shelf life (peak age ~24.8, cliff ~27). Verified not fragile
  vs `rb_top44` (best 3 of yrs 1-4), `rb_early3` (total pts yrs 1-3), `rb_best`.

## Data-quality fixes made along the way
- Rebuilt `cfbd_ppa` / `cfbd_usage` / `cfbd_recruiting` from cached raw JSON — the
  wrpi-board copies were silently truncated (~40% of rows missing, incl. Saquon
  Barkley and most RBs entirely). **The live WRPI pipeline may be affected too —
  worth a re-audit.** (rebuild_ppa_usage.py)
- RB scrimmage dominator (rush+rec yards & TDs), reliability-masked at
  team_scrim_yds >= 2500, capped 0.70 (small-school partial team-seasons inflate
  it past 1.0 otherwise — same class of bug WRPI's audit caught).
- Entry age from PFR draft-day age (audited integer field) primary; birthdate
  fallback with an 18-27 sanity gate.

## Pre-draft RUPI  (talent read, no draft capital)
- **in-sample 0.565, LOCO-CV 0.426** (Spearman). Honestly modest — and that's the
  correct answer for RB: the position is opportunity-gated, so a pure pre-NFL
  talent read has a low ceiling (pre-draft WRPI was 0.50; RB lands lower by
  design, not by error). High fold variance (0.11 the 2019 class, 0.69 the 2021).
  Middle of the range is compressed (cap saturation) — treat pre-draft RUPI as a
  coarse talent tier, not a precise rank.
- Component weights (v1.1, after tightening bounds to kill spike-overfit terms):
  - College dominator .... min(27.8*share, 3.2)      [scrimmage share]
  - Receiving role ....... min(48.9*rec_yd_share, 2.9)   <-- RB-specific, ~equal to dominator
  - Athletic explosion ... min(19.9*pctl, 2.3)
  - NFL entry age ........ min(1.4*(24.5-age), 2.2)
  - Production volume .... min(7.7*(best_scrim_yds/1000), 1.4)
  - Efficiency (YPC/PPA) . min(0.6*(z+2), 1.5)       [deliberately small — weak signal]
  - Breakout age ......... min(0.3*(19.9-age), 3.3)
- Surfaces real "market missed him" talent: Kareem Hunt (pre 1.00, pick 86,
  outcome pctl .97), Michael Carter, Jonathan Taylor, Nick Chubb, James Conner
  (pre .95, pick 105, .94). Also over-rates a few small-school UDFAs (Josh Adams,
  Jaret Patterson) — the pre-model's built-in noise.

## Post-draft RUPI  (topline — use this one)
- **in-sample 0.737, LOCO-CV 0.714** vs **draft pick alone 0.682**. Beats capital
  by a hair and is stable across folds (.57–.84). This is the number for
  post-NFL-draft dynasty rookie drafts.
- Component weights (v1):
  - Draft capital ... min(3743*(pick+15.1)^-1.17, 55.0)
    pick 1–20 -> 55.0 (saturated) · 32 -> 41 · 50 -> 28 · 75 -> 19 · 100 -> 15 ·
    150 -> 10 · 260 -> 5.  (More top-heavy than WRPI's WR curve — R1 RB ≈ locked-in
    volume.)
  - Receiving role ...... min(76.9*rec_yd_share, 6.2)   <-- biggest non-capital term
  - Efficiency (YPC/PPA)  min(2.1*(z+2), 6.1)
  - College dominator ... min(3.2*share, 19.3)
  - Athletic explosion .. min(27.1*pctl, 2.7)
  - Breakout age ........ min(8.4*(18.9-age), 4.4)
  - NFL entry age ....... min(1.0*(24.2-age), 1.3)
  - Production volume ... min(12.7*(scrim/1000), 1.9)  (saturates -> ~constant)
- Target robustness: the fitted scores correlate ~identically (pre .56 / post .74)
  with rb_top34, rb_top44, rb_early3, rb_best, and raw best-season PPG. Not fragile
  to the target definition.
- Historical top-15 (post): Barkley, Gibbs, Bijan, CMC, Zeke, Gordon, Fournette,
  Jacobs, Etienne, Najee, Penny, Michel, Chubb, Breece, CEH. Clean face validity.

## Star flag
- **90th percentile** of the score being viewed (pre or post). Calibration decile
  table: post-draft decile 10 (pctl >= .90) hit-rate **0.73** vs decile 9's 0.39;
  pre-draft 0.57 vs 0.38. RB has fewer elite fantasy seasons than WR, so 0.90
  (not WRPI's 0.95) is where the league-winner signal turns on.
- 25 pre-draft stars, 29 post-draft, across the 271-player board.

## Diamond-in-the-rough flag  (DONE)
- Pool: pick >= 33 (everyone outside round 1) + UDFA. CUT swept {33..100}; 33 won
  (LOCO lift 2.2x @P5 vs 1.3-1.7x). Day-1 RBs already hit ~71% on capital alone,
  so the diamond question for RB is "who among R2+ still hits."
- Hit = best season PPG >= 13 (yrs 1-4) OR best-2-of-3 avg >= 11.
- n=208, base rate 24.5%, 51 hits.
- LOCO-CV precision@3/5/10 = 0.59 / 0.53 / 0.37 ; lift@5 = 2.2x.
- Quartile hit rates: 5.8% / 11.5% / 34.6% / 46.2%.
- Index weights (share): early_declare .18, career_ypc .14, td_rate .14,
  best_rush_share .12, explosion_p .09, best_dom .08, avg_ppa .07, best_ppa_rush
  .05, n_seasons_15 .05, best_usage .05, entry_age .02, agility .01.
- Catches Kamara, Hunt, D.Johnson, A.Jones, J.Robinson, Lindsay, Kyren Williams,
  Achane, Howard, Gibson, Conner (idx pctls 50-100%); misses Chris Carson (20%).
