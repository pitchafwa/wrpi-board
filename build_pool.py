"""Assemble the 2023-2025 WR prospect pool: drafted OR combine-invited OR pro-day-charted."""
import pandas as pd, re, unicodedata
def norm(n):
    n=unicodedata.normalize('NFKD',str(n)).encode('ascii','ignore').decode().lower()
    n=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b","",n); n=re.sub(r"[^a-z ]","",n)
    return re.sub(r"\s+"," ",n).strip()

YEARS=[2023,2024,2025]
draft=pd.read_csv("data/draft_picks.csv",low_memory=False)
comb =pd.read_csv("data/combine.csv")
rc   =pd.read_csv("data/combine_pro_day.csv")

d = draft[(draft.season.isin(YEARS)) & (draft.position=='WR')][['season','pfr_player_name','pick','team','college']].copy()
d.columns=['Year','Player','draft_pick','nfl_team','college']; d['src_draft']=1

c = comb[(comb.season.isin(YEARS)) & (comb.pos=='WR')][['season','player_name','school','draft_ovr']].copy()
c.columns=['Year','Player','college','draft_pick']; c['src_combine']=1

p = rc[(rc.Year.isin(YEARS)) & (rc.POS_GP=='WR')][['Year','player','College','athlete_id']].copy()
p.columns=['Year','Player','college','athlete_id']; p['src_proday']=1

pool = pd.concat([d,c,p], ignore_index=True)
pool['key']=pool['Player'].map(norm)
# collapse to one row per (key, Year)
agg = pool.groupby(['key','Year']).agg(
    Player=('Player','first'),
    draft_pick=('draft_pick', lambda s: s.dropna().min() if s.notna().any() else pd.NA),
    college=('college', lambda s: next((x for x in s if pd.notna(x)), pd.NA)),
    nfl_team=('nfl_team', lambda s: next((x for x in s if pd.notna(x)), pd.NA)) if 'nfl_team' in pool else ('Player','first'),
    athlete_id=('athlete_id', lambda s: next((x for x in s if pd.notna(x)), pd.NA)),
    src_draft=('src_draft','max'), src_combine=('src_combine','max'), src_proday=('src_proday','max'),
).reset_index()
for c_ in ['src_draft','src_combine','src_proday']: agg[c_]=agg[c_].fillna(0).astype(int)
agg['drafted']= agg['draft_pick'].notna() & (agg['src_draft']==1)

agg.to_csv("data/pool_2023_2025.csv", index=False)
print(f"POOL: {len(agg)} WR prospects, 2023-2025")
print(agg.groupby('Year').agg(n=('key','size'), drafted=('drafted','sum')).to_string())
print("\nsource coverage:")
print(agg.groupby('Year')[['src_draft','src_combine','src_proday']].sum().to_string())
print("\nsample (2025):")
print(agg[agg.Year==2025].sort_values('draft_pick')[['Player','college','draft_pick','drafted']].head(15).to_string(index=False))
