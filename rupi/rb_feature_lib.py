"""Shared per-player feature builder for RUPI, used by both the drafted-pool
and UDFA-supplement builders so the logic (and any future fixes) lives once."""
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

DOM_CAP = 0.70
REL_MIN = 2500
BREAKOUT_DOM = 0.15
P5 = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "Pac-10"}

class Sources:
    def __init__(self, WB, RD):
        self.comb = pd.read_csv(WB + "combine.csv"); self.comb = self.comb[self.comb.pos == "RB"]
        self.comb["key"] = self.comb.player_name.map(norm)
        self.rc = pd.read_csv(WB + "combine_pro_day.csv"); self.rc = self.rc[self.rc.POS_GP == "RB"]
        self.rc["key"] = self.rc.player.map(norm)
        self.cf = pd.read_csv(RD + "cfbd_rb_seasons.csv"); self.cf["key"] = self.cf.player.map(norm)
        self.ppa = pd.read_csv(WB + "cfbd_ppa_full.csv"); self.ppa["key"] = self.ppa.name.map(norm)
        self.usg = pd.read_csv(WB + "cfbd_usage_full.csv"); self.usg["key"] = self.usg.name.map(norm)
        self.sp_i = pd.read_csv(WB + "cfbd_sp.csv").set_index(["year", "team"])
        self.rec = pd.read_csv(WB + "cfbd_recruiting_full.csv")
        self.rec = self.rec[self.rec.position.isin(["RB", "ATH"])].copy(); self.rec["key"] = self.rec.name.map(norm)
        self.ret = pd.read_csv(WB + "cfbd_returns.csv"); self.ret["key"] = self.ret.player.map(norm)
        self.rct_i = pd.read_csv(WB + "cfbd_recteam.csv").set_index(["year", "team"])
        self.qb = pd.read_csv(WB + "cfbd_qb.csv"); self.qb["key"] = self.qb.player.map(norm)
        self.portal = pd.read_csv(WB + "cfbd_portal.csv"); self.portal["key"] = self.portal.name.map(norm)


