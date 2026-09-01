"""Comprehensive pre-NFL-debut feature table for the exhaustive model search."""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata
import numpy as np, pandas as pd

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()
def nteam(s):
    s = norm(s); return re.sub(r"\b(university|college|of|the|state|st|at)\b", "", s).replace(" ", "")
def G(s, c): return s[c] if (s is not None and c in s and pd.notna(s[c])) else np.nan
def C(*v):
    for x in v:
        if pd.notna(x): return x
    return np.nan

f4 = pd.read_csv("../PSI-reverse-engineering/data/features4.csv").loc[:, lambda x: ~x.columns.duplicated()]
hist = f4[f4.Year.between(2015, 2022)][["Player", "Year"]]
pool = pd.read_csv("data/pool_2023_2025.csv")[["Player", "Year", "athlete_id", "college", "draft_pick"]].rename(
    columns={"athlete_id": "aid", "draft_pick": "pick_pool"})
P = pd.concat([hist.assign(aid=np.nan, college=np.nan, pick_pool=np.nan), pool], ignore_index=True)
P["key"] = P.Player.map(norm); P = P.drop_duplicates(["key", "Year"])

comb = pd.read_csv("data/combine.csv"); comb["key"] = comb.player_name.map(norm)
rc = pd.read_csv("data/combine_pro_day.csv"); rc = rc[rc.POS_GP == "WR"]; rc["key"] = rc.player.map(norm)
pl = pd.read_csv("data/players.csv", low_memory=False); pl["key"] = pl.display_name.map(norm)
dr = pd.read_csv("data/draft_picks.csv", low_memory=False); dr["key"] = dr.pfr_player_name.map(norm)
dr_all_keys = set(dr.key)
cf = pd.read_csv("data/cfbd_player_seasons.csv"); cf["key"] = cf.player.map(norm)
ppa = pd.read_csv("data/cfbd_ppa.csv"); ppa["key"] = ppa.name.map(norm)
usg = pd.read_csv("data/cfbd_usage.csv"); usg["key"] = usg.name.map(norm)
sp = pd.read_csv("data/cfbd_sp.csv"); sp_i = sp.set_index(["year", "team"])
rec = pd.read_csv("data/cfbd_recruiting.csv"); rec["key"] = rec.name.map(norm)
ret = pd.read_csv("data/cfbd_returns.csv"); ret["key"] = ret.player.map(norm)
rct = pd.read_csv("data/cfbd_recteam.csv"); rct_i = rct.set_index(["year", "team"])
qb = pd.read_csv("data/cfbd_qb.csv"); qb["key"] = qb.player.map(norm)
portal = pd.read_csv("data/cfbd_portal.csv"); portal["key"] = portal.name.map(norm)
cf_ids = set(cf.playerId.unique())
P5 = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "Pac-10"}

def py(df, key, yr, yc):
    c = df[df.key == key]
    if len(c) == 0: return None
    if yc in c: c = c.iloc[(c[yc] - yr).abs().values.argsort()]
    return c.iloc[0]

