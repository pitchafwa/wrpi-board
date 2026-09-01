"""Build the full WRPI database (2015-2025) + dashboard feed.
Historical 2015-2022 comes from the reverse-engineering feature table (with the
real PSI percentile alongside for validation); 2023-2025 is featurized fresh from
combine/pro-day + CollegeFootballData. Everything is scored with the frozen WRPI
model, era-detrended, and ranked against the frozen 2014-2022 reference.
Unmatched (no college data / no birth date) prospects are flagged, never scored."""
import warnings; warnings.filterwarnings("ignore")
import json, re, unicodedata, os, time, urllib.request
import numpy as np, pandas as pd
import wrpi_score as P

KEY = os.environ.get("CFBD_KEY", "")   # free key: https://collegefootballdata.com/key
SC_PATH = "data/cfbd_raw/player_search.json"
_sc = json.load(open(SC_PATH)) if os.path.exists(SC_PATH) else {}

def search(term):
    if term in _sc: return _sc[term]
    url = 'https://api.collegefootballdata.com/player/search?searchTerm=' + urllib.request.quote(term)
    r = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + KEY, 'User-Agent': 'Mozilla/5.0'})
    try: d = json.loads(urllib.request.urlopen(r, timeout=45).read())
    except Exception: d = []
    _sc[term] = d; json.dump(_sc, open(SC_PATH, 'w')); time.sleep(0.4)
    return d

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()
_ALIAS = {'mississippi':'olemiss','southerncalifornia':'usc','southerncal':'usc','pittsburgh':'pitt',
    'texaschristian':'tcu','centralflorida':'ucf','louisianastate':'lsu','miamifl':'miami',
    'brighamyoung':'byu','northcarolina':'unc'}
def nteam(s):
    s = norm(s); s = re.sub(r"\b(university|college|of|the|at|a m|am|st)\b", "", s).replace(" ", "")
    s = s.replace("state", "st"); return _ALIAS.get(s, s)
def school_match(a, b):
    a, b = nteam(a), nteam(b)
    if not a or not b: return False
    if a == b: return True
    if len(a) >= 5 and len(b) >= 5 and (a in b or b in a): return True
    return len(a) >= 7 and len(b) >= 7 and a[:7] == b[:7]
def g(src, col):
    return src[col] if (src is not None and col in src and pd.notna(src[col])) else np.nan
def coal(*v):
    for x in v:
        if pd.notna(x): return x
    return np.nan

# ---------- sources ----------
pool    = pd.read_csv("data/pool_2023_2025.csv")
# collapse duplicate rows for the same person (e.g. "Tank Dell" + "Nathaniel Dell")
pool['_aid'] = pd.to_numeric(pool['athlete_id'], errors='coerce')
_dups = pool[pool['_aid'].notna()].sort_values('draft_pick').drop_duplicates(['_aid', 'Year'], keep='first')
pool = pd.concat([pool[pool['_aid'].isna()], _dups], ignore_index=True)
comb    = pd.read_csv("data/combine.csv");            comb['key'] = comb['player_name'].map(norm)
players = pd.read_csv("data/players.csv", low_memory=False); players['key'] = players['display_name'].map(norm)
draft   = pd.read_csv("data/draft_picks.csv", low_memory=False); draft['key'] = draft['pfr_player_name'].map(norm)
rc      = pd.read_csv("data/combine_pro_day.csv");    rc['key'] = rc['player'].map(norm)
rc      = rc[rc['POS_GP'] == 'WR']
cf      = pd.read_csv("data/cfbd_player_seasons.csv"); cf['key'] = cf['player'].map(norm)
cf_ids  = set(cf['playerId'].unique())
id_school = cf.groupby('playerId')['team'].agg(lambda s: s.mode().iloc[0]).to_dict()

def pick_year(df, key, yr, ycol):
    c = df[df['key'] == key]
    if len(c) == 0: return None
    if yr is not None and ycol in c: c = c.iloc[(c[ycol] - yr).abs().values.argsort()]
    return c.iloc[0]

