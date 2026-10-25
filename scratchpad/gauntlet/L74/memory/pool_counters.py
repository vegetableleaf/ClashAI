"""S4 pool check (owner 10-25: the pool must contain fast-cycle counter decks, not one average opponent).
Per deck of a league_decks JSON: avg elixir, 4-card cycle cost (4 cheapest), X-Bow counters it holds (pro answer view lift
<= -0.07 at n >= 60, xbow_cards_pro.out) and their count; then the training weight share of fast (avg <= 3.2) counter decks.
Usage: python pool_counters.py <decks.json>"""
import json
import sys

sys.path.insert(0, __file__.rsplit("scratchpad", 1)[0])
from pipeline.habit_terms import play_cost  # noqa: E402

COUNTERS = {'electro-giant', 'goblinstein', 'giant', 'pekka', 'giant-skeleton', 'ice-golem', 'ice-spirit', 'bowler',
            'cannon-cart', 'mega-knight', 'valkyrie', 'tesla', 'barbarian-barrel', 'skeletons'}   # answer lift <= -0.07


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    rows = []
    for k in d["decks"]:
        s = [x.replace("-ev1", "").replace("-hero", "") for x in k["slugs"]]
        c = sorted(play_cost(x) for x in s)
        cn = sorted(set(s) & COUNTERS)
        rows.append((k["name"], k.get("sides", 0), sum(c) / len(c), sum(c[:4]), cn))
    W = sum(r[1] for r in rows)
    fast = [r for r in rows if r[2] <= 3.2 and r[4]]
    print(f"decks {len(rows)}, weight {W}; fast (avg <= 3.2) with >= 1 counter: {len(fast)} decks, "
          f"{sum(r[1] for r in fast) / W:.1%} of weight; >= 2 counters: {sum(r[1] for r in fast if len(r[4]) >= 2) / W:.1%}")
    print(f"{'deck':10s} {'w':>4s} {'avg':>5s} {'cyc4':>5s}  counters")
    for r in sorted(rows, key=lambda r: -r[1])[:40]:
        print(f"{r[0]:10s} {r[1]:4d} {r[2]:5.2f} {r[3]:5.1f}  {', '.join(r[4])}")


if __name__ == "__main__":
    main()