rows = []
for _, p in P.iterrows():
    k, yr = p.key, int(p.Year)
    o = {"Player": p.Player, "Year": yr}
    pcR = py(comb, k, yr, "season"); plR = py(pl, k, yr, "draft_year"); drR = py(dr, k, yr, "season")
    bd = pd.to_datetime(G(plR, "birth_date"), errors="coerce")
    college = C(p.get("college"), G(plR, "college_name"), G(drR, "college"))
    rcc = rc[rc.key == k]; rr = rcc.iloc[(rcc.Year - yr).abs().values.argsort()].iloc[0] if len(rcc) else None
    def M(a, b): return C(G(rr, a), G(pcR, b))
    ht = M("Height (in)", "ht")
    if isinstance(ht, str) and "-" in ht:
        a_, b_ = ht.split("-"); ht = int(a_) * 12 + int(b_)
    wt = M("Weight (lbs)", "wt"); forty = M("40 Yard", "forty"); vert = M("Vert Leap (in)", "vertical")
    broad = M("Broad Jump (in)", "broad_jump"); cone = M("3Cone", "cone"); shu = M("Shuttle", "shuttle")
    bench = M("Bench Press", "bench"); hand = G(rr, "Hand Size (in)"); arm = G(rr, "Arm Length (in)")
    tsp = G(rr, "10-Yard Split")
    o.update(height=ht, weight=wt, hand=hand, arm=arm, forty=forty, ten_split=tsp,
             vertical=vert, broad=broad, cone=cone, shuttle=shu, bench=bench)
    o["bmi"] = wt / ht ** 2 * 703 if (pd.notna(wt) and pd.notna(ht)) else np.nan
    o["speed_score"] = wt * 200 / forty ** 4 if (pd.notna(wt) and pd.notna(forty)) else np.nan
    o["burst_score"] = vert + broad / 12 if (pd.notna(vert) and pd.notna(broad)) else np.nan
    o["agility_score"] = cone + shu if (pd.notna(cone) and pd.notna(shu)) else np.nan
    o["n_drills"] = int(sum(pd.notna(x) for x in [forty, vert, broad, cone, shu, bench, hand, arm]))
    o["elite_forty"] = int(pd.notna(forty) and forty <= 4.45)
    o["elite_burst"] = int(pd.notna(vert) and pd.notna(broad) and vert >= 37 and broad >= 122)
    o["elite_agility"] = int(pd.notna(cone) and cone <= 6.9)
    o["big_bodied"] = int(pd.notna(ht) and pd.notna(wt) and ht >= 74 and wt >= 210)

    pick = C(p.get("pick_pool"), G(drR, "pick"), G(pcR, "draft_ovr"), G(plR, "draft_pick"))
    o["pick"] = float(pick) if pd.notna(pick) else 270.0
    o["undrafted"] = int(o["pick"] >= 260); o["log_pick"] = np.log(min(o["pick"], 300))
    o["round"] = float(G(drR, "round")) if pd.notna(G(drR, "round")) else (8.0 if o["undrafted"] else np.nan)
    o["nfl_entry_age"] = (pd.Timestamp(yr, 1, 1) - bd).days / 365.25 if pd.notna(bd) else np.nan

    # ---- college ----
    aid = p.get("aid"); cid = int(aid) if (pd.notna(aid) and int(aid) in cf_ids) else None
    if cid is None:
        c0 = cf[cf.key == k]
        if len(c0): cid = int(c0.groupby("playerId").rec_yds.sum().idxmax())
    cc = cf[cf.playerId == cid].sort_values("season") if cid is not None else pd.DataFrame()
    o["has_college"] = int(len(cc) > 0)
    if len(cc):
        o["best_dom"] = cc.dominator.max(); o["final_dom"] = cc.iloc[-1].dominator; o["first_dom"] = cc.iloc[0].dominator
        o["best_ydshare"] = cc.yd_share.max(); o["final_ydshare"] = cc.iloc[-1].yd_share
        o["career_yds"] = cc.rec_yds.sum(); o["best_yds"] = cc.rec_yds.max()
        o["career_rec"] = cc.rec.sum(); o["career_ypr"] = cc.rec_yds.sum() / max(cc.rec.sum(), 1)
        o["best_long"] = cc.LONG.max(); o["td_rate"] = cc.rec_td.sum() / max(cc.rec.sum(), 1)
        o["rush_yds_career"] = cc.rush_yds.sum()
        o["n_seasons"] = cc.season.nunique(); o["n_seasons_20"] = int((cc.dominator >= .20).sum())
        o["n_seasons_30"] = int((cc.dominator >= .30).sum())
        o["alpha"] = int((cc.team_rec_rank == 1).any()); o["final_rank"] = float(cc.iloc[-1].team_rec_rank)
        o["dom_growth"] = float(cc.iloc[-1].dominator - cc.iloc[0].dominator)
        o["final_spike"] = float(cc.iloc[-1].rec_yds / max(cc.iloc[:-1].rec_yds.max(), 1)) if len(cc) > 1 else 1.0
        fs = int(cc.season.min())
        if pd.notna(bd):
            o["college_entry_age"] = fs - bd.year - (1 if bd.month >= 8 else 0)
            bo = cc[cc.dominator >= .20]
            o["breakout_age"] = (pd.Timestamp(int(bo.season.min()), 10, 15) - bd).days / 365.25 if len(bo) else 99.0
            cc2 = cc.assign(age=(pd.to_datetime(cc.season.astype(str) + "-10-15") - bd).dt.days / 365.25)
            o["dom_age19"] = float(cc2[cc2.age <= 19.5].dominator.max()) if (cc2.age <= 19.5).any() else 0.0
            o["dom_age20"] = float(cc2[cc2.age <= 20.5].dominator.max()) if (cc2.age <= 20.5).any() else 0.0
            o["age_final_season"] = float(cc2.age.max())
            o["early_declare"] = int(o["n_seasons"] <= 3 and cc2.age.max() < 21.8)
        pw = ppa[ppa.key == k]
        if len(pw):
            o["best_ppa"] = float(pw.avg_ppa.max()); o["final_ppa"] = float(pw.sort_values("year").iloc[-1].avg_ppa)
            o["avg_ppa"] = float(pw.avg_ppa.mean())
            if "avg_ppa_pass" in pw: o["best_ppa_pass"] = float(pw.avg_ppa_pass.max())
        uw = usg[usg.key == k]
        if len(uw):
            o["best_usage"] = float(uw.usage_overall.max()); o["final_usage"] = float(uw.sort_values("year").iloc[-1].usage_overall)
        bsn = cc.loc[cc.rec_yds.idxmax()]
        spr = sp_i.loc[(int(bsn.season), bsn.team)] if (int(bsn.season), bsn.team) in sp_i.index else None
        if spr is not None:
            o["team_sp_off"] = float(G(spr, "sp_offense")); o["team_sp_overall"] = float(G(spr, "sp_overall"))
            o["team_sp_def"] = float(G(spr, "sp_defense")); o["team_sos"] = float(G(spr, "sos"))
        fspr = sp_i.loc[(int(cc.iloc[-1].season), cc.iloc[-1].team)] if (int(cc.iloc[-1].season), cc.iloc[-1].team) in sp_i.index else None
        if fspr is not None: o["team_sp_off_final"] = float(G(fspr, "sp_offense"))
        rcr = rct_i.loc[(int(bsn.season) - 1, bsn.team)] if (int(bsn.season) - 1, bsn.team) in rct_i.index else None
        if rcr is not None: o["team_recruit_rank"] = float(G(rcr, "rec_rank"))
        o["power5"] = int(bsn.conference in P5); o["conf_g5"] = int(bsn.conference not in P5 and pd.notna(bsn.conference))
        o["n_teams"] = int(cc.team.nunique())
        # college QB quality (best season's team)
        qs = qb[(qb.team == bsn.team) & (qb.season == int(bsn.season))]
        if len(qs):
            q1 = qs.loc[qs.YDS.idxmax()]
            o["col_qb_ypa"] = float(G(q1, "YPA")); o["col_qb_td"] = float(G(q1, "TD"))
            o["col_qb_drafted"] = int(norm(q1.player) in dr_all_keys)
        # return usage
        rw = ret[ret.key == k]
        if len(rw):
            o["ret_yds"] = float(rw.YDS.sum()); o["ret_td"] = float(rw.TD.sum())
            o["ret_avg"] = float(rw.YDS.sum() / max(rw.NO.sum(), 1)); o["was_returner"] = 1
        else:
            o["was_returner"] = 0
        # transfer
        pt = portal[portal.key == k]
        o["transferred"] = int(len(pt) > 0 or o["n_teams"] > 1)
    # recruiting
    rw = rec[rec.key == k]
    if len(rw):
        rw = rw.iloc[(rw.year - (yr - 4)).abs().values.argsort()]
        o["recruit_stars"] = float(G(rw.iloc[0], "stars")); o["recruit_rating"] = float(G(rw.iloc[0], "rating"))
        o["recruit_rank"] = float(G(rw.iloc[0], "rank"))
        o["blue_chip"] = int(G(rw.iloc[0], "stars") >= 4)
    rows.append(o)

