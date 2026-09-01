"""RB-appropriate CFBD season table: keeps rush ATTEMPTS/YPC/LONG (the WR build
drops them) and computes a SCRIMMAGE dominator (rush+rec yards AND TDs). Reuses
the raw JSON cached by build_cfbd.py in data/cfbd_raw/ -- no new API calls.
Run from the repo root."""
import json, os
import pandas as pd, numpy as np

RAW = "data/cfbd_raw"
OUT = "rbpi/data"
os.makedirs(OUT, exist_ok=True)

def wide(cat, year):
    fn = f"{RAW}/{cat}_{year}.json"
    if not os.path.exists(fn):
        return pd.DataFrame()
    rows = json.load(open(fn))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["stat"] = pd.to_numeric(df["stat"], errors="coerce")
    w = df.pivot_table(index=["season", "playerId", "player", "position", "team", "conference"],
                        columns="statType", values="stat", aggfunc="first").reset_index()
    w.columns.name = None
    return w

rec_all, rush_all = [], []
for yr in range(2004, 2028):
    rec_all.append(wide("receiving", yr))
    rush_all.append(wide("rushing", yr))
rec = pd.concat([d for d in rec_all if not d.empty], ignore_index=True)
rush = pd.concat([d for d in rush_all if not d.empty], ignore_index=True)

rec = rec.rename(columns={"YDS": "rec_yds", "TD": "rec_td", "REC": "rec", "LONG": "rec_long", "YPR": "ypr"})
rush = rush.rename(columns={"YDS": "rush_yds", "TD": "rush_td", "CAR": "rush_att",
                             "LONG": "rush_long", "YPC": "ypc"})
for c in ["rec_yds", "rec_td", "rec", "rec_long"]:
    if c in rec: rec[c] = pd.to_numeric(rec[c], errors="coerce").fillna(0)
for c in ["rush_yds", "rush_td", "rush_att", "rush_long"]:
    if c in rush: rush[c] = pd.to_numeric(rush[c], errors="coerce").fillna(0)

m = rush.merge(rec[["season", "playerId", "team", "rec", "rec_yds", "rec_td", "rec_long"]],
               on=["season", "playerId", "team"], how="outer")
for c in ["player", "position", "conference"]:
    m[c] = m[c].combine_first(m[c])
m[["rush_yds", "rush_td", "rush_att", "rec", "rec_yds", "rec_td"]] = \
    m[["rush_yds", "rush_td", "rush_att", "rec", "rec_yds", "rec_td"]].fillna(0)
m["ypc"] = np.where(m.rush_att > 0, m.rush_yds / m.rush_att, np.nan)
m["ypr"] = np.where(m.rec > 0, m.rec_yds / m.rec, np.nan)
m["scrim_yds"] = m.rush_yds + m.rec_yds
m["scrim_td"] = m.rush_td + m.rec_td

team = m.groupby(["season", "team"]).agg(
    team_rush_yds=("rush_yds", "sum"), team_rush_td=("rush_td", "sum"),
    team_rec_yds=("rec_yds", "sum"), team_rec_td=("rec_td", "sum"),
    team_rush_att=("rush_att", "sum")).reset_index()
team["team_scrim_yds"] = team.team_rush_yds + team.team_rec_yds
team["team_scrim_td"] = team.team_rush_td + team.team_rec_td
m = m.merge(team, on=["season", "team"], how="left")

m["rush_yd_share"] = m.rush_yds / m.team_rush_yds.replace(0, np.nan)
m["rec_yd_share"] = m.rec_yds / m.team_rec_yds.replace(0, np.nan)
m["scrim_yd_share"] = m.scrim_yds / m.team_scrim_yds.replace(0, np.nan)
m["scrim_td_share"] = m.scrim_td / m.team_scrim_td.replace(0, np.nan)
m["rush_share"] = m.rush_att / m.team_rush_att.replace(0, np.nan)
m["dominator"] = np.nanmean(np.c_[m.scrim_yd_share, m.scrim_td_share.fillna(m.scrim_yd_share)], axis=1)
m["team_scrim_rank"] = m.groupby(["season", "team"])["scrim_yds"].rank(ascending=False, method="min")

m.to_csv(f"{OUT}/cfbd_rb_seasons.csv", index=False)
print(f"cfbd_rb_seasons.csv  {m.shape}  seasons {int(m.season.min())}-{int(m.season.max())}")