BO_THR = 0.20
rows = []
for _, r in pool.iterrows():
    k, yr = r['key'], int(r['Year'])
    o = {'Player': r['Player'], 'Year': yr, 'drafted': bool(r['drafted'])}
    pl = pick_year(players, k, yr, 'draft_year'); dr = pick_year(draft, k, yr, 'season')
    pc = pick_year(comb, k, yr, 'season')
    college = coal(r.get('college'), g(pl, 'college_name'), g(dr, 'college'))
    ck = nteam(college) if pd.notna(college) else ""
    bd = pd.to_datetime(g(pl, 'birth_date'), errors='coerce') if pl is not None else None

    rcc = rc[rc['key'] == k]
    if len(rcc) and ck:
        pref = rcc[rcc['College'].apply(lambda t: school_match(college, t))]
        if len(pref): rcc = pref
    rr = rcc.iloc[(rcc['Year'] - yr).abs().values.argsort()].iloc[0] if len(rcc) else None

    ht = coal(g(rr, 'Height (in)'), g(pc, 'ht'))
    if isinstance(ht, str) and '-' in ht:
        a_, b_ = ht.split('-'); ht = int(a_) * 12 + int(b_)
    wt    = coal(g(rr, 'Weight (lbs)'), g(pc, 'wt'))
    forty = coal(g(rr, '40 Yard'), g(pc, 'forty'))
    bench = coal(g(rr, 'Bench Press'), g(pc, 'bench'))
    vert  = coal(g(rr, 'Vert Leap (in)'), g(pc, 'vertical'))
    broad = coal(g(rr, 'Broad Jump (in)'), g(pc, 'broad_jump'))
    cone  = coal(g(rr, '3Cone'), g(pc, 'cone'))
    shu   = coal(g(rr, 'Shuttle'), g(pc, 'shuttle'))
    hand  = g(rr, 'Hand Size (in)')
    aid   = coal(r.get('athlete_id'), g(rr, 'athlete_id'))
    ppi   = (wt / ht) if (pd.notna(wt) and pd.notna(ht) and ht) else np.nan

    checks = [(ppi, 2.75, '>='), (hand, 9.5, '>='), (ht, 72, '>='), (forty, 4.50, '<='),
              (vert, 35.0, '>='), (broad, 120, '>='), (shu, 4.30, '<='), (cone, 7.00, '<=')]
    hits = tested = 0
    for v, thr, op in checks:
        if pd.notna(v):
            tested += 1
            hits += (v >= thr) if op == '>=' else (v <= thr)
    o['swrm_hits'], o['swrm_tested'] = int(hits), int(tested)
    o['benchp'] = float(bench >= 10) if pd.notna(bench) else 0.0
    o['bench_known'] = pd.notna(bench)

    pick = coal(r.get('draft_pick'), g(dr, 'pick'), g(pc, 'draft_ovr'), g(pl, 'draft_pick'))
    o['pick'] = float(pick) if pd.notna(pick) else 270.0
    o['nfl_age'] = ((pd.Timestamp(yr, 1, 1) - bd).days / 365.25) if (bd is not None and pd.notna(bd)) else np.nan

    # ---- CFBD college: athlete_id -> school-matched search -> name-only search ----
    cid = None; how = 'none'
    toks = norm(r['Player']).split()
    if pd.notna(aid) and int(aid) in cf_ids:
        cid = int(aid); how = 'athlete_id'
    if cid is None:
        res = list(search(r['Player'])) + (search(toks[-1]) if len(toks) >= 2 else [])
        cands = []
        for x in res:
            try: xid = int(x['id'])
            except Exception: continue
            if xid <= 0 or xid not in cf_ids: continue
            pos = (x.get('position') or '').upper()
            if pos and pos not in ('WR', 'ATH', 'TE'): continue
            xn = norm(x.get('name') or ''); xt = xn.split()
            name_ok = bool(xt) and xt[-1] == toks[-1] and (xn == norm(r['Player']) or (toks and xt[0][:1] == toks[0][:1]))
            id_ok = pd.notna(aid) and xid == int(aid)
            sch_ok = bool(ck) and school_match(college, x.get('team') or '')
            yds = cf[cf['playerId'] == xid]['rec_yds'].sum()
            cands.append({'id': xid, 'name_ok': name_ok, 'id_ok': id_ok, 'sch_ok': sch_ok, 'yds': yds})
        cands = {c['id']: c for c in cands}.values()
        # 1: id match from search  2: school match  3: unique/strong name match
        for tier, keyfn, lab in [
            (1, lambda c: c['id_ok'], 'search_idmatch'),
            (2, lambda c: c['sch_ok'], 'search_school'),
            (3, lambda c: c['name_ok'], 'search_nameonly')]:
            hits = [c for c in cands if keyfn(c)]
            if hits:
                cid = max(hits, key=lambda c: c['yds'])['id']; how = lab; break
    o['col_match'] = how

    cc = cf[cf['playerId'] == cid] if cid is not None else pd.DataFrame()
    o['cfbd_id'] = cid
    # recover birthdate / age via the CFBD canonical name if the pool name missed
    if (bd is None or pd.isna(bd)) and len(cc):
        cname = norm(cc['player'].mode().iloc[0])
        pl2 = pick_year(players, cname, yr, 'draft_year')
        if pl2 is not None and pd.notna(pl2.get('birth_date')):
            bd = pd.to_datetime(pl2['birth_date'], errors='coerce')
        if bd is None or pd.isna(bd):
            dr2 = pick_year(draft, cname, yr, 'season')
            if dr2 is not None and pd.notna(dr2.get('age')):
                o['nfl_age'] = float(dr2['age']) - 0.33   # draft age (Apr) -> ~Jan 1
    if bd is not None and pd.notna(bd):
        o['nfl_age'] = (pd.Timestamp(yr, 1, 1) - bd).days / 365.25
    # drafted players: age via exact pick lookup (name-agnostic)
    if pd.isna(o.get('nfl_age')) and pd.notna(r.get('draft_pick')):
        drp = draft[(draft['season'] == yr) & (draft['pick'] == float(r['draft_pick']))]
        if len(drp) and pd.notna(drp.iloc[0].get('age')):
            o['nfl_age'] = float(drp.iloc[0]['age']) - 0.33
    # last resort: nflverse players by last-name + college + rookie season (catches spelling variants)
    if pd.isna(o.get('nfl_age')) and toks and pd.notna(college):
        cand = players[players['key'].str.endswith(' ' + toks[-1], na=False) |
                       (players['key'] == toks[-1])]
        cand = cand[cand['college_name'].apply(lambda t: school_match(college, t))
                    & cand['birth_date'].notna()]
        if 'rookie_season' in cand:
            cand = cand[cand['rookie_season'].between(yr - 1, yr + 1) | cand['rookie_season'].isna()]
        if len(cand) == 1:
            o['nfl_age'] = (pd.Timestamp(yr, 1, 1) - pd.to_datetime(cand.iloc[0]['birth_date'])).days / 365.25
    if len(cc):
        cc = cc.sort_values('season')
        o['dom']   = float(cc['dominator'].max())
        o['alpha_f'] = float((cc['team_rec_rank'] == 1).any())
        bo = cc[cc['dominator'] >= BO_THR]
        if len(bo) and bd is not None and pd.notna(bd):
            s = int(bo['season'].min())
            o['bo_age'] = (pd.Timestamp(s, 10, 15) - bd).days / 365.25
        else:
            o['bo_age'] = 99.0
        o['n_col_seasons'] = int(cc['season'].nunique())
        o['scored'] = True
    else:
        o.update(dom=np.nan, alpha_f=np.nan, bo_age=np.nan, n_col_seasons=0, scored=False)
    rows.append(o)

