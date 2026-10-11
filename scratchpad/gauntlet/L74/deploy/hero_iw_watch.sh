#!/bin/bash
# Owner 10-11: "wire in hero ice wizard's ability the moment royalegym updates its sim with it". Free watcher (no Claude):
# every 3 h, fetch RoyaleSim/RoyaleGym upstream + PyPI versions; post ONE Discord alert per new matching commit / version.
cd /c/Users/benpe/ClashBot; PY=icebow/.venv/Scripts/python.exe; S=scratchpad/gauntlet/L74/deploy/hero_iw_seen.txt; touch $S
post() { printf '%s\n' "$1" > /tmp/hiw_msg.txt 2>/dev/null || printf '%s\n' "$1" > hiw_msg.txt; $PY scratchpad/gauntlet/L69/discord/post.py /tmp/hiw_msg.txt 2>/dev/null || $PY scratchpad/gauntlet/L69/discord/post.py hiw_msg.txt; }
while true; do
  for r in RoyaleSim RoyaleGym; do
    git -C research/ext/Royale/$r fetch -q 2>/dev/null
    git -C research/ext/Royale/$r log --format='%h %s' HEAD..@{u} 2>/dev/null | grep -iE 'hero ice wizard|ice ?wizard hero|icewizardhero|frosty|snowman' \
      | grep -viE 'extract_cards|census|docs' | while read h rest; do
        grep -q "$r $h" $S && continue; echo "$r $h" >> $S
        post "**Hero Ice Wizard update upstream ($r $h):** ${rest:0:300}
Next: wire it into our simulator runtime (rebuild, parity tests, then a 960-game check) -- ask Claude."
      done
  done
  v=$($PY -m pip index versions royalegym 2>/dev/null | head -1)
  if [ -n "$v" ] && ! grep -qF "pypi $v" $S; then echo "pypi $v" >> $S; post "**RoyaleGym release seen on PyPI:** $v (check whether it adds Hero Ice Wizard)"; fi
  sleep 10800
done
