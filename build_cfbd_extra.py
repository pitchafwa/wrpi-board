"""Pull the extra CFBD feeds for v2 features: HS recruiting rankings, SP+ team
ratings, player PPA (efficiency), player usage share. Cached per year."""
import warnings; warnings.filterwarnings("ignore")
import os, json, time, urllib.request
import pandas as pd

KEY = os.environ.get("CFBD_KEY", "5x8zLVHFDJbBmVYC5xyik1/InQXnpQsS9CzZCyoDf8h4gmsS3OVRyUWcvVP2xUA8")
os.makedirs("data/cfbd_raw", exist_ok=True)

def get(path, cache):
    fn = f"data/cfbd_raw/{cache}.json"
    if os.path.exists(fn):
        return json.load(open(fn))
    r = urllib.request.Request("https://api.collegefootballdata.com" + path,
                               headers={"Authorization": "Bearer " + KEY, "User-Agent": "Mozilla/5.0"})
    try:
        d = json.loads(urllib.request.urlopen(r, timeout=60).read())
    except Exception as e:
        print("  !", cache, repr(e)[:80]); d = []
    json.dump(d, open(fn, "w")); time.sleep(0.35)
    return d

recruit, spp, ppa, usage = [], [], [], []
for yr in range(2011, 2026):
    r = get(f"/recruiting/players?year={yr}&classification=HighSchool", f"recruit_{yr}")
    for x in r:
        if (x.get("position") or "") in ("WR", "PRO", "APB", "ATH"):
            recruit.append({"year": yr, "athleteId": x.get("athleteId"), "name": x.get("name"),
                            "school": x.get("committedTo"), "stars": x.get("stars"),
                            "rating": x.get("rating"), "rank": x.get("ranking")})
    for x in get(f"/ratings/sp?year={yr}", f"sp_{yr}"):
        spp.append({"year": yr, "team": x.get("team"), "sp_overall": x.get("rating"),
                    "sp_offense": (x.get("offense") or {}).get("rating"),
                    "sp_defense": (x.get("defense") or {}).get("rating"), "sos": x.get("sos")})
    def _n(v):
        return (v or {}).get("all") if isinstance(v, dict) else v
    for x in get(f"/ppa/players/season?year={yr}", f"ppa_{yr}"):
        if (x.get("position") or "") in ("WR", "TE"):
            ppa.append({"year": yr, "athleteId": x.get("id"), "name": x.get("name"), "team": x.get("team"),
                        "avg_ppa": _n(x.get("averagePPA")), "avg_ppa_pass": (x.get("averagePPA") or {}).get("pass") if isinstance(x.get("averagePPA"), dict) else None,
                        "total_ppa": _n(x.get("totalPPA"))})
    for x in get(f"/player/usage?year={yr}", f"usage_{yr}"):
        if (x.get("position") or "") in ("WR", "TE"):
            u = x.get("usage") or {}
            usage.append({"year": yr, "athleteId": x.get("id"), "name": x.get("name"), "team": x.get("team"),
                          "usage_overall": u.get("overall"), "usage_pass": u.get("passingDowns"),
                          "usage_std": u.get("standardDowns")})
    print(f"{yr}: recruit+{len([r for r in recruit if r['year']==yr])} sp+{len([s for s in spp if s['year']==yr])} "
          f"ppa+{len([p for p in ppa if p['year']==yr])} usage+{len([u for u in usage if u['year']==yr])}")

pd.DataFrame(recruit).to_csv("data/cfbd_recruiting.csv", index=False)
pd.DataFrame(spp).to_csv("data/cfbd_sp.csv", index=False)
pd.DataFrame(ppa).to_csv("data/cfbd_ppa.csv", index=False)
pd.DataFrame(usage).to_csv("data/cfbd_usage.csv", index=False)
print("saved cfbd_recruiting / cfbd_sp / cfbd_ppa / cfbd_usage .csv")
