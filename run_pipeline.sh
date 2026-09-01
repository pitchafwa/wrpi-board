#!/usr/bin/env bash
# Full data refresh + score, shared by update.yml and refit-review.yml.
# Assumes cwd = repo root and CFBD_KEY is set. Does NOT commit anything.
set -euo pipefail

echo "::group::nflverse feeds"
python fetch_sources.py
python fetch_weekly.py
echo "::endgroup::"

echo "::group::CollegeFootballData feeds"
# cold-start seed: if the Actions cache missed, unpack the committed raw-JSON
# snapshot so a CFBD outage can't stop a fresh runner. cfbd_get.cached() then
# only calls the API for years not already on disk.
if [ ! -d data/cfbd_raw ] || [ -z "$(ls -A data/cfbd_raw 2>/dev/null)" ]; then
  echo "seeding data/cfbd_raw/ from committed snapshot"
  mkdir -p data && tar xzf data/cfbd_raw.tgz -C data
fi
# a live-API hiccup just means we build on the cached raw JSON.
python build_cfbd.py        || echo "WARNING: build_cfbd.py failed - using cached raw JSON"
python build_cfbd_extra.py  || echo "WARNING: build_cfbd_extra.py failed - using cached raw JSON"
python build_cfbd_extra2.py || echo "WARNING: build_cfbd_extra2.py failed - using cached raw JSON"
# hard-stop if the core college table is missing entirely (no cache + API down)
test -s data/cfbd_player_seasons.csv || { echo "FATAL: data/cfbd_player_seasons.csv not produced"; exit 1; }
echo "::endgroup::"

echo "::group::WRPI build + score"
python build_pool.py
python build_features_v3.py
python build_outcomes.py
python score_v2.py
echo "::endgroup::"

echo "::group::RBPI build + score"
python rbpi/build_cfbd_rb.py
python rbpi/rebuild_ppa_usage.py
python rbpi/build_features_rb2.py
python rbpi/build_features_rb_udfa.py
python rbpi/build_features_rb_projected_udfa.py
python rbpi/build_outcomes_rb.py
python rbpi/combine_pool.py
python rbpi/score_rbpi.py
echo "::endgroup::"
