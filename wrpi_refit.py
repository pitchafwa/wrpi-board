"""Fit WRPI on 2014-2022 clean data (conservative SWRM = count), freeze params +
era-detrended reference distribution + drift-monitor baseline."""
import warnings; warnings.filterwarnings("ignore")
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from scipy.optimize import differential_evolution
import wrpi_score as W

def load_clean_2014():
    f = pd.read_csv("data/features4.csv")
    BAD = {"Tyrell Williams", "Mike Woods"}
    c = f[(f['col_match'] != 'none') & (~f['Player'].isin(BAD)) &
          f['best_dom'].notna() & f['nfl_entry_age'].notna() & (f['Year'] >= 2014)].copy()
    c.loc[c['ever_breakout'] == 0, 'breakout_age'] = 99.0
    c['alpha_f']     = c['alpha'].fillna(0).astype(float)
    c['bo_age']      = c['breakout_age'].fillna(99.0)
    c['nfl_age']     = c['nfl_entry_age']
    c['dom']         = c['best_dom'].clip(0, 0.8)
    c['swrm_hits']   = c['swrm_hits'].fillna(0)
    c['swrm_tested'] = c['swrm_tested'].fillna(0)
    c['benchp']      = c['bench_pass'].fillna(0).astype(float)
    c['pick']        = c['draft_pick'].fillna(270).clip(1, 300)
    return c.reset_index(drop=True)

def obj(p, d, post):
    r = W.raw_post(p, d) if post else W.raw_pre(p, d)
    tgt = 'pctl_post' if post else 'pctl_pre'
    rho = spearmanr(r, d[tgt]).correlation
    return -(rho if np.isfinite(rho) else 0.0)

def fit(d, post, seed=1):
    b = W.BOUNDS_POST if post else W.BOUNDS_PRE
    r = differential_evolution(obj, b, args=(d, post), seed=seed, maxiter=120,
        popsize=16, tol=1e-6, mutation=(0.5, 1.0), recombination=0.7,
        polish=True, workers=1, updating='deferred')
    return list(r.x), -r.fun

def kfold(p, d, post, k=5):
    idx = np.arange(len(d)); np.random.default_rng(0).shuffle(idx)
    tgt = 'pctl_post' if post else 'pctl_pre'
    return float(np.mean([
        spearmanr((W.raw_post(p, d.iloc[idx[i::k]]) if post else W.raw_pre(p, d.iloc[idx[i::k]])),
                  d.iloc[idx[i::k]][tgt]).correlation for i in range(k)]))

def loco(d, post):
    tgt = 'pctl_post' if post else 'pctl_pre'
    out = []
    for yr in sorted(d['Year'].unique()):
        p, _ = fit(d[d['Year'] != yr], post, 0)
        te = d[d['Year'] == yr]
        r = W.raw_post(p, te) if post else W.raw_pre(p, te)
        out.append(spearmanr(r, te[tgt]).correlation)
    return float(np.mean(out))

if __name__ == "__main__":
    d = load_clean_2014()
    print(f"fit set: {len(d)} players (2014-2022, clean college, conservative SWRM)")
    p_pre,  s_pre  = fit(d, False)
    p_post, s_post = fit(d, True)
    print(f"  PRE : in-sample {s_pre:.3f}  5-fold CV {kfold(p_pre,d,False):.3f}  LOCO {loco(d,False):.3f}")
    print(f"  POST: in-sample {s_post:.3f}  5-fold CV {kfold(p_post,d,True):.3f}  LOCO {loco(d,True):.3f}")

    ref_pre  = np.sort(W.detrend(W.raw_pre(p_pre,  d), d['Year']))
    ref_post = np.sort(W.detrend(W.raw_post(p_post, d), d['Year']))
    d['_adj'] = W.detrend(W.raw_post(p_post, d), d['Year'])
    cmeans = d.groupby('Year')['_adj'].mean().round(3).to_dict()
    cm = np.array(list(cmeans.values()))

    json.dump({"params": p_pre},  open("data/wrpi_params_pre.json", "w"), indent=1)
    json.dump({"params": p_post}, open("data/wrpi_params_post.json", "w"), indent=1)
    json.dump({
        "detrend_slope": W.DETREND_SLOPE, "detrend_anchor": W.DETREND_ANCHOR,
        "reference_pre":  [round(x, 4) for x in ref_pre.tolist()],
        "reference_post": [round(x, 4) for x in ref_post.tolist()],
        "n_reference": len(d), "reference_years": [2014, 2022],
        "cv_spearman_pre": round(kfold(p_pre, d, False), 3),
        "cv_spearman_post": round(kfold(p_post, d, True), 3),
        "drift_monitor": {
            "class_means_detrended_post": cmeans,
            "historical_mean": round(float(cm.mean()), 3),
            "historical_sd": round(float(cm.std()), 3),
            "band": [round(float(cm.mean() - 2 * cm.std()), 1), round(float(cm.mean() + 2 * cm.std()), 1)],
            "note": ("A new class whose mean detrended post score leaves the band is a signal that the "
                     "-0.69 pts/yr era drift assumption has changed (e.g. college passing trends reversed) "
                     "and the detrend slope should be re-estimated.")
        }
    }, open("data/wrpi_reference.json", "w"), indent=1)
    print("saved data/wrpi_params_{pre,post}.json, data/wrpi_reference.json")
    print(f"drift band: {cm.mean()-2*cm.std():.1f} - {cm.mean()+2*cm.std():.1f}")
