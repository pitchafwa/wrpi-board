"""Pull CFBD season player stats, build per-player-season receiving production +
team totals + College Dominator Rating (yards-share & TD-share).
Requires env var CFBD_KEY (free key: https://collegefootballdata.com/key)."""
import json, os, datetime
import pandas as pd, numpy as np
from cfbd_get import cached as _cached

LAST_YEAR = datetime.date.today().year
os.makedirs("data/cfbd_raw", exist_ok=True)

def cached(year, cat):
    return _cached(f"/stats/player/season?year={year}&category={cat}", f"{cat}_{year}")

def wide(rows, cat):
    df = pd.DataFrame(rows)
    if df.empty: return df
    df['stat'] = pd.to_numeric(df['stat'], errors='coerce')
    w = df.pivot_table(index=['season','playerId','player','position','team','conference'],
                       columns='statType', values='stat', aggfunc='first').reset_index()
    w.columns.name = None
    return w

rec_all, rush_all = [], []
n_fail = 0
for yr in range(2004, LAST_YEAR + 1):
    try:
        rw = wide(cached(yr, 'receiving'), 'receiving'); rec_all.append(rw)
        print(yr, 'rec rows', len(rw))
    except Exception as e:
        n_fail += 1; print(yr, 'receiving FAILED', repr(e)[:80])
    try:
        rush_all.append(wide(cached(yr, 'rushing'), 'rushing'))
    except Exception as e:
        print(yr, 'rushing err', repr(e)[:80])

if not rec_all:
    import sys
    print("build_cfbd: every CFBD receiving pull failed and nothing was cached — "
          "keeping the committed data/cfbd_player_seasons.csv"); sys.exit(0)
rec = pd.concat(rec_all, ignore_index=True).rename(columns={'YDS':'rec_yds','TD':'rec_td','REC':'rec'})
rush = pd.concat(rush_all or [rec.iloc[:0]], ignore_index=True).rename(columns={'YDS':'rush_yds','TD':'rush_td','CAR':'rush_att'})
for c in ['rec_yds','rec_td','rec']:
    rec[c] = pd.to_numeric(rec[c], errors='coerce').fillna(0)
for c in ['rush_yds','rush_td']:
    if c in rush: rush[c] = pd.to_numeric(rush[c], errors='coerce').fillna(0)

m = rec.merge(rush[['season','playerId','team','rush_yds','rush_td']],
              on=['season','playerId','team'], how='left')
m[['rush_yds','rush_td']] = m[['rush_yds','rush_td']].fillna(0)

team = m.groupby(['season','team']).agg(
    team_rec_yds=('rec_yds','sum'), team_rec_td=('rec_td','sum'),
    team_rush_yds=('rush_yds','sum'), team_rush_td=('rush_td','sum')).reset_index()
m = m.merge(team, on=['season','team'], how='left')

m['yd_share'] = m['rec_yds'] / m['team_rec_yds'].replace(0,np.nan)
m['td_share'] = m['rec_td'] / m['team_rec_td'].replace(0,np.nan)
m['dominator'] = np.nanmean(np.c_[m['yd_share'], m['td_share'].fillna(m['yd_share'])], axis=1)
# scrimmage dominator
m['sc_yd_share'] = (m['rec_yds']+m['rush_yds']) / (m['team_rec_yds']+m['team_rush_yds']).replace(0,np.nan)
m['team_rec_rank'] = m.groupby(['season','team'])['rec_yds'].rank(ascending=False, method='min')

m.to_csv("data/cfbd_player_seasons.csv", index=False)
print("\nsaved data/cfbd_player_seasons.csv", m.shape)
print(m.sort_values('rec_yds',ascending=False).head(8)[
    ['season','team','player','rec_yds','rec_td','yd_share','td_share','dominator','team_rec_rank']].to_string())