F = pd.DataFrame(rows)
ATH = {"height": 1, "weight": 1, "hand": 1, "arm": 1, "forty": -1, "ten_split": -1, "vertical": 1,
       "broad": 1, "cone": -1, "shuttle": -1, "speed_score": 1, "burst_score": 1}
for c, s in ATH.items(): F[c + "_p"] = (F[c] * s).rank(pct=True)
F["ras"] = F[[c + "_p" for c in ATH]].mean(axis=1) * 100
F["explosion_p"] = F[["vertical_p", "broad_p", "speed_score_p"]].mean(axis=1)
F["catch_radius"] = F[["height_p", "arm_p", "hand_p", "vertical_p"]].mean(axis=1)
# recruiting vs production: dominance percentile minus recruiting percentile
F["prod_p"] = F["best_dom"].rank(pct=True)
F["recruit_p"] = (-F["recruit_rank"]).rank(pct=True)
F["prod_over_recruit"] = F["prod_p"] - F["recruit_p"]
F.to_csv("data/features_v3.csv", index=False)
print(f"features_v3.csv  {F.shape[0]} x {F.shape[1]}")
for c in ["best_dom", "breakout_age", "best_ppa", "team_sp_off", "recruit_stars", "ras",
          "col_qb_ypa", "was_returner", "team_recruit_rank", "transferred", "early_declare"]:
    print(f"  {c:18s} {F[c].notna().sum()}/{len(F)}")