feat = pd.DataFrame(rows).reset_index(drop=True)
# merge duplicate people: same CFBD id, or same (year, real draft pick) e.g. Tank/Nathaniel Dell
feat['_rank'] = feat['scored'].astype(int) + feat['nfl_age'].notna().astype(int)
def _gkey(r):
    if pd.notna(r['pick']) and r['pick'] < 260: return f"pk:{r['Year']}:{int(r['pick'])}"
    if pd.notna(r['cfbd_id']):            return f"id:{int(r['cfbd_id'])}:{r['Year']}"
    return f"row:{r.name}"
feat['_gk'] = feat.apply(_gkey, axis=1)
feat = (feat.sort_values('_rank', ascending=False)
            .drop_duplicates('_gk', keep='first')
            .drop(columns=['_rank', '_gk'])
            .sort_index().reset_index(drop=True))

newfeat = pd.DataFrame(rows)
newfeat['era'] = 'prediction'
newfeat['actual_pctl_pre'] = np.nan
newfeat['actual_pctl_post'] = np.nan

# ---- historical 2015-2022 from the reverse-engineering feature table ----
h = pd.read_csv("data/historical_2015_2022.csv")
h = h[(h['col_match'] != 'none') & h['best_dom'].notna() & h['nfl_entry_age'].notna() &
      ~h['Player'].isin({"Tyrell Williams", "Mike Woods"})].copy()
