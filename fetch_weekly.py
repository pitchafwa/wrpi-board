"""Build data/nfl_weekly.csv from scratch for the pipeline.

Base = nflverse legacy `player_stats` release (1999 .. its last season, one file).
Top-up = the newer `stats_player` release, one file per season, for every year
after the legacy file ends through the current calendar year. Years that 404
(season not started / not yet published) are skipped. Generalises add_2025.py so
new NFL seasons roll in on their own.
"""
import warnings; warnings.filterwarnings("ignore")
import io, urllib.request, datetime
import pandas as pd

B = "https://github.com/nflverse/nflverse-data/releases/download/"

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=180).read()

base = pd.read_csv(io.BytesIO(get(B + "player_stats/player_stats.csv")), low_memory=False)
legacy_last = int(base.season.max())
frames = [base]
this_year = datetime.date.today().year

for yr in range(legacy_last + 1, this_year + 1):
    try:
        new = pd.read_csv(io.BytesIO(get(B + f"stats_player/stats_player_week_{yr}.csv")), low_memory=False)
    except Exception as e:
        print(f"  {yr}: not available yet ({repr(e)[:60]})")
        continue
    if "recent_team" not in new.columns and "team" in new.columns:
        new = new.rename(columns={"team": "recent_team"})
    keep = [c for c in base.columns if c in new.columns]
    frames.append(new[keep])
    print(f"  {yr}: +{len(new):,} rows  ({len(keep)}/{len(base.columns)} legacy cols matched)")

out = pd.concat(frames, ignore_index=True)
# de-dupe defensively (a season could appear in both feeds during a transition)
out = out.drop_duplicates(subset=[c for c in ("player_id", "season", "week", "season_type") if c in out.columns])
out.to_csv("data/nfl_weekly.csv", index=False)
print(f"nfl_weekly.csv  {int(out.season.min())}-{int(out.season.max())}  {len(out):,} rows")
