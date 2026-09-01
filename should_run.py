"""Self-scheduling gate for the update pipeline. Exit 0 = run, 1 = skip.

Reads data/draft_dates.json and data/.last_pipeline_run and decides:
  - today in [draft_day, draft_day + 10]        -> run every day (catch the picks)
  - Jan 1 .. upcoming draft day (pre-draft ramp) -> run if >= 6 days since last run
  - otherwise (off-season)                       -> run only ~monthly

workflow_dispatch bypasses this (handled in the workflow, not here).
"""
import json, datetime, os, sys

today = datetime.date.today()

try:
    dd = json.load(open("data/draft_dates.json"))
    dates = sorted(datetime.date.fromisoformat(v) for k, v in dd.items() if k.isdigit())
except Exception:
    dates = []
if not dates or max(dates).year < today.year:
    # fallback: last Thursday of April this year
    apr = datetime.date(today.year, 4, 30)
    while apr.weekday() != 3:  # Thursday
        apr -= datetime.timedelta(days=1)
    dates = sorted(set(dates) | {apr})

future = [d for d in dates if d >= today]
past = [d for d in dates if d < today]
upcoming = future[0] if future else None
recent = past[-1] if past else None

last = None
lp = "data/.last_pipeline_run"
if os.path.exists(lp):
    try:
        last = datetime.date.fromisoformat(open(lp).read().strip())
    except Exception:
        pass
days_since = (today - last).days if last else 999


def decide(run, why):
    print(f"{'RUN' if run else 'SKIP'}  ({why})")
    sys.exit(0 if run else 1)


if recent and today <= recent + datetime.timedelta(days=10):
    decide(True, f"draft window: {recent} + 10d")

if upcoming and datetime.date(upcoming.year, 1, 1) <= today <= upcoming:
    decide(days_since >= 6, f"pre-draft ramp; {days_since}d since last run (want >=6)")

decide(today.day <= 2 or days_since >= 28,
       f"off-season; day-of-month {today.day}, {days_since}d since last run (want day<=2 or >=28d)")
