"""Data-quality audit: age, draft-pick assignment, dominator, efficiency (PPA)."""
import warnings; warnings.filterwarnings("ignore")
import re, unicodedata
import numpy as np, pandas as pd
pd.set_option("display.width", 200)
def norm(n):
    n = unicodedata.normalize('NFKD', str(n)).encode('ascii', 'ignore').decode().lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", n); n = re.sub(r"[^a-z ]", "", n)
    return re.sub(r"\s+", " ", n).strip()

F = pd.read_csv("data/features_v3.csv")
pl = pd.read_csv("data/players.csv", low_memory=False); pl["key"] = pl.display_name.map(norm)
dr = pd.read_csv("data/draft_picks.csv", low_memory=False)
cf = pd.read_csv("data/cfbd_player_seasons.csv"); cf["key"] = cf.player.map(norm)
ppa = pd.read_csv("data/cfbd_ppa.csv"); ppa["key"] = ppa.name.map(norm)
F["key"] = F.Player.map(norm)

print("=" * 70, "\n1. AGE — nfl_entry_age outliers (expect ~20-24)\n", "=" * 70)
bad = F[(F.nfl_entry_age > 25) | (F.nfl_entry_age < 19)].sort_values("nfl_entry_age", ascending=False)
for _, r in bad.iterrows():
    pm = pl[pl.key == r.key]
    bds = pm.birth_date.tolist() if len(pm) else []
    print(f"  {r.Player:24s} {int(r.Year)}  age={r.nfl_entry_age:.1f}  birth_date(s)={bds}")
print(f"  -> {len(bad)} rows flagged")

print("\n" + "=" * 70, "\n2. DRAFT PICK — pool player vs the actual draftee at that (year,pick)\n", "=" * 70)
dr_wr = dr[["season", "pick", "pfr_player_name", "position"]].copy()
mism = []
for _, r in F[F.pick < 260].iterrows():
    m = dr_wr[(dr_wr.season == r.Year) & (dr_wr.pick == r.pick)]
    if len(m) and norm(m.iloc[0].pfr_player_name) != r.key:
        mism.append((r.Player, int(r.Year), int(r.pick), m.iloc[0].pfr_player_name, m.iloc[0].position))
print(f"  {len(mism)} rows where the assigned pick belongs to someone else:")
for a in mism[:40]:
    print(f"  {a[0]:24s} {a[1]} pick {a[2]:3d}  -> actually {a[3]} ({a[4]})")

print("\n" + "=" * 70, "\n3. DOMINATOR — best_dom > 0.55 (check team totals)\n", "=" * 70)
hi = F[F.best_dom > 0.55].sort_values("best_dom", ascending=False)
for _, r in hi.iterrows():
    cc = cf[cf.key == r.key]
    if len(cc):
        s = cc.loc[cc.dominator.idxmax()]
        print(f"  {r.Player:22s} dom={r.best_dom:.2f}  {int(s.season)} {s.team:20s} "
              f"rec_yds={s.rec_yds:.0f}/{s.team_rec_yds:.0f} ({s.yd_share:.2f})  "
              f"rec_td={s.rec_td:.0f}/{s.team_rec_td:.0f} ({s.td_share:.2f})")
print(f"  -> {len(hi)} rows. Suspicious if team_rec_yds < ~1800 (partial CFBD team data).")

print("\n" + "=" * 70, "\n4. EFFICIENCY — final_ppa distribution + outliers\n", "=" * 70)
v = F.final_ppa.dropna()
print(f"  final_ppa: mean {v.mean():.2f}  sd {v.std():.2f}  p50 {v.median():.2f}  p95 {v.quantile(.95):.2f}  max {v.max():.2f}")
for _, r in F[F.final_ppa > 1.3].sort_values("final_ppa", ascending=False).iterrows():
    pw = ppa[ppa.key == r.key]
    print(f"  {r.Player:22s} final_ppa={r.final_ppa:.2f}  ppa rows: "
          + ", ".join(f"{int(x.year)}:{x.avg_ppa:.2f}" for _, x in pw.sort_values('year').iterrows()))
mt = ppa[ppa.key == "michael thomas"]
print("\n  Michael Thomas ppa rows (all):")
print(mt[["year", "team", "avg_ppa", "avg_ppa_pass", "total_ppa"]].to_string(index=False))
