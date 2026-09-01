"""Wide pre-NFL-debut feature table for WRPI v2, all prospects 2015-2026.
Joins: raw combine/pro-day measurables, birthdates, draft slot, CFBD college
receiving + PPA + usage + SP+ team ratings + HS recruiting rankings.
Athletic composites (speed/burst/agility/RAS-style) computed here.
"""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata, json
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()
def g(src, c):
    return src[c] if (src is not None and c in src and pd.notna(src[c])) else np.nan
def coal(*v):
    for x in v:
        if pd.notna(x): return x
    return np.nan

# ---------- prospect list: 2015-2022 from features4 + 2023-2026 from pool ----------
f4 = pd.read_csv("../PSI-reverse-engineering/data/features4.csv").loc[:, lambda x: ~x.columns.duplicated()]
hist = f4[f4.Year.between(2015, 2022)][["Player", "Year"]].copy()
pool = pd.read_csv("data/pool_2023_2025.csv")[["Player", "Year", "athlete_id", "college", "draft_pick"]]
pool = pool.rename(columns={"athlete_id": "aid", "draft_pick": "pick_pool"})
prospects = pd.concat([hist.assign(aid=np.nan, college=np.nan, pick_pool=np.nan), pool], ignore_index=True)
prospects["key"] = prospects.Player.map(norm)
prospects = prospects.drop_duplicates(["key", "Year"])

# ---------- sources ----------
comb = pd.read_csv("data/combine.csv"); comb["key"] = comb.player_name.map(norm)
rc   = pd.read_csv("data/combine_pro_day.csv"); rc = rc[rc.POS_GP == "WR"]; rc["key"] = rc.player.map(norm)
pl   = pd.read_csv("data/players.csv", low_memory=False); pl["key"] = pl.display_name.map(norm)
dr   = pd.read_csv("data/draft_picks.csv", low_memory=False); dr["key"] = dr.pfr_player_name.map(norm)
cf   = pd.read_csv("data/cfbd_player_seasons.csv"); cf["key"] = cf.player.map(norm)
ppa  = pd.read_csv("data/cfbd_ppa.csv"); ppa["key"] = ppa.name.map(norm)
usg  = pd.read_csv("data/cfbd_usage.csv"); usg["key"] = usg.name.map(norm)
sp   = pd.read_csv("data/cfbd_sp.csv")
rec  = pd.read_csv("data/cfbd_recruiting.csv"); rec["key"] = rec.name.map(norm)
cf_ids = set(cf.playerId.unique())

def pick_year(df, key, yr, ycol):
    c = df[df.key == key]
    if len(c) == 0: return None
    if ycol in c: c = c.iloc[(c[ycol] - yr).abs().values.argsort()]
    return c.iloc[0]

sp_idx = sp.set_index(["year", "team"]) if len(sp) else None
def sp_row(team, yr):
    try: return sp_idx.loc[(yr, team)]
    except Exception: return None

