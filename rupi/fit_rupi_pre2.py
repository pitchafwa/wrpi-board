"""Pre-draft RUPI refit with saner/tighter bounds -- v1's pre-draft fit produced
a couple of spike-overfit terms (breakout-age threshold 18.3 w/ cap 20.8; an
inactive entry-age slope; an efficiency cap that dominated despite the research
saying RB efficiency translates weakly). Tighten every component cap to a
comparable range and constrain the age-ramp thresholds to realistic windows so
DE can't buy in-sample rank corr with 2-3 outlier spikes."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from scipy.optimize import differential_evolution

F = pd.read_csv("rupi/data/features_rb.csv")
O = pd.read_csv("rupi/data/rb_outcomes.csv").drop(columns=["pick"])
g = F.merge(O, on=["Player", "Year"])
g = g[(g.has_college == 1) & g.nfl_entry_age.notna() & (g.win3_full == 1)].reset_index(drop=True)
T = "rb_top34"
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
}).reset_index(drop=True)
yr = X.Year.values
print(f"{len(X)} RBs, target {T}\n")

def ramp(x, z, s, c): return np.clip(s * (z - x), 0, c)

def score(p, d):
    return (ramp(d["nfl_age"], p[0], p[1], p[2])
            + ramp(d["bo_age"],  p[3], p[4], p[5])
            + np.clip(p[6] * d["dom"], 0, p[7])
            + np.clip(p[8] * d["rec"], 0, p[9])
            + np.clip(p[10] * (d["eff"] + 2.0), 0, p[11])
            + np.clip(p[12] * d["expl"], 0, p[13])
            + np.clip(p[14] * d["yds"], 0, p[15]))

# tighter: realistic age windows, every cap in a comparable 0-8 band
B = [(22.0, 25.0), (0, 4), (0, 8),     # nfl entry age ramp
     (19.5, 21.5), (0, 5), (0, 8),     # breakout age ramp (realistic threshold window)
     (0, 30), (0, 8),                  # dominator
     (0, 50), (0, 8),                  # receiving role
     (0, 5),  (0, 6),                  # efficiency (kept modest -- weak signal per research)
     (0, 20), (0, 8),                  # athletic explosion
     (0, 10), (0, 6)]                  # production volume

def obj_full(p): return -(spearmanr(score(p, X), X[T]).correlation or 0)
r = differential_evolution(obj_full, B, seed=1, maxiter=120, popsize=16, tol=1e-6,
                           mutation=(.5, 1), recombination=.7, polish=True,
                           workers=1, updating="deferred")
p = r.x
print(f"in-sample {-r.fun:.3f}", flush=True)
outs = []
for c in sorted(set(yr)):
    tr = X[yr != c]
    rr = differential_evolution(lambda q: -(spearmanr(score(q, tr), tr[T]).correlation or 0),
                                B, seed=1, maxiter=70, popsize=12, tol=1e-6, polish=True,
                                workers=1, updating="deferred")
    te = X[yr == c]
    rho = spearmanr(score(rr.x, te), te[T]).correlation
    outs.append(rho); print(f"  fold {c}: {rho:+.3f}", flush=True)
cv = float(np.mean(outs))
print(f"\n==== RUPI v1.1 PRE-DRAFT ====  in-sample {-r.fun:.3f}  LOCO-CV {cv:.3f}")
print(f"  NFL entry age ...... min({p[1]:.1f}*({p[0]:.1f}-age), {p[2]:.1f})")
print(f"  Breakout age ....... min({p[4]:.1f}*({p[3]:.1f}-age), {p[5]:.1f})")
print(f"  College dominator .. min({p[6]:.1f}*share, {p[7]:.1f})")
print(f"  Receiving role ..... min({p[8]:.1f}*share, {p[9]:.1f})")
print(f"  Efficiency ......... min({p[10]:.1f}*(z+2), {p[11]:.1f})")
print(f"  Athletic explosion  min({p[12]:.1f}*pctl, {p[13]:.1f})")
print(f"  Production volume .. min({p[14]:.1f}*(yds/1000), {p[15]:.1f})")
np.save("rupi/data/rupi_v1_pre.npy", p)
print("\nsaved data/rupi_v1_pre.npy (overwrote v1 pre)")
