"""Layer (a) of pipeline.opp_elixir_count measured on the driven sandbox corpora (perfect detection).

For every replay in corpus_v6/{icebow,hogeq} and for BOTH sides as "the opponent": feed OppElixirCounter the
opponent's accepted log plays (cost from CardDB, as the live path will), and grade its estimate against the
TRUE elixir in every recorded frame. A frame at a play tick shows the PRE-play value, so a play is fed only
once the query tick is past it. Variants:
  all_logcost every accepted play, priced at the log's own (engine-charged) cost -- pure accounting error
  all        every accepted play, priced via CardDB (what the live path will charge)
  no_spell   every CardDB-kind 'spell' play dropped (the ticket's literal spell-less variant)
  reader     only spells that leave NO bodies dropped; Graveyard / Goblin Barrel / Barbarian Barrel /
             Royal Delivery / Clone bodies carry the spell's card id in the engine, so the reader sees them
             (UNTESTED on the live reader)
Also: log cost vs CardDB cost mismatches, re-base counts, and error split by whether the match had an
Elixir Collector / Elixir Golem (not modelled).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/opp_elixir/eval_accounting.py
"""
from __future__ import annotations

import collections
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline.opp_elixir_count import OppElixirCounter, card_cost, card_db  # noqa: E402

BODY_SPELLS = {"graveyard", "goblin_barrel", "barbarian_barrel", "royal_delivery", "clone"}
PHASES = (("0-120s", 0, 2400), ("120-180s", 2400, 3600), ("overtime", 3600, 10 ** 9),
          ("ot_triple>=240s", 4800, 10 ** 9))
VARIANTS = ("all_logcost", "all", "no_spell", "reader")


def key_of(card: str) -> str:
    return card.replace("-", "_")


def keep(variant: str, key: str) -> bool:
    if variant in ("all", "all_logcost"):
        return True
    spell = card_db().kind(key) == "spell"
    return not spell or (variant == "reader" and key in BODY_SPELLS)


def run() -> dict:
    err = {v: collections.defaultdict(list) for v in VARIANTS}          # (variant) -> bucket -> [est - truth]
    rebases = collections.Counter()
    n_plays = collections.Counter()
    cost_mismatch = collections.Counter()
    n_replays = collections.Counter()
    for deck in ("icebow", "hogeq"):
        for f in sorted(glob.glob(str(REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json"))):
            d = json.load(open(f))
            n_replays[deck] += 1
            frames = sorted(d["frames"], key=lambda fr: fr["tick"])
            log = [e for e in d["log"] if e.get("accepted")]
            pump = {key_of(e["card"]) for e in log} & {"elixir_collector", "elixir_golem"}
            for e in log:
                c = card_cost(key_of(e["card"]))
                if c != e["cost"]:
                    cost_mismatch[(key_of(e["card"]), e["cost"], c)] += 1
            for opp in (0, 1):
                plays = sorted((e["tick"], key_of(e["card"]), e["cost"]) for e in log if e["side"] == opp)
                for v in VARIANTS:
                    evs = [(t, k, lc if v == "all_logcost" else card_cost(k)) for t, k, lc in plays if keep(v, k)]
                    n_plays[v] += len(evs)
                    c, i = OppElixirCounter(), 0
                    for fr in frames:
                        t = fr["tick"]
                        while i < len(evs) and evs[i][0] < t:
                            c.play(*evs[i])
                            i += 1
                        diff = c.at(t) - float(fr["elixir"][opp])
                        for name, lo, hi in PHASES:
                            if lo <= t < hi:
                                err[v][name].append(diff)
                        err[v]["all"].append(diff)
                        err[v]["pump_match" if pump else "no_pump_match"].append(diff)
                    rebases[v] += c.rebases
    def stats(xs):
        n = len(xs)
        if not n:
            return {"n": 0}
        a = [abs(x) for x in xs]
        return {"n": n, "mae": round(sum(a) / n, 4), "bias": round(sum(xs) / n, 4),
                "within_0.5": round(sum(x <= 0.5 for x in a) / n, 4), "within_1.0": round(sum(x <= 1.0 for x in a) / n, 4),
                "max_abs": round(max(a), 3)}
    return {"replays": dict(n_replays), "sides_graded": 2 * sum(n_replays.values()),
            "plays_fed": dict(n_plays), "rebases": dict(rebases),
            "log_vs_carddb_cost_mismatch": {f"{k}|log={a}|db={b}": n for (k, a, b), n in cost_mismatch.items()},
            "results": {v: {b: stats(xs) for b, xs in err[v].items()} for v in VARIANTS}}


if __name__ == "__main__":
    out = run()
    (HERE / "eval_accounting.json").write_text(json.dumps(out, indent=1))
    print(f"replays {out['replays']}  sides graded {out['sides_graded']}  plays fed {out['plays_fed']}")
    print(f"rebases {out['rebases']}  cost mismatches (log vs CardDB) {out['log_vs_carddb_cost_mismatch']}")
    for v, res in out["results"].items():
        print(f"\n[{v}]  bucket              n      MAE    bias  <=0.5  <=1.0  max|err|")
        for b in ("0-120s", "120-180s", "overtime", "ot_triple>=240s", "all", "no_pump_match", "pump_match"):
            s = res.get(b, {"n": 0})
            if s["n"]:
                print(f"      {b:18s} {s['n']:7d} {s['mae']:7.3f} {s['bias']:+7.3f} {s['within_0.5']:6.3f} "
                      f"{s['within_1.0']:6.3f} {s['max_abs']:8.2f}")
