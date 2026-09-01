"""Download the raw input feeds (kept out of git; refreshed every pipeline run)."""
import urllib.request, os
os.makedirs("data", exist_ok=True)
FILES = {
    "data/combine.csv":         "https://github.com/nflverse/nflverse-data/releases/download/combine/combine.csv",
    "data/draft_picks.csv":     "https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv",
    "data/players.csv":         "https://github.com/nflverse/nflverse-data/releases/download/players/players.csv",
    "data/combine_pro_day.csv": "https://raw.githubusercontent.com/array-carpenter/nfl-draft-data/HEAD/data/combine_pro_day.csv",
}
for path, url in FILES.items():
    d = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120).read()
    open(path, "wb").write(d)
    print(f"{path}  {len(d):,} bytes")
