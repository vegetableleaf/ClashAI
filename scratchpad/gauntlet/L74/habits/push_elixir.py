"""L74/habits B like-for-like: at each PLAY-based heavy push, the X-Bow player's OWN elixir (OppElixirCounter over its own plays --
exact for pros and live up to Elixir Collector / ability costs) and the response split by own elixir >= 6 (a Rocket affordable
at once) vs < 6. Live, pros.
    python push_elixir.py"""
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hablib as H  # noqa: E402
import live_tables as LT  # noqa: E402
import pro_tables as PT  # noqa: E402

pct = LT.pct


def main():
    live = LT.load()
    pros = PT.load()
    print('PLAY-based heavy pushes: response share by the X-Bow player\'s own elixir at the event (counter over its own plays)')
    for g in ['CXXIV', 'CXXXVIII', 'CLIII', 'pro icebow crawl2', 'pro icebow8 HF', 'pro other X-Bow HF']:
        M = [m for m in live + pros if m['group'] == g and m.get('rocket_deck', True)]
        for lab, cond in (('own >= 6', lambda e: e >= 6), ('own < 6', lambda e: e < 6)):
            rows = []
            for m in M:
                own_el = H.counter_fn(m['own'])
                for r in H.push_events(m):
                    if cond(own_el(r['tick'] + H.RESP[0])):
                        rows.append(r)
            if not rows:
                continue
            c = Counter(r['resp'] for r in rows)
            rk = (c['rocket'] + c['rocket+tornado']) / len(rows)
            print(f"  {g:20s} {lab:8s} n {len(rows):5d}  Rocket(any) {pct(rk)}  cheap_only {pct(c['cheap_only'] / len(rows))}  "
                  f"other {pct(c['other'] / len(rows))}  none {pct(c['none'] / len(rows))}  win {pct(H.wr(rows))}")


if __name__ == '__main__':
    main()
