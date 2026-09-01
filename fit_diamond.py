"""Diamonds in the rough — an interpretable INDEX of pre-draft indicators that,
for WRs drafted after ~round 2 (pick >= 50), separates the future fantasy assets
(Kupp, M.Thomas, ARSB, Godwin, Diggs, Nacua...) from the rest."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

F = pd.read_csv("data/features_v3.csv"); O = pd.read_csv("data/nfl_outcomes.csv")
d = F.merge(O, on=["Player", "Year"])
# use the longest completed window available; need >= 3 NFL seasons
d = d[(d.has_college == 1) & d.nfl_entry_age.notna() & (d.win3_full == 1)].reset_index(drop=True)
d["best_ppg"] = d[["best3", "best5"]].max(axis=1)
d["sustain"] = d[["top35", "top33"]].max(axis=1)      # best-3 avg PPG (career-ish)

CUT = 50
late = d[d.pick >= CUT].reset_index(drop=True)
late["hit"] = ((late.best_ppg >= 12) | (late.sustain >= 10)).astype(int)   # became a real asset
yr = late.Year.values
print(f"late pool (pick>={CUT}): {len(late)} WRs · hit rate {late.hit.mean():.1%} ({late.hit.sum()} hits)")
print("  hits:", ", ".join(late[late.hit == 1].sort_values("best_ppg", ascending=False).Player.head(24)))

# indicator set with expected direction (+1 = higher is more diamond-like)
IND = {
 "n_seasons_30":     +1,   # multiple 30%+ dominator seasons
 "best_ydshare":     +1,   # peak share of team receiving yards
 "td_rate":          +1,   # college TD production rate
 "dom_age20":        +1,   # dominated young
 "early_declare":    +1,   # left with eligibility
 "final_ppa":        +1,   # final-season efficiency
 "best_usage":       +1,   # college usage share
 "prod_over_recruit":+1,   # out-produced his recruiting rank
 "team_sos":         +1,   # produced vs a tough schedule
 "explosion_p":      +1,   # vertical + broad + speed
 "n_drills":         +1,   # complete athletic profile (didn't hide)
 "best_long":        +1,   # big-play ability
 "nfl_entry_age":    -1,   # younger
 "agility_score":    -1,   # lower 3cone+shuttle = better
}
IND = {k: v for k, v in IND.items() if k in late.columns}
for c in IND: late[c] = pd.to_numeric(late[c], errors="coerce")
med = late[list(IND)].median()
mu = late[list(IND)].mean(); sd = late[list(IND)].std() + 1e-9

def zmat(df):
    return pd.DataFrame({k: v * ((pd.to_numeric(df[k], errors="coerce").fillna(med[k]) - mu[k]) / sd[k])
                         for k, v in IND.items()})

Z = zmat(late)
y = late.hit.values

# weights: heavily-regularised logistic (keeps directions sane, avoids overfit on ~25 hits)
lr = LogisticRegression(C=0.05, max_iter=6000, class_weight="balanced").fit(Z, y)
w = pd.Series(lr.coef_[0], index=list(IND))
# floor tiny/negative-after-sign weights at 0 so the index stays an "additive strengths" score
w = w.clip(lower=0)
w = w / w.sum() if w.sum() else pd.Series(1 / len(IND), index=list(IND))
print("\nindex weights (share):")
for k, v in w.sort_values(ascending=False).items():
    print(f"   {k:18s} {v:.3f}   (univ. hit-miss gap {((late.loc[y==1,k].mean()-late.loc[y==0,k].mean())/(late[k].std()+1e-9)) * IND[k]:+.2f})")

late["dscore"] = (Z * w.values).sum(axis=1)

# evaluate: LOCO-CV — rank by index within held-out class, precision@k + lift
def loco_prec():
    pr = {3: [], 5: [], 10: []}
    for c in sorted(set(yr)):
        tr, te = yr != c, yr == c
        wl = LogisticRegression(C=0.05, max_iter=6000, class_weight="balanced").fit(Z[tr], y[tr]).coef_[0]
        wl = np.clip(wl, 0, None); wl = wl / wl.sum() if wl.sum() else np.ones(len(IND)) / len(IND)
        s = (Z[te].values * wl).sum(1)
        for k in pr:
            pr[k].append(y[te][np.argsort(-s)[:k]].mean())
    return {k: np.mean(v) for k, v in pr.items()}
P = loco_prec()
base = late.hit.mean()
print(f"\nLOCO-CV precision@3/5/10 = {P[3]:.2f} / {P[5]:.2f} / {P[10]:.2f}   (base rate {base:.2f})   "
      f"lift@5 = {P[5]/base:.1f}x")

# quartile hit rates
late["q"] = pd.qcut(late.dscore, 4, labels=["Q1", "Q2", "Q3", "Q4"])
print("\nhit rate by index quartile:")
print(late.groupby("q").hit.agg(["mean", "size"]).round(3).to_string())

print("\ncanonical diamonds — index percentile within the late pool:")
late["dpct"] = late.dscore.rank(pct=True)
for nm in ["Cooper Kupp", "Michael Thomas", "Amon-Ra St. Brown", "Chris Godwin", "Stefon Diggs",
           "Puka Nacua", "Nico Collins", "Terry McLaurin", "Hunter Renfrow", "Tyler Lockett",
           "Adam Thielen", "Kenny Golladay", "Diontae Johnson"]:
    r = late[late.Player == nm]
    if len(r): print(f"   {nm:20s} idx pctl {r.dpct.iloc[0]:.0%}  pick {int(r.pick.iloc[0])}  hit={int(r.hit.iloc[0])}")

FLAG = float(late.dscore.quantile(0.80))   # top 20% of the late pool
json.dump({"ind": IND, "w": {k: float(v) for k, v in w.items()},
           "mean": {k: float(mu[k]) for k in IND}, "std": {k: float(sd[k]) for k in IND},
           "median": {k: float(med[k]) for k in IND},
           "cut_pick": CUT, "flag_threshold": FLAG,
           "loco_prec5": float(P[5]), "base_rate": float(base), "lift5": float(P[5] / base)},
          open("data/wrpi_diamond.json", "w"), indent=1)
print(f"\nflag threshold (80th pctl of late pool dscore) = {FLAG:.2f} -> saved data/wrpi_diamond.json")
