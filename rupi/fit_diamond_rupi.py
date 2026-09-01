"""Diamonds in the rough for RB -- an interpretable INDEX of pre-draft indicators
that, for RBs drafted after ~pick 90 (Day 3) PLUS the UDFA supplement, separates
the future fantasy assets (Kamara, Hunt, D.Johnson, Jones, Ekeler, Robinson,
Lindsay, Pacheco, Kyren Williams, Achane...) from the rest. RB draft capital runs
later than WR and the position is exactly where undrafted/Day-3 talent gets
missed, so the late pool + UDFA is the whole point here (more so than WRPI)."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression

F = pd.read_csv("rupi/data/features_rb_all.csv")
O = pd.read_csv("rupi/data/rb_outcomes_all.csv").drop(columns=["pick"])
d = F.merge(O, on=["Player", "Year"])
d = d[(d.has_college == 1) & d.nfl_entry_age.notna() & (d.win3_full == 1)].reset_index(drop=True)
d["best_ppg"] = d[["best3", "best4"]].max(axis=1)
d["sustain"] = d[["top23", "top34"]].max(axis=1)

CUT = 33   # swept {33,50,65,75,90,100}: CUT=33 (outside round 1) gave the best
           # LOCO lift (2.2x @P5 vs 1.3-1.7x elsewhere) -- Day-1 RBs already hit at
           # ~71% by draft-capital alone (see RESEARCH.md), so the real diamond
           # question for RB is "who among R2+ still hits," not just Day-3/UDFA.
late = d[d.pick >= CUT].reset_index(drop=True)
late["hit"] = ((late.best_ppg >= 13) | (late.sustain >= 11)).astype(int)
yr = late.Year.values
print(f"late pool (pick>={CUT}, incl. UDFA): {len(late)} RBs · hit rate {late.hit.mean():.1%} ({late.hit.sum()} hits)")
print("  hits:", ", ".join(late[late.hit == 1].sort_values("best_ppg", ascending=False).Player.head(30)))

IND = {
 "best_dom":          +1,
 "best_rec_ydshare":  +1,   # receiving role -- the RB-specific diamond tell
 "n_seasons_15":      +1,
 "td_rate":           +1,
 "early_declare":     +1,
 "avg_ppa":           +1,
 "best_ppa_rush":     +1,
 "best_usage":        +1,
 "career_ypc":         +1,
 "explosion_p":       +1,
 "agility_p":         +1,
 "best_long":         +1,
 "prod_over_recruit": +1,
 "best_rush_share":   +1,   # college workload/bell-cow share
 "nfl_entry_age":     -1,
 "breakout_age":      -1,
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
lr = LogisticRegression(C=0.05, max_iter=6000, class_weight="balanced").fit(Z, y)
w = pd.Series(lr.coef_[0], index=list(IND)).clip(lower=0)
w = w / w.sum() if w.sum() else pd.Series(1 / len(IND), index=list(IND))
print("\nindex weights (share):")
for k, v in w.sort_values(ascending=False).items():
    gap = ((late.loc[y == 1, k].mean() - late.loc[y == 0, k].mean()) / (late[k].std() + 1e-9)) * IND[k]
    print(f"   {k:18s} {v:.3f}   (univ. hit-miss gap {gap:+.2f})")

late["dscore"] = (Z * w.values).sum(axis=1)

def loco_prec():
    pr = {3: [], 5: [], 10: []}
    for c in sorted(set(yr)):
        tr, te = yr != c, yr == c
        if y[tr].sum() < 3: continue
        wl = LogisticRegression(C=0.05, max_iter=6000, class_weight="balanced").fit(Z[tr], y[tr]).coef_[0]
        wl = np.clip(wl, 0, None); wl = wl / wl.sum() if wl.sum() else np.ones(len(IND)) / len(IND)
        s = (Z[te].values * wl).sum(1)
        for k in pr:
            kk = min(k, te.sum())
            pr[k].append(y[te][np.argsort(-s)[:kk]].mean())
    return {k: np.mean(v) for k, v in pr.items()}
P = loco_prec()
base = late.hit.mean()
print(f"\nLOCO-CV precision@3/5/10 = {P[3]:.2f} / {P[5]:.2f} / {P[10]:.2f}   (base rate {base:.2f})   "
      f"lift@5 = {P[5]/base:.1f}x")

late["q"] = pd.qcut(late.dscore, 4, labels=["Q1", "Q2", "Q3", "Q4"])
print("\nhit rate by index quartile:")
print(late.groupby("q").hit.agg(["mean", "size"]).round(3).to_string())

late["dpct"] = late.dscore.rank(pct=True)
print("\ncanonical diamonds — index percentile within the late pool:")
for nm in ["Alvin Kamara", "Kareem Hunt", "David Johnson", "Aaron Jones", "Austin Ekeler",
           "James Robinson", "Phillip Lindsay", "Isiah Pacheco", "Kyren Williams",
           "De'Von Achane", "Chris Carson", "Jordan Howard", "Antonio Gibson", "James Conner"]:
    r = late[late.Player == nm]
    if len(r): print(f"   {nm:20s} idx pctl {r.dpct.iloc[0]:.0%}  pick {int(r.pick.iloc[0])}  hit={int(r.hit.iloc[0])}")

FLAG = float(late.dscore.quantile(0.80))
json.dump({"ind": IND, "w": {k: float(v) for k, v in w.items()},
           "mean": {k: float(mu[k]) for k in IND}, "std": {k: float(sd[k]) for k in IND},
           "median": {k: float(med[k]) for k in IND},
           "cut_pick": CUT, "flag_threshold": FLAG,
           "loco_prec5": float(P[5]), "base_rate": float(base), "lift5": float(P[5] / base)},
          open("rupi/data/rupi_diamond.json", "w"), indent=1)
print(f"\nflag threshold (80th pctl of late pool dscore) = {FLAG:.2f} -> saved data/rupi_diamond.json")