h.loc[h['ever_breakout'] == 0, 'breakout_age'] = 99.0
hist = pd.DataFrame({
    'Player': h['Player'], 'Year': h['Year'].astype(int),
    'drafted': h['draft_pick'].fillna(270) < 260,
    'swrm_hits': h['swrm_hits'].fillna(0).astype(int), 'swrm_tested': h['swrm_tested'].fillna(0).astype(int),
    'benchp': h['bench_pass'].fillna(0).astype(float), 'bench_known': h['bench_pass'].notna(),
    'pick': h['draft_pick'].fillna(270).clip(1, 300),
    'nfl_age': h['nfl_entry_age'], 'col_match': h['col_match'], 'cfbd_id': np.nan,
    'dom': h['best_dom'].clip(0, 0.8), 'alpha_f': h['alpha'].fillna(0).astype(float),
    'bo_age': h['breakout_age'].fillna(99.0), 'n_col_seasons': h.get('n_col_seasons', 0),
    'scored': True, 'era': 'historical',
    'actual_pctl_pre': h['pctl_pre'], 'actual_pctl_post': h['pctl_post'],
})

feat = pd.concat([hist, newfeat], ignore_index=True)

ref = json.load(open("data/wrpi_reference.json"))
p_pre  = json.load(open("data/wrpi_params_pre.json"))["params"]
p_post = json.load(open("data/wrpi_params_post.json"))["params"]

ok = feat['scored'] & feat['nfl_age'].notna()
sc  = feat[ok].copy()
uns = feat[~ok].copy()
uns['reason'] = np.where(~uns['scored'], 'no college data', 'no birth date')

def pctl(df, params, post, whatif=False):
    raw = P.raw_post(params, df, whatif) if post else P.raw_pre(params, df, whatif)
    adj = P.detrend(raw, df['Year'])
    return raw, P.to_percentile(adj, ref['reference_post' if post else 'reference_pre'])

def components(d, p):
    R = P._ramp
    return pd.DataFrame({
        'NFL entry age': R(d['nfl_age'].to_numpy(float), p[4], p[5], p[6]),
        'Alpha WR':      p[0] * d['alpha_f'].to_numpy(float),
        'Dominator':     np.where(d['dom'] >= 0.35, p[7], np.where(d['dom'] >= 0.20, p[8], 0.0)),
        'Breakout age':  R(d['bo_age'].to_numpy(float), p[1], p[2], p[3]),
        'SWRM':          P.swrm_points(p, d['swrm_hits'], d['swrm_tested']),
        'Bench':         p[10] * d['benchp'].to_numpy(float),
    }, index=d.index).round(1)

