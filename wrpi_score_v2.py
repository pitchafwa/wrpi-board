"""WRPI v2 — frozen scoring, fitted to actual fantasy production (best-3-of-first-5
PPR PPG). Post-draft is the topline; pre-draft is the pre-NFL-draft ranking.
Plus the head-to-head tiebreaker score."""
import numpy as np

def _ramp(x, z, s, c): return np.clip(s * (z - x), 0, c)

# feature columns expected: alpha, nfl_age, bo_age, dom(0-0.6), ppa(final_ppa),
#   expl(explosion_p 0-1), yds(best_yds/1000), pick(1-300)
def raw_pre(p, d):
    return (p[0] * d["alpha"].to_numpy(float)
            + _ramp(d["nfl_age"].to_numpy(float), p[1], p[2], p[3])
            + _ramp(d["bo_age"].to_numpy(float),  p[4], p[5], p[6])
            + np.clip(p[7] * d["dom"].to_numpy(float), 0, p[8])
            + np.clip(p[9] * (d["ppa"].to_numpy(float) + 0.5), 0, p[10])
            + np.clip(p[11] * d["expl"].to_numpy(float), 0, p[12])
            + np.clip(p[13] * d["yds"].to_numpy(float), 0, p[14]))

def cap_points(p, pick):
    return np.clip(p[15] * np.power(np.clip(pick, 1, 300) + p[16], -p[17]), 0, p[18])

def raw_post(p, d):
    return raw_pre(p, d) + cap_points(p, d["pick"].to_numpy(float))

def components_post(p, d):
    return {
        "Draft capital":            cap_points(p, d["pick"].to_numpy(float)),
        "Final-season efficiency":  np.clip(p[9] * (d["ppa"].to_numpy(float) + 0.5), 0, p[10]),
        "Production volume":        np.clip(p[13] * d["yds"].to_numpy(float), 0, p[14]),
        "NFL entry age":            _ramp(d["nfl_age"].to_numpy(float), p[1], p[2], p[3]),
        "Breakout age":             _ramp(d["bo_age"].to_numpy(float), p[4], p[5], p[6]),
        "College dominator":        np.clip(p[7] * d["dom"].to_numpy(float), 0, p[8]),
        "Athletic explosion":       np.clip(p[11] * d["expl"].to_numpy(float), 0, p[12]),
        "Alpha WR":                 p[0] * d["alpha"].to_numpy(float),
    }

def components_pre(p, d):
    return {
        "Final-season efficiency": np.clip(p[9] * (d["ppa"].to_numpy(float) + 0.5), 0, p[10]),
        "Production volume":       np.clip(p[13] * d["yds"].to_numpy(float), 0, p[14]),
        "Athletic explosion":      np.clip(p[11] * d["expl"].to_numpy(float), 0, p[12]),
        "NFL entry age":           _ramp(d["nfl_age"].to_numpy(float), p[1], p[2], p[3]),
        "Breakout age":            _ramp(d["bo_age"].to_numpy(float), p[4], p[5], p[6]),
        "College dominator":       np.clip(p[7] * d["dom"].to_numpy(float), 0, p[8]),
        "Alpha WR":                p[0] * d["alpha"].to_numpy(float),
    }

def to_percentile(x, ref_sorted):
    ref = np.asarray(ref_sorted, float)
    return np.searchsorted(ref, np.asarray(x, float), side="right") / len(ref)

def tiebreaker_score(tb, df):
    """one linear score per player; P(A>B) = sigmoid(tb_A - tb_B)"""
    s = np.zeros(len(df))
    for f in tb["feats"]:
        z = (df[f].to_numpy(float) - tb["mean"][f]) / tb["std"][f]
        s = s + tb["w"][f] * np.nan_to_num(z, nan=0.0)
    return s
