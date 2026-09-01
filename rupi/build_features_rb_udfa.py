"""UDFA supplement: undrafted RBs with real NFL touches (>=80 career carries+
receptions, 2015-2026 rookie classes). RB is exactly the position where UDFA
hits are common (Ekeler, Mostert, Lindsay, James Robinson, Warren, Gus
Edwards...) so excluding them would starve the diamond-in-the-rough signal.
Joined by gsis_id/player_id (NOT name) to avoid namesake collisions (an early
pass on this matched "Frank Gore Jr." 2024 UDFA to his father's 16-year, 4220-
touch career via a Jr./Sr.-stripped name join)."""
import warnings; warnings.filterwarnings("ignore")
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import re, unicodedata
import numpy as np, pandas as pd
from rb_feature_lib import norm, Sources, build_row, add_athletic_percentiles

WB = "data/"
RD = "rupi/data/"

pl = pd.read_csv(WB + "players.csv", low_memory=False)
udfa = pl[(pl.position == "RB") & pl.draft_round.isna() & pl.rookie_season.between(2015, 2026)].copy()

w = pd.read_csv(WB + "nfl_weekly.csv", low_memory=False)
w = w[(w.position == "RB") & (w.season_type == "REG")]
g = w.groupby("player_id").agg(car=("carries", "sum"), rec=("receptions", "sum"),
                                ppr=("fantasy_points_ppr", "sum")).reset_index()
g["touches"] = g.car + g.rec
udfa = udfa.merge(g, left_on="gsis_id", right_on="player_id", how="left")
sig = udfa[udfa.touches >= 80].copy()
sig["key"] = sig.display_name.map(norm)
print(f"{len(sig)} UDFA RBs with >=80 career touches (out of {len(udfa)} UDFA RB rows)")

S = Sources(WB, RD)
rows = []
for _, p in sig.iterrows():
    yr = int(p.rookie_season)
    bd = pd.to_datetime(p["birth_date"], errors="coerce")
    age_hint = (pd.Timestamp(yr, 1, 1) - bd).days / 365.25 if pd.notna(bd) else np.nan
    o = {"Player": p.display_name, "Year": yr}
    o.update(build_row(p.key, yr, 270.0, age_hint, bd, S))
    rows.append(o)

F = pd.DataFrame(rows)
F.to_csv(RD + "features_rb_udfa_raw.csv", index=False)
print(F[["Player", "Year", "pick", "nfl_entry_age", "has_college", "best_dom"]].to_string(index=False))