sc['raw_pre'],  sc['pctl_pre']  = pctl(sc, p_pre,  False)
sc['raw_post'], sc['pctl_post'] = pctl(sc, p_post, True)
_, sc['pctl_pre_whatif']  = pctl(sc, p_pre,  False, whatif=True)
_, sc['pctl_post_whatif'] = pctl(sc, p_post, True,  whatif=True)
_comp = components(sc, p_post)
_comp['Draft capital'] = P.cap_points(p_post, sc['pick'].to_numpy(float)).round(1)
sc['components'] = _comp.to_dict(orient='records')
sc['tier_post'] = np.ceil(sc['pctl_post'] * 10).clip(1, 10).astype(int)
sc['tier_pre']  = np.ceil(sc['pctl_pre']  * 10).clip(1, 10).astype(int)
sc['partial_testing'] = sc['swrm_tested'] < 5
sc['whatif_gap'] = (sc['pctl_post_whatif'] - sc['pctl_post']).round(4)

# validation: WRPI vs the real PSI percentile, historical rows only
from scipy.stats import spearmanr
hv = sc[sc['era'] == 'historical']
val = {"n": int(len(hv)),
       "spearman_pre":  round(float(spearmanr(hv['pctl_pre'],  hv['actual_pctl_pre']).correlation), 3),
       "spearman_post": round(float(spearmanr(hv['pctl_post'], hv['actual_pctl_post']).correlation), 3)}

# drift monitor
lo, hi = ref['drift_monitor']['band']
drift = {}
for y in sorted(sc.loc[sc['era'] == 'prediction', 'Year'].unique()):
    m = float(P.detrend(P.raw_post(p_post, sc[sc.Year == y]), y).mean())
    drift[int(y)] = {"mean_detrended_post": round(m, 2), "in_band": bool(lo <= m <= hi)}

cols = ["Player", "Year", "era", "drafted", "tier_post", "pctl_post", "pctl_pre",
        "pctl_post_whatif", "whatif_gap", "actual_pctl_post", "partial_testing",
        "alpha_f", "bo_age", "nfl_age", "dom", "swrm_hits", "swrm_tested", "benchp",
        "pick", "n_col_seasons", "col_match", "raw_pre", "raw_post", "components"]
out = {
    "generated": pd.Timestamp.utcnow().isoformat(timespec="minutes"),
    "model": {"cv_spearman_pre": ref["cv_spearman_pre"], "cv_spearman_post": ref["cv_spearman_post"],
              "reference_n": ref["n_reference"], "reference_years": ref["reference_years"],
              "detrend_slope": ref["detrend_slope"], "detrend_anchor": ref["detrend_anchor"]},
    "validation": val,
    "drift_monitor": {"band": [lo, hi], "by_class": drift, "note": ref['drift_monitor']['note']},
    "scored": json.loads(sc.sort_values(["Year", "pctl_post"], ascending=[True, False])[cols].round(4).to_json(orient="records")),
    "unscored": json.loads(uns[["Player", "Year", "era", "drafted", "col_match", "reason"]].to_json(orient="records")),
}
os.makedirs("dashboard", exist_ok=True)
json.dump(out, open("dashboard/scores.json", "w"), indent=1)
sc[[c for c in cols if c != 'components']].to_csv("data/wrpi_database.csv", index=False)

print(f"WRPI database: {len(sc)} scored ({(sc.era=='historical').sum()} historical, "
      f"{(sc.era=='prediction').sum()} prediction) · {len(uns)} flagged")
print(f"validation vs real PSI (n={val['n']}): Spearman pre {val['spearman_pre']}  post {val['spearman_post']}")
print(f"drift band {lo}-{hi}:  " + "  ".join(f"{y}:{v['mean_detrended_post']}{'ok' if v['in_band'] else ' OUT'}" for y, v in drift.items()))
print("\ntop 12, 2023-2025:")
print(sc[sc.era == 'prediction'].sort_values("pctl_post", ascending=False)
        .head(12)[["Year", "Player", "tier_post", "pctl_post", "pctl_post_whatif", "alpha_f", "bo_age", "nfl_age", "dom", "swrm_hits", "swrm_tested", "pick"]]
        .to_string(index=False))
