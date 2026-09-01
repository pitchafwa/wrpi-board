"""Append the 2025 NFL season (nflverse newer 'stats_player' release) to nfl_weekly.csv
+ pull 2025 NGS receiving + snap counts if available, so outcomes run through 2025."""
import warnings; warnings.filterwarnings("ignore")
import io, gzip, urllib.request
import pandas as pd

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=90).read()

B = "https://github.com/nflverse/nflverse-data/releases/download/"

# ---- weekly player stats 2025 ----
new = pd.read_csv(io.BytesIO(get(B + "stats_player/stats_player_week_2025.csv")), low_memory=False)
old = pd.read_csv("data/nfl_weekly.csv", low_memory=False)
if "recent_team" in old.columns and "recent_team" not in new.columns and "team" in new.columns:
    new = new.rename(columns={"team": "recent_team"})
keep = [c for c in old.columns if c in new.columns]
merged = pd.concat([old[old.season != 2025], new[keep]], ignore_index=True)
merged.to_csv("data/nfl_weekly.csv", index=False)
print(f"nfl_weekly.csv now {merged.season.min()}-{merged.season.max()}, 2025 rows {(merged.season==2025).sum()}")

# ---- NGS receiving 2025 (best effort) ----
try:
    raw = get(B + "nextgen_stats/ngs_2025_receiving.csv.gz")
    open("data/ngs_rec_2025.csv", "wb").write(gzip.decompress(raw)); print("ngs_rec_2025.csv ok")
except Exception as e:
    print("ngs 2025:", repr(e)[:60])
# ---- snaps 2025 ----
try:
    raw = get(B + "snap_counts/snap_counts_2025.csv.gz")
    open("data/snaps_2025.csv", "wb").write(gzip.decompress(raw)); print("snaps_2025.csv ok")
except Exception as e:
    print("snaps 2025:", repr(e)[:60])
