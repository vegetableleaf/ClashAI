#!/bin/bash
# Plan 10-26 decision 4 (owner: poll the battle log after every match): our 25-battle log every 15 min (the log holds
# ~4-5 h of live play, so nothing is missed) -> data/own_battlelog.jsonl (git-ignored). Direct first, RoyaleAPI proxy if
# the laptop IP changed (the key allows both). Stop: touch data/OWN_POLL_STOP.
cd "$(dirname "$0")" || exit 1
while [ ! -e data/OWN_POLL_STOP ]; do
  python crapi.py own --tag 20Q0UV0GPQ >> data/own_poll.out 2>&1 ||
    CR_API_BASE=https://proxy.royaleapi.dev/v1 python crapi.py own --tag 20Q0UV0GPQ >> data/own_poll.out 2>&1
  sleep 900
done
