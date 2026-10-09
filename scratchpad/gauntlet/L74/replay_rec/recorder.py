"""OBSERVE-ONLY recorder for a battle shown by the game's own replay viewer (TV Royale / battle-log replay). L74.

    # on the device (owner OK first; the replay must already be playing or about to start):
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/recorder.py --device [--max-seconds 600]
    # offline: re-stream a saved reader stream (one reader JSON frame per line, or a recording) through the same logic
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/recorder.py --from-file FRAMES.jsonl

No taps, no model, no game-memory writes: the only device command is the same read-only memory sampler live_play.py
runs (the command line live_play.py builds from the local reader config). Every reader line is saved with the host
receive time to OUT/rec_<stamp>.jsonl as {"event": "frame", "t_host", "f": <reader frame>}, plus rec_start /
battle_start / battle_end / refused events.
Battle start = the first active+coherent frame whose game_tick advanced past 0. End = (a) frames inactive for
END_IDLE_S after the start, (b) the tick stalled END_IDLE_S, (c) the tick went backwards (next replay), or (d)
--max-seconds. Refusal (exit 3): among the first SEAT_FRAMES advancing frames, if most show EXACTLY ONE visible hand
the reader is in a live battle we play in (live_mem.my_side_of's own test) -- not a spectated replay. The same test
keeps running: SEAT_FRAMES consecutive one-hand frames later also stop the recording as refused.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
OUT = REPO / "icebow" / "data" / "replay_rec"      # git-ignored data dir (never staged)
SEAT_FRAMES = 20
END_IDLE_S = 3.0
REFUSED = 3


def seat(frame) -> str:
    vis = sum(any(i >= 0 for i in p["hand_deck_indices"]) for p in frame.get("players") or ())
    return {1: "player", 2: "spectator"}.get(vis, "blind")


class Recorder:
    """Pure state machine: feed(line, now) -> None (keep going) or the stop reason. Writes through `write`."""

    def __init__(self, write):
        self.write = write
        self.started = False
        self.last_tick, self.last_adv = -1, None
        self.seats: list[str] = []
        self.run_player = 0

    def feed(self, line: str, now: float) -> str | None:
        try:
            f = json.loads(line)
        except ValueError:
            return None
        if not isinstance(f, dict) or "game_tick" not in f:
            return None
        if f.get("event") == "frame" and "f" in f:      # re-streaming a recording
            f = f["f"]
        self.write(dict(event="frame", t_host=now, f=f))
        active = bool(f.get("battle_active") and f.get("coherent"))
        if not active:
            if self.started and now - self.last_adv > END_IDLE_S:
                return "battle_inactive"
            return None
        tick = int(f["game_tick"])
        if self.started and tick < self.last_tick - 20:
            return "tick_reset"
        if tick > self.last_tick:
            if tick > 0 and not self.started:
                self.started = True
                self.write(dict(event="battle_start", t_host=now, tick=tick,
                                applied_replay_tick=f.get("applied_replay_tick")))
            self.last_tick, self.last_adv = tick, now
            if self.started:
                s = seat(f)
                if len(self.seats) < SEAT_FRAMES:
                    self.seats.append(s)
                    if len(self.seats) == SEAT_FRAMES and self.seats.count("player") > SEAT_FRAMES // 2:
                        return "refused_player_seat"
                self.run_player = self.run_player + 1 if s == "player" else 0
                if self.run_player >= SEAT_FRAMES:
                    return "refused_player_seat"
        elif self.started and now - self.last_adv > END_IDLE_S:
            return "tick_stalled"
        return None


def device_lines():
    """The live_play.py reader command, read-only. Imported lazily: live_play pulls torch."""
    sys.path.insert(0, str(REPO / "scratchpad" / "gauntlet" / "L68" / "live_reader"))
    import live_play as lp
    lp.apply_reader_config(strict=True)           # clear error when the local reader config is absent
    sampler, extra = lp.READERS["v2"]
    # `echo $$; exec` = the first line is the sampler's own device PID, so stop() kills exactly it (never a pattern
    # kill: a live_play.py sampler of the owner's may be running too)
    cmd = f"echo $$; exec {sampler} $(pidof com.supercell.clashroyale) 100 {lp.RVA} {lp.ROOT_CTX}{extra}"
    p = subprocess.Popen(lp.ADB + ["shell", cmd], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                         env=lp.ENV)
    pid = p.stdout.readline().strip()
    if not pid.isdigit():
        p.terminate()
        raise SystemExit(f"sampler did not start (first line {pid!r})")

    def stop():
        lp.adb("shell", f"kill {pid}")
        p.terminate()
    # ponytail: blocking readline -- a reader that goes fully silent hangs until Ctrl-C (live_play's queue+timeout
    # pattern is the upgrade if that happens on the device test)
    return p.stdout, stop


def run(lines, out: Path, max_seconds: float, clock=time.time) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    t0 = clock()
    with open(out, "w", encoding="utf-8") as h:
        def write(r):
            h.write(json.dumps(r) + "\n")
        write(dict(event="rec_start", t_host=t0, observe_only=True))
        rec, why = Recorder(write), "stream_ended"
        for line in lines:
            now = clock()
            why = rec.feed(line, now) or ("max_seconds" if now - t0 > max_seconds else None)
            if why:
                break
        else:
            why = "stream_ended"
        write(dict(event="refused" if why.startswith("refused") else "battle_end", t_host=clock(), why=why,
                   last_tick=rec.last_tick, started=rec.started, seats=rec.seats))
    return why


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--device", action="store_true", help="run the read-only memory sampler on MuMu")
    src.add_argument("--from-file", help="re-stream saved reader lines (offline test)")
    ap.add_argument("--out", help=f"recording path (default {OUT}/rec_<stamp>.jsonl)")
    ap.add_argument("--max-seconds", type=float, default=600.0)
    a = ap.parse_args()
    out = Path(a.out) if a.out else OUT / f"rec_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    if a.device:
        lines, stop = device_lines()
    else:
        lines, stop = open(a.from_file, encoding="utf-8"), lambda: None
    try:
        why = run(lines, out, a.max_seconds)
    finally:
        stop()
    print(json.dumps(dict(recording=str(out), why=why)))
    return REFUSED if why.startswith("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
