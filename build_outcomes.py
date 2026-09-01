"""Per-prospect NFL fantasy outcomes over first 3 and first 5 seasons.
Source: nflverse weekly player_stats (fantasy_points_ppr). Emits raw components;
the blended target is assembled in the modeling scripts so it can be tuned."""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()

w = pd.read_csv("data/nfl_weekly.csv", low_memory=False)
w = w[(w.season_type == "REG") & w.position.isin(["WR", "TE", "RB"])].copy()
LAST = int(w.season.max())
print(f"outcomes available through the {LAST} NFL season")

s = (w.groupby(["player_display_name", "season"], as_index=False)
       .agg(g=("week", "nunique"), ppr=("fantasy_points_ppr", "sum"),
            rec=("receptions", "sum"), ryd=("receiving_yards", "sum"), tgt=("targets", "sum")))
s["ppg"] = s["ppr"] / s["g"].clip(lower=1)
s["key"] = s["player_display_name"].map(norm)

def block(sub, nyr):
    """metrics over a player's first `nyr` seasons"""
    sub = sub.sort_values("season").head(nyr)
    if len(sub) == 0:
        return dict(played=0, best=0., top2=0., top3=0., total=0., games=0, seasons=0)
    ppg = sorted(sub[sub.g >= 4]["ppg"].tolist(), reverse=True) or [0.]
    return dict(played=1, best=ppg[0],
                top2=np.mean(ppg[:2]), top3=np.mean(ppg[:3]),
                total=float(sub["ppr"].sum()), games=int(sub["g"].sum()), seasons=len(sub))

rows = []
# pool = every prospect in the current feature table (run build_features_v3.py first)
try:
    pool = pd.read_csv("data/features_v3.csv")[["Player", "Year"]].drop_duplicates()
except FileNotFoundError:
    pool = pd.read_csv("data/wrpi_database.csv")[["Player", "Year"]].drop_duplicates()
for _, p in pool.iterrows():
    yr, k = int(p["Year"]), norm(p["Player"])
    car = s[(s["key"] == k) & (s["season"] >= yr) & (s["season"] <= yr + 5)]
    o = {"Player": p["Player"], "Year": yr,
         "win3_full": int(yr + 2 <= LAST), "win5_full": int(yr + 4 <= LAST)}
    for tag, n in [("3", 3), ("5", 5)]:
        for kk, vv in block(car, n).items():
            o[f"{kk}{tag}"] = vv
    rows.append(o)

out = pd.DataFrame(rows)
out.to_csv("data/nfl_outcomes.csv", index=False)
full5 = out[out.win5_full == 1]
print(f"{len(out)} prospects · {len(full5)} with a full 5-yr window (classes "
      f"{full5.Year.min()}-{full5.Year.max()})")
print("\ntop 10 by best-3-of-5 avg PPR PPG:")
print(full5.sort_values("top35", ascending=False)
      .head(10)[["Player", "Year", "best5", "top35", "total5", "games5"]].to_string(index=False))
