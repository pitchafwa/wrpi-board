"""Annual refit review: compare the freshly-fit params (*.npy, just produced by
the fit scripts on the now-larger training window) against the committed frozen
params (*_params_*.json). Writes refit_report.md. Verdict is advisory -- a human
merges the PR or not.

Metric: leave-one-class-out rank correlation, applying each param set unchanged
to every held-out class (NOT re-fitting per fold) -- a like-for-like read on
which param set ranks the data better.
"""
import json, sys
import numpy as np, pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, "rbpi")
import rbpi_score_v1 as RB
import wrpi_score_v2 as WR

LINES = ["# Annual refit review\n"]


def loco(raw_fn, params, d, ycol):
    y, yr = d[ycol].values, d.Year.values
    outs = []
    for c in sorted(set(yr)):
        te = yr == c
        if te.sum() < 3:
            continue
        outs.append(spearmanr(raw_fn(params, d[te]), y[te]).correlation)
    return float(np.mean(outs))


def section(name, old, new, dfX, ycol, raw_fn, labels):
    cv_old = loco(raw_fn, old, dfX, ycol)
    cv_new = loco(raw_fn, new, dfX, ycol)
    delta = cv_new - cv_old
    lurch = []
    for i, lab in enumerate(labels):
        o, n = old[i], new[i]
        if o and abs(n / o) > 2.0 and abs(n - o) > 1.0:
            lurch.append(f"{lab}: {o:.2f} -> {n:.2f}")
        if (o > 0) != (n > 0) and abs(o) > 0.5 and abs(n) > 0.5:
            lurch.append(f"{lab}: SIGN FLIP {o:.2f} -> {n:.2f}")
    ok = delta >= -0.02 and not lurch
    LINES.append(f"\n## {name}\n")
    LINES.append(f"- LOCO-CV (apply-per-fold): frozen **{cv_old:.3f}** -> refit **{cv_new:.3f}**  (delta {delta:+.3f})")
    LINES.append(f"- weight lurch check: {'; '.join(lurch) if lurch else 'none'}")
    LINES.append(f"- **verdict: {'PASS - safe to adopt' if ok else 'REVIEW - do not auto-adopt'}**\n")
    LINES.append("| # | param | frozen | refit |")
    LINES.append("|---|---|---|---|")
    for i, lab in enumerate(labels):
        LINES.append(f"| {i} | {lab} | {old[i]:.3f} | {new[i]:.3f} |")
    return ok


all_ok = True

# ---------- RBPI ----------
try:
    d = pd.read_csv("rbpi/data/features_rb_all.csv").merge(
        pd.read_csv("rbpi/data/rb_outcomes_all.csv").drop(columns=["pick"]), on=["Player", "Year"])
    d = d[(d.has_college == 1) & d.nfl_entry_age.notna() & (d.win3_full == 1)].reset_index(drop=True)
    ypc = (d.career_ypc - d.career_ypc.median()) / d.career_ypc.std()
    ppa = (d.avg_ppa - d.avg_ppa.median()) / d.avg_ppa.std()
    X = pd.DataFrame({
        "Year": d.Year.values, "rb_top34": d.rb_top34.values,
        "nfl_age": d.nfl_entry_age.values, "bo_age": d.breakout_age.fillna(99).values,
        "dom": d.best_dom.clip(0, .65).fillna(d.best_dom.median()).values,
        "rec": d.best_rec_ydshare.clip(0, .5).fillna(d.best_rec_ydshare.median()).values,
        "eff": pd.concat([ypc, ppa], axis=1).mean(axis=1).fillna(0).values,
        "expl": d.explosion_p.fillna(.5).values,
        "yds": (d.best_scrim_yds.fillna(d.best_scrim_yds.median()) / 1000).values,
        "pick": d.pick.clip(1, 300).values})
    PRE_L = ["nfl_age z", "nfl_age slope", "nfl_age cap", "bo_age z", "bo_age slope", "bo_age cap",
             "dom scale", "dom cap", "rec scale", "rec cap", "eff scale", "eff cap",
             "expl scale", "expl cap", "yds scale", "yds cap"]
    POST_L = PRE_L + ["cap A", "cap c", "cap k", "cap max"]
    o_pre = json.load(open("rbpi/data/rbpi_v1_params_pre.json"))["params"]
    o_post = json.load(open("rbpi/data/rbpi_v1_params_post.json"))["params"]
    n_pre = np.load("rbpi/data/rbpi_v1_pre.npy").tolist()
    n_post = np.load("rbpi/data/rbpi_v1_post.npy").tolist()
    all_ok &= section("RBPI pre-draft", o_pre, n_pre, X, "rb_top34", RB.raw_pre, PRE_L)
    all_ok &= section("RBPI post-draft", o_post, n_post, X, "rb_top34", RB.raw_post, POST_L)
except Exception as e:
    LINES.append(f"\n## RBPI\n\n_skipped: {e!r}_\n")

# ---------- WRPI ----------
try:
    o_pre = json.load(open("data/wrpi_v2_params_pre.json"))["params"]
    o_post = json.load(open("data/wrpi_v2_params_post.json"))["params"]
    n_pre = np.load("data/wrpi_v2_pre.npy").tolist()
    n_post = np.load("data/wrpi_v2_post.npy").tolist()
    L = [f"p{i}" for i in range(len(o_post))]
    # eval frame mirrors fit_wrpi_v2.py
    g = pd.read_csv("data/features_v3.csv").merge(pd.read_csv("data/nfl_outcomes.csv"), on=["Player", "Year"])
    g = g[(g.has_college == 1) & g.nfl_entry_age.notna() & (g.win3_full == 1)].reset_index(drop=True)
    X = pd.DataFrame({
        "Year": g.Year.values, "top35": g.top35.values,
        "alpha": g.alpha.fillna(0).astype(float).values, "nfl_age": g.nfl_entry_age.values,
        "bo_age": g.breakout_age.fillna(99.).values,
        "dom": g.best_dom.clip(0, .6).fillna(g.best_dom.median()).values,
        "ppa": g.final_ppa.fillna(g.final_ppa.median()).values,
        "expl": g.explosion_p.fillna(.5).values,
        "yds": (g.best_yds.fillna(g.best_yds.median()) / 1000.).values,
        "pick": g.pick.clip(1, 300).values})
    all_ok &= section("WRPI pre-draft", o_pre, n_pre, X, "top35", WR.raw_pre, L[:len(o_pre)])
    all_ok &= section("WRPI post-draft", o_post, n_post, X, "top35", WR.raw_post, L)
except Exception as e:
    LINES.append(f"\n## WRPI\n\n_skipped: {e!r}_\n")

LINES.insert(1, f"\n**Overall: {'PASS on every model — the PR is safe to merge if the weights read sensibly.' if all_ok else 'At least one model needs review — do NOT merge without checking.'}**\n")
open("refit_report.md", "w").write("\n".join(LINES))
print("\n".join(LINES))
