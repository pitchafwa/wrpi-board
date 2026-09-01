"""RBPI v1 — frozen scoring functions, fitted to actual fantasy production
(best-2-of-first-3 PPR PPG, front-loaded for RB shelf life). Post-draft is the
topline; pre-draft is the pre-NFL-draft talent read."""
import numpy as np

def _ramp(x, z, s, c): return np.clip(s * (z - x), 0, c)

# feature columns expected: nfl_age, bo_age, dom(0-.65), rec(0-.5), eff(z-score),
#   expl(explosion_p 0-1), yds(best_scrim_yds/1000), pick(1-300)
def raw_pre(p, d):
    return (_ramp(d["nfl_age"].to_numpy(float), p[0], p[1], p[2])
            + _ramp(d["bo_age"].to_numpy(float),  p[3], p[4], p[5])
            + np.clip(p[6] * d["dom"].to_numpy(float), 0, p[7])
            + np.clip(p[8] * d["rec"].to_numpy(float), 0, p[9])
            + np.clip(p[10] * (d["eff"].to_numpy(float) + 2.0), 0, p[11])
            + np.clip(p[12] * d["expl"].to_numpy(float), 0, p[13])
            + np.clip(p[14] * d["yds"].to_numpy(float), 0, p[15]))

def cap_points(p, pick):
    return np.clip(p[16] * np.power(np.clip(pick, 1, 300) + p[17], -p[18]), 0, p[19])

def raw_post(p, d):
    return raw_pre(p, d) + cap_points(p, d["pick"].to_numpy(float))

def components_post(p, d):
    return {
        "Draft capital":        cap_points(p, d["pick"].to_numpy(float)),
        "Efficiency (YPC/PPA)": np.clip(p[10] * (d["eff"].to_numpy(float) + 2.0), 0, p[11]),
        "Production volume":    np.clip(p[14] * d["yds"].to_numpy(float), 0, p[15]),
        "NFL entry age":        _ramp(d["nfl_age"].to_numpy(float), p[0], p[1], p[2]),
        "Breakout age":         _ramp(d["bo_age"].to_numpy(float), p[3], p[4], p[5]),
        "College dominator":    np.clip(p[6] * d["dom"].to_numpy(float), 0, p[7]),
        "Receiving role":       np.clip(p[8] * d["rec"].to_numpy(float), 0, p[9]),
        "Athletic explosion":   np.clip(p[12] * d["expl"].to_numpy(float), 0, p[13]),
    }

def components_pre(p, d):
    return {
        "Efficiency (YPC/PPA)": np.clip(p[10] * (d["eff"].to_numpy(float) + 2.0), 0, p[11]),
        "Production volume":    np.clip(p[14] * d["yds"].to_numpy(float), 0, p[15]),
        "Athletic explosion":   np.clip(p[12] * d["expl"].to_numpy(float), 0, p[13]),
        "NFL entry age":        _ramp(d["nfl_age"].to_numpy(float), p[0], p[1], p[2]),
        "Breakout age":         _ramp(d["bo_age"].to_numpy(float), p[3], p[4], p[5]),
        "College dominator":    np.clip(p[6] * d["dom"].to_numpy(float), 0, p[7]),
        "Receiving role":       np.clip(p[8] * d["rec"].to_numpy(float), 0, p[9]),
    }

def to_percentile(x, ref_sorted):
    ref = np.asarray(ref_sorted, float)
    return np.searchsorted(ref, np.asarray(x, float), side="right") / len(ref)
