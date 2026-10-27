"""S3b-1: which bodies each card form puts on the board in RoyaleSim fin15, as the production path reads them
(RoyaleSelfPlayEnv.raw(): entity name = the PARENT card's display name, max_hp, status_flags; engine_unit_id on top).

Per (card, flag) of the census: side 0's deck = the card (evo slot 0 / hero slot 2, '@evolution' / '@hero' as
forms_mode 'deck' reads them) + 7 damage spells that summon nothing; side 0 plays the card whenever it is in hand
(up to 5 times: an evolution needs its cycles; troops at the bridges, spells on the enemy princess towers), a filler at full elixir; side 1 plays
nothing; 2,400 ticks. Every side-0 entity of the target card id is recorded.

usage (pod 32657): ROYALE_RUNTIME=fin15-linux /workspace/venvf15/bin/python -I rs_probe.py jobs.tsv spells.txt out.tsv
"""
import sys
from pathlib import Path

sys.path[:0] = ["/workspace/cfspeed/cb"]
from pipeline.royale_runtime import activate  # noqa: E402

activate()
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from pipeline import vocab  # noqa: E402

FILLERS = ["Zap", "Arrows", "Fireball", "Rocket", "Earthquake", "Freeze", "Poison", "Lightning"]
OPP = ["Knight", "Archer", "Giant", "Musketeer", "MiniPekka", "Fireball", "Arrows", "Zap"]


def probe(card, flag, spell, ticks=2400):
    deck = [f for f in FILLERS if f != card][:7]
    at = 2 if flag == 2 else 0
    deck.insert(at, card + ("@evolution" if flag == 1 else "@hero" if flag == 2 else ""))
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck")
    env.reset(deck, OPP, 7)
    cid = env.deck_ids[0][at]
    seen, uids, plays = {}, set(), 0
    for t in range(10, ticks, 10):
        env._advance_to(t)
        if env.done:
            break
        raw = env.raw()
        me = next(p for p in raw["players"] if p["side"] == 0)
        if plays < 5:
            x, y = (3500 if plays % 2 == 0 else 14500), (25500 if spell else 12500)
            if env.eng.act(side=0, deck_index=at, x=x, y=y)["accepted"]:
                plays += 1
            elif me["elixir_exact"] >= 9.9:
                for i in range(8):
                    if i != at and env.eng.act(side=0, deck_index=i, x=9000, y=29000)["accepted"]:
                        break
        for e in raw["entities"]:
            if e["side"] != 0 or e["card_id"] != cid:
                continue
            k = (e["name"], int(e["max_hp"]), int(e.get("status_flags", 0)), e.get("unit_name", ""))
            v = seen.setdefault(k, [int(raw["tick"]), 0])
            if e["entity_id"] not in uids:
                uids.add(e["entity_id"])
                v[1] += 1
    return seen, plays


def main():
    jobs = [ln.split("\t") for ln in Path(sys.argv[1]).read_text().splitlines() if ln.strip()]
    spells = set(Path(sys.argv[2]).read_text().split("\n"))
    with open(sys.argv[3], "w") as w:
        w.write("card\tflag\tplays\trs_name\tmax_hp\tstatus_flags\tunit_name\tvocab_id\tfirst_tick\tcount\terror\n")
        for card, flag in jobs:
            try:
                seen, plays = probe(card, int(flag), card in spells)
                for (name, mhp, st, un), (first, n) in sorted(seen.items()):
                    vid = vocab.engine_unit_id(name, float(mhp))
                    w.write(f"{card}\t{flag}\t{plays}\t{name}\t{mhp}\t{st}\t{un}\t{vid}\t{first}\t{n}\t\n")
                if not seen:
                    w.write(f"{card}\t{flag}\t{plays}\t-\t-\t-\t-\t-\t-\t0\t\n")
            except Exception as ex:  # noqa: BLE001 -- one card's refusal is a row, not a stop
                w.write(f"{card}\t{flag}\t0\t-\t-\t-\t-\t-\t-\t0\t{type(ex).__name__}: {str(ex)[:150]}\n")
            w.flush()


if __name__ == "__main__":
    main()
