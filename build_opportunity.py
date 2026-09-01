"""Landing-spot opportunity, computed from nflverse: for each drafted rookie, the
targets & air yards VACATED by the drafting team the prior season (players who were
on the roster in Y-1 but not Y), plus prior-year team pass volume."""
import warnings; warnings.filterwarnings("ignore")
import io, gzip, urllib.request, re, unicodedata
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()

B = "https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{}.csv"
rost = []
for y in range(2014, 2026):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(B.format(y), headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()
        r = pd.read_csv(io.BytesIO(raw), low_memory=False)
        r = r[r.week <= 4]                                   # early-season roster
        rost.append(r[["season", "team", "full_name", "position"]].drop_duplicates())
        print(f"roster {y}: {len(r)} rows")
    except Exception as e:
        print("roster", y, repr(e)[:60])
R = pd.concat(rost, ignore_index=True)
R["key"] = R.full_name.map(norm)
R["team"] = R.team.replace({"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "LVR": "LV"})

w = pd.read_csv("data/nfl_weekly.csv", low_memory=False)
w = w[(w.season_type == "REG") & w.position.isin(["WR", "TE", "RB"])]
tm = w.rename(columns={"recent_team": "team"})
tm["team"] = tm["team"].replace({"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "LVR": "LV"})
tm["key"] = tm.player_display_name.map(norm)
ps = (tm.groupby(["team", "season", "key"], as_index=False)
        .agg(tgt=("targets", "sum"), ay=("receiving_air_yards", "sum")))

def roster_set(team, yr):
    return set(R[(R.team == team) & (R.season == yr)].key)

draft = pd.read_csv("data/draft_picks.csv", low_memory=False)
draft = draft[draft.position == "WR"][["season", "pfr_player_name", "team", "pick"]].copy()
draft["team"] = draft["team"].replace({"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "LVR": "LV"})

rows = []
for _, r in draft.iterrows():
    yr, team = int(r.season), r.team
    prev = ps[(ps.team == team) & (ps.season == yr - 1)]
    o = {"Player": r.pfr_player_name, "Year": yr, "key": norm(r.pfr_player_name)}
    if len(prev):
        ret = roster_set(team, yr)
        gone = prev[~prev.key.isin(ret)]
        o["team_tgt_prev"] = float(prev.tgt.sum())
        o["team_ay_prev"] = float(prev.ay.sum())
        o["vac_tgt"] = float(gone.tgt.sum())
        o["vac_ay"] = float(gone.ay.sum())
        o["vac_tgt_share"] = o["vac_tgt"] / max(o["team_tgt_prev"], 1)
        o["vac_ay_share"] = o["vac_ay"] / max(o["team_ay_prev"], 1)
    rows.append(o)
O = pd.DataFrame(rows)
O.to_csv("data/opportunity.csv", index=False)
print(f"\nopportunity.csv: {O.vac_tgt.notna().sum()} of {len(O)} drafted WRs with prior-team data")
print(O.dropna().sort_values("vac_tgt_share", ascending=False).head(8)[
    ["Player", "Year", "team_tgt_prev", "vac_tgt", "vac_tgt_share"]].to_string(index=False))
