"""Score every RB prospect (+ UDFA supplement) with RUPI v1 ->
dashboard/rupi_scores.json + rupi/out/rupi_database.csv. Mirrors score_v2.py.
Run from the repo root: `python rupi/score_rupi.py`."""
import warnings; warnings.filterwarnings("ignore")
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import json, numpy as np, pandas as pd
import rupi_score_v1 as W

RD = "rupi/data/"
F = pd.read_csv(RD + "features_rb_all.csv")
O = pd.read_csv(RD + "rb_outcomes_all.csv").drop(columns=["pick"])
d = F.merge(O, on=["Player", "Year"])
d = d[d.has_college == 1].reset_index(drop=True)

d["nfl_age"] = d.nfl_entry_age
d["bo_age_raw"] = d.breakout_age                     # keep raw (NaN = no bd) for the low-conf flag
d["bo_age"] = d.breakout_age.fillna(99.0)
d["dom"] = d.best_dom.clip(0, .65)
d["rec"] = d.best_rec_ydshare.clip(0, .5)
ypc_z_all = (d.career_ypc - d.career_ypc.median()) / d.career_ypc.std()
ppa_z_all = (d.avg_ppa - d.avg_ppa.median()) / d.avg_ppa.std()
d["eff"] = pd.concat([ypc_z_all, ppa_z_all], axis=1).mean(axis=1)
d["expl"] = d.explosion_p
d["yds"] = d.best_scrim_yds / 1000.0
d["pick"] = d.pick.clip(1, 300)

tr = d[d.Year.between(2015, 2023)]
for c in ["nfl_age", "dom", "rec", "eff", "expl", "yds"]:
    d[c] = d[c].fillna(tr[c].median())

pp = json.load(open(RD + "rupi_v1_params_pre.json"))["params"]
qq = json.load(open(RD + "rupi_v1_params_post.json"))["params"]
dm = json.load(open(RD + "rupi_diamond.json"))

# reference distribution = 2015-2020 classes (mature outcome window used to fit)
ref_pool = d[d.Year.between(2015, 2020)]
ref_pre = np.sort(W.raw_pre(pp, ref_pool))
ref_post = np.sort(W.raw_post(qq, ref_pool))

d["raw_pre"] = W.raw_pre(pp, d)
d["raw_post"] = W.raw_post(qq, d)
d["rupi_pre"] = W.to_percentile(d["raw_pre"], ref_pre)
d["rupi_post"] = W.to_percentile(d["raw_post"], ref_post)
d["tier"] = np.ceil(d["rupi_post"] * 10).clip(1, 10).astype(int)

# ---- diamond-in-the-rough index (RBs drafted outside round 1, incl. UDFA) ----
dsc = np.zeros(len(d))
for f, sgn in dm["ind"].items():
    v = pd.to_numeric(d.get(f), errors="coerce")
    v = v.fillna(dm["median"][f]) if f in dm["median"] else v.fillna(0)
    z = sgn * (v - dm["mean"][f]) / dm["std"][f]
    dsc = dsc + dm["w"][f] * np.nan_to_num(z, nan=0.0)
d["diamond_score"] = dsc
d["is_diamond"] = ((d["pick"] >= dm["cut_pick"]) & (d["diamond_score"] >= dm["flag_threshold"])).astype(int)

# ---- calibration first (needed to pick the star threshold empirically) ----
d["era"] = np.where(d.Year <= 2023, "historical", "prediction")
h = d[(d.era == "historical") & (d.win3_full == 1)].copy()
h["actual_fantasy_pctl"] = h["rb_top34"].rank(pct=True)
h["hit"] = (pd.to_numeric(h["best3"], errors="coerce") >= 14).astype(int)
cal = {}
for which, col in [("post", "rupi_post"), ("pre", "rupi_pre")]:
    h["_t"] = np.ceil(h[col] * 10).clip(1, 10).astype(int)
    g = h.groupby("_t").agg(n=("hit", "size"), hit_rate=("hit", "mean"),
                             avg_outcome_pctl=("actual_fantasy_pctl", "mean")).reset_index()
    cal[which] = json.loads(g.round(3).to_json(orient="records"))
    print(f"\n{which}-draft RUPI decile calibration:")
    print(g.to_string(index=False))

