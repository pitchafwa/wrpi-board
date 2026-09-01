"""Fit RUPI v1 as an interpretable additive model (mirrors WRPI v2's structure),
to actual fantasy production. Target = rb_top34 (best-2-of-first-3 PPR PPG,
front-loaded for RB shelf life -- see RESEARCH.md). Pre-draft + post-draft,
LOCO-CV by draft class. Adds a RECEIVING-ROLE component that WR didn't need
(all WR production IS receiving); age ramps get wider bounds (steeper penalty
allowed) per the research on RB shelf life."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from scipy.optimize import differential_evolution

F = pd.read_csv("rupi/data/features_rb.csv")
O = pd.read_csv("rupi/data/rb_outcomes.csv").drop(columns=["pick"])
g = F.merge(O, on=["Player", "Year"])
g = g[(g.has_college == 1) & g.nfl_entry_age.notna() & (g.win3_full == 1)].reset_index(drop=True)
T = "rb_top34"

# blended efficiency z-score: career YPC (best coverage, strongest raw signal)
# + college PPA (CFBD points-added/play, rush-inclusive) when available
ypc_z = (g.career_ypc - g.career_ypc.median()) / g.career_ypc.std()
ppa_z = (g.avg_ppa - g.avg_ppa.median()) / g.avg_ppa.std()
eff_z = pd.concat([ypc_z, ppa_z], axis=1).mean(axis=1).fillna(0.0)

X = pd.DataFrame({
    "Year": g.Year.values, T: g[T].values,
    "nfl_age": g.nfl_entry_age.values,
    "bo_age":  g.breakout_age.fillna(99.0).values,
    "dom":     g.best_dom.clip(0, .65).fillna(g.best_dom.median()).values,
    "rec":     g.best_rec_ydshare.clip(0, .5).fillna(g.best_rec_ydshare.median()).values,
    "eff":     eff_z.values,
    "expl":    g.explosion_p.fillna(0.5).values,
    "yds":     (g.best_scrim_yds.fillna(g.best_scrim_yds.median()) / 1000.0).values,
    "pick":    g.pick.clip(1, 300).values,
}).reset_index(drop=True)
yr = X.Year.values
print(f"{len(X)} drafted RBs 2015-2023, target = {T} (best-2-of-first-3 PPR PPG)\n")

def ramp(x, z, s, c): return np.clip(s * (z - x), 0, c)

def score(p, d, post):
    v = (ramp(d["nfl_age"], p[0], p[1], p[2])
         + ramp(d["bo_age"],  p[3], p[4], p[5])
         + np.clip(p[6] * d["dom"], 0, p[7])
         + np.clip(p[8] * d["rec"], 0, p[9])
         + np.clip(p[10] * (d["eff"] + 2.0), 0, p[11])
         + np.clip(p[12] * d["expl"], 0, p[13])
         + np.clip(p[14] * d["yds"], 0, p[15]))
    if post:
        v = v + np.clip(p[16] * np.power(d["pick"] + p[17], -p[18]), 0, p[19])
    return v

B_PRE = [(21, 25), (0, 15), (0, 35),    # nfl entry age ramp (steeper allowed than WRPI)
         (18, 22), (0, 16), (0, 30),    # breakout age ramp  (steeper allowed than WRPI)
         (0, 60), (0, 25),              # dominator (scrimmage)
         (0, 80), (0, 25),              # receiving role  <-- new vs WRPI
         (0, 15), (0, 20),              # efficiency (YPC/PPA blend)
         (0, 30), (0, 25),              # athletic explosion
         (0, 20), (0, 20)]              # production volume (scrimmage yards)
B_POST = B_PRE + [(1, 5000), (0, 40), (0.2, 1.5), (0, 70)]   # draft capital A,c,k,cap

def fit(post):
    b = B_POST if post else B_PRE
    def obj(p):
        return -(spearmanr(score(p, X, post), X[T]).correlation or 0)
    r = differential_evolution(obj, b, seed=1, maxiter=90, popsize=14, tol=1e-6,
                               mutation=(.5, 1), recombination=.7, polish=True,
                               workers=1, updating="deferred")
    p = r.x
    print(f"  [{'post' if post else 'pre'}] in-sample fit done: {-r.fun:.3f}", flush=True)
    outs = []
    for c in sorted(set(yr)):
        tr = X[yr != c]
        rr = differential_evolution(lambda q: -(spearmanr(score(q, tr, post), tr[T]).correlation or 0),
                                    b, seed=1, maxiter=55, popsize=10, tol=1e-6, polish=True,
                                    workers=1, updating="deferred")
        te = X[yr == c]
        rho = spearmanr(score(rr.x, te, post), te[T]).correlation
        outs.append(rho)
        print(f"  [{'post' if post else 'pre'}] LOCO fold {c}: test rho {rho:+.3f}", flush=True)
    return p, -r.fun, float(np.mean(outs))

if __name__ == "__main__":
    for post in (False, True):
        p, ins, cv = fit(post)
        tag = "POST-DRAFT" if post else "PRE-DRAFT"
        pk = -spearmanr(X.pick, X[T]).correlation
        print(f"==== RUPI v1 {tag} ====   in-sample {ins:.3f}   LOCO-CV {cv:.3f}"
              + (f"   (draft pick alone {pk:.3f})" if post else ""))
        print(f"  NFL entry age ............ min({p[1]:.1f}*({p[0]:.1f}-age), {p[2]:.1f})")
        print(f"  Breakout age ............. min({p[4]:.1f}*({p[3]:.1f}-age), {p[5]:.1f})")
        print(f"  College dominator ........ min({p[6]:.1f}*share, {p[7]:.1f})       [scrimmage share, 0-0.65]")
        print(f"  Receiving role ........... min({p[8]:.1f}*share, {p[9]:.1f})       [rec-yd share, 0-0.50]")
        print(f"  Efficiency (YPC/PPA) ..... min({p[10]:.1f}*(z+2.0), {p[11]:.1f})")
        print(f"  Athletic explosion ....... min({p[12]:.1f}*pctl, {p[13]:.1f})      [vert+broad+speed, 0-1]")
        print(f"  Production volume ........ min({p[14]:.1f}*(best_scrim_yds/1000), {p[15]:.1f})")
        if post:
            print(f"  Draft capital ........... min({p[16]:.0f}*(pick+{p[17]:.1f})^-{p[18]:.2f}, {p[19]:.1f})")
            for pk_ in (1, 5, 10, 20, 32, 50, 75, 100, 150, 220, 260):
                val = min(p[16] * (pk_ + p[17]) ** (-p[18]), p[19])
                print(f"        pick {pk_:3d} -> {val:5.1f}")
        np.save(f"rupi/data/rupi_v1_{'post' if post else 'pre'}.npy", p)
        print()
