"""Assemble the WR prospect pool (drafted OR combine-invited OR pro-day-charted)
for the not-yet-mature classes. Runs in the scheduled pipeline, so YEARS extends
itself: from 2023 through next calendar year (covers the upcoming class the
moment nflverse posts its projected picks / combine invites)."""
import datetime
import pandas as pd, re, unicodedata

YEARS = list(range(2023, datetime.date.today().year + 2))

# known name variants: NFL sources vs college sources use different names
NAME_ALIAS = {
    "tank dell": "nathaniel dell",
    "tutu atwell": "chatarius atwell",
    "bisi johnson": "olabisi johnson",
    "scotty miller": "scott miller",
    "gabe davis": "gabriel davis",
}

def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return NAME_ALIAS.get(n, n)
def nteam(s):
    s = norm(s); return re.sub(r"\b(university|college|of|the|state|st|at)\b", "", s).replace(" ", "")

draft = pd.read_csv("data/draft_picks.csv", low_memory=False)
comb  = pd.read_csv("data/combine.csv")
rc    = pd.read_csv("data/combine_pro_day.csv")

d = draft[(draft.season.isin(YEARS)) & (draft.position == 'WR')][['season', 'pfr_player_name', 'pick', 'team', 'college']].copy()
d.columns = ['Year', 'Player', 'draft_pick', 'nfl_team', 'college']; d['src_draft'] = 1
c = comb[(comb.season.isin(YEARS)) & (comb.pos == 'WR')][['season', 'player_name', 'school', 'draft_ovr']].copy()
c.columns = ['Year', 'Player', 'college', 'draft_pick']; c['src_combine'] = 1
p = rc[(rc.Year.isin(YEARS)) & (rc.POS_GP == 'WR')][['Year', 'player', 'College', 'athlete_id']].copy()
p.columns = ['Year', 'Player', 'college', 'athlete_id']; p['src_proday'] = 1

pool = pd.concat([d, c, p], ignore_index=True)
pool['key'] = pool['Player'].map(norm)

agg = pool.groupby(['key', 'Year']).agg(
    Player=('Player', 'first'),
    draft_pick=('draft_pick', lambda s: s.dropna().min() if s.notna().any() else pd.NA),
    college=('college', lambda s: next((x for x in s if pd.notna(x)), pd.NA)),
    nfl_team=('nfl_team', lambda s: next((x for x in s if pd.notna(x)), pd.NA)) if 'nfl_team' in pool else ('Player', 'first'),
    athlete_id=('athlete_id', lambda s: next((x for x in s if pd.notna(x)), pd.NA)),
    src_draft=('src_draft', 'max'), src_combine=('src_combine', 'max'), src_proday=('src_proday', 'max'),
).reset_index()

# second pass: merge rows that are the same person under different names
#   (same Year + same school + same surname, one of them drafted)
agg['_ln'] = agg['key'].str.split().str[-1]
agg['_tk'] = agg['college'].map(nteam)
agg['_g'] = agg.apply(lambda r: f"{r.Year}|{r._tk}|{r._ln}" if pd.notna(r._tk) and r._tk else f"solo|{r.name}", axis=1)
agg['_haspick'] = agg['draft_pick'].notna().astype(int)
merged = (agg.sort_values(['_haspick', 'src_proday'], ascending=False)
             .groupby('_g', as_index=False)
             .agg({'key': 'first', 'Year': 'first', 'Player': 'first',
                   'draft_pick': 'min', 'college': 'first', 'nfl_team': 'first',
                   'athlete_id': lambda s: next((x for x in s if pd.notna(x)), pd.NA),
                   'src_draft': 'max', 'src_combine': 'max', 'src_proday': 'max'}))
for c_ in ['src_draft', 'src_combine', 'src_proday']:
    merged[c_] = merged[c_].fillna(0).astype(int)
merged['drafted'] = merged['draft_pick'].notna() & (merged['src_draft'] == 1)

merged.drop(columns=[]).to_csv("data/pool_2023_2025.csv", index=False)
print(f"POOL: {len(merged)} WR prospects, {YEARS[0]}-{YEARS[-1]}  (merged {len(agg)-len(merged)} name-variant dups)")
print(merged.groupby('Year').agg(n=('key', 'size'), drafted=('drafted', 'sum')).to_string())
