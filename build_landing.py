"""Landing-spot opportunity features: for each drafted prospect, the drafting
team's PRIOR-season passing profile (all knowable before the rookie debuts).
"""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()

w = pd.read_csv("data/nfl_weekly.csv", low_memory=False)
w = w[(w.season_type == "REG")].copy()

# team-season passing volume
tm = (w.groupby(["recent_team", "season"], as_index=False)
        .agg(team_pass_att=("attempts", "sum"), team_pass_yd=("passing_yards", "sum")))

# WR target distribution per team-season
wr = w[w.position == "WR"].groupby(["recent_team", "season", "player_display_name"], as_index=False).agg(tgt=("targets", "sum"))
def conc(grp):
    t = grp.tgt.sort_values(ascending=False).values
    tot = t.sum()
    return pd.Series({"wr_tgt_total": tot,
                      "wr1_share": (t[0] / tot) if tot else np.nan,
                      "top3_share": (t[:3].sum() / tot) if tot else np.nan,
                      "n_wr_50tgt": int((grp.tgt >= 50).sum())})
wc = wr.groupby(["recent_team", "season"]).apply(conc).reset_index()

team = tm.merge(wc, on=["recent_team", "season"], how="outer")

draft = pd.read_csv("data/draft_picks.csv", low_memory=False)
draft = draft[draft.position == "WR"][["season", "pfr_player_name", "team", "pick"]].copy()
draft["key"] = draft.pfr_player_name.map(norm)

# nflverse draft team abbreviations vs weekly recent_team — mostly match; fix a few
FIX = {"OAK": "LV", "SD": "LAC", "STL": "LA", "LAR": "LA", "WAS": "WAS", "LVR": "LV"}
draft["team"] = draft["team"].replace(FIX)
team["recent_team"] = team["recent_team"].replace(FIX)

rows = []
for _, r in draft.iterrows():
    yr = int(r.season); tprev = team[(team.recent_team == r.team) & (team.season == yr - 1)]
    o = {"Player": r.pfr_player_name, "Year": yr, "key": r.key}
    if len(tprev):
        t = tprev.iloc[0]
        o.update(land_pass_att=t.team_pass_att, land_wr_tgt=t.wr_tgt_total,
                 land_wr1_share=t.wr1_share, land_top3_share=t.top3_share, land_n_wr50=t.n_wr_50tgt)
    rows.append(o)

L = pd.DataFrame(rows)
L.to_csv("data/landing.csv", index=False)
print(f"landing.csv: {len(L)} drafted WRs, {L.land_pass_att.notna().sum()} with prior-team data")
print(L.dropna().sort_values("land_wr1_share").head(6)[["Player", "Year", "land_pass_att", "land_wr1_share", "land_top3_share"]].to_string(index=False))