STAR_PCTL = 0.90   # calibration (above): decile 10 (pctl>=.90) post-draft hit-rate
                   # 0.73 vs decile 9's 0.39 -- the star signal jump is exactly at
                   # the 90th pctl (pre-draft: 0.57 vs 0.38). RB has fewer elite
                   # fantasy seasons than WR so 0.90 (not WRPI's 0.95) is the mark.
d["is_star_pre"] = (d["rupi_pre"] >= STAR_PCTL).astype(int)
d["is_star_post"] = (d["rupi_post"] >= STAR_PCTL).astype(int)

# ---- low-confidence profile ----
_nd = pd.to_numeric(d.get("n_drills"), errors="coerce").fillna(0)
_rel = pd.to_numeric(d.get("reliable_dom"), errors="coerce").fillna(0)
_noage = d["bo_age_raw"].isna()
def _lcr(r):
    x = []
    if r["_rel"] == 0: x.append("no reliable college production data (thin CFBD team-season)")
    if r["_noage"]: x.append("no verified birth date")
    if r["_nd"] == 0: x.append("no athletic testing at all")
    return "; ".join(x)
d["_nd"], d["_rel"], d["_noage"] = _nd, _rel, _noage
d["low_conf"] = ((_rel == 0) | _noage | (_nd == 0)).astype(int)
d["low_conf_reason"] = d.apply(_lcr, axis=1)
d = d.drop(columns=["_nd", "_rel", "_noage"])

cp = pd.DataFrame({k: np.round(v, 1) for k, v in W.components_post(qq, d).items()}, index=d.index)
d["comp_post"] = cp.to_dict("records")
cpre = pd.DataFrame({k: np.round(v, 1) for k, v in W.components_pre(pp, d).items()}, index=d.index)
d["comp_pre"] = cpre.to_dict("records")

d = d.merge(h[["Player", "Year", "actual_fantasy_pctl"]], on=["Player", "Year"], how="left")

# ---- profile similarity: nearest neighbours over model inputs + archetype + body ----
#   RUPI profile leads; receiving-role + carry-share are weighted up so a 3-down
#   receiving back doesn't get matched to an early-down grinder; body measurements
#   up too (bruiser vs scatback).
SIM_W = {
    "best_dom": 1.0, "breakout_age": 1.0, "nfl_entry_age": 1.0,
    "career_ypc": 0.8, "avg_ppa": 0.8, "explosion_p": 1.0, "agility_p": 0.6,
    "best_scrim_yds": 1.0, "n_seasons_15": 0.8, "ras": 1.0, "recruit_stars": 0.7,
    "best_rec_ydshare": 1.8, "best_rush_share": 1.2,
    "height": 1.8, "weight": 2.2, "bmi": 1.8,
    "rupi_pre": 0.6, "rupi_post": 0.6, "diamond_score": 0.6,
}
_S = d.copy()
_S["breakout_age"] = pd.to_numeric(_S["breakout_age"], errors="coerce").clip(upper=25)
M = pd.DataFrame(index=_S.index)
for c, wgt in SIM_W.items():
    v = pd.to_numeric(_S[c], errors="coerce"); v = v.fillna(v.median())
    z = (v - v.mean()) / (v.std() + 1e-9)
    M[c] = z * wgt
Marr = M.values
players = _S["Player"].values; years = _S["Year"].values
fant = _S["actual_fantasy_pctl"].values
sims = []
for i in range(len(Marr)):
    dist = np.sqrt(((Marr - Marr[i]) ** 2).sum(1))
    order = np.argsort(dist)
    top = [j for j in order if j != i][:6]
    scale = np.median(dist[dist > 0])
    sims.append([{"p": str(players[j]), "y": int(years[j]),
                  "sim": round(float(100 * np.exp(-dist[j] / scale)), 0),
                  "fant": (None if pd.isna(fant[j]) else round(float(fant[j]), 3))} for j in top])
