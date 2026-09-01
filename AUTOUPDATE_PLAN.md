# Auto-update & stable future use — plan for review

Goal: a board at `pitchafwa.github.io/wrpi-board` (WR + RB tabs) that stays current
on its own for 2027 and beyond, is most fresh in the run-up to the NFL draft and
especially right after it (rookie-draft season), and whose **model never changes
on a schedule** — only the data does.

---

## 1. Core principle — refresh the data, freeze the model

The scoring is a fixed function. These files are checked into git and the
scheduled job **never touches them**:

| Model | Frozen params |
|---|---|
| WRPI | `data/wrpi_v2_params_{pre,post}.json`, `data/wrpi_tiebreaker.json`, `data/wrpi_diamond.json`, `data/wrpi_reference.json` |
| RBPI | `data/rbpi_v1_params_{pre,post}.json`, `data/rbpi_diamond.json`, reference distribution baked into `score_rbpi.py` |

The job only re-pulls raw feeds → rebuilds feature tables → re-scores with those
frozen params → regenerates `dashboard/scores.json` + `dashboard/rbpi_scores.json`
→ commits. `deploy.yml` (already live) publishes on that push.

Net effect: the board always reflects the newest data available (combine numbers,
declarations, draft picks, NFL outcomes maturing into the calibration tables),
but the number each player gets is produced by the exact same model all year.

---

## 2. Cadence — matched to how you actually use it   *(confirmed)*

Key insight (yours): once the draft's picks are in, the current class's
pre-NFL-debut inputs are **complete** — combine, college production, draft
capital all known. Nothing about that class changes afterward except its
actual-fantasy columns as those players accrue NFL seasons, and that only feeds
the *calibration tables*, not the rookies you're drafting. So there's no reason to
run daily for months post-draft.

| Window | Frequency | Why |
|---|---|---|
| **Pre-draft ramp** (Jan 1 → draft day) | weekly | Bowl games done, underclassmen declare, **combine** (late Feb), **pro days** (Mar). The pre-draft board firms up week to week. Board shows a "projected picks — not final" banner for the current class. |
| **Draft window** (draft day → +10 days) | daily | The one moment the **post-draft** score becomes real. nflverse ingests the picks over 1–3 days; a daily run through the following week catches them, refreshes post-draft scores + ★ + ◆, and drops the provisional banner. |
| **Rest of year** (post-window → Dec) | 1st of each month | Current class is frozen. The monthly run only keeps the calibration tables maturing as older classes finish NFL seasons, and picks up nflverse corrections. |

**Implementation — the workflow schedules itself.** One workflow on a **daily
cron**. First step reads `data/draft_dates.json` + today's date and decides its
own mode:

- inside the pre-draft ramp → run only if ≥6 days since the last full run (≈weekly)
- inside the draft window (`[draft_day, draft_day + 10]`) → run every day
- else → run only on the 1st of the month
- otherwise → exit in ~5 seconds, no-op

`draft_dates.json` holds the known future draft dates (the NFL publishes them
~2 years out). Adding next year's date is one line — it's on the August checklist
(§4). This gives you exactly "the site knows when the draft is and produces the
final draft-capital results the next day," with no cron babysitting.

`workflow_dispatch` is always available for an on-demand run.

---

## 3. New draft class onboarding (2027, 2028, …) — mostly automatic

The raw feeds already carry upcoming classes:

- **`draft_picks.csv`** (nflverse release) — carries the upcoming class with
  *projected* picks pre-draft (a consensus/mock), then *real* picks after the
  draft. The RB pool is literally `draft_picks[position == RB]`; the WR pool adds
  a CFBD-player-search supplement (`build_pool.py`) for notable undrafted college
  WRs. → **the 2027 class appears on its own** once nflverse posts it.
- **`combine.csv`** — new combine results land Feb–Mar each year.
- **`players.csv`** — new prospects added with birthdates (drives age / breakout age).
- **CFBD** — one pull of the new college season adds their production.

