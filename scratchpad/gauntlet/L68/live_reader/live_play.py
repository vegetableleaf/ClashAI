"""L68 live test: generalist pilots a TRAINING CAMP match on MuMu from the memory reader. Owner-run.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/live_play.py --training-camp [--dry-run]

Loop: reader frame (100 ms) -> pipeline.live_gen.GenPilot (opponent hand/next/elixir never used) -> if it plays,
two ordinary Android taps (hand slot, board) -> receipt from the NEXT frames: the tapped hand slot rotated AND my
elixir dropped (upstream mumu_live_actions.card_receipt). No game-memory writes. Taps follow upstream's ScreenLayout
(native X kept on screen for side 1; arena shifted one tile from the Cannon read-back). Each confirmed troop's
spawn position is compared with the intended cell -> tap-calibration error in tiles.
Stops: battle over / tick stalled 3 s, 5 unconfirmed taps, --max-seconds. Log: live_play_<ts>.jsonl here.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline.live_gen import GenPilot  # noqa: E402

# adb.exe directly (same device pin as adb.sh): from Python, "bash" resolves to WSL's System32 bash, which cannot
# run the Windows adb -> empty output.
ADB = [r"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe", "-s", "127.0.0.1:16384"]
ENV = dict(os.environ)
RVA, ROOT_CTX = "0x1aeef98", "0x18"
UI_READY_MIN_TICK = 150


def adb(*args: str, timeout: float = 5) -> str:
    return subprocess.run(ADB + list(args), capture_output=True, text=True, timeout=timeout, env=ENV).stdout


class Layout:
    """upstream native_core/mumu_live_actions.ScreenLayout.from_size, taking OUR board frame (me at the bottom,
    side 1 rotated 180 deg) instead of a canonical cell."""
    def __init__(self, w: int, h: int):
        vw = min(float(w), h * 9 / 16) if w / h > 0.8 else float(w)
        left = (w - vw) / 2
        self.w, self.h = w, h
        self.ax0, self.ax1 = left + vw * .055, left + vw * .945
        self.ay0, self.ay1 = h * (.105 - .685 / 32), h * (.790 - .685 / 32)
        self.hand_y, self.hand_x = h * .890, [left + vw * f for f in (.31, .50, .69, .88)]

    def board(self, xy: tuple[float, float], side: int) -> tuple[int, int]:
        fx = 1.0 - xy[0] if side == 1 else xy[0]          # screen keeps native X; our frame rotated it
        return round(self.ax0 + fx * (self.ax1 - self.ax0)), round(self.ay0 + xy[1] * (self.ay1 - self.ay0))

    def hand(self, pos: int) -> tuple[int, int]:
        return round(self.hand_x[pos]), round(self.hand_y)


def screen_size() -> tuple[int, int]:
    sizes = re.findall(r"(\d+)x(\d+)", adb("shell", "wm size"))
    w, h = sizes[-1]                                        # an Override size, if any, is listed last
    return int(w), int(h)


def my_frame_xy(e: dict, side: int) -> tuple[float, float]:
    x, y = (18000 - e["x"], 32000 - e["y"]) if side == 1 else (e["x"], e["y"])
    return x / 18000, 1 - y / 32000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--training-camp", action="store_true", help="REQUIRED: you confirm the match is Training Camp")
    ap.add_argument("--ckpt", default=str(REPO / "icebow/data/pipeline/gen_v1_s0/gen_s0.pt"))
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--leak", type=float, default=9.5, help="force a play at >= this elixir (anti-leak rule)")
    ap.add_argument("--interval-ms", type=int, default=100)
    ap.add_argument("--max-seconds", type=float, default=260)
    ap.add_argument("--dry-run", action="store_true", help="decide and log, never tap")
    a = ap.parse_args()
    if not a.training_camp:
        print("refusing: pass --training-camp to confirm the match is Training Camp (bot opponent)")
        return 2
    pilot = GenPilot(a.ckpt, gate_tau=a.tau)
    lay = Layout(*screen_size())
    log = open(HERE / f"live_play_{time.strftime('%Y%m%d_%H%M%S')}.jsonl", "w", encoding="utf-8")
    W = lambda **k: (log.write(json.dumps(k, default=str) + "\n"), log.flush())  # noqa: E731
    W(event="start", screen=[lay.w, lay.h], tau=a.tau, leak=a.leak, dry_run=a.dry_run, ckpt=a.ckpt)
    cmd = (f"/data/local/tmp/live_sampler $(pidof com.supercell.clashroyale) {a.interval_ms} {RVA} {ROOT_CTX} "
           f"--unified 0")
    procs: list = []

    def stream():
        """Reader lines; the 2026-09-25 01:55 run lost the stream silently at tick 953, so a closed stream is now
        logged (exit code + stderr) and the reader restarted, at most 3 times."""
        for attempt in range(4):
            p = subprocess.Popen(ADB + ["shell", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 env=ENV)
            procs.append(p)
            yield from p.stdout
            try:
                rc = p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rc = None
            W(event="reader_closed", attempt=attempt, rc=rc, stderr=(p.stderr.read() or "")[-500:],
              last_tick=last_tick)
            time.sleep(0.5)
        W(event="stop", why="reader_closed_4x")

    t0, pending, fails, played, confirmed, last_tick, last_adv = time.time(), None, 0, 0, 0, -1, time.time()
    seen_active = False
    try:
        for line in stream():
            now = time.time()
            if now - t0 > a.max_seconds:
                W(event="stop", why="max_seconds"); break
            try:
                f = json.loads(line)
            except ValueError:
                continue
            if not (f.get("battle_active") and f.get("coherent")):
                if seen_active and now - last_adv > 3:
                    W(event="stop", why="battle_inactive"); break
                continue
            tick = int(f["game_tick"])
            if tick > last_tick:
                last_tick, last_adv = tick, now
            elif now - last_adv > 3:
                W(event="stop", why="tick_stalled", tick=tick); break
            seen_active = True
            if tick < UI_READY_MIN_TICK:
                continue
            side = next(p["side"] for p in f["players"] if any(i >= 0 for i in p["hand_deck_indices"]))
            me = next(p for p in f["players"] if p["side"] == side)
            if pending:
                old = pending["me"]
                pos = pending["d"]["hand_pos"]
                rotated = me["hand_deck_indices"][pos] != old["hand_deck_indices"][pos]
                dropped = old["elixir_raw"] - me["elixir_raw"]
                if rotated and dropped > 0:
                    d = pending["d"]
                    cid = me["deck_card_ids"][d["deck_index"]]
                    new = [e for e in f["entities"] if e["side"] == side and e["card_id"] == cid
                           and e["address"] not in pending["addrs"]]
                    err = None
                    if new:
                        ex, ey = my_frame_xy(new[0], side)
                        err = round(((ex - d["xy"][0]) * 18) ** 2 + ((ey - d["xy"][1]) * 32) ** 2, 4) ** 0.5
                    pilot.record_play(d["card"], d["form"], d["xy"], d["bs"].t_sec)
                    confirmed += 1
                    W(event="confirmed", tick=tick, name=d["name"], intended=d["xy"], elixir_drop=dropped / 1e4,
                      spawn=[my_frame_xy(e, side) for e in new[:1]], err_tiles=err, latency_s=round(now - pending["t"], 3))
                    pending = None
                elif now - pending["t"] > 2.0:
                    fails += 1
                    W(event="unconfirmed", tick=tick, name=pending["d"]["name"], intended=pending["d"]["xy"],
                      p_play=pending["d"]["p_play"], elixir=old["elixir_raw"] / 1e4, fails=fails)
                    pending = None
                    if fails >= 5:
                        W(event="stop", why="5_unconfirmed"); break
                continue
            d = pilot.decide(f)
            el = me["elixir_raw"] / 1e4
            forced = not d["play"] and el >= a.leak and d["card"] > 0
            if not (d["play"] or forced):
                continue
            hand, board = lay.hand(d["hand_pos"]), lay.board(d["xy"], side)
            W(event="play", tick=tick, name=d["name"], p_play=round(d["p_play"], 4), forced=forced, elixir=el,
              hand_pos=d["hand_pos"], xy=[round(v, 4) for v in d["xy"]], tap_hand=hand, tap_board=board)
            played += 1
            if a.dry_run:
                continue
            adb("shell", f"input tap {hand[0]} {hand[1]}; sleep 0.05; input tap {board[0]} {board[1]}")
            pending = {"d": d, "me": me, "t": now, "addrs": {e["address"] for e in f["entities"]}}
    finally:
        for p in procs:
            p.terminate()
        adb("shell", "pkill -f live_sampler")
        W(event="end", played=played, confirmed=confirmed, fails=fails, seconds=round(time.time() - t0, 1))
        log.close()
    print(json.dumps({"played": played, "confirmed": confirmed, "fails": fails, "log": log.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
