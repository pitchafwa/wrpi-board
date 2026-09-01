"""Merge drafted RBs + UDFA supplement into one pool, compute athletic
percentiles ONCE across the combined pool (so RAS/explosion are comparable),
and build outcomes for the combined set."""
import warnings; warnings.filterwarnings("ignore")
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re, unicodedata
import numpy as np, pandas as pd
from rb_feature_lib import norm, add_athletic_percentiles

RD = "rbpi/data/"
WB = "data/"

drafted = pd.read_csv(RD + "features_rb.csv")
udfa = pd.read_csv(RD + "features_rb_udfa_raw.csv")
_pp = RD + "features_rb_projected_udfa_raw.csv"
proj = pd.read_csv(_pp) if os.path.exists(_pp) else pd.DataFrame(columns=udfa.columns)
# drop the percentile/RAS cols from the drafted file (recomputed below on the merged pool)
drop_c = [c for c in drafted.columns if c.endswith("_p") or c in
          ("ras", "explosion_p", "agility_p", "prod_p", "recruit_p", "prod_over_recruit")]
drafted = drafted.drop(columns=drop_c)
drafted["is_udfa"] = 0;  drafted["udfa_type"] = ""
udfa["is_udfa"] = 1;     udfa["udfa_type"] = "retro"
proj["is_udfa"] = 1;     proj["udfa_type"] = "projected"
# a projected UDFA who later logged real touches is already in `udfa` -> drop the dup
_have = {(r.Player, int(r.Year)) for _, r in pd.concat([drafted, udfa]).iterrows()}
proj = proj[~proj.apply(lambda r: (r.Player, int(r.Year)) in _have, axis=1)]
F = pd.concat([drafted, udfa, proj], ignore_index=True)
F = F.drop_duplicates(subset=["Player", "Year"], keep="first")
F = add_athletic_percentiles(F)
F.to_csv(RD + "features_rb_all.csv", index=False)
print(f"combined pool: {len(F)}  ({(F.udfa_type=='').sum()} drafted + "
      f"{(F.udfa_type=='retro').sum()} retro-UDFA + {(F.udfa_type=='projected').sum()} projected-UDFA)")
udfa = pd.concat([udfa, proj], ignore_index=True)   # both get outcome rows below

# ---- outcomes for the UDFA rows, same block() logic as build_outcomes_rb.py ----
w = pd.read_csv(WB + "nfl_weekly.csv", low_memory=False)
w = w[(w.season_type == "REG") & (w.position == "RB")].copy()
LAST = int(w.season.max())
s = (w.groupby(["player_display_name", "season"], as_index=False)
       .agg(g=("week", "nunique"), ppr=("fantasy_points_ppr", "sum")))
s["ppg"] = s["ppr"] / s["g"].clip(lower=1)
s["key"] = s["player_display_name"].map(norm)

def block(sub, nyr):
    sub = sub.sort_values("season").head(nyr)
    if len(sub) == 0:
        return dict(played=0, best=0., top2=0., top3=0., total=0., games=0, seasons=0)
    ppg = sorted(sub[sub.g >= 4]["ppg"].tolist(), reverse=True) or [0.]
    return dict(played=1, best=ppg[0], top2=np.mean(ppg[:2]), top3=np.mean(ppg[:3]),
                total=float(sub["ppr"].sum()), games=int(sub["g"].sum()), seasons=len(sub))

drafted_out = pd.read_csv(RD + "rb_outcomes.csv")
rows = []
for _, p in udfa.iterrows():
    yr, k = int(p.Year), norm(p.Player)
    car = s[(s["key"] == k) & (s["season"] >= yr) & (s["season"] <= yr + 4)]
    o = {"Player": p.Player, "Year": yr, "pick": 270.0, "draft_age": np.nan,
         "win3_full": int(yr + 2 <= LAST), "win4_full": int(yr + 3 <= LAST)}
    for tag, n in [("3", 3), ("4", 4)]:
        for kk, vv in block(car, n).items():
            o[f"{kk}{tag}"] = vv
    rows.append(o)
udfa_out = pd.DataFrame(rows)
udfa_out["rb_top34"] = udfa_out["top23"]; udfa_out["rb_top44"] = udfa_out["top34"]
udfa_out["rb_early3"] = udfa_out["total3"]; udfa_out["rb_best"] = udfa_out[["best3", "best4"]].max(axis=1)
O = pd.concat([drafted_out, udfa_out], ignore_index=True)
O.to_csv(RD + "rb_outcomes_all.csv", index=False)
print(f"combined outcomes: {len(O)}")
print("\ntop UDFA hits by rb_top34:")
print(udfa_out.sort_values("rb_top34", ascending=False).head(10)[["Player", "Year", "rb_top34"]].to_string(index=False))
