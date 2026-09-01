"""Rebuild clean cfbd_ppa / cfbd_usage / cfbd_recruiting from the raw JSON cached
by build_cfbd_extra.py -- the processed cfbd_*.csv it writes are silently
truncated (~40% of rows lost, incl. most RBs). Keeps the RUSH split + position.
Run from the repo root. (WRPI still reads the truncated files -- backlog audit.)"""
import json, os
import pandas as pd

RAW = "data/cfbd_raw"
OUT = "rupi/data"
os.makedirs(OUT, exist_ok=True)
YEARS = range(2011, 2028)

def load(prefix):
    frames = []
    for yr in YEARS:
        fn = f"{RAW}/{prefix}_{yr}.json"
        if not os.path.exists(fn):
            continue
        d = json.load(open(fn))
        df = pd.json_normalize(d, sep="_")
        if not df.empty:
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

# ---- PPA ----
p = load("ppa")
p = p.rename(columns={"averagePPA_all": "avg_ppa", "averagePPA_pass": "avg_ppa_pass",
                       "averagePPA_rush": "avg_ppa_rush", "totalPPA_all": "total_ppa",
                       "totalPPA_rush": "total_ppa_rush", "id": "athleteId", "season": "year"})
keep = ["year", "athleteId", "name", "position", "team", "conference",
        "avg_ppa", "avg_ppa_pass", "avg_ppa_rush", "total_ppa", "total_ppa_rush"]
PPA = p[[c for c in keep if c in p]].copy()
PPA["athleteId"] = pd.to_numeric(PPA.athleteId, errors="coerce")
PPA.to_csv(f"{OUT}/cfbd_ppa_full.csv", index=False)

# ---- usage ----
u = load("usage")
u = u.rename(columns={"id": "athleteId", "season": "year"})
keep = ["year", "athleteId", "name", "position", "team", "conference",
        "usage_overall", "usage_pass", "usage_rush"]
USG = u[[c for c in keep if c in u]].copy()
USG["athleteId"] = pd.to_numeric(USG.athleteId, errors="coerce")
USG.to_csv(f"{OUT}/cfbd_usage_full.csv", index=False)

# ---- recruiting ----
r = load("recruit")
r = r.rename(columns={"ranking": "rank"})
keep = ["year", "athleteId", "name", "position", "stars", "rating", "rank"]
REC = r[[c for c in keep if c in r]].copy()
REC["athleteId"] = pd.to_numeric(REC.athleteId, errors="coerce")
REC.to_csv(f"{OUT}/cfbd_recruiting_full.csv", index=False)

print(f"ppa {PPA.shape} (RB {int((PPA.position=='RB').sum())}) · "
      f"usage {USG.shape} · recruiting {REC.shape} (RB {int((REC.position=='RB').sum())})")