d["similar"] = sims

COLS = ["Player", "Year", "era", "is_udfa", "udfa_type", "tier", "rupi_post", "rupi_pre", "raw_post", "raw_pre",
        "diamond_score", "is_diamond", "is_star_pre", "is_star_post", "low_conf", "low_conf_reason",
        "actual_fantasy_pctl", "pick", "nfl_entry_age", "breakout_age", "best_dom", "best_rec_ydshare",
        "career_ypc", "avg_ppa", "explosion_p", "best_scrim_yds", "best_rush_share",
        "recruit_stars", "comp_post", "comp_pre", "similar"]
# fitted model stats (from fit_rupi.py / fit_rupi_pre2.py runs 2026-09-01)
POST_CV, PRE_CV, PICK_ALONE = 0.714, 0.448, 0.682

# ---- provisional flag: is the newest class's draft capital real yet? ----
import datetime
_cur = int(d.Year.max())
_prov = {"class": _cur, "provisional": False, "draft_date": None}
try:
    _dd = json.load(open("data/draft_dates.json"))
    _dt = _dd.get(str(_cur))
    if _dt:
        _prov["draft_date"] = _dt
        _prov["provisional"] = datetime.date.today() < datetime.date.fromisoformat(_dt)
except Exception:
    pass

out = {
    "generated": pd.Timestamp.utcnow().isoformat(timespec="minutes"),
    "draft_status": _prov,
    "model": {
        "target": "best-2-of-first-3 seasons PPR PPG",
        "post_cv_spearman": POST_CV, "pre_cv_spearman": PRE_CV, "pick_alone_spearman": PICK_ALONE,
        "reference_years": [2015, 2020], "reference_n": int(len(ref_pool)),
        "star_pctl": STAR_PCTL, "n_udfa": int((d.is_udfa == 1).sum()),
        "diamond": {"cut_pick": dm["cut_pick"], "lift5": round(dm["lift5"], 1),
                    "base_rate": round(dm["base_rate"], 3), "prec5": round(dm["loco_prec5"], 3),
                    "weights": dm["w"]},
    },
    "scored": json.loads(d.sort_values(["Year", "rupi_post"], ascending=[True, False])[COLS].round(4).to_json(orient="records")),
    "calibration": cal,
}
import shutil
os.makedirs("rupi/out", exist_ok=True)
json.dump(out, open("rupi/out/rupi_scores.json", "w"), indent=1)
d[[c for c in COLS if c not in ("comp_post", "comp_pre")]].to_csv("rupi/out/rupi_database.csv", index=False)
shutil.copy("rupi/out/rupi_scores.json", "dashboard/rupi_scores.json")
print("wrote rupi/out/rupi_scores.json + rupi/out/rupi_database.csv -> dashboard/rupi_scores.json")

print(f"\nscored {len(d)} RB prospects 2015-2026 ({(d.is_udfa==1).sum()} UDFA)")
print(f"star flag: {(d.is_star_pre==1).sum()} pre-draft, {(d.is_star_post==1).sum()} post-draft (pctl>={STAR_PCTL})")
print(f"diamond flag: {(d.is_diamond==1).sum()} flagged")
print(f"low-conf flag: {(d.low_conf==1).sum()} total, {((d.low_conf==1)&(d.era=='prediction')).sum()} in prediction era")
print("\ntop 15 (2024-2026) by RUPI post-draft:")
print(d[d.era == "prediction"].sort_values("rupi_post", ascending=False)
      .head(15)[["Year", "Player", "tier", "rupi_post", "rupi_pre", "pick", "is_diamond", "is_star_post"]].to_string(index=False))