def build_row(k, yr, pick, age_hint, bd, S: Sources):
    """k=normalized name key, yr=draft/rookie class year, pick=float (270 if UDFA),
    age_hint=float|nan (PFR draft-day age if known), bd=Timestamp|NaT (birthdate)."""
    o = {}
    py = S.comb[S.comb.key == k]
    pcR = py.iloc[(py.draft_year - yr).abs().values.argsort()].iloc[0] if len(py) else None
    if pd.notna(bd):
        _age = (pd.Timestamp(yr, 1, 1) - bd).days / 365.25
        if not (18.0 <= _age <= 27.0):
            bd = pd.NaT

    rcc = S.rc[S.rc.key == k]; rr = rcc.iloc[(rcc.Year - yr).abs().values.argsort()].iloc[0] if len(rcc) else None
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
    o["elite_forty"] = int(pd.notna(forty) and forty <= 4.48)
    o["elite_burst"] = int(pd.notna(vert) and pd.notna(broad) and vert >= 36 and broad >= 122)
    o["elite_agility"] = int(pd.notna(cone) and cone <= 6.95)
    o["workhorse_build"] = int(pd.notna(wt) and wt >= 215)

    o["pick"] = float(pick)
    o["undrafted"] = int(o["pick"] >= 260); o["log_pick"] = np.log(min(o["pick"], 300))
    # age on Jan 1 of the draft year, from the verified birth date -- same convention
    # as WRPI. PFR's whole-year draft-day age (age_hint for drafted players) is only a
    # last-resort fallback: it's rounded AND noisy (off by >1yr for a few players).
    o["nfl_entry_age"] = C((pd.Timestamp(yr, 1, 1) - bd).days / 365.25 if pd.notna(bd) else np.nan, age_hint)

    c0 = S.cf[S.cf.key == k]
    cid = None
    if len(c0):
        win = c0[c0.season.between(yr - 5, yr - 1)]
        win = win if len(win) else c0
        cid = int(win.groupby("playerId").scrim_yds.sum().idxmax())
    cc = S.cf[S.cf.playerId == cid].sort_values("season") if cid is not None else pd.DataFrame()
    o["has_college"] = int(len(cc) > 0)
    if len(cc):
        rel = cc[cc.team_scrim_yds >= REL_MIN].copy()
        rel["dominator"] = rel["dominator"].clip(upper=DOM_CAP)
        rel["scrim_yd_share"] = rel["scrim_yd_share"].clip(upper=DOM_CAP + 0.05)
        o["reliable_dom"] = int(len(rel) > 0)
        if len(rel):
            o["best_dom"] = rel.dominator.max(); o["final_dom"] = rel.iloc[-1].dominator
            o["first_dom"] = rel.iloc[0].dominator
            o["best_ydshare"] = rel.scrim_yd_share.max(); o["final_ydshare"] = rel.iloc[-1].scrim_yd_share
        cc = cc.assign(dominator=cc.dominator.clip(upper=DOM_CAP))
        cc.loc[cc.team_scrim_yds < REL_MIN, "dominator"] = np.nan

        o["career_scrim_yds"] = cc.scrim_yds.sum(); o["best_scrim_yds"] = cc.scrim_yds.max()
        o["career_rush_yds"] = cc.rush_yds.sum(); o["best_rush_yds"] = cc.rush_yds.max()
        o["career_rec_yds"] = cc.rec_yds.sum(); o["best_rec_yds"] = cc.rec_yds.max()
        o["career_rush_att"] = cc.rush_att.sum(); o["career_rec"] = cc.rec.sum()
        o["career_touches"] = o["career_rush_att"] + o["career_rec"]
        o["career_ypc"] = cc.rush_yds.sum() / max(cc.rush_att.sum(), 1)
        o["best_ypc"] = cc[cc.rush_att >= 80].ypc.max() if (cc.rush_att >= 80).any() else np.nan
        o["career_ypr"] = cc.rec_yds.sum() / max(cc.rec.sum(), 1)
        o["best_long"] = cc.rush_long.max()
        o["td_rate"] = (cc.rush_td.sum() + cc.rec_td.sum()) / max(o["career_touches"], 1)
        o["best_rec_ydshare"] = rel.rec_yd_share.clip(upper=0.5).max() if len(rel) else np.nan
        o["rec_share_of_touches"] = cc.rec.sum() / max(o["career_touches"], 1)
        o["best_rush_share"] = cc.rush_share.clip(upper=1.0).max()

        o["n_seasons"] = cc.season.nunique()
        o["n_seasons_15"] = int((cc.dominator >= .15).sum())
        o["n_seasons_25"] = int((cc.dominator >= .25).sum())
        o["alpha"] = int((cc.team_scrim_rank == 1).any()); o["final_rank"] = float(cc.iloc[-1].team_scrim_rank)
        o["dom_growth"] = float(cc.iloc[-1].dominator - cc.iloc[0].dominator) if cc.dominator.notna().sum() > 1 else np.nan
        fs = int(cc.season.min())
        if pd.notna(bd):
            o["college_entry_age"] = fs - bd.year - (1 if bd.month >= 8 else 0)
            bo = cc[cc.dominator >= BREAKOUT_DOM]
            o["breakout_age"] = (pd.Timestamp(int(bo.season.min()), 10, 15) - bd).days / 365.25 if len(bo) else 99.0
            cc2 = cc.assign(age=(pd.to_datetime(cc.season.astype(str) + "-10-15") - bd).dt.days / 365.25)
            o["dom_age19"] = float(cc2[cc2.age <= 19.5].dominator.max()) if (cc2.age <= 19.5).any() else 0.0
            o["age_final_season"] = float(cc2.age.max())
            o["early_declare"] = int(o["n_seasons"] <= 3 and cc2.age.max() < 21.8)
        col_seasons = set(cc.season.astype(int)); col_teams = set(cc.team)
        pw = S.ppa[(S.ppa.athleteId == cid) & S.ppa.year.isin(col_seasons) & S.ppa.team.isin(col_teams)]
        if len(pw) == 0: pw = S.ppa[S.ppa.athleteId == cid]
        if len(pw):
            o["best_ppa"] = float(pw.avg_ppa.max()); o["final_ppa"] = float(pw.sort_values("year").iloc[-1].avg_ppa)
            o["avg_ppa"] = float(pw.avg_ppa.mean())
            if "avg_ppa_rush" in pw: o["best_ppa_rush"] = float(pw.avg_ppa_rush.max())
        uw = S.usg[(S.usg.athleteId == cid) & S.usg.year.isin(col_seasons) & S.usg.team.isin(col_teams)]
        if len(uw) == 0: uw = S.usg[S.usg.athleteId == cid]
        if len(uw):
            o["best_usage"] = float(uw.usage_overall.max()); o["final_usage"] = float(uw.sort_values("year").iloc[-1].usage_overall)
            if "usage_rush" in uw: o["best_usage_rush"] = float(uw.usage_rush.max())
        bsn = cc.loc[cc.scrim_yds.idxmax()]
        spr = S.sp_i.loc[(int(bsn.season), bsn.team)] if (int(bsn.season), bsn.team) in S.sp_i.index else None
        if spr is not None:
            o["team_sp_off"] = float(G(spr, "sp_offense")); o["team_sp_overall"] = float(G(spr, "sp_overall"))
            o["team_sp_def"] = float(G(spr, "sp_defense")); o["team_sos"] = float(G(spr, "sos"))
        rcr = S.rct_i.loc[(int(bsn.season) - 1, bsn.team)] if (int(bsn.season) - 1, bsn.team) in S.rct_i.index else None
        if rcr is not None: o["team_recruit_rank"] = float(G(rcr, "rec_rank"))
        o["power5"] = int(bsn.conference in P5); o["conf_g5"] = int(bsn.conference not in P5 and pd.notna(bsn.conference))
        o["n_teams"] = int(cc.team.nunique())
        qs = S.qb[(S.qb.team == bsn.team) & (S.qb.season == int(bsn.season))]
        if len(qs):
            q1 = qs.loc[qs.YDS.idxmax()]
            o["col_qb_ypa"] = float(G(q1, "YPA"))
        rw = S.ret[(S.ret.playerId == cid) & S.ret.season.isin(col_seasons)]
        if len(rw) == 0: rw = S.ret[(S.ret.key == k) & S.ret.team.isin(col_teams)]
        if len(rw):
            o["ret_yds"] = float(rw.YDS.sum()); o["was_returner"] = 1
        else:
            o["was_returner"] = 0
        pt = S.portal[S.portal.key == k]
        o["transferred"] = int(len(pt) > 0 or o["n_teams"] > 1)
    rw = S.rec[S.rec.key == k]
    if len(rw):
        rw = rw.iloc[(rw.year - (yr - 4)).abs().values.argsort()]
        o["recruit_stars"] = float(G(rw.iloc[0], "stars")); o["recruit_rating"] = float(G(rw.iloc[0], "rating"))
        o["recruit_rank"] = float(G(rw.iloc[0], "rank"))
        o["blue_chip"] = int(G(rw.iloc[0], "stars") >= 4)
    return o


def add_athletic_percentiles(F):
    ATH = {"height": 1, "weight": 1, "hand": 1, "arm": 1, "forty": -1, "ten_split": -1, "vertical": 1,
           "broad": 1, "cone": -1, "shuttle": -1, "speed_score": 1, "burst_score": 1}
    for c, s in ATH.items(): F[c + "_p"] = (F[c] * s).rank(pct=True)
    F["ras"] = F[[c + "_p" for c in ATH]].mean(axis=1) * 100
    F["explosion_p"] = F[["vertical_p", "broad_p", "speed_score_p"]].mean(axis=1)
    F["agility_p"] = F[["cone_p", "shuttle_p"]].mean(axis=1)
    F["prod_p"] = F["best_dom"].rank(pct=True)
    F["recruit_p"] = (-F["recruit_rank"]).rank(pct=True)
    F["prod_over_recruit"] = F["prod_p"] - F["recruit_p"]
    return F
