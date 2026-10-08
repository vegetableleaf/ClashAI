#!/bin/sh
# Cron entry point (one light process: flock skips a run while the previous one is still going).
#   17 */2 * * * /home/clashbot-gauntlet/crapi/run.sh
cd "$HOME/crapi" || exit 1
mkdir -p data
exec >>data/cron.out 2>&1
echo "=== $(date -u +%FT%TZ) run"
flock -n run.lock nice -n 19 python3 crapi.py crawl --max-players 400 && nice -n 19 python3 census.py
