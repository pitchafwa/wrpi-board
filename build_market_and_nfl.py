"""(1) market.csv  — each prospect's rookie-year dynasty consensus rank (the market)
   (2) nfl_eff.csv — NFL efficiency + opportunity metrics over first 3 seasons
       (talent signals that are less opportunity-gated than raw PPG)."""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata, glob
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()

prospects = pd.read_csv("data/wrpi_database.csv")[["Player", "Year"]].drop_duplicates()
prospects["key"] = prospects.Player.map(norm)

# ---------- (1) market: rookie-year dynasty ECR ----------
ec = pd.read_csv("data/fpecr_wr_dynasty.csv")
ec["key"] = ec.player.map(norm)
ec["scrape_date"] = pd.to_datetime(ec.scrape_date, errors="coerce")
ec["ecr"] = pd.to_numeric(ec.ecr, errors="coerce")
ec["yr"] = ec.scrape_date.dt.year
ec["mo"] = ec.scrape_date.dt.month
rows = []
for _, p in prospects.iterrows():
    yr = int(p.Year)
    # dynasty rankings May-Sep of the draft year = post-NFL-draft rookie consensus
    w = ec[(ec.key == p.key) & (ec.yr == yr) & (ec.mo.between(5, 9)) &
           (ec.page_type.isin(["dynasty-rk", "dynasty-wr", "dynasty-op"]))]
    o = {"Player": p.Player, "Year": yr}
    if len(w):
        o["mkt_dynasty_ecr"] = float(w[w.page_type == "dynasty-wr"].ecr.min()
                                     if (w.page_type == "dynasty-wr").any() else w.ecr.min())
        rk = w[w.page_type == "dynasty-rk"]
        if len(rk): o["mkt_rookie_rank"] = float(rk.ecr.min())
    rows.append(o)
M = pd.DataFrame(rows)
M.to_csv("data/market.csv", index=False)
print(f"market.csv: {M.mkt_dynasty_ecr.notna().sum()} prospects with dynasty ECR, "
      f"{M.mkt_rookie_rank.notna().sum()} with rookie-rank ECR "
      f"(classes {M.dropna(subset=['mkt_dynasty_ecr']).Year.min():.0f}-{M.dropna(subset=['mkt_dynasty_ecr']).Year.max():.0f})")

# ---------- (2) NFL efficiency / opportunity, first 3 seasons ----------
adv = pd.read_csv("data/nfl_advstats_rec.csv"); adv["key"] = adv.player.map(norm)
ngs = pd.concat([pd.read_csv(f) for f in glob.glob("data/ngs_rec_*.csv")], ignore_index=True)
ngs = ngs[ngs.season_type == "REG"]; ngs["key"] = ngs.player_display_name.map(norm)
ngs_s = (ngs.groupby(["key", "season"], as_index=False)
            .agg(sep=("avg_separation", "mean"), cush=("avg_cushion", "mean"),
                 yacoe=("avg_yac_above_expectation", "mean"), catchpct=("catch_percentage", "mean"),
                 airshare=("percent_share_of_intended_air_yards", "mean"), tgt=("targets", "sum")))
sn = pd.concat([pd.read_csv(f) for f in glob.glob("data/snaps_*.csv")], ignore_index=True)
sn = sn[(sn.game_type == "REG") & (sn.position == "WR")]
sn["key"] = sn.player.map(norm)
sn_s = sn.groupby(["key", "season"], as_index=False).agg(snap_pct=("offense_pct", "mean"), gp=("week", "nunique"))

rows = []
for _, p in prospects.iterrows():
    yr, k = int(p.Year), p.key
    o = {"Player": p.Player, "Year": yr}
    a = adv[(adv.key == k) & (adv.season.between(yr, yr + 2))]
    if len(a):
        wsum = a.rec.sum() or 1
        o["nfl_adot"] = np.average(a.adot, weights=a.tgt.clip(lower=1))
        o["nfl_yac_r"] = float((a.yac.sum()) / wsum)
        o["nfl_ybc_r"] = float((a.ybc.sum()) / wsum)
        o["nfl_brk_tkl_r"] = float(a.brk_tkl.sum() / wsum)
        o["nfl_drop_pct"] = float(a["drop"].sum() / max(a.tgt.sum(), 1))
        o["nfl_1d_r"] = float(a.x1d.sum() / wsum)
        o["nfl_yptgt"] = float(a.yds.sum() / max(a.tgt.sum(), 1))
    g = ngs_s[(ngs_s.key == k) & (ngs_s.season.between(yr, yr + 2))]
    if len(g):
        o["nfl_separation"] = float(np.average(g.sep, weights=g.tgt.clip(lower=1)))
        o["nfl_yacoe"] = float(np.average(g.yacoe.fillna(0), weights=g.tgt.clip(lower=1)))
        o["nfl_airshare"] = float(g.airshare.max())
        o["nfl_catchpct"] = float(np.average(g.catchpct.fillna(0), weights=g.tgt.clip(lower=1)))
    s = sn_s[(sn_s.key == k) & (sn_s.season.between(yr, yr + 2))]
    if len(s):
        o["nfl_snap_pct_peak"] = float(s.snap_pct.max())
        o["nfl_snap_pct_y1"] = float(s.sort_values("season").iloc[0].snap_pct)
    rows.append(o)
E = pd.DataFrame(rows)
E.to_csv("data/nfl_eff.csv", index=False)
print(f"nfl_eff.csv: separation {E.nfl_separation.notna().sum()}, adot {E.nfl_adot.notna().sum()}, "
      f"snap% {E.nfl_snap_pct_peak.notna().sum()} of {len(E)}")
