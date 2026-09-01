# RUPI — research & design (Running Back Prospect Indicator)

Analog to WRPI. Goal: predict dynasty-fantasy production for RB prospects, pre- and
post-draft, plus star + diamond flags. This doc = the research phase + the design
decisions before building.

## 1. What predicts RB fantasy success (literature synthesis)

Ranked roughly by consensus strength:

1. **Draft capital** — even more dominant than for WR. R1 RBs finish top-24 as
   rookies ~71% of the time; Day-3 RBs ~1%. RB fantasy = volume, and volume
   follows draft investment almost mechanically. This will anchor the post-draft
   score, same as WRPI.
2. **College Dominator (scrimmage)** — share of team yards + TDs, rushing AND
   receiving. #2 signal after draft capital. "Breakout" ≈ 15%+ scrimmage
   dominator (lower bar than WR's ~20% because RB shares a room and defenses
   stack the box).
3. **Breakout age / age at draft** — RBs break out YOUNG. Backs with 15+ FPPG
   since 2017 averaged a 19.5 breakout age; only 5 of 67 broke out at 22+.
   Younger entry = more prime NFL years before the cliff. Bigger effect than for
   WR.
4. **College receiving profile** — target/reception share, receiving-yard share.
   ~10% target share is the cited threshold. The elite receiving-back college
   profile (multiple 10%+ receiving-yard-share seasons) is a strong ceiling
   signal: Bush, CMC, Barkley, Gibbs, Bijan. Receiving backs see the field
   faster and have PPR floors + ceilings. This is a **bigger deal for PPR
   dynasty than for WR modeling**.
5. **Speed Score** = weight × 200 / forty⁴ (Barnwell). Weight-adjusted 40;
   avg ~100, useful range 85–110. More predictive than raw 40 for RBs — rewards
   big backs who run fast.
6. **Explosion / burst** — broad jump + vertical. 27 of 34 combine-tested RB1s
   had good-to-elite broad jumps. Lower-body explosion is the athletic trait
   that translates. Agility (short shuttle, 3-cone) second.
7. **Size / weight** — workhorse early-down role historically wants ~210+ lbs,
   but the league is trending toward committees and receiving roles, so weight
   is a soft signal, not a gate. BMI as a build proxy.
8. **RAS** (composite athletic score) — positive correlation with RB fantasy
   points; useful as a tiebreaker, weaker than draft capital/production.
9. **Level of competition** — P5 vs G5, SP+ of college team / schedule.
10. **College efficiency (YPC, PPA/EPA-per-play)** — WEAK and noisy. YPC ~6.0 is
    cited as a "threshold" but efficiency translates poorly; treat as minor.
11. **College workload / career touches** — the "tread on the tires" idea. Best
    academic study (Carter et al., n=103) found **no** relationship between
    college carry volume and NFL injury rate or YPC; high-carry backs were
    slightly *more* durable early. So: not a bust signal by itself. Career
    touches matter for the *aging curve* (~2,250–2,500 combined touches = decline
    point), which is a longevity concern, not a rookie-projection input.
12. **RYOE / rushing over expected vs stacked boxes** — Koalaty-style. Needs
    college play-by-play + box counts; a real signal but heavy to build and not
    free at the college level. Backlog.
13. **Elusiveness — missed tackles forced/att, yards after contact** — strong in
    PFF's model (bottom-15th-pct MTF ⇒ 1 of 56 hit top-12) but **PFF-College
    only, not free**. This is RUPI's analog to WRPI's "no separation data" gap.
    Proxy pre-draft with PPA-per-play + explosive-run rate if buildable.

## 2. Dynasty RB valuation — how RBs differ from WRs

- **Shelf life is short and early.** Peak fantasy age ≈ 24.8 and falling; sharp
  cliff around 27–28. Rule-of-thumb dynasty advice: sell Day-2 RBs after their
  age-23 season, Day-1 RBs after age-24.
- **Immediate production.** Unlike WRs (who often need year 2–3), RBs pay off as
  rookies. In dynasty, a hit rookie RB is frequently the single most valuable
  asset in a rookie draft class even though the *market* now drafts rookie WRs
  higher (positional devaluation ≠ per-player fantasy value).
- **Opportunity dependence.** RB fantasy points ≈ f(touches, TD share, pass-game
  role), which is set by team situation as much as talent. Snaps/touches correlate
  with fantasy better than efficiency does; ~58% of RB fantasy points come from
  receptions + green-zone touches (< 25% of touches). Consequence: a pure "talent"
  (pre-draft) model has a **lower ceiling** for RB than WR, and **landing
  spot/opportunity matters more** post-draft.
- **Modeling implications:**
  - Target should be **front-loaded** — reward early production, don't wait for a
    5-year window. Use years 1–3 (or 1–4) rather than WRPI's best-3-of-5.
  - The pre-draft score is explicitly a *talent/archetype* read; expect its CV
    ceiling to be lower than pre-draft WRPI (~0.50). That's fine and honest.
  - The **diamond (late-round hit) flag matters more for RB** — the league pushes
    real talent to Day 3, and injuries open paths (James Robinson, Jordan Howard,
    Aaron Jones, Kareem Hunt, Isiah Pacheco, Chris Carson, Tyler Allgeier,
    Jaylen Warren, Elijah Mitchell). Worth engineering carefully.
  - **Age belongs in the pre-draft score with a steeper penalty** than WRPI.

