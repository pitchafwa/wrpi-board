"""Per-prospect NFL fantasy outcomes for RBs, front-loaded for RB shelf life:
first 3 and first 4 seasons (not 3/5 like WRPI). Source: nflverse weekly
player_stats. Pool = all drafted RBs 2015-2026 (draft_picks.csv)."""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()

WB = ""
OUT = "rupi/data"

w = pd.read_csv(WB + "data/nfl_weekly.csv", low_memory=False)
w = w[(w.season_type == "REG") & (w.position == "RB")].copy()
LAST = int(w.season.max())
print(f"outcomes available through the {LAST} NFL season")

s = (w.groupby(["player_display_name", "season"], as_index=False)
       .agg(g=("week", "nunique"), ppr=("fantasy_points_ppr", "sum"),
            rec=("receptions", "sum"), ryd=("receiving_yards", "sum"), tgt=("targets", "sum"),
            car=("carries", "sum"), ruy=("rushing_yards", "sum")))
s["ppg"] = s["ppr"] / s["g"].clip(lower=1)
s["key"] = s["player_display_name"].map(norm)

def block(sub, nyr):
    sub = sub.sort_values("season").head(nyr)
    if len(sub) == 0:
        return dict(played=0, best=0., top2=0., top3=0., total=0., games=0, seasons=0, touches=0)
    ppg = sorted(sub[sub.g >= 4]["ppg"].tolist(), reverse=True) or [0.]
    return dict(played=1, best=ppg[0],
                top2=np.mean(ppg[:2]), top3=np.mean(ppg[:3]),
                total=float(sub["ppr"].sum()), games=int(sub["g"].sum()), seasons=len(sub),
                touches=int((sub["car"] + sub["rec"]).sum()))

dp = pd.read_csv(WB + "data/draft_picks.csv")
pool = dp[(dp.position == "RB") & dp.season.between(2015, 2026)][
    ["pfr_player_name", "season", "pick", "age"]].rename(columns={"pfr_player_name": "Player", "season": "Year"})

rows = []
for _, p in pool.iterrows():
    yr, k = int(p["Year"]), norm(p["Player"])
    car = s[(s["key"] == k) & (s["season"] >= yr) & (s["season"] <= yr + 4)]
    o = {"Player": p["Player"], "Year": yr, "pick": p["pick"], "draft_age": p["age"],
         "win3_full": int(yr + 2 <= LAST), "win4_full": int(yr + 3 <= LAST)}
    for tag, n in [("3", 3), ("4", 4)]:
        for kk, vv in block(car, n).items():
            o[f"{kk}{tag}"] = vv
    rows.append(o)

out = pd.DataFrame(rows)
# primary target: mean of best-2-of-first-3 PPR PPG  (front-loaded shelf life)
out["rb_top34"] = out["top23"]
# secondary: best-3-of-first-4, total points yrs 1-3, single best season (ceiling) yrs 1-4
out["rb_top44"] = out["top34"]
out["rb_early3"] = out["total3"]
out["rb_best"] = out[["best3", "best4"]].max(axis=1)  # best season within first 4 yrs

out.to_csv(f"{OUT}/rb_outcomes.csv", index=False)
full3 = out[out.win3_full == 1]
print(f"{len(out)} drafted RBs 2015-2026 · {len(full3)} with a full 3-yr window "
      f"(classes {full3.Year.min()}-{full3.Year.max()})")
print("\ntop 12 by rb_top34 (best-2-of-first-3 PPR PPG):")
print(full3.sort_values("rb_top34", ascending=False)
      .head(12)[["Player", "Year", "pick", "best3", "rb_top34", "rb_top44", "games3"]].to_string(index=False))
