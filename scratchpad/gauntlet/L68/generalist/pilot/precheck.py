"""Offline (no engine) check of every pilot battle: can replay_drive build BOTH decks? Same calls the drive makes
(deck_for_side -> card_for_slug/resolve_card, then catalog.validate_deck for the evo/hero form flags).

    cd ~/cb && PYTHONPATH=~/cb:~/cb/research/ext/cr-native-sandbox python3 <this> <crawl dir with chunk_*/>
"""
import csv
import glob
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path.home() / "cb" / "research" / "sandbox_tools"))
import replay_drive as rd  # noqa: E402
from native_core.card_catalog import validate_deck  # noqa: E402

bad_tags, reasons, cards = set(), Counter(), Counter()
n = 0
for f in sorted(glob.glob(f"{sys.argv[1]}/chunk_*/battles.csv")):
    for b in csv.DictReader(open(f, encoding="utf-8", newline="")):
        n += 1
        for side in (0, 1):
            try:
                validate_deck([{"card_id": c["card_id"], "form": c["form"]} for c in rd.deck_for_side(b, side)])
            except (BaseException) as e:  # SystemExit/KeyError/ValueError, as the drive would raise
                bad_tags.add(b["replay_tag"])
                msg = str(e)
                reasons[type(e).__name__ + ": " + msg.split(":")[0]] += 1
                cards[msg.split(":")[-1].strip()] += 1
print(json.dumps({"battles": n, "undrivable_replays": len(bad_tags), "rate": round(len(bad_tags) / max(n, 1), 4),
                  "side_failures_by_reason": dict(reasons), "failing_card": dict(cards.most_common(20))}, indent=1))
