"""League decks with fast-cycle X-Bow counter decks weighted 3x (owner 10-10 unfavourable-matchup rule, 10-25 counter decks).
A deck is upweighted when its average cost <= 3.2 AND it holds >= 1 card with shrunk answer lift < -0.10 (the S1c counter set,
s1c/counter_priors.json). Writes <out>.json with those decks' "sides" x3 (the league samples by sides^alpha).
Usage: python counter_x3.py <decks.json> <counter_priors.json> <out.json>"""
import json
import sys

sys.path.insert(0, __file__.rsplit("scratchpad", 1)[0])
from pipeline.habit_terms import play_cost  # noqa: E402


def counters(priors):
    """the counter-card slugs: shrunk answer-view lift < -0.10 (s1c threshold)."""
    cards = priors.get("cards", priors)
    out = set()
    for slug, v in cards.items():
        if not isinstance(v, dict):
            continue
        lift = v.get("answer_lift", v.get("answer", {}).get("lift") if isinstance(v.get("answer"), dict) else None)
        if lift is not None and lift < -0.10:
            out.add(slug)
    return out


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    C = counters(json.load(open(sys.argv[2], encoding="utf-8")))
    assert len(C) >= 10, f"counter set too small ({len(C)}): check counter_priors.json keys"
    n = w0 = w1 = 0
    for k in d["decks"]:
        s = [x.replace("-ev1", "").replace("-hero", "") for x in k["slugs"]]
        w0 += k.get("sides", 0)
        if sum(play_cost(x) for x in s) / len(s) <= 3.2 and set(s) & C:
            k["sides"] = 3 * k.get("sides", 0)
            k["counter_x3"] = True
            n += 1
        w1 += k.get("sides", 0)
    d["source"] = d.get("source", "") + " | counter_x3.py: fast counter decks sides x3"
    json.dump(d, open(sys.argv[3], "w", encoding="utf-8"))
    print(f"counter cards {len(C)}; decks x3: {n}; weight share of those decks {1 - (w0 - (w1 - w0) / 2) / w1:.1%}")


if __name__ == "__main__":
    main()
