"""WRPI (Wide Receiver Prospect Indicator) — frozen scoring function.

Reverse-engineered from the 2010-2022 "Prospect Success Indicator" percentile
database, then re-fit and cross-validated on 2014-2022. This module is the single
source of truth for scoring; params + reference distribution are frozen JSON.

Param vector (JSON lists):
  PRE  (11): [alpha, bo_zero, bo_slope, bo_cap, nfl_zero, nfl_slope, nfl_cap,
              dom35, dom20, swrm_per_hit, bench]
  POST (13):  PRE + [cap_slope, cap_ceil]

SWRM is scored CONSERVATIVELY: a drill a prospect did not run counts as a miss,
not a pass. Modern prospects skip drills they expect to test poorly in, so an
unrun drill is evidence against, not neutral. The "what-if ceiling" flips this
(every unrun drill = pass) to bound the optimistic case; the truth sits in the band.
"""
import numpy as np

DETREND_SLOPE  = 0.69
DETREND_ANCHOR = 2018
SWRM_MAX       = 8

def _ramp(x, zero, slope, ceil):
    return np.clip(slope * (zero - x), 0, ceil)

def swrm_points(p, hits, tested, whatif=False):
    hits = np.asarray(hits, float)
    if whatif:                                   # every unrun drill assumed a pass
        hits = hits + (SWRM_MAX - np.asarray(tested, float))
    return p[9] * np.clip(hits, 0, SWRM_MAX)

def raw_pre(p, d, whatif=False):
    return (
        p[0] * d['alpha_f'].to_numpy(float)
        + _ramp(d['bo_age'].to_numpy(float),  p[1], p[2], p[3])
        + _ramp(d['nfl_age'].to_numpy(float), p[4], p[5], p[6])
        + np.where(d['dom'].to_numpy(float) >= 0.35, p[7],
          np.where(d['dom'].to_numpy(float) >= 0.20, p[8], 0.0))
        + swrm_points(p, d['swrm_hits'], d['swrm_tested'], whatif)
        + p[10] * d['benchp'].to_numpy(float)
    )

def cap_points(p, pick):
    pick = np.clip(np.asarray(pick, float), 1, 300)
    return np.clip(p[11] * (np.log(300) - np.log(pick)), 0, p[12])

def raw_post(p, d, whatif=False):
    return raw_pre(p, d, whatif) + cap_points(p, d['pick'].to_numpy(float))

def detrend(raw, year):
    return np.asarray(raw, float) + DETREND_SLOPE * (np.asarray(year, float) - DETREND_ANCHOR)

def to_percentile(adj_raw, reference_sorted):
    ref = np.asarray(reference_sorted, float)
    return np.searchsorted(ref, np.asarray(adj_raw, float), side='right') / len(ref)

BOUNDS_PRE = [
    (0, 40),
    (19, 24), (0, 15), (0, 30),
    (21, 25), (0, 15), (0, 30),
    (0, 20), (0, 15),
    (0, 4),
    (0, 12),
]
BOUNDS_POST = BOUNDS_PRE + [(0, 25), (0, 45)]
