"""Shared CollegeFootballData fetch: retries transient failures, never caches an
empty/failed response, longer timeout. Used by build_cfbd*.py."""
import json, os, time, urllib.request, urllib.error

KEY = os.environ.get("CFBD_KEY", "").strip()   # only needed when a live fetch happens
os.makedirs("data/cfbd_raw", exist_ok=True)

_TRANSIENT = (500, 502, 503, 504, 429)


def fetch(path, tries=4):
    """GET a CFBD endpoint, decoded JSON. Retries 5xx/429/timeout with backoff.
    Raises after the last try (callers decide whether that's fatal)."""
    if not KEY:
        raise RuntimeError("CFBD_KEY not set and the requested data is not cached")
    last = None
    for i in range(tries):
        req = urllib.request.Request("https://api.collegefootballdata.com" + path,
                                     headers={"Authorization": "Bearer " + KEY,
                                              "User-Agent": "Mozilla/5.0"})
        try:
            return json.loads(urllib.request.urlopen(req, timeout=120).read())
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in _TRANSIENT:
                raise
        except Exception as e:                       # timeout, conn reset, ...
            last = e
        if i < tries - 1:
            time.sleep(2 ** i * 3)                    # 3s, 6s, 12s
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