rows = []
for _, p in prospects.iterrows():
    k, yr = p.key, int(p.Year)
    o = {"Player": p.Player, "Year": yr}
    pcR = pick_year(comb, k, yr, "season"); plR = pick_year(pl, k, yr, "draft_year"); drR = pick_year(dr, k, yr, "season")
    bd = pd.to_datetime(g(plR, "birth_date"), errors="coerce")
    college = coal(p.get("college"), g(plR, "college_name"), g(drR, "college"))

    rcc = rc[rc.key == k]
    rr = rcc.iloc[(rcc.Year - yr).abs().values.argsort()].iloc[0] if len(rcc) else None
    def m(a, b): return coal(g(rr, a), g(pcR, b))
    ht = m("Height (in)", "ht");  wt = m("Weight (lbs)", "wt")
    if isinstance(ht, str) and "-" in ht:
        a_, b_ = ht.split("-"); ht = int(a_) * 12 + int(b_)
    forty = m("40 Yard", "forty"); vert = m("Vert Leap (in)", "vertical"); broad = m("Broad Jump (in)", "broad_jump")
    cone = m("3Cone", "cone"); shu = m("Shuttle", "shuttle"); bench = m("Bench Press", "bench")
    hand = g(rr, "Hand Size (in)"); arm = g(rr, "Arm Length (in)"); tsplit = g(rr, "10-Yard Split")
    o.update(height=ht, weight=wt, hand=hand, arm=arm, forty=forty, ten_split=tsplit,
             vertical=vert, broad=broad, cone=cone, shuttle=shu, bench=bench)
    o["bmi"] = (wt / (ht ** 2) * 703) if (pd.notna(wt) and pd.notna(ht)) else np.nan
    o["speed_score"] = (wt * 200 / forty ** 4) if (pd.notna(wt) and pd.notna(forty)) else np.nan
    o["burst_score"] = (vert + broad / 12) if (pd.notna(vert) and pd.notna(broad)) else np.nan
    o["agility_score"] = (cone + shu) if (pd.notna(cone) and pd.notna(shu)) else np.nan
    o["n_drills"] = sum(pd.notna(x) for x in [forty, vert, broad, cone, shu, bench, hand, arm])

    pick = coal(p.get("pick_pool"), g(drR, "pick"), g(pcR, "draft_ovr"), g(plR, "draft_pick"))
    o["pick"] = float(pick) if pd.notna(pick) else 270.0
    o["undrafted"] = int(o["pick"] >= 260)
    o["log_pick"] = np.log(min(o["pick"], 300))
    o["nfl_entry_age"] = ((pd.Timestamp(yr, 1, 1) - bd).days / 365.25) if pd.notna(bd) else np.nan

    # ---- CFBD college career (athlete_id first) ----
    aid = p.get("aid")
    cid = int(aid) if (pd.notna(aid) and int(aid) in cf_ids) else None
    if cid is None:
        cc0 = cf[cf.key == k]
        if len(cc0):
            cid = int(cc0.groupby("playerId").rec_yds.sum().idxmax())
    cc = cf[cf.playerId == cid].sort_values("season") if cid is not None else pd.DataFrame()
    o["has_college"] = int(len(cc) > 0)
    if len(cc):
        o["best_dom"] = cc.dominator.max(); o["final_dom"] = cc.iloc[-1].dominator
        o["best_ydshare"] = cc.yd_share.max(); o["final_ydshare"] = cc.iloc[-1].yd_share
        o["career_yds"] = cc.rec_yds.sum(); o["best_yds"] = cc.rec_yds.max()
        o["n_seasons"] = cc.season.nunique(); o["n_seasons_20"] = int((cc.dominator >= .20).sum())
        o["alpha"] = int((cc.team_rec_rank == 1).any())
        o["final_rank"] = float(cc.iloc[-1].team_rec_rank)
        fs = int(cc.season.min())
        if pd.notna(bd):
            o["college_entry_age"] = fs - bd.year - (1 if bd.month >= 8 else 0)
            bo = cc[cc.dominator >= .20]
            o["breakout_age"] = ((pd.Timestamp(int(bo.season.min()), 10, 15) - bd).days / 365.25) if len(bo) else 99.0
            # dominator achieved young
            cc2 = cc.assign(age=lambda d: (pd.to_datetime(d.season.astype(str) + "-10-15") - bd).dt.days / 365.25)
            o["dom_age19"] = float(cc2[cc2.age <= 19.5].dominator.max()) if (cc2.age <= 19.5).any() else 0.0
            o["dom_age20"] = float(cc2[cc2.age <= 20.5].dominator.max()) if (cc2.age <= 20.5).any() else 0.0
        # trajectory
        o["dom_growth"] = float(cc.iloc[-1].dominator - cc.iloc[0].dominator)
        o["final_spike"] = float(cc.iloc[-1].rec_yds / max(cc.iloc[:-1].rec_yds.max(), 1)) if len(cc) > 1 else 1.0
        # efficiency & usage (best + final season)
        pw = ppa[ppa.key == k]
        if len(pw):
            o["best_ppa"] = float(pw.avg_ppa.max()); o["final_ppa"] = float(pw.sort_values("year").iloc[-1].avg_ppa)
        uw = usg[usg.key == k]
        if len(uw):
            o["best_usage"] = float(uw.usage_overall.max()); o["final_usage"] = float(uw.sort_values("year").iloc[-1].usage_overall)
        # competition context: best season's team SP+
        bsn = cc.loc[cc.rec_yds.idxmax()]
        spr = sp_row(bsn.team, int(bsn.season))
        if spr is not None:
            o["team_sp_off"] = float(g(spr, "sp_offense")); o["team_sp_overall"] = float(g(spr, "sp_overall"))
            o["team_sos"] = float(g(spr, "sos"))
        o["power5"] = int(bsn.conference in ("SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "Pac-10"))
    # recruiting
    rw = rec[rec.key == k]
    if len(rw):
        rw = rw.iloc[(rw.year - (yr - 4)).abs().values.argsort()]
        o["recruit_stars"] = float(g(rw.iloc[0], "stars")); o["recruit_rating"] = float(g(rw.iloc[0], "rating"))
        o["recruit_rank"] = float(g(rw.iloc[0], "rank"))
    rows.append(o)

F = pd.DataFrame(rows)
# homegrown RAS: percentile-rank each measurable within the WR pool
ATH = {"height": 1, "weight": 1, "hand": 1, "arm": 1, "forty": -1, "ten_split": -1,
       "vertical": 1, "broad": 1, "cone": -1, "shuttle": -1, "speed_score": 1, "burst_score": 1}
for c, sgn in ATH.items():
    F[c + "_pctl"] = (F[c] * sgn).rank(pct=True)
F["ras"] = F[[c + "_pctl" for c in ATH]].mean(axis=1) * 100
F["explosion_pctl"] = F[["vertical_pctl", "broad_pctl", "speed_score_pctl"]].mean(axis=1)

F.to_csv("data/features_v2.csv", index=False)
cov = lambda c: f"{F[c].notna().sum()}/{len(F)}"
print(f"features_v2.csv: {F.shape[0]} prospects x {F.shape[1]} cols")
for c in ["best_dom", "breakout_age", "nfl_entry_age", "best_ppa", "best_usage",
          "team_sp_off", "recruit_stars", "ras", "speed_score", "pick"]:
    print(f"  {c:16s} {cov(c)}")
