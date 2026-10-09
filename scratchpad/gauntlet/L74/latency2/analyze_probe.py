"""Read the live_play logs of a --follow-up-taps run (probe_live.py or the combo) and report the numbers the live test is for.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency2/analyze_probe.py live_play_<ts>.jsonl [...]

Per pair (first play A, follow-up B, matched by name + order, NOT by the play->confirmed adjacency other scripts assume):
  gap_decision   B's tap tick - A's decision tick               (the number this work is about; planned 2-4)
  gap_landing    B's confirmation tick - A's confirmation tick  (what the combo needs; the game's own spacing)
  confirm_A/B    decision -> confirmation ticks of each          (A is ~24 as today; B should be gap_decision + ~24)
  outcome        both_confirmed | B_unconfirmed | A_unconfirmed(+B cancelled) | B_cancelled(why)
and the safety lines: elixir at B's tap, reserved, refusals of B split by need, any 'unconfirmed' on a non-follow-up play.
"""
from __future__ import annotations

import json
import statistics as st
import sys


def load(path):
    return [json.loads(x) for x in open(path, encoding="utf-8") if x.startswith("{")]


def pairs(ev):
    """-> list of dict(a_play, b_play|None, a_conf, b_conf, cancelled, b_unconf, a_unconf) per scheduled follow-up."""
    out, open_ = [], {}
    last_a = None
    for e in ev:
        k = e["event"]
        if k == "play" and not e.get("follow_up"):
            last_a = dict(a_play=e, b_play=None, a_conf=None, b_conf=None, cancelled=None, b_unconf=None, a_unconf=None,
                          sched=None)
        elif k == "follow_up_scheduled" and last_a is not None:
            last_a["sched"] = e
            last_a["name_b"] = e["name"]
            out.append(last_a)
            open_[e["name"]] = last_a
        elif k == "play" and e.get("follow_up") and e["name"] in open_:
            open_[e["name"]]["b_play"] = e
        elif k == "follow_up_cancelled" and e["name"] in open_:
            open_[e["name"]]["cancelled"] = e
        elif k in ("confirmed", "unconfirmed"):
            for p in out:
                if k == "confirmed":
                    if e.get("follow_up") and e["name"] == p.get("name_b") and p["b_play"] and not p["b_conf"]:
                        p["b_conf"] = e
                        break
                    if not e.get("follow_up") and e["name"] == p["a_play"]["name"] and not p["a_conf"] and not p["a_unconf"]:
                        p["a_conf"] = e
                        break
                else:
                    if e.get("follow_up") and e["name"] == p.get("name_b") and p["b_play"] and not p["b_unconf"] and not p["b_conf"]:
                        p["b_unconf"] = e
                        break
                    if not e.get("follow_up") and e["name"] == p["a_play"]["name"] and not p["a_conf"] and not p["a_unconf"]:
                        p["a_unconf"] = e
                        break
    return out


def main() -> None:
    rows, plain_unconf, plain, scheduled = [], 0, 0, 0
    for path in sys.argv[1:]:
        ev = load(path)
        scheduled += sum(e["event"] == "follow_up_scheduled" for e in ev)
        plain += sum(e["event"] == "play" and not e.get("follow_up") for e in ev)
        plain_unconf += sum(e["event"] == "unconfirmed" and not e.get("follow_up") for e in ev)
        rows += pairs(ev)
    print(f"logs {len(sys.argv) - 1}; first plays {plain}; follow-ups scheduled {scheduled}; pairs {len(rows)}")
    print(f"non-follow-up plays unconfirmed in these logs: {plain_unconf}")
    for i, p in enumerate(rows):
        a, b = p["a_play"], p["b_play"]
        if b is None:
            why = p["cancelled"]["why"] if p["cancelled"] else "not fired"
            print(f"#{i} {a['name']}@{a['tick']} + {p['name_b']}: B not tapped ({why})")
            continue
        ca, cb = p["a_conf"], p["b_conf"]
        out = ("both_confirmed" if ca and cb else "B_unconfirmed" if p["b_unconf"] else
               "A_unconfirmed" if p["a_unconf"] else "open")
        print(f"#{i} {a['name']}@{a['tick']} + {p['name_b']}@{b['tick']}: gap_decision {b['tick'] - a['tick']} "
              f"reserved {b.get('reserved_elixir')} elixir_B {b['elixir']:.2f} outstanding {b.get('outstanding')} | "
              f"confirm_A {ca['tick'] - a['tick'] if ca else None} confirm_B {cb['tick'] - b['tick'] if cb else None} "
              f"gap_landing {cb['tick'] - ca['tick'] if ca and cb else None} | {out}")
    done = [p for p in rows if p["a_conf"] and p["b_conf"]]
    if done:
        gd = [p["b_play"]["tick"] - p["a_play"]["tick"] for p in done]
        gl = [p["b_conf"]["tick"] - p["a_conf"]["tick"] for p in done]
        print(f"\nboth confirmed {len(done)}/{len(rows)}: gap_decision median {st.median(gd)} (min {min(gd)}, max {max(gd)}); "
              f"gap_landing median {st.median(gl)} (min {min(gl)}, max {max(gl)})")
    bad = [p for p in rows if p["b_unconf"] or p["a_unconf"]]
    print(f"refusals: B {sum(1 for p in rows if p['b_unconf'])}, A {sum(1 for p in rows if p['a_unconf'])} "
          f"(go/no-go: B refused in more than 1 of 5 pairs, or any extra lockout, = stop)")


if __name__ == "__main__":
    main()
