"""Head-to-head tiebreaker model: logistic on feature-differences of WRs drafted
within ~20 picks of each other. Reduces to one linear 'tiebreaker score' per player;
P(A better than B) = sigmoid(tb_A - tb_B)."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from itertools import combinations

F = pd.read_csv("data/features_v3.csv"); O = pd.read_csv("data/nfl_outcomes.csv")
d = F.merge(O, on=["Player", "Year"])
d = d[(d.has_college == 1) & d.nfl_entry_age.notna() & (d.win3_full == 1)].reset_index(drop=True)

FEATS = ["best_dom", "final_dom", "dom_age20", "n_seasons_30", "best_yds", "career_yds",
         "final_ppa", "best_ppa", "best_usage", "nfl_entry_age", "breakout_age", "early_declare",
         "ras", "explosion_p", "speed_score", "weight", "catch_radius",
         "team_sp_off", "team_sp_overall", "recruit_rating", "prod_over_recruit",
         "was_returner", "ret_td", "col_qb_ypa", "final_spike", "dom_growth"]
FEATS = [c for c in FEATS if c in d.columns]
for c in FEATS: d[c] = pd.to_numeric(d[c], errors="coerce")
med = d[FEATS].median()
Z = (d[FEATS].fillna(med) - d[FEATS].fillna(med).mean()) / (d[FEATS].fillna(med).std() + 1e-9)
zmean = d[FEATS].fillna(med).mean().to_dict()
zstd = (d[FEATS].fillna(med).std() + 1e-9).to_dict()

GAP = 20
Xtr, ytr = [], []
for i, j in combinations(range(len(d)), 2):
    if abs(d.pick[i] - d.pick[j]) > GAP: continue
    if abs(d.top35[i] - d.top35[j]) < 2: continue
    diff = Z.iloc[i].values - Z.iloc[j].values
    lab = int(d.top35[i] > d.top35[j])
    Xtr += [diff, -diff]; ytr += [lab, 1 - lab]
Xtr = np.array(Xtr); ytr = np.array(ytr)
lr = LogisticRegression(C=0.08, max_iter=4000).fit(Xtr, ytr)
w = pd.Series(lr.coef_[0], index=FEATS)

# leave-one-class-out accuracy
yr = d.Year.values
acc = tot = 0
for c in sorted(set(yr)):
    tr, te = yr != c, yr == c
    Xt, yt = [], []
    idx = np.where(tr)[0]
    for a, b in combinations(idx, 2):
        if abs(d.pick[a] - d.pick[b]) > GAP or abs(d.top35[a] - d.top35[b]) < 2: continue
        df = Z.iloc[a].values - Z.iloc[b].values
        Xt += [df, -df]; yt += [int(d.top35[a] > d.top35[b]), int(d.top35[b] > d.top35[a])]
    m = LogisticRegression(C=0.08, max_iter=4000).fit(np.array(Xt), np.array(yt))
    ii = np.where(te)[0]
    for a, b in combinations(ii, 2):
        if abs(d.pick[a] - d.pick[b]) > GAP or abs(d.top35[a] - d.top35[b]) < 2: continue
        df = (Z.iloc[a].values - Z.iloc[b].values)
        acc += int((m.predict_proba(df.reshape(1, -1))[0, 1] > .5) == (d.top35[a] > d.top35[b])); tot += 1
print(f"tiebreaker LOCO accuracy: {acc/tot:.3f} over {tot} pairs (|pick diff|<={GAP})")
print("\ntop drivers (standardized logistic weight):")
for k, v in w.sort_values(key=abs, ascending=False).head(12).items():
    print(f"  {k:18s} {v:+.3f}")

json.dump({"feats": FEATS, "w": w.to_dict(), "mean": zmean, "std": zstd,
           "loco_acc": acc / tot, "gap": GAP},
          open("data/wrpi_tiebreaker.json", "w"), indent=1)
print("\nsaved data/wrpi_tiebreaker.json")