### UDFAs — two kinds, both kept   *(your point 5)*

1. **Projected-pool players who went undrafted** *(new — add this)*. The pre-draft
   pool for a class = nflverse's projected `draft_picks.csv` (goes ~250 deep) plus
   any CFBD-search supplement. After the real draft, some pool members have no
   pick. Instead of dropping them, we mark them `pick = 270`, `is_udfa = 1`,
   `udfa_type = "projected"` and keep them on the board: their pre-draft
   RBPI/WRPI is intact, and their post-draft score is computed with the pick-270
   draft-capital value (≈0) — correctly reflecting "the model liked him, the
   league didn't." This is only 3–5 backs a year (the projected pool is already
   draftable-caliber, not a sleeper dump), so it's low-noise, and the ◆ diamond
   flag naturally surfaces any that are interesting. **This is what you want for
   a late rookie-draft flier.**
2. **Retrospective UDFAs** (`build_features_rb_udfa.py`, the current 38) — players
   with ≥80 career NFL touches who were never on any pre-draft board. Kept as
   they are, for calibration + comps. A brand-new class's contribution here
   self-lags a year or two (correct — they haven't earned a role yet).

Implementation: split the UDFA step into `build_features_rb_projected_udfa.py`
(current class, from the projected pool minus the real drafted set) and the
existing retrospective one; both feed `combine_pool.py`. Same pattern can be added
to WRPI.

**If nflverse is slow** to post the projected class, the board just shows the
prior classes until it does. Acceptable. A CFBD-declaration-based fallback pool
could be added later if this proves annoying (backlog).

---

## 4. Annual model refit — how it actually works   *(confirmed: yes, gated)*

There's no pop-up (nothing here can raise one). Instead, a **separate scheduled
workflow, `refit-review.yml`, cron'd for mid-August**, does the whole thing and
hands you a decision:

1. Extends the training window to include the newest class that now has a mature
   outcome window (WR/RB both need 3 completed NFL seasons). E.g. mid-Aug 2027 →
   the 2024 class has 3 seasons, so the window goes 2015–2023 → 2015–2024.
2. Re-runs `fit_wrpi_v2.py`, `fit_rbpi.py`, `fit_rbpi_pre2.py` on that window.
3. Computes the gate:
   - LOCO-CV Spearman within ~0.02 of the frozen model (no degradation), and
   - no weight lurch — no sign flips, no >2× scale change on a major term,
     draft-capital curve shape stable.
4. **Opens a GitHub Issue** ("Annual refit review — Aug 20XX") containing: old vs
   new CV for every model, a side-by-side weight table, and PASS/FAIL on the gate.
   It also pushes a branch `refit-20XX` with the new param JSONs and opens a PR.
5. **You decide.** Gate PASS + you like it → merge the PR (the next scheduled
   board run picks up the new params). Gate FAIL or you'd rather not → close the
   PR; the frozen params stay. Never auto-adopts.

You get an email from the Issue/PR (standard GitHub notification). If you miss it,
it just sits there and the board keeps running on the frozen model — nothing
breaks.

The Issue's checklist also includes **"add next year's NFL draft dates to
`draft_dates.json`"** so §2's self-scheduling stays fed.

**Why bother at all:** more data slightly tightens the fit and catches genuine
drift (if the NFL keeps pushing RB value later, the draft-capital curve should
follow). Both models are already cross-validated and stable, so the expected
result most years is "gate passes, changes are trivial, adopt or don't — doesn't
matter much." It's insurance.

---

## 5. Implementation checklist (my next work session, on your go)

1. **Relocate the RB scripts into the repo.** They currently live in
   `PSI-reverse-engineering/rbpi/` with absolute paths. Move to
   `wrpi-board/rbpi/` (or fold into the main dir) and switch to repo-relative paths.
2. **Rewrite `update.yml`** (currently `update.yml.disabled`; the existing one is a
   stale v1 scaffold). New job:
   - `fetch_sources.py` — nflverse + array-carpenter feeds
   - CFBD pull — `build_cfbd.py` (WR) + `build_cfbd_rb.py` + `rebuild_ppa_usage.py`
     + `build_cfbd_extra*` (needs `CFBD_KEY`); wrap in `continue-on-error` so a
     CFBD hiccup doesn't block an nflverse-only refresh
   - Feature builds — `build_features_v3.py` (WR); `build_features_rb2.py` +
     `build_features_rb_udfa.py` + `combine_pool.py` (RB)
   - Outcomes — `build_outcomes.py` (WR), `build_outcomes_rb.py` (RB) for the
     calibration tables
   - Score — `score_v2.py` → `dashboard/scores.json`; `score_rbpi.py` →
     `dashboard/rbpi_scores.json` (remove its current dev-only absolute-path copy)
   - Commit refreshed `dashboard/*.json` + `data/*_database.csv`
   - `deploy.yml` publishes the push
3. ~~Set the `CFBD_KEY` repo secret~~ — **done (you added it).**
4. **"Provisional" banner.** In `score_*.py`, detect when the max class year's
   picks look projected (e.g. all from a mock source / a `provisional` column) and
   emit `"draft_status":"pre-draft"` in the JSON. Board shows a banner on that
   class: *"2027 — projected picks; post-draft score not final until the NFL
   draft."*
5. **Robustness:**
   - Pin `pandas` / `numpy` / `scipy` versions in the workflow so a library
     update can't silently shift outputs.
   - GitHub Actions cache for `data/cfbd_raw/` so we re-pull only the current
     college season, not 15 years every run.
   - Job re-pulls everything fresh → naturally idempotent. On any source failure
     the step errors, nothing commits, board keeps last good state, you get a
     failure email.

---

## 6. What you get day to day

- Board never more than ~a week stale (daily in draft season), both positions.
- **Pre-draft:** talent tiers for the current class, updated as combine / pro-day
  numbers land, clearly labeled provisional.
- **Post-draft (the main event):** within ~a day of the NFL draft, post-draft
  scores + ★ + ◆ refresh with real draft capital — ready for your rookie drafts.
- Calibration tables keep maturing as each class finishes its outcome window.
- Model unchanged all year; one gated, supervised refit each August.

---

## Commit scope — plain english   *(your point 3)*

Each scheduled run regenerates files and commits them back to the repo. What
should it commit?

- **The board JSON** (`dashboard/scores.json`, `dashboard/rbpi_scores.json`) —
  the only files the website reads. Must be committed. Small; each diff is
  basically "these players' numbers moved."
- **The summary tables** (`data/wrpi_database.csv`, `data/rbpi_database.csv`) —
  one row per player: their scores + the key inputs, human-readable. The site
  doesn't use them, but if you ever ask "why did player X's score change between
  April and May," you diff these two files and see exactly which input moved.
  A few hundred rows; diffs are readable.
- **The big raw feature tables + CFBD dumps** (`features_*.csv`,
  `data/cfbd_raw/*`) — thousands of rows, 90+ columns. Committing these on every
  run would bloat the repo and make every commit a 5,000-line diff for no real
  gain (they're regenerated deterministically from the raw feeds anyway).

**Recommendation:** commit the board JSON + the two summary CSVs. Skip the rest
(cache it between runs instead). Enough audit trail to answer "what changed,"
without turning every run into noise.

---

## Status of your answers

1. Cadence — **confirmed** (weekly pre-draft, daily for the ~10-day draft window,
   monthly otherwise; workflow self-schedules off `draft_dates.json`). §2 updated.
2. Refit — **confirmed** gated. Mechanics in §4: a mid-August `refit-review.yml`
   runs it, opens an Issue + PR with the old/new comparison, you merge or close.
3. Commit scope — recommendation above: board JSON + the 2 summary CSVs.
4. `CFBD_KEY` — **done.**
5. Undrafted projected-pool players — **yes, adding them** as
   `udfa_type="projected"` (§3). Distinct from the retrospective ≥80-touch UDFAs.
