"""Pull CFBD season player stats, build per-player-season receiving production +
team totals + College Dominator Rating (yards-share & TD-share).
Requires env var CFBD_KEY (free key: https://collegefootballdata.com/key)."""
import urllib.request, json, os, time, datetime
import pandas as pd, numpy as np

KEY = os.environ["CFBD_KEY"].strip()
LAST_YEAR = datetime.date.today().year
os.makedirs("data/cfbd_raw", exist_ok=True)

def get(path):
    req = urllib.request.Request('https://api.collegefootballdata.com'+path,
                                 headers={'Authorization':'Bearer '+KEY,'User-Agent':'Mozilla/5.0'})
    return json.loads(urllib.request.urlopen(req, timeout=90).read())

def cached(year, cat):
    fn = f"data/cfbd_raw/{cat}_{year}.json"
    if not os.path.exists(fn):
        d = get(f"/stats/player/season?year={year}&category={cat}")
        json.dump(d, open(fn,'w'))
        time.sleep(0.6)
    return json.load(open(fn))

def wide(rows, cat):
    df = pd.DataFrame(rows)
    if df.empty: return df
    df['stat'] = pd.to_numeric(df['stat'], errors='coerce')
    w = df.pivot_table(index=['season','playerId','player','position','team','conference'],
                       columns='statType', values='stat', aggfunc='first').reset_index()
    w.columns.name = None
    return w

rec_all, rush_all = [], []
for yr in range(2004, LAST_YEAR + 1):
    rw = wide(cached(yr,'receiving'), 'receiving')
    rec_all.append(rw)
    try:
        uw = wide(cached(yr,'rushing'), 'rushing')
        rush_all.append(uw)
    except Exception as e:
        print(yr,'rushing err', e)
    print(yr, 'rec rows', len(rw))

rec = pd.concat(rec_all, ignore_index=True).rename(columns={'YDS':'rec_yds','TD':'rec_td','REC':'rec'})
rush = pd.concat(rush_all, ignore_index=True).rename(columns={'YDS':'rush_yds','TD':'rush_td','CAR':'rush_att'})
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
