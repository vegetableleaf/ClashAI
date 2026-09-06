"""L63e: tag lists for the S0 corpus rebuild -- every replay whose non-ability plays are ALL positioned."""
import csv, json, sys
from collections import defaultdict
from pathlib import Path
ROOT = Path(r"C:/Users/benpe/ClashBot")
OUT = ROOT / "scratchpad/gauntlet/ext/corpus_v3"
OUT.mkdir(parents=True, exist_ok=True)
for deck in ("icebow", "hogeq"):
    crawl = ROOT / deck / "data/royaleapi/crawl2"
    battles = list(csv.DictReader((crawl / "battles.csv").open(encoding="utf-8", newline="")))
    n_plays, n_pos, n_abil = defaultdict(int), defaultdict(int), defaultdict(int)
    with (crawl / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
        cols = None
        for row in csv.DictReader(h):
            cols = cols or list(row)
            t = row["replay_tag"]
            card = row.get("attr_card", "")
            if card.endswith("_invalid") or row.get("ability", "") in ("1", "True", "true"):
                n_abil[t] += 1; continue
            n_plays[t] += 1
            if row.get("x_units", "") not in ("", "None") and row.get("y_units", "") not in ("", "None"):
                n_pos[t] += 1
    tags = [b["replay_tag"] for b in battles if n_plays[b["replay_tag"]] > 0 and n_pos[b["replay_tag"]] == n_plays[b["replay_tag"]]]
    partial = sum(1 for b in battles if 0 < n_pos[b["replay_tag"]] < n_plays[b["replay_tag"]])
    (OUT / f"tags_{deck}.json").write_text(json.dumps(tags), encoding="utf-8")
    print(json.dumps({"deck": deck, "battles": len(battles), "fully_positioned": len(tags), "partial": partial,
                      "unpositioned": len(battles) - len(tags) - partial, "plays_in_set": sum(n_plays[t] for t in tags),
                      "abilities_in_set": sum(n_abil[t] for t in tags), "cols": cols[:14]}))
