"""Shared CollegeFootballData fetch: retries transient failures, never caches an
empty/failed response, fails fast when the API is unreachable. Used by
build_cfbd*.py."""
import datetime, json, os, time, urllib.request, urllib.error

KEY = os.environ.get("CFBD_KEY", "").strip()   # only needed when a live fetch happens
os.makedirs("data/cfbd_raw", exist_ok=True)

_TRANSIENT = (500, 502, 503, 504, 429)


def last_college_season(today=None):
    """The newest CFB season worth pulling. Before October the current season has
    only ~4 weeks of games -- not enough for prospect eval, and pulling a season
    the API barely has data for is what makes runs hang. So: current year from
    October on, otherwise last year."""
    d = today or datetime.date.today()
    return d.year if d.month >= 10 else d.year - 1


def fetch(path, tries=3):
    """GET a CFBD endpoint, decoded JSON. Retries 5xx/429/timeout, then raises
    (callers decide whether that's fatal). Kept short so a hanging endpoint
    can't stall the whole run: ~35s x 3 with 4s/8s backoff, ~90s worst case."""
    if not KEY:
        raise RuntimeError("CFBD_KEY not set and the requested data is not cached")
    last = None
    for i in range(tries):
        req = urllib.request.Request("https://api.collegefootballdata.com" + path,
                                     headers={"Authorization": "Bearer " + KEY,
                                              "User-Agent": "Mozilla/5.0"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=35).read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in _TRANSIENT:
                raise
        except Exception as e:                       # timeout, conn reset, ...
            last = e
        if i < tries - 1:
            time.sleep(4 * (i + 1))                   # 4s, 8s
    raise last


def cached(path, cache_name, tries=4):
    """As fetch(), but persist the JSON under data/cfbd_raw/<cache_name>.json.
    A cached file is reused on later runs. An empty/failed response is NOT
    cached (so a CFBD outage doesn't poison the cache)."""
    fn = f"data/cfbd_raw/{cache_name}.json"
    if os.path.exists(fn):
        try:
            d = json.load(open(fn))
            if d:
                return d
        except Exception:
            pass
    d = fetch(path, tries=tries)
    if d:
        json.dump(d, open(fn, "w"))
        time.sleep(0.3)
    return d
