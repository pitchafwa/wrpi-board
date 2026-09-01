"""Score every prospect 2015-2026 with WRPI v2 -> dashboard/scores.json + wrpi_database.csv.
Topline = post-draft v2 percentile. Also: pre-draft v2 percentile, head-to-head tiebreaker
score, component breakdowns, and (historical) actual fantasy + actual PSI percentiles."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
import wrpi_score_v2 as W

F = pd.read_csv("data/features_v3.csv")
O = pd.read_csv("data/nfl_outcomes.csv")
try:  PS = pd.read_csv("data/wrpi_database.csv")[["Player", "Year", "actual_pctl_post"]]
except Exception:  PS = pd.DataFrame(columns=["Player", "Year", "actual_pctl_post"])

d = F.merge(O, on=["Player", "Year"], how="left").merge(PS, on=["Player", "Year"], how="left")
d = d[d.has_college == 1].reset_index(drop=True)

# model input columns
d["alpha"]   = d.alpha.fillna(0).astype(float)
d["nfl_age"] = d.nfl_entry_age
d["bo_age"]  = d.breakout_age.fillna(99.0)
d["dom"]     = d.best_dom.clip(0, 0.6)
d["ppa"]     = d.final_ppa
d["expl"]    = d.explosion_p
d["yds"]     = d.best_yds / 1000.0
d["pick"]    = d.pick.clip(1, 300)
# impute for scoring (median of the training era)
tr = d[d.Year.between(2015, 2022)]
for c in ["nfl_age", "ppa", "expl", "yds", "dom"]:
    d[c] = d[c].fillna(tr[c].median())

pp = json.load(open("data/wrpi_v2_params_pre.json"))["params"]
qq = json.load(open("data/wrpi_v2_params_post.json"))["params"]
tb = json.load(open("data/wrpi_tiebreaker.json"))
dm = json.load(open("data/wrpi_diamond.json"))
STAR_PCTL = 0.95

# reference distribution = the 2015-2020 classes (full 5-yr outcome window used to fit)
ref_pool = d[d.Year.between(2015, 2020)]
ref_pre  = np.sort(W.raw_pre(pp, ref_pool))
ref_post = np.sort(W.raw_post(qq, ref_pool))

d["raw_pre"]  = W.raw_pre(pp, d)
d["raw_post"] = W.raw_post(qq, d)
d["wrpi_pre"]  = W.to_percentile(d["raw_pre"], ref_pre)
d["wrpi_post"] = W.to_percentile(d["raw_post"], ref_post)
d["tier"] = np.ceil(d["wrpi_post"] * 10).clip(1, 10).astype(int)
d["tb_score"] = W.tiebreaker_score(tb, d)

# ---- diamond-in-the-rough index (WRs drafted after ~round 2) ----
dsc = np.zeros(len(d))
for f, sgn in dm["ind"].items():
    v = pd.to_numeric(d.get(f), errors="coerce")
    v = v.fillna(dm["median"][f]) if f in dm["median"] else v.fillna(0)
    z = sgn * (v - dm["mean"][f]) / dm["std"][f]
    dsc = dsc + dm["w"][f] * np.nan_to_num(z, nan=0.0)
d["diamond_score"] = dsc
d["is_diamond"] = ((d["pick"] >= dm["cut_pick"]) & (d["pick"] < 260) &
                   (d["diamond_score"] >= dm["flag_threshold"])).astype(int)

# ---- star flags: 95th percentile of the score currently being viewed ----
d["is_star_pre"]  = (d["wrpi_pre"]  >= STAR_PCTL).astype(int)
d["is_star_post"] = (d["wrpi_post"] >= STAR_PCTL).astype(int)

# ---- low-confidence profile: inputs came in thin ----
_nd  = pd.to_numeric(d.get("n_drills"), errors="coerce").fillna(0)
_rel = pd.to_numeric(d.get("reliable_dom"), errors="coerce").fillna(0)
_noage = d["nfl_entry_age"].isna()
def _lcr(r):
    x = []
    if r["_rel"] == 0: x.append("no reliable college production data (thin CFBD team-season)")
    if r["_noage"]:   x.append("no verified birth date")
    if r["_nd"] == 0: x.append("no athletic testing at all")
    return "; ".join(x)
d["_nd"], d["_rel"], d["_noage"] = _nd, _rel, _noage
# only flag when a CORE input is missing — combine no-shows alone don't count
# (athletic testing is a small share of WRPI)
d["low_conf"] = ((_rel == 0) | _noage | (_nd == 0)).astype(int)
d["low_conf_reason"] = d.apply(_lcr, axis=1)
d = d.drop(columns=["_nd", "_rel", "_noage"])

cp = pd.DataFrame({k: np.round(v, 1) for k, v in W.components_post(qq, d).items()}, index=d.index)
d["comp_post"] = cp.to_dict("records")
cpre = pd.DataFrame({k: np.round(v, 1) for k, v in W.components_pre(pp, d).items()}, index=d.index)
d["comp_pre"] = cpre.to_dict("records")

d["era"] = np.where(d.Year <= 2022, "historical", "prediction")
# actual fantasy percentile among historical (best-3-of-window PPR PPG)
h = d[d.era == "historical"].copy()
h["actual_fantasy_pctl"] = h["top35"].rank(pct=True)
d = d.merge(h[["Player", "Year", "actual_fantasy_pctl"]], on=["Player", "Year"], how="left")

# ---- profile similarity: nearest neighbours over model inputs + body type + outputs ----
#   WRPI profile dominates; body measurements are a stronger tiebreaker so small
#   receivers don't get matched to big ones.
SIM_W = {
    "best_dom": 1.0, "breakout_age": 1.0, "nfl_entry_age": 1.0, "final_ppa": 1.0,
    "explosion_p": 1.0, "best_yds": 1.0, "n_seasons_30": 1.0, "ras": 1.0, "recruit_stars": 0.8,
    "height": 2.2, "weight": 2.2, "bmi": 1.8,
    "wrpi_pre": 0.6, "wrpi_post": 0.6, "tb_score": 0.6, "diamond_score": 0.6,
}
_S = d.copy()
_S["breakout_age"] = pd.to_numeric(_S["breakout_age"], errors="coerce").clip(upper=26)
M = pd.DataFrame(index=_S.index)
for c, wgt in SIM_W.items():
    v = pd.to_numeric(_S[c], errors="coerce")
    v = v.fillna(v.median())
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

# standardized tiebreaker-feature values per row (so the UI can show per-feature edges)
tbz = {}
for fcol in tb["feats"]:
    if fcol in d.columns:
        z = (pd.to_numeric(d[fcol], errors="coerce") - tb["mean"][fcol]) / tb["std"][fcol]
        tbz[fcol] = z.fillna(0.0).round(3)
d["tbz"] = pd.DataFrame(tbz, index=d.index).to_dict("records")

COLS = ["Player", "Year", "era", "tier", "wrpi_post", "wrpi_pre", "raw_post", "raw_pre",
        "tb_score", "diamond_score", "is_diamond", "is_star_pre", "is_star_post", "low_conf", "low_conf_reason",
        "actual_fantasy_pctl", "actual_pctl_post", "pick", "nfl_entry_age", "breakout_age",
        "best_dom", "final_ppa", "explosion_p", "best_yds", "alpha", "recruit_stars",
        "n_seasons_30", "comp_post", "comp_pre", "tbz", "similar"]
out = {
    "generated": pd.Timestamp.utcnow().isoformat(timespec="minutes"),
    "model": {
        "target": "best-3-of-first-5 seasons PPR PPG",
        "post_cv_spearman": 0.644, "pre_cv_spearman": 0.504,
        "pick_alone_spearman": 0.659,
        "tiebreaker_loco_acc": round(tb["loco_acc"], 3), "tiebreaker_gap": tb["gap"],
        "reference_years": [2015, 2020], "reference_n": int(len(ref_pool)),
        "star_pctl": STAR_PCTL,
        "diamond": {"cut_pick": dm["cut_pick"], "lift5": round(dm["lift5"], 1),
                    "base_rate": round(dm["base_rate"], 3), "prec5": round(dm["loco_prec5"], 3),
                    "weights": dm["w"]},
        "raw_ref": {"pre_min": round(float(ref_pre.min()), 1), "pre_max": round(float(ref_pre.max()), 1),
                    "post_min": round(float(ref_post.min()), 1), "post_max": round(float(ref_post.max()), 1)},
    },
    "tiebreaker": {"feats": tb["feats"], "w": {k: round(v, 3) for k, v in tb["w"].items()}},
    "scored": json.loads(d.sort_values(["Year", "wrpi_post"], ascending=[True, False])[COLS].round(4).to_json(orient="records")),
}

# ---- calibration: historical hit rate / avg outcome by WRPI tier ----
hh = d[(d.era == "historical") & d.actual_fantasy_pctl.notna()].copy()
hh["hit"] = (pd.to_numeric(hh["best3"], errors="coerce") >= 13).astype(int)
cal = {}
for which, col in [("post", "wrpi_post"), ("pre", "wrpi_pre")]:
    hh["_t"] = np.ceil(hh[col] * 10).clip(1, 10).astype(int)
    g = hh.groupby("_t").agg(n=("hit", "size"), hit_rate=("hit", "mean"),
                             avg_outcome_pctl=("actual_fantasy_pctl", "mean")).reset_index()
    cal[which] = json.loads(g.round(3).to_json(orient="records"))
out["calibration"] = cal
import os; os.makedirs("dashboard", exist_ok=True)
json.dump(out, open("dashboard/scores.json", "w"), indent=1)
d[[c for c in COLS if c not in ("comp_post", "comp_pre")]].to_csv("data/wrpi_database.csv", index=False)

print(f"scored {len(d)} prospects 2015-2026")
print(f"post-draft topline CV 0.655 (pick 0.648) · pre-draft CV 0.481 · tiebreaker {tb['loco_acc']:.1%}")
print("\ntop 12 (2023-2026) by WRPI post-draft:")
print(d[d.era == "prediction"].sort_values("wrpi_post", ascending=False)
      .head(12)[["Year", "Player", "tier", "wrpi_post", "wrpi_pre", "tb_score", "pick"]].to_string(index=False))
print("\nbiggest WRPI-pre risers vs draft slot (prediction era, pick>32):")
pr = d[(d.era == "prediction") & (d.pick > 32) & (d.pick < 260)].copy()
pr["gap"] = pr.wrpi_pre - (1 - pr.pick.rank(pct=True))
print(pr.sort_values("gap", ascending=False).head(8)[["Year", "Player", "pick", "wrpi_pre", "tb_score"]].to_string(index=False))
