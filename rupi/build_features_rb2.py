"""Drafted-RB feature table, via the shared rb_feature_lib builder.
Run from the repo root: `python rupi/build_features_rb2.py`."""
import warnings; warnings.filterwarnings("ignore")
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rb_feature_lib import norm, Sources, build_row, add_athletic_percentiles

WB = "data/"
RD = "rupi/data/"

dr = pd.read_csv(WB + "draft_picks.csv", low_memory=False); dr["key"] = dr.pfr_player_name.map(norm)
pool = dr[(dr.position == "RB") & dr.season.between(2015, 2026)].copy()
pool = pool.rename(columns={"pfr_player_name": "Player", "season": "Year"})
pl = pd.read_csv(WB + "players.csv", low_memory=False); pl["key"] = pl.display_name.map(norm)

S = Sources(WB, RD)
rows = []
for _, p in pool.iterrows():
    k, yr = p.key, int(p.Year)
    _pc = pl[pl.key == k].copy()
    if len(_pc):
        _yy = _pc["draft_year"].fillna(_pc["rookie_season"])
        _pc["_score"] = (_yy - yr).abs(); _pc = _pc[_pc._score <= 1]
    plR = _pc.sort_values("_score").iloc[0] if len(_pc) else None
    bd = pd.to_datetime(plR["birth_date"], errors="coerce") if plR is not None else pd.NaT
    o = {"Player": p.Player, "Year": yr}
    o.update(build_row(k, yr, p["pick"], float(p["age"]) if pd.notna(p["age"]) else np.nan, bd, S))
    rows.append(o)

F = pd.DataFrame(rows)
F = add_athletic_percentiles(F)
F.to_csv(RD + "features_rb.csv", index=False)
print(f"features_rb.csv (drafted)  {F.shape[0]} x {F.shape[1]}")
for c in ["best_dom", "breakout_age", "best_ppa", "recruit_stars", "ras", "best_rec_ydshare"]:
    print(f"  {c:18s} {F[c].notna().sum()}/{len(F)}")
