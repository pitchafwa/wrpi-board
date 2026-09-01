"""Fit the official WRPI v2 as an interpretable additive model, to actual fantasy
production (top35 = best-3-of-first-5 PPR PPG). Pre-draft and post-draft versions.
Reports LOCO-CV Spearman + exact weights, and freezes params + reference dist."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from scipy.optimize import differential_evolution

F = pd.read_csv("data/features_v3.csv"); O = pd.read_csv("data/nfl_outcomes.csv")
g = F.merge(O, on=["Player", "Year"])
g = g[(g.has_college == 1) & g.nfl_entry_age.notna() & (g.win3_full == 1)].reset_index(drop=True)
T = "top35"
X = pd.DataFrame({
    "Year": g.Year.values, T: g[T].values,
    "alpha":   g.alpha.fillna(0).astype(float).values,
    "nfl_age": g.nfl_entry_age.values,
    "bo_age":  g.breakout_age.fillna(99.0).values,
    "dom":     g.best_dom.clip(0, .6).fillna(g.best_dom.median()).values,
    "ppa":     g.final_ppa.fillna(g.final_ppa.median()).values,
    "expl":    g.explosion_p.fillna(0.5).values,
    "yds":     (g.best_yds.fillna(g.best_yds.median()) / 1000.0).values,
    "pick":    g.pick.clip(1, 300).values,
}).reset_index(drop=True)
yr = X.Year.values
print(f"{len(X)} prospects 2015-2022, target = {T}\n")

def ramp(x, z, s, c): return np.clip(s * (z - x), 0, c)

def score(p, d, post):
    v = (p[0] * d["alpha"]
         + ramp(d["nfl_age"], p[1], p[2], p[3])
         + ramp(d["bo_age"],  p[4], p[5], p[6])
         + np.clip(p[7] * d["dom"], 0, p[8])
         + np.clip(p[9] * (d["ppa"] + 0.5), 0, p[10])
         + np.clip(p[11] * d["expl"], 0, p[12])
         + np.clip(p[13] * d["yds"], 0, p[14]))
    if post:
        v = v + np.clip(p[15] * np.power(d["pick"] + p[16], -p[17]), 0, p[18])
    return v

B_PRE = [(0, 15),                       # alpha
         (22, 26), (0, 12), (0, 30),    # nfl age ramp
         (20, 24), (0, 10), (0, 20),    # breakout age ramp
         (0, 60), (0, 25),              # dominator
         (0, 25), (0, 25),              # efficiency (ppa)
         (0, 30), (0, 25),              # athletic explosion
         (0, 20), (0, 20)]              # production volume
B_POST = B_PRE + [(1, 4000), (0, 40), (0.2, 1.4), (0, 60)]   # draft capital A,c,k,cap

def fit(post):
    b = B_POST if post else B_PRE
    def obj(p):
        return -(spearmanr(score(p, X, post), X[T]).correlation or 0)
    r = differential_evolution(obj, b, seed=1, maxiter=140, popsize=18, tol=1e-7,
                               mutation=(.5, 1), recombination=.7, polish=True,
                               workers=1, updating="deferred")
    p = r.x
    # LOCO-CV
    outs = []
    for c in sorted(set(yr)):
        tr = X[yr != c]
        rr = differential_evolution(lambda q: -(spearmanr(score(q, tr, post), tr[T]).correlation or 0),
                                    b, seed=1, maxiter=70, popsize=12, polish=True,
                                    workers=1, updating="deferred")
        te = X[yr == c]
        outs.append(spearmanr(score(rr.x, te, post), te[T]).correlation)
    return p, -r.fun, float(np.mean(outs))

for post in (False, True):
    p, ins, cv = fit(post)
    tag = "POST-DRAFT" if post else "PRE-DRAFT"
    pk = -spearmanr(X.pick, X[T]).correlation
    print(f"==== WRPI v2 {tag} ====   in-sample {ins:.3f}   LOCO-CV {cv:.3f}"
          + (f"   (draft pick alone {pk:.3f})" if post else ""))
    print(f"  Alpha WR ..................... +{p[0]:.1f}  (pass) / 0")
    print(f"  NFL entry age ............... min({p[2]:.1f}*({p[1]:.1f}-age), {p[3]:.1f})")
    print(f"  Breakout age ............... min({p[5]:.1f}*({p[4]:.1f}-age), {p[6]:.1f})")
    print(f"  College dominator ......... min({p[7]:.1f}*share, {p[8]:.1f})     [share = best-season, 0-0.60]")
    print(f"  Final-season efficiency .. min({p[9]:.1f}*(PPA+0.5), {p[10]:.1f})  [CFBD points-added/play]")
    print(f"  Athletic explosion ...... min({p[11]:.1f}*pctl, {p[12]:.1f})       [vert+broad+speed, 0-1]")
    print(f"  Production volume ...... min({p[13]:.1f}*(best_yds/1000), {p[14]:.1f})")
    if post:
        print(f"  Draft capital ......... min({p[15]:.0f}*(pick+{p[16]:.1f})^-{p[17]:.2f}, {p[18]:.1f})")
        for pk_ in (1, 5, 10, 20, 32, 50, 75, 120, 200, 270):
            val = min(p[15] * (pk_ + p[16]) ** (-p[17]), p[18])
            print(f"        pick {pk_:3d} -> {val:5.1f}")
    np.save(f"data/wrpi_v2_{'post' if post else 'pre'}.npy", p)
    print()
