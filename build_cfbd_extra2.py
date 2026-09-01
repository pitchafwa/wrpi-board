"""CFBD wave 2: return usage, team recruiting rank, college QB quality, transfer portal."""
import warnings; warnings.filterwarnings("ignore")
import os, json, datetime
import pandas as pd
from cfbd_get import cached

def get(path, cache):
    try:
        return cached(path, cache)
    except Exception as e:
        print("  !", cache, repr(e)[:70]); return []

def flat_season(rows):
    df = pd.DataFrame(rows)
    if df.empty: return df
    df["stat"] = pd.to_numeric(df["stat"], errors="coerce")
    return df.pivot_table(index=["season", "playerId", "player", "team"], columns="statType",
                          values="stat", aggfunc="first").reset_index()

ret, rec_t, qb, portal = [], [], [], []
for yr in range(2011, datetime.date.today().year + 1):
    for cat in ("kickReturns", "puntReturns"):
        w = flat_season(get(f"/stats/player/season?year={yr}&category={cat}", f"{cat}_{yr}"))
        if len(w): w["kind"] = cat; ret.append(w)
    for x in get(f"/recruiting/teams?year={yr}", f"recteam_{yr}"):
        rec_t.append({"year": yr, "team": x.get("team"), "rec_rank": x.get("rank"), "rec_points": x.get("points")})
    qw = flat_season(get(f"/stats/player/season?year={yr}&category=passing", f"passing_{yr}"))
    if len(qw): qb.append(qw)
    for x in get(f"/player/portal?year={yr}", f"portal_{yr}"):
        portal.append({"year": yr, "name": f"{x.get('firstName','')} {x.get('lastName','')}".strip(),
                       "pos": x.get("position"), "origin": x.get("origin"), "dest": x.get("destination"),
                       "stars": x.get("stars"), "rating": x.get("rating")})
    print(f"{yr} done")

pd.concat(ret, ignore_index=True).to_csv("data/cfbd_returns.csv", index=False)
pd.DataFrame(rec_t).to_csv("data/cfbd_recteam.csv", index=False)
pd.concat(qb, ignore_index=True).to_csv("data/cfbd_qb.csv", index=False)
pd.DataFrame(portal).to_csv("data/cfbd_portal.csv", index=False)
print("saved cfbd_returns / cfbd_recteam / cfbd_qb / cfbd_portal")
