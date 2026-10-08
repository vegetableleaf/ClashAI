"""L74 latency budget from EXISTING live_play logs (read-only; no device access).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency/latency_budget.py [glob ...] > budget.txt

Per confirmed play in a RECORDED log (frame events present):
  T0      decision tick (play event), its device time t_dev0
  T_el    first frame after T0 whose elixir fell >= 0.3 vs the previous frame (the game state's elixir charge)
  T_sp    first frame after T0 with a NEW own entity (address unseen at T0, card_id >= 0) -- troops / buildings
  T_rot   the confirmation frame (hand slot rotated; the `confirmed` event)
  T_prev  the frame before T_rot -> rotation happened in (T_prev, T_rot]
plus decide_ms / tap_ms / frame_age_backlog (tap_timing) and latency_s (host wall, decision frame -> confirm frame).
Unrecorded logs contribute only T0 -> T_rot + host timings.
live_play >= L74 also logs, per tap: recv_age_ms (queue wait), sample_age_ms (device sample -> decide start) and
tap_end_ms (device sample -> board tap returned), on the device clock minus the fastest frame transport; then
game part = (T_rot - T0) * 50 ms - tap_end_ms is everything after our board tap returned.

Look-ahead horizon procedure (--extrapolate live, action_delay SIM; both 26 today; changing them is a separate,
owner-approved step and SIM and live move together):
  1. baseline = this script on the pre-change logs (2026-10-08: T_rot - T0 median 28, mean 28.9, n = 6,530;
     rotation midpoint median 27, n = 1,256 recorded) -> budget_20261008.txt
  2. owner runs >= 5 ladder matches with the new input flags (--clip-every keeps a few recorded for the midpoint)
  3. run this script on those logs; the "by input configuration" block compares the configurations directly
  4. new horizon = 26 + (new median gap - baseline median gap), i.e. shift by the measured change and keep 26's
     calibration convention; apply the same shift to SIM action_delay and re-run the SIM paired eval before deploy
"""
from __future__ import annotations

import glob
import json
import statistics as st
import sys
from pathlib import Path

try:                                    # owner is playing live: stay out of the way
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except Exception:
    pass

LOGS = Path(__file__).resolve().parents[4] / "scratchpad/gauntlet/L68/live_reader"
MAIN_LOGS = Path(r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader")


def q(v, ps=(5, 25, 50, 75, 95)):
    v = sorted(v)
    if not v:
        return "n=0"
    pick = lambda p: v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]
    return f"n={len(v)} mean={st.mean(v):.2f} " + " ".join(f"p{p}={pick(p)}" for p in ps)


def parse(path: Path):
    frames, plays, out = [], [], []
    cur, gap, fast = None, 50, False
    for ln in path.open(encoding="utf-8"):
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ev = e.get("event")
        if ev == "frame":
            frames.append((e["tick"], e["t_dev"], e["elixir"], e["my_side"],
                           {x[7]: x for x in e["ents"]}))
        elif ev == "play":
            cur = dict(T0=e["tick"], t_dev0=e.get("t_dev"), name=e["name"], elixir0=e.get("elixir"))
            plays.append(cur)
        elif ev == "start":
            gap, fast = e.get("tap_gap_ms", 50), e.get("fast_input", False)
        elif ev == "tap_timing" and cur is not None and e["tick"] == cur["T0"]:
            cur.update(decide_ms=e["decide_ms"], tap_ms=e["tap_ms"], backlog=e.get("frame_age_backlog"),
                       tap_gap_ms=gap, fast_input=e.get("fast_input", fast),
                       **{k: e[k] for k in ("recv_age_ms", "sample_age_ms", "tap_end_ms") if k in e})
        elif ev == "confirmed" and cur is not None and "T_rot" not in cur:
            cur.update(T_rot=e["tick"], latency_s=e.get("latency_s"))
        elif ev == "unconfirmed" and cur is not None:
            cur["unconfirmed"] = True
    by_tick = {f[0]: i for i, f in enumerate(frames)}
    for p in plays:
        if "T_rot" not in p or "tap_ms" not in p:
            continue
        p["file"] = path.name
        if frames and p["T0"] in by_tick and p["T_rot"] in by_tick:
            i0, ir = by_tick[p["T0"]], by_tick[p["T_rot"]]
            side, addrs0 = frames[i0][3], set(frames[i0][4])
            p["T_prev"] = frames[ir - 1][0]
            p["t_dev_rot"] = frames[ir][1]
            for j in range(i0 + 1, min(len(frames), ir + 40)):
                if "T_el" not in p and frames[j][2] < frames[j - 1][2] - 0.3:
                    p["T_el"] = frames[j][0]
                if "T_sp" not in p and any(a not in addrs0 and x[0] == side and x[3] >= 0
                                           for a, x in frames[j][4].items()):
                    p["T_sp"] = frames[j][0]
            p["tick_rate"] = ((frames[ir][0] - frames[i0][0]) / (frames[ir][1] - frames[i0][1])
                              if frames[ir][1] > frames[i0][1] else None)
        out.append(p)
    return out, frames


