#!/usr/bin/env bash
# Full data refresh + score, shared by update.yml and refit-review.yml.
# Assumes cwd = repo root and CFBD_KEY is set. Does NOT commit anything.
set -euo pipefail
step() { echo "::endgroup::"; echo "::group::[$(date -u +%H:%M:%S)] $*"; }
echo "::group::start"

step "fetch_sources.py"
python fetch_sources.py
step "fetch_weekly.py"
python fetch_weekly.py

step "seed data/cfbd_raw/ from the committed snapshot (fills gaps; a warm cache keeps its fresher files)"
mkdir -p data/cfbd_raw
before=$(ls data/cfbd_raw | wc -l)
tar xzf data/cfbd_raw.tgz -C data --skip-old-files
echo "cfbd_raw: $before cached files before, $(ls data/cfbd_raw | wc -l) after seed"
step "build_cfbd.py"
python build_cfbd.py        || echo "WARNING: build_cfbd.py failed - using cached raw JSON"
step "build_cfbd_extra.py"
python build_cfbd_extra.py  || echo "WARNING: build_cfbd_extra.py failed - using cached raw JSON"
step "build_cfbd_extra2.py"
python build_cfbd_extra2.py || echo "WARNING: build_cfbd_extra2.py failed - using cached raw JSON"
test -s data/cfbd_player_seasons.csv || { echo "FATAL: data/cfbd_player_seasons.csv not produced"; exit 1; }
step "rebuild_ppa_usage.py (clean PPA/usage/recruiting -> data/cfbd_*_full.csv, used by WRPI + RUPI)"
python rupi/rebuild_ppa_usage.py

step "WRPI: build_pool -> build_features_v3 -> build_outcomes -> score_v2"
python build_pool.py
python build_features_v3.py
python build_outcomes.py
python score_v2.py

step "RUPI: cfbd_rb -> features -> outcomes -> combine -> score"
python rupi/build_cfbd_rb.py
python rupi/build_features_rb2.py
python rupi/build_features_rb_udfa.py
python rupi/build_features_rb_projected_udfa.py
python rupi/build_outcomes_rb.py
python rupi/combine_pool.py
python rupi/score_rupi.py
echo "::endgroup::"
echo "[$(date -u +%H:%M:%S)] pipeline done"
