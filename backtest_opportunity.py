"""Does landing-spot opportunity improve the post-draft model? LOCO-CV."""
import warnings; warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import RidgeCV
from sklearn.isotonic import IsotonicRegression

F = pd.read_csv("data/features_v3.csv"); O = pd.read_csv("data/nfl_outcomes.csv")
P = pd.read_csv("data/opportunity.csv")[["Player", "Year", "team_tgt_prev", "vac_tgt", "vac_ay",
                                          "vac_tgt_share", "vac_ay_share"]]
d = F.merge(O, on=["Player", "Year"]).merge(P, on=["Player", "Year"], how="left")
d = d[(d.has_college == 1) & d.nfl_entry_age.notna() & (d.win3_full == 1) &
      (d.pick < 260) & d.vac_tgt_share.notna() & (d.Year.between(2015, 2022))].reset_index(drop=True)
T = "top35"; y = d[T].values; yr = d.Year.values
print(f"{len(d)} drafted WRs 2015-2022 with opportunity data\n")

BASE = ["best_dom", "final_dom", "n_seasons_30", "best_yds", "final_ppa", "best_usage",
        "nfl_entry_age", "breakout_age", "explosion_p", "ras", "recruit_rating"]
OPP  = ["team_tgt_prev", "vac_tgt", "vac_ay", "vac_tgt_share", "vac_ay_share"]
for c in BASE + OPP + ["pick"]:
    d[c] = pd.to_numeric(d[c], errors="coerce")
med = d[BASE + OPP].median()

def loco(cols, resid=True):
    pred = np.full(len(d), np.nan)
    for c in sorted(set(yr)):
        tr, te = yr != c, yr == c
        Xtr, Xte = d.loc[tr, cols].fillna(med).values, d.loc[te, cols].fillna(med).values
        mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
        if resid:
            iso = IsotonicRegression(increasing=False, out_of_bounds="clip").fit(d.pick[tr], y[tr])
            b_te = iso.predict(d.pick[te])
            rm = RidgeCV(alphas=np.logspace(-2, 3, 20)).fit((Xtr - mu) / sd, y[tr] - iso.predict(d.pick[tr]))
            pred[te] = b_te + rm.predict((Xte - mu) / sd)
        else:
            pred[te] = RidgeCV(alphas=np.logspace(-2, 3, 20)).fit((Xtr - mu) / sd, y[tr]).predict((Xte - mu) / sd)
    rho = spearmanr(pred, y).correlation
    p15 = np.mean([(y[yr == c][np.argsort(-pred[yr == c])[:15]] >= 13).mean() for c in sorted(set(yr))])
    return rho, p15

pk = -spearmanr(d.pick, y).correlation
pkp = np.mean([(y[yr == c][np.argsort(d.pick.values[yr == c])[:15]] >= 13).mean() for c in sorted(set(yr))])
print(f"draft pick alone           Spearman {pk:+.3f}   P@15 {pkp:.2f}")
r0, p0 = loco(BASE, resid=True);  print(f"residual: base college feats     {r0:+.3f}   {p0:.2f}")
r1, p1 = loco(BASE + OPP, resid=True); print(f"residual: + opportunity          {r1:+.3f}   {p1:.2f}   (delta {r1-r0:+.3f})")
r2, p2 = loco(OPP, resid=True);   print(f"residual: opportunity ONLY       {r2:+.3f}   {p2:.2f}")
# opportunity alone vs outcome
for c in OPP:
    print(f"   {c:16s} raw Spearman vs outcome {spearmanr(d[c], y).correlation:+.3f}   partial|pick "
          f"{spearmanr(d[c] - np.polyval(np.polyfit(d.pick.rank(), d[c].rank(), 1), d.pick.rank()), y).correlation:+.3f}")