def main() -> None:
    pats = sys.argv[1:] or [str(MAIN_LOGS / "live_play_20261008_*.jsonl")]
    files = sorted({f for pat in pats for f in glob.glob(pat)})
    rows, spacing, rates = [], [], []
    for f in files:
        r, frames = parse(Path(f))
        rows += r
        spacing += [b[0] - a[0] for a, b in zip(frames, frames[1:]) if 0 < b[0] - a[0] < 20]
        if len(frames) > 100:
            rates.append((frames[-1][0] - frames[0][0]) / (frames[-1][1] - frames[0][1]))
    rec = [r for r in rows if "T_prev" in r]
    print(f"logs {len(files)}; confirmed plays with host timings {len(rows)}; in recorded logs {len(rec)}")
    print(f"game ticks per device second (whole recorded matches): {q([round(x, 2) for x in rates])}")
    print(f"frame spacing in ticks: {q(spacing)}")
    print("\n== all confirmed plays ==")
    print(f"T_rot - T0 (ticks):            {q([r['T_rot'] - r['T0'] for r in rows])}")
    print(f"latency_s (host, s):           {q([r['latency_s'] for r in rows if r.get('latency_s') is not None])}")
    print(f"decide_ms:                     {q([r['decide_ms'] for r in rows])}")
    print(f"tap_ms:                        {q([r['tap_ms'] for r in rows])}")
    print(f"frames queued during decide+tap: {q([r['backlog'] for r in rows if r.get('backlog') is not None])}")
    print("\n== recorded logs (frame-level) ==")
    print(f"T_rot - T0:                    {q([r['T_rot'] - r['T0'] for r in rec])}")
    print(f"T_prev - T0 (rotation lower bound): {q([r['T_prev'] - r['T0'] for r in rec])}")
    print(f"(T_prev + T_rot)/2 - T0 (midpoint): {q([(r['T_prev'] + r['T_rot']) / 2 - r['T0'] for r in rec])}")
    el = [r for r in rec if "T_el" in r]
    print(f"T_el - T_rot (elixir charge vs rotation): {q([r['T_el'] - r['T_rot'] for r in el])}")
    sp = [r for r in rec if "T_sp" in r]
    print(f"T_sp - T_rot (new own entity vs rotation): {q([r['T_sp'] - r['T_rot'] for r in sp])}")
    print(f"ticks/s inside play windows:   {q([round(r['tick_rate'], 2) for r in rec if r.get('tick_rate')])}")
    # how much of the gap does host time explain? ordinary least squares gap_ticks ~ a + b * host_ms
    xs = [r["decide_ms"] + r["tap_ms"] for r in rows]
    ys = [r["T_rot"] - r["T0"] for r in rows]
    if len(set(xs)) > 1:
        mx, my = st.mean(xs), st.mean(ys)
        b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
        print(f"\nOLS gap_ticks = {my - b * mx:.2f} + {b * 1000:.2f} ticks/s * (decide+tap s)   "
              f"[1:1 host->game would be 20 ticks/s]; corr={st.correlation(xs, ys):.3f}")
        # binned
        for lo, hi in ((0, 200), (200, 260), (260, 320), (320, 400), (400, 10 ** 6)):
            g = [y for x, y in zip(xs, ys) if lo <= x < hi]
            if g:
                print(f"  decide+tap in [{lo},{hi}) ms: n={len(g)} median gap {st.median(g)} ticks, mean {st.mean(g):.2f}")
    # per input configuration (fast_input, tap_gap_ms): the comparison to make after the owner's live test
    print("\n== by input configuration ==")
    for key in sorted({(r.get("fast_input", False), r.get("tap_gap_ms", 50)) for r in rows}):
        g = [r for r in rows if (r.get("fast_input", False), r.get("tap_gap_ms", 50)) == key]
        print(f"fast_input={key[0]} tap_gap_ms={key[1]}: gap ticks {q([r['T_rot'] - r['T0'] for r in g])}")
        print(f"    tap_ms {q([r['tap_ms'] for r in g])}")
        new = [r for r in g if "tap_end_ms" in r]      # live_play >= L74: host part on the device clock
        if new:
            print(f"    recv_age_ms (queue)            {q([r['recv_age_ms'] for r in new])}")
            print(f"    sample_age_ms (sample->decide) {q([r['sample_age_ms'] for r in new])}")
            print(f"    tap_end_ms (sample->board tap returned) {q([r['tap_end_ms'] for r in new])}")
            print(f"    game part ms = (T_rot-T0)*50 - tap_end_ms {q([(r['T_rot'] - r['T0']) * 50 - r['tap_end_ms'] for r in new])}")
    devs = {}
    for f in files:
        for ln in open(f, encoding="utf-8"):
            if '"event": "start"' in ln:
                devs[Path(f).name] = json.loads(ln).get("device")
                break
    for dev in sorted(set(devs.values()), key=str):
        g = [r for r in rows if devs.get(r["file"]) == dev]
        print(f"device={dev}: decide_ms {q([r['decide_ms'] for r in g])}")


if __name__ == "__main__":
    main()
