"""P3-FORK3 summary tables from CF_DUMP jsonl files, one ARM per file (p4_audit.py gives the full per-arm tables).

    python fork3_tables.py base=data/f3base2.jsonl ftR=data/f3ftR2.jsonl oplcB=data/f3oplcB2.jsonl [--from-update 1] > out.md

Rows = contrasts (a - b in the K-mean return Q, +-1 = a win; 90% match-cluster bootstrap CI, p4_audit.boot_ci) at the
stated read: the main horizon ("q": 900 ticks for the Rocket family, 1200 for def_xbow, the match end for rocket_cycle), a
sweep read ("qh600" ...), or the audited terminal return ("qend"). Opponent-response columns come from the dg records at the
main stop (alternative - chosen): own / foe princess HP lost (princess units), plays landed (np), foe elixir at the stop.
def_xbow "def - bridge" pools def_tile - chosen (when the policy's own X-Bow was a reach one: no xbow_reach_lane offered) and
def_tile - xbow_reach_lane (the policy's own X-Bow was defensive)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p4_audit as PA  # noqa: E402

COLS = ("q", "dg_stop:own_p_lost", "dg_stop:foe_p_lost", "dg_stop:np0", "dg_stop:np1", "dg_stop:foe_elixir")


def phase(t):
    return "1x" if t < 2400 else "2x" if t < 3600 else "OT"


def contrast(S, trig, a, b, which="q", ph=None, pick=None):
    """[(value, match id)] of cand a - cand b (b "chosen" = candidate 0) over samples of ``trig`` holding both."""
    out = []
    for s in S:
        if s["trigger"] != trig or (ph and phase(s["tick"]) != ph) or (pick and not pick(s)):
            continue
        ks = {c["kind"]: c for c in s["cands"]}
        if a not in ks or (b != "chosen" and b not in ks):
            continue
        v = PA.metric(s, ks[a], which, base=s["cands"][0] if b == "chosen" else ks[b])
        if v is not None:
            out.append((v, s["mid"]))
    return out


def fmt(v):
    if len(v) < 5:
        return f"n {len(v)}"
    x = [p for p, _ in v]
    lo, hi = PA.boot_ci(x, [m for _, m in v])
    return f"{np.mean(x):+.3f} [{lo:+.3f}, {hi:+.3f}] (n {len(v)})"


def def_bridge(S, which):
    out = []
    for s in S:
        if s["trigger"] != "def_xbow":
            continue
        ks = {c["kind"]: c for c in s["cands"]}
        if "xbow_def_tile" not in ks:
            continue
        base = ks.get("xbow_reach_lane", s["cands"][0])
        v = PA.metric(s, ks["xbow_def_tile"], which, base=base)
        if v is not None:
            out.append((v, s["mid"]))
    return out


def rockets_in(c, key, within):
    """Share of continuations whose OWN plays include a Rocket landing <= ``within`` ticks after the root (dg[key]["pl"])."""
    d = (c.get("dg") or {}).get(key) or {}
    pl = d.get("pl") or []
    v = [any(n == "rocket" and dt <= within for dt, n in x[0]) for x in pl if x is not None]
    return v


def prefix_rates(S):
    n = {"fired": 0, "lapsed": 0, "no_cell": 0, "pending": 0}
    for s in S:
        for c in s["cands"]:
            for outc in c.get("prefix") or []:
                for o in outc or []:
                    for k in n:
                        if k in o:
                            n[k] += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("arms", nargs="+", help="NAME=dump.jsonl")
    ap.add_argument("--from-update", type=int, default=1)
    a = ap.parse_args()
    arms = {}
    for x in a.arms:
        name, fn = x.split("=", 1)
        arms[name] = PA.load([fn], a.from_update)
    names = list(arms)
    print(f"# P3-FORK3 arm comparison (updates >= {a.from_update})\n")
    print("| | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    res = {}
    for x in a.arms:                                           # CLXIII's real-match result per arm (updates >= from_update)
        name, fn = x.split("=", 1)
        oc = [json.loads(ln).get("outcome") for ln in open(fn, encoding="utf-8") if json.loads(ln).get("update", 0) >= a.from_update]
        res[name] = (len(oc), sum(o == "win" for o in oc) / max(len(oc), 1), sum(o == "draw" for o in oc) / max(len(oc), 1))
    print("| CLXIII win (draw) in the real matches | " + " | ".join(f"{res[n][1]:.3f} ({res[n][2]:.3f}) of {res[n][0]}" for n in names) + " |")
    print("| samples | " + " | ".join(str(len(arms[n])) for n in names) + " |")
    print("| matches | " + " | ".join(str(len({s['mid'] for s in arms[n]})) for n in names) + " |")
    rows = [("rocket", "rocket_princess", "chosen", "q", None), ("rocket", "rocket_princess", "chosen", "q", "1x"),
            ("rocket", "rocket_princess", "chosen", "q", "2x"), ("rocket", "rocket_princess", "chosen", "q", "OT"),
            ("rocket", "rocket_princess", "chosen", "qend", None),
            ("rocket", "rocket_empty", "chosen", "q", None), ("rocket", "rocket_empty", "chosen", "q", "1x"),
            ("rocket", "rocket_empty", "chosen", "q", "2x"), ("rocket", "rocket_empty", "chosen", "q", "OT"),
            ("rocket", "rocket_princess", "rocket_empty", "q", None),
            ("rocket", "rocket_clump", "chosen", "q", None),
            ("xbow_after_fail", "rocket_princess", "chosen", "q", None),
            ("xbow_after_fail", "rocket_empty", "chosen", "q", None),
            ("rocket_tornado", "combo", "rocket_clump", "q", None),
            ("tornado_redirect", "tornado_king", "tornado_on", "q", None),
            ("rocket_cycle", "rocket_princess", "chosen", "q", None),
            ("rocket_cycle", "rocket_princess", "chosen", "qh600", None),
            ("rocket_cycle", "rocket_princess", "chosen", "qh900", None),
            ("rocket_cycle", "rocket_princess", "chosen", "q", "2x"), ("rocket_cycle", "rocket_princess", "chosen", "q", "OT"),
            ("rocket_cycle", "rocket_empty", "chosen", "q", None),
            ("rocket_cycle", "rocket_princess", "rocket_empty", "q", None),
            ("def_xbow", "xbow_def_tile", "chosen", "q", None), ("def_xbow", "xbow_def_tile", "chosen", "qh600", None),
            ("def_xbow", "xbow_def_tile", "chosen", "qend", None), ("def_xbow", "wait", "chosen", "q", None)]
    for trig, x, y, which, ph in rows:
        print(f"| {trig}: {x} - {y} @{which}{' ' + ph if ph else ''} | "
              + " | ".join(fmt(contrast(arms[n], trig, x, y, which, ph)) for n in names) + " |")
    for which in ("q", "qh600", "qend"):
        print(f"| def_xbow: def - bridge @{which} | " + " | ".join(fmt(def_bridge(arms[n], which)) for n in names) + " |")
    print("\n## Opponent response at the main stop (rocket_princess - chosen, trigger rocket)\n")
    print("| column | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    for col in COLS[1:]:
        for ph in (None, "1x", "2x", "OT"):
            print(f"| {col}{' ' + ph if ph else ''} | " + " | ".join(fmt(contrast(arms[n], "rocket", "rocket_princess", "chosen", col, ph))
                                                         for n in names) + " |")
    print("\n| rocket_empty - chosen | " + " | ".join(names) + " |\n|---|" + "---|" * len(names))
    for col in COLS[1:]:
        print(f"| {col} | " + " | ".join(fmt(contrast(arms[n], "rocket", "rocket_empty", "chosen", col)) for n in names) + " |")
    print("\n## Macro bookkeeping\n")
    for n in names:
        rc = [s for s in arms[n] if s["trigger"] == "rocket_cycle"]
        own = [v for s in rc for v in rockets_in(s["cands"][0], "600", 600)]
        print(f"- {n}: rocket_cycle samples {len(rc)}; the chosen continuation Rockets within 600 ticks in "
              f"{(np.mean(own) if own else float('nan')):.2f} of {len(own)} continuations; def_xbow prefix outcomes "
              f"{prefix_rates([s for s in arms[n] if s['trigger'] == 'def_xbow'])}")


if __name__ == "__main__":
    main()
