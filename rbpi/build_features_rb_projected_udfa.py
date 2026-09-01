"""Prospective UDFAs: RBs the league brought to the Combine (i.e. draftable-
calibre, "on our radar") who then went UNDRAFTED and don't yet have enough NFL
touches to show up in the retrospective supplement. Keeps them on the board so a
late rookie-draft flier the model likes is still visible. Tagged
udfa_type="projected". Run from the repo root.

Recent classes only (2023+). A projected-pool RB who later logs >=80 NFL touches
gets picked up (and overwritten) by build_features_rb_udfa.py instead.
"""
import warnings; warnings.filterwarnings("ignore")
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from rb_feature_lib import norm, Sources, build_row

WB = "data/"
RD = "rbpi/data/"
FIRST_CLASS = 2023

comb = pd.read_csv(WB + "combine.csv")
comb = comb[(comb.pos == "RB") & (comb.season >= FIRST_CLASS)].copy()
comb["key"] = comb.player_name.map(norm)

dr = pd.read_csv(WB + "draft_picks.csv", low_memory=False)
dr = dr[dr.position == "RB"]
drafted_key = {(int(r.season), norm(r.pfr_player_name)) for _, r in dr.iterrows()}
drafted_pfr = set(dr.pfr_player_id.dropna())
drafted_cfb = set(dr.cfb_player_id.dropna())

retro = set()
_rp = RD + "features_rb_udfa_raw.csv"
if os.path.exists(_rp):
    retro = {(int(r.Year), norm(r.Player)) for _, r in pd.read_csv(_rp).iterrows()}

pl = pd.read_csv(WB + "players.csv", low_memory=False); pl["key"] = pl.display_name.map(norm)
S = Sources(WB, RD)

rows = []
for _, c in comb.iterrows():
    yr, k = int(c.season), c.key
    # drafted if: combine's own draft columns are filled, OR id/name matches a draft pick
    if pd.notna(c.get("draft_ovr")) or pd.notna(c.get("draft_round")):
        continue
    if (c.get("pfr_id") in drafted_pfr) or (c.get("cfb_id") in drafted_cfb):
        continue
    if (yr, k) in drafted_key or (yr, k) in retro:
        continue
    _pc = pl[pl.key == k].copy()
    if len(_pc):
        _yy = _pc["draft_year"].fillna(_pc["rookie_season"])
        _pc["_s"] = (_yy - yr).abs(); _pc = _pc[_pc._s <= 1]
    plR = _pc.sort_values("_s").iloc[0] if len(_pc) else None
    bd = pd.to_datetime(plR["birth_date"], errors="coerce") if plR is not None else pd.NaT
    age_hint = (pd.Timestamp(yr, 1, 1) - bd).days / 365.25 if pd.notna(bd) else np.nan
    o = {"Player": c.player_name, "Year": yr}
    o.update(build_row(k, yr, 270.0, age_hint, bd, S))
    rows.append(o)

F = pd.DataFrame(rows)
F.to_csv(RD + "features_rb_projected_udfa_raw.csv", index=False)
print(f"prospective UDFAs (combine RB, {FIRST_CLASS}+, undrafted, not yet in retro set): {len(F)}")
if len(F):
    print(F[["Player", "Year", "has_college", "best_dom", "nfl_entry_age"]].to_string(index=False))
