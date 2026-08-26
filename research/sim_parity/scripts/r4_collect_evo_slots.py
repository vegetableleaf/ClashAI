"""R4 -- collect the REAL per-deck evolution + tower-troop slots from the official CR API.

`deck_import.py` folds every evolution name onto its base key (`_name_to_key` + the `_evo` strip),
so the sim has never known WHICH card in a meta deck was evolved -- and `ScriptedBot` had to guess.
The battlelog card entries carry `evolutionLevel` / `maxEvolutionLevel`, and each team entry carries
`supportCards` (the tower troop), so both slots are recoverable without any scraping.

Same access pattern as `clashrl.deck_import`: token from the git-ignored data file, Bearer header,
Path-of-Legends rankings newest-season-first, ~0.2 s between calls. The token is never printed.

Writes research/sim_parity/ledger/meta_evo_slots.json. Read-only against the game; safe to re-run.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

BASE = "https://api.clashroyale.com/v1"
ROOT = Path(__file__).resolve().parents[3]                      # the worktree root
OUT = ROOT / "research" / "sim_parity" / "ledger" / "meta_evo_slots.json"
# The token lives ONLY in the original tree's git-ignored data dir (the worktree's data/ was never
# populated). Read-only -- nothing here writes to that tree.
TOKEN_FILES = [ROOT / "icebow" / "data" / "cr_api_token.txt",
               Path("C:/Users/benpe/ClashBot/icebow/data/cr_api_token.txt")]
CARDS_YAML = ROOT / "icebow" / "config" / "cards.yaml"

PLAYERS = int(sys.argv[1]) if len(sys.argv) > 1 else 120


def name_to_key(name: str) -> str:
    """Byte-identical to clashrl.deck_import._name_to_key, so keys line up with meta_decks.yaml."""
    k = name.lower().replace(".", "").replace("'", "")
    return re.sub(r"[ \-]+", "_", k).strip("_")


def load_token() -> str:
    for p in TOKEN_FILES:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    return line
    return ""


def get(url: str, token: str, timeout: float = 25.0):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def top_player_tags(token: str, players: int):
    seasons = []
    try:
        got = get(BASE + "/locations/global/seasons", token).get("items", [])
        seasons = sorted({s["id"] for s in got if s.get("id")}, reverse=True)
    except Exception as e:                                       # noqa: BLE001
        print("[r4] seasons list failed: " + repr(e))
    for sid in seasons[:6]:
        try:
            d = get(BASE + "/locations/global/pathoflegend/" + str(sid)
                    + "/rankings/players?limit=" + str(players), token)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        items = d.get("items", [])
        if items:
            return [p["tag"] for p in items][:players], "path-of-legends " + str(sid)
        time.sleep(0.2)
    d = get(BASE + "/locations/global/rankings/players?limit=" + str(players), token)
    return [p["tag"] for p in d.get("items", [])][:players], "global trophy rankings"


def main() -> int:
    sys.path.insert(0, str(ROOT / "icebow" / "src"))
    from clashrl.cards import CardDB
    db = CardDB(path=CARDS_YAML)

    token = load_token()
    if not token:
        print("[r4] no API token found; STOPPING (no fabricated slots).")
        return 2

    try:
        tags, source = top_player_tags(token, PLAYERS)
    except urllib.error.HTTPError as e:
        print("[r4] rankings HTTP " + str(e.code) + " -- 403 means the key's IP moved. STOPPING.")
        return 3
    if not tags:
        print("[r4] no players returned by any ranking endpoint. STOPPING.")
        return 4
    print("[r4] " + str(len(tags)) + " players from " + source)

    tally: Counter = Counter()                 # (cards, evo, support) -> sightings
    evo_freq: Counter = Counter()
    support_freq: Counter = Counter()
    unmapped: Counter = Counter()
    entries_seen = 0
    dropped_event = 0
    multi_evo: Counter = Counter()
    evo_count_hist: Counter = Counter()        # how many evo slots a deck-sighting actually fields
    evo_level_hist: Counter = Counter()        # evolutionLevel values seen (1..maxEvolutionLevel)
    players_read = 0
    battle_ids = set()

    for i, tag in enumerate(tags):
        enc = urllib.parse.quote(tag, safe="")
        try:
            battles = get(BASE + "/players/" + enc + "/battlelog", token)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("[r4] HTTP 403 on player " + str(i + 1) + " -- the key's IP moved. STOPPING.")
                return 3
            continue
        except Exception:                                        # noqa: BLE001
            continue
        players_read += 1
        for b in battles:
            battle_ids.add((b.get("battleTime"), b.get("type"),
                            (b.get("team") or [{}])[0].get("tag")))
            for side in ("team", "opponent"):
                for entry in b.get(side, []):
                    entries_seen += 1
                    raw = entry.get("cards", []) or []
                    keys, evos, bad = [], [], []
                    for c in raw:
                        nm = c.get("name", "")
                        k = name_to_key(nm)
                        base_k = k[:-4] if k.endswith("_evo") else k
                        if db.get(base_k):
                            keys.append(base_k)
                            if c.get("evolutionLevel"):
                                evos.append(base_k)
                                evo_level_hist[int(c["evolutionLevel"])] += 1
                        else:
                            bad.append(nm)
                    sup = []
                    for c in (entry.get("supportCards", []) or []):
                        nm = c.get("name", "")
                        sk = name_to_key(nm)
                        sup.append(sk)
                        if not db.get(sk):
                            unmapped[nm] += 1
                    if len(raw) == 8 and len(keys) < 8:
                        dropped_event += 1
                        for nm in bad:
                            unmapped[nm] += 1
                        continue
                    if len(keys) != 8:
                        continue
                    evo_count_hist[len(set(evos))] += 1
                    if len(evos) > 1:
                        multi_evo[tuple(sorted(evos))] += 1
                    ck = tuple(sorted(keys))
                    tally[(ck, tuple(sorted(set(evos))), tuple(sorted(set(sup))))] += 1
                    for e in set(evos):
                        evo_freq[e] += 1
                    for s in set(sup):
                        support_freq[s] += 1
        if (i + 1) % 20 == 0:
            print("[r4] " + str(i + 1) + "/" + str(len(tags)) + " players, "
                  + str(sum(tally.values())) + " deck-sightings")
        time.sleep(0.2)

    decks = [{"cards": list(ck), "evo": list(ev), "support": list(sp), "sightings": n}
             for (ck, ev, sp), n in tally.most_common()]
    doc = {
        "meta": {
            "collected": time.strftime("%Y-%m-%d"),
            "players": players_read,
            "battles": len(battle_ids),
            "decks": len(decks),
            "method": "battlelog evolutionLevel",
            "source": source,
            "provenance": "official_api",
            "deck_sightings": sum(tally.values()),
            "entries_scanned": entries_seen,
            "dropped_event_only": dropped_event,
            "sightings_with_evo": sum(n for (_, ev, _), n in tally.items() if ev),
            "sightings_with_support": sum(n for (_, _, sp), n in tally.items() if sp),
            "multi_evo_sightings": sum(multi_evo.values()),
            # SLOT RULE, measured rather than assumed: opponents.py's comment claims "each deck
            # fields ONE evolution (the 2026 slot rules)". The battlelog says otherwise -- see
            # conflicts.md "R4 collection 2026-08-26".
            "evo_slots_per_deck_sighting": {str(k): v for k, v in sorted(evo_count_hist.items())},
            "evolution_level_values": {str(k): v for k, v in sorted(evo_level_hist.items())},
            "note": ("`support` = the team's tower troop (API `supportCards`); those names are NOT "
                     "KB cards, so they also appear in unmapped_names."),
        },
        "decks": decks,
        "evo_frequency": dict(evo_freq.most_common()),
        "support_frequency": dict(support_freq.most_common()),
        "multi_evo_combos": {"+".join(k): v for k, v in multi_evo.most_common()},
        "unmapped_names": [n for n, _ in unmapped.most_common()],
        "unmapped_counts": dict(unmapped.most_common()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print("[r4] wrote " + str(OUT) + ": " + str(len(decks)) + " (cards,evo,support) rows, "
          + str(sum(tally.values())) + " sightings, " + str(len(evo_freq)) + " distinct evos, "
          + str(len(support_freq)) + " tower troops, " + str(len(unmapped)) + " unmapped names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