## 3. Success metric (target) — proposal

Fantasy = **PPR points per game** (0.5 also computed for sensitivity). Per season,
require ≥ 6 games played to count a season (same as WRPI's practical cut).

**Primary target `rb_top34`** = mean of a player's **best 2 PPR-PPG seasons within
NFL years 1–3**. Rationale: matches RB shelf life, matches how the literature
(PFF, Koalaty) frames it, and rewards a high early peak — which is what wins
dynasty.

**Secondary targets (for sensitivity / model-selection):**
- `rb_top44` = best 3 of years 1–4 PPG (a little more forgiving of a slow rookie
  year for backs behind a vet).
- `rb_early3` = total PPR points, years 1–3 (volume-flavored).
- `rb_best` = single best PPG season, years 1–4 (ceiling).

I'll fit to `rb_top34`, then confirm the chosen model isn't fragile across the
others (WRPI lesson: optimize one, verify on the family).

Maturity: a class needs 3 NFL seasons to score `rb_top34`. With 2025 data loaded,
**2015–2022 draft classes** are fully mature (2022 → 2022-24 seasons). Use
**2015–2022 to fit**, 2015–2020 as the percentile reference pool, score
2015–2026 for the board.

## 4. Model form — mirrors WRPI v2

Interpretable additive model: component ramps/bands + a power-law draft-capital
curve, fit with `differential_evolution`, objective = mean LOCO (leave-one-class-
out) Spearman. Windows guard (`__main__` + workers=1) — WRPI lesson.

- **Pre-draft RUPI** (talent read, no draft capital): scrimmage dominator,
  breakout age, entry age, receiving-role score (rec-yd share / rec share),
  athletic explosion (speed score + burst), production volume (best scrimmage
  yds), competition (SP+/P5). Age penalties steeper than WRPI.
- **Post-draft RUPI** (topline): draft-capital power-law curve + a small
  college/receiving efficiency term, tuned to roughly tie draft capital alone —
  same philosophy Tommy chose for WRPI. Report the weights, set as topline.
- **Star flag** — empirically pick the RUPI percentile where genuine league-winner
  signal kicks in (WRPI used 95th; will re-derive for RB — likely similar or a
  touch lower given fewer elite RB seasons).
- **Diamond flag** — heavily-regularized weighted index over indicators for RBs
  drafted after ~pick 90–100 (Day 3+), hit = early PPG ≥ ~14 or a sustained
  role. Expect receiving profile, breakout age, dominator, athletic explosion,
  early declare, and college scrimmage volume to carry it.
- **Head-to-head tiebreaker** — same logistic-on-feature-diffs approach for RBs
  drafted within ~20 picks. Optional this round; will build if time permits.

## 5. Data — what's accessible (reuse WRPI pipeline)

Have already (wrpi-board/data): CFBD raw season stats (rushing + receiving,
2004–2026), `cfbd_ppa.csv`, `cfbd_usage.csv`, `cfbd_recruiting.csv`, `cfbd_sp.csv`,
`combine.csv`, `draft_picks.csv` (has **age at draft** for all 245 RBs
2015–2026), `players.csv` (birthdates), `nfl_weekly.csv` (RB fantasy, 1999–2025),
`nfl_advstats_rec.csv` + PFR rush advstats available from nflverse.

Need to add:
- Re-derive CFBD season table keeping **rush attempts / YPC / long** and an
  **RB scrimmage dominator** (rush+rec yd share, rush+rec TD share). Raw JSON is
  cached — no new API calls.
- **Breakout age** = age during first college season with scrimmage dominator ≥
  0.15 (fallbacks if never).
- **Speed score / burst / agility / RAS / BMI** from combine (+ pro-day fallback).
- NFL rushing advanced stats (YBC/att, YAC/att, broken tackles) — post-draft
  context only, optional.

Not accessible free (document as limitation, same as WRPI): PFF-College
elusiveness (MTF/att, YAC over expected, YPRR), college RYOE vs box count,
true college target data pre-2014.

## 6. Judgment calls being made (proceeding unless redirected)

1. **Target = best-2-of-years-1-3 PPR PPG** (`rb_top34`). Front-loaded for RB
   shelf life. Verifying against 3 secondary targets.
2. **Fit window 2015–2022; reference pool 2015–2020; board 2015–2026.**
3. **Age gets a steeper pre-draft penalty than WRPI**, and breakout age is a
   first-class input (not a near-zero term like it landed for WR).
4. **Diamond pool cut ≈ pick ≥ 90** (Day 3-ish), vs WRPI's 50 — because RB draft
   capital runs later and the Day-3 RB hit is the whole point.
5. **No college play-by-play build in v1** (RYOE, explosive rate). Backlog it;
   add only if the pre-draft model is starved for signal.
