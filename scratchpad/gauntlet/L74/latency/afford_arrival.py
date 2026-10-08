"""L74 affordability timing: when does the game refuse a card tapped without enough elixir?

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency/afford_arrival.py [glob ...] > afford_arrival.txt

Per live play (play event -> its confirmed / unconfirmed outcome): el = reader elixir at the decision frame (the play
event's `elixir`, NOT the look-ahead), cost = card_cost, need = game ticks of regen until el reaches cost (0 if
affordable now; REGEN_SCHEDULE), arrival = ticks from the decision frame's sample to the board tap returning
(tap_end_ms / 50 where logged, else (2 + decide_ms + tap_ms) / 50; 2 ms = the median of tap_end_ms - decide_ms -
tap_ms over the 388 logged plays: frames are decided on arrival), wait = need - arrival.

Prints (a) refusal by wait (pooled: the game behaviour), (b) the "affordable at arrival" rule's counterfactual,
(c) the afford-horizon rule A (allowed iff need <= A, i.e. elixir at decision tick + A >= cost) per input mode.
"""
from __future__ import annotations

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

try:
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except Exception:
    pass

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from pipeline import vocab  # noqa: E402
from pipeline.opp_elixir_count import card_cost, regen_between  # noqa: E402

LOGS = r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\live_play_2026100[5-8]_*.jsonl"
LOCK = 60                                               # live_play CONFIRM_TICKS: a refusal holds the bot this long
BASE = 22                                               # measured (a): an accepted play executes ~22 ticks after it can


def need_ticks(el: float, cost: float, t0: int) -> int:
    """Ticks from t0 until el + regen >= cost (cap 600)."""
    if el >= cost:
        return 0
    for k in range(1, 601):
        if el + regen_between(t0, t0 + k) >= cost:
            return k
    return 600


def plays(path: str):
    mode, cur, out = "default/gap50", None, []
    for ln in open(path, encoding="utf-8"):
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ev = e.get("event")
        if ev == "start":
            mode = ("fast" if e.get("fast_input") else "default") + f"/gap{e.get('tap_gap_ms', 50)}"
        elif ev == "play":
            cur = dict(file=Path(path).name, mode=mode, T0=int(e["tick"]), el=float(e["elixir"]), name=e["name"])
        elif ev == "tap_timing" and cur is not None and int(e["tick"]) == cur["T0"]:
            cur["arr_ms"] = e.get("tap_end_ms")
            cur["arr_est"] = cur["arr_ms"] is None
            if cur["arr_ms"] is None:
                cur["arr_ms"] = 2 + e["decide_ms"] + e["tap_ms"]
        elif ev in ("confirmed", "unconfirmed") and cur is not None and "arr_ms" in cur:
            cur["ok"] = ev == "confirmed"
            cur["T1"] = int(e["tick"])
            out.append(cur)
            cur = None
    return out


def load(pats) -> list[dict]:
    rows = []
    for f in sorted({f for pat in pats for f in glob.glob(pat)}):
        for p in plays(f):
            c = card_cost(vocab.engine_key(p["name"]))
            if c is None:
                continue
            p.update(cost=c, need=need_ticks(p["el"], c, p["T0"]), arr=p["arr_ms"] / 50)
            rows.append(p)
    return rows


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p / 100 * (len(v) - 1)))] if v else None


def main() -> None:
    rows = load(sys.argv[1:] or [LOGS])
    ref = lambda v: f"{sum(not r['ok'] for r in v)}/{len(v)} ({100 * sum(not r['ok'] for r in v) / max(1, len(v)):.0f}%)"
    print(f"plays with an outcome {len(rows)}")
    un = [r for r in rows if r["need"] > 0]
    print(f"\n(a) game behaviour, all modes: refused when affordable at the decision frame {ref([r for r in rows if r['need'] == 0])}")
    print("    not affordable at the decision frame, by wait = need - arrival (ticks):")
    for w in range(-2, 26):
        v = [r for r in un if w <= r["need"] - r["arr"] < w + 1]
        if v:
            lat = [r["T1"] - r["T0"] - r["need"] for r in v if r["ok"]]
            print(f"      [{w:>3},{w + 1:>3}): refused {ref(v):<16} accepted: confirm tick - decision tick - need, median {pct(lat, 50)}")
    by = defaultdict(list)
    for r in rows:
        by[r["mode"]].append(r)
    print("\n(b) 'affordable at arrival' rule (block iff need > arrival):")
    for mode, g in sorted(by.items()):
        blk = [r for r in g if r["need"] > r["arr"]]
        print(f"    {mode}: blocks {len(blk)}/{len(g)} plays, of which refused {sum(not r['ok'] for r in blk)} / "
              f"accepted {sum(r['ok'] for r in blk)}")
    print("\n(c) afford horizon A (allowed iff need <= A); today's rule = A 26 (the look-ahead elixir):")
    for mode, g in sorted(by.items()):
        arr = [r["arr"] for r in g]
        print(f"  {mode}: plays {len(g)}, arrival ticks p5 {pct(arr, 5):.1f} p50 {pct(arr, 50):.1f} p95 {pct(arr, 95):.1f};"
              f" refused now {ref(g)}")
        for A in range(20, 27):
            blk = [r for r in g if r["need"] > A]
            kept = [r for r in g if r["need"] <= A]
            nr, na = sum(not r["ok"] for r in blk), sum(r["ok"] for r in blk)
            print(f"     A {A}: blocks {len(blk):>4} (refused {nr:>3}, accepted {na:>3});"
                  f" kept plays refused {ref(kept)}; lock ticks saved ~{nr * LOCK}")
    print(f"\n(d) early release: confirmed plays' residual = (confirm tick - decision tick) - (max(arrival, need) + {BASE})")
    for mode, g in sorted(by.items()):
        res = [r["T1"] - r["T0"] - (max(r["arr"], r["need"]) + BASE) for r in g if r["ok"]]
        print(f"  {mode}: n {len(res)}  p50 {pct(res, 50):.1f} p90 {pct(res, 90):.1f} p99 {pct(res, 99):.1f} "
              f"p99.9 {pct(res, 99.9):.1f} max {max(res):.1f}")
        for m in (6, 8, 10, 12, 15):
            late = sum(x > m for x in res)
            rel = [min(LOCK, max(r["arr"], r["need"]) + BASE + m) for r in g if not r["ok"]]
            print(f"     margin {m:>2}: confirmations after the release {late}/{len(res)}; refused plays released at "
                  f"median tick {pct(rel, 50):.1f} instead of {LOCK} (saves {LOCK - pct(rel, 50):.1f} ticks each, "
                  f"{len(rel)} refusals)")


if __name__ == "__main__":
    main()
