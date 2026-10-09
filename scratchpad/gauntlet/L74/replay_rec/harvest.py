"""TV Royale harvest loop: navigate -> record each replay at 4x -> convert -> sanity-check -> dedupe -> manifest. L74.

    # LEAD OK FIRST (device). Classify + decide only, no taps, no recording:
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/harvest.py --dry-run [--minutes 5]
    # real run (refuses while tv_nav.missing_templates() is not empty):
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/harvest.py --minutes 60 [--max-replays N]
    # offline: (re)process recordings already on disk into the harvest folder
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/harvest.py --process REC.jsonl [...] --channel X

Output (git-ignored): OUT/manifest.jsonl (one row per recording, accepted or rejected, with the reasons),
OUT/crawl/battles.csv + plays_ext_i1.csv (accepted replays appended; replay_drive --crawl OUT/crawl), and
OUT/corpus/replay_<tag>.json (to_record.py; dataset_gen --corpus OUT/corpus --feature-version 4).
Inputs: taps only through tv_nav.allowed(); the recorder is recorder.Recorder (refuses a battle we play in).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time
from collections import deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert as cv  # noqa: E402
import recorder as rc  # noqa: E402

OUT = HERE.parents[3] / "icebow" / "data" / "replay_rec" / "harvest"
MIN_PLAYS = 5                 # per side
MIN_POSITIONED = 0.90
MAX_FIRST_TICK = 200          # recorded from the start (the recorder opens BEFORE the replay row is tapped)
REPLAY_WALL_S = 420.0         # longest crawl battle 15,851 ticks = 13.2 min real = 3.3 min at 4x (+ loading)
NAV_PERIOD_S = 1.0


# ---- per-replay processing (pure file work; tested offline) -------------------------------------------------------
def checks(res: dict) -> list[str]:
    bad = []
    if res["mode"] != "hand":
        bad.append("hands_not_visible")
    b = res["battle"]
    for col in ("team_deck", "opponent_deck"):
        if len([c for c in b[col].split(",") if c]) != 8:
            bad.append(f"{col}_incomplete")
    for s in ("red", "blue"):
        rows = [r for r in res["plays"] if r["attr_s"] == s]
        if len(rows) < MIN_PLAYS:
            bad.append(f"{s}_plays<{MIN_PLAYS}")
        elif sum(r["located"] for r in rows) / len(rows) < MIN_POSITIONED:
            bad.append(f"{s}_positioned<{MIN_POSITIONED}")
    if res["first_tick"] > MAX_FIRST_TICK:
        bad.append(f"started_late:{res['first_tick']}")
    if res.get("cycle_bad") and any(v != 0 for v in res["cycle_bad"].values()):
        bad.append(f"cycle_mismatch:{res['cycle_bad']}")
    return bad


def identity(res: dict) -> dict:
    """What makes two recordings the same replay: both decks + the (side, card, tick) play list."""
    b = res["battle"]
    return {"decks": [sorted(b["team_deck"].split(",")), sorted(b["opponent_deck"].split(","))],
            "plays": [[r["attr_s"], r["attr_card"], int(r["tick"])] for r in res["plays"]]}


def same_replay(a: dict, b: dict, dt: int = 16, frac: float = 0.8) -> bool:
    """Same decks and >= frac of the shorter play list matched (same side + card, |tick diff| <= dt: 2 samples at 4x)."""
    if a["decks"] != b["decks"]:
        return False
    short, other = sorted((a["plays"], b["plays"]), key=len)
    if not short:
        return True
    used, hit = set(), 0
    for s, c, t in short:
        j = next((j for j, (s2, c2, t2) in enumerate(other) if j not in used and s2 == s and c2 == c and abs(t2 - t) <= dt), None)
        if j is not None:
            used.add(j)
            hit += 1
    return hit >= frac * len(short)


def load_manifest(out: Path) -> list[dict]:
    p = out / "manifest.jsonl"
    return [json.loads(line) for line in open(p, encoding="utf-8")] if p.exists() else []


def append_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    new = not path.exists()
    with open(path, "a", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=cols)
        if new:
            w.writeheader()
        w.writerows(rows)


def process(rec_path: Path, out: Path, channel: str | None, tier: int | None = None) -> dict:
    """Convert one recording; accept it into the harvest (CSV + corpus) or log why not. -> its manifest row."""
    out.mkdir(parents=True, exist_ok=True)
    row = {"recording": str(rec_path), "channel": channel, "tier": tier,
           "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(rec_path.stat().st_mtime))}
    try:
        res = cv.convert(rec_path)
    except SystemExit as e:                             # refused (a battle we played) / no frames
        row.update(verdict="rejected", reasons=[str(e)])
    else:
        b = res["battle"]
        ident = identity(res)
        row.update(tag=b["replay_tag"], decks={"blue": b["team_deck"], "red": b["opponent_deck"]}, result=b["result"],
                   crowns=[b["team_crowns"], b["opponent_crowns"]], ticks=[res["first_tick"], res["last_tick"]],
                   plays={s: sum(r["attr_s"] == s for r in res["plays"]) for s in ("red", "blue")},
                   positioned={s: sum(r["located"] for r in res["plays"] if r["attr_s"] == s) for s in ("red", "blue")},
                   cycle_bad=res.get("cycle_bad"), identity=ident)
        reasons = checks(res)
        dup = next((m["tag"] for m in load_manifest(out) if m.get("verdict") == "accepted"
                    and same_replay(ident, m["identity"])), None)
        if dup:
            reasons.append(f"duplicate_of:{dup}")
        row.update(verdict="rejected" if reasons else "accepted", reasons=reasons)
        if not reasons:
            (out / "crawl").mkdir(parents=True, exist_ok=True)
            append_csv(out / "crawl" / "battles.csv", cv.BATTLE_COLS, [b])
            append_csv(out / "crawl" / "plays_ext_i1.csv", cv.PLAY_COLS, res["plays"])
            import to_record as tr
            (out / "corpus").mkdir(parents=True, exist_ok=True)
            rec = tr.to_record(rec_path)
            (out / "corpus" / f"replay_{rec['tag']}.json").write_text(json.dumps(rec), encoding="utf-8")
    with open(out / "manifest.jsonl", "a", encoding="utf-8") as h:
        h.write(json.dumps(row) + "\n")
    return row


# ---- device side ---------------------------------------------------------------------------------------------------
class ReaderPump:
    """Reads reader lines in a thread; reports in_replay / tick rate; feeds the open recording (recorder.Recorder)."""

    def __init__(self, lines, clock=time.time):
        self.clock, self.lock = clock, threading.Lock()
        self.recent: deque = deque(maxlen=60)          # (t, tick) of active spectator frames
        self.rec = self.h = None
        self.path, self.ended = None, None
        self.thread = threading.Thread(target=self._run, args=(lines,), daemon=True)
        self.thread.start()

    def _run(self, lines) -> None:
        for line in lines:
            now = self.clock()
            try:
                f = json.loads(line)
            except ValueError:
                continue
            with self.lock:
                if f.get("battle_active") and f.get("coherent") and rc.seat(f) == "spectator":
                    self.recent.append((now, int(f["game_tick"])))
                if self.rec is not None and self.ended is None:
                    why = self.rec.feed(line, now) or ("max_seconds" if now - self.t0 > REPLAY_WALL_S else None)
                    if why:
                        self._close(why)

    def _close(self, why: str) -> None:
        self.ended = why
        self.h.write(json.dumps(dict(event="refused" if why.startswith("refused") else "battle_end",
                                     t_host=self.clock(), why=why, last_tick=self.rec.last_tick,
                                     started=self.rec.started, seats=self.rec.seats)) + "\n")
        self.h.close()
        self.rec = None

    def open(self, path: Path) -> None:
        with self.lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.path, self.ended, self.t0 = path, None, self.clock()
            self.h = open(path, "w", encoding="utf-8")
            self.h.write(json.dumps(dict(event="rec_start", t_host=self.t0, observe_only=True)) + "\n")
            self.rec = rc.Recorder(lambda r: self.h.write(json.dumps(r) + "\n"))

    def status(self) -> dict:
        with self.lock:
            now = self.clock()
            r = [x for x in self.recent if now - x[0] <= 2.5]
            rate = (r[-1][1] - r[0][1]) / (r[-1][0] - r[0][0]) if len(r) >= 2 and r[-1][0] > r[0][0] else None
            return {"in_replay": bool(r) and now - r[-1][0] <= 1.5, "ticks_per_s": rate,
                    "recording": self.rec is not None, "ended": self.ended}

    def take(self):
        """-> (path, why) of a finished recording, once; else None."""
        with self.lock:
            if self.path is not None and self.ended is not None:
                out, self.path = (self.path, self.ended), None
                return out
        return None


def run(grab, tap, pump, classifier, out: Path, minutes: float, max_replays: int, dry_run: bool,
        clock=time.time, sleep=time.sleep, log=print) -> str:
    import tv_nav
    st, t0, n = {}, clock(), 0
    while clock() - t0 < minutes * 60:
        done = pump.take() if pump else None
        if done:
            row = process(done[0], out, tv_nav.CHANNELS[st.get("channel", 0)], st.get("channel", 0))
            n += 1
            log(json.dumps({k: row.get(k) for k in ("tag", "verdict", "reasons", "plays", "ticks")}))
            if n >= max_replays:
                return "max_replays"
        scr = classifier.classify(grab())
        status = pump.status() if pump else {}
        if dry_run:
            status["recording"] = True                  # dry run never records: act as if the recorder were open
        act = tv_nav.decide(st, scr, status, clock())
        log(json.dumps({"t": round(clock() - t0, 1), "screen": scr["screen"], "speed": scr.get("speed"),
                        "phase": st.get("phase"), "action": [str(a) for a in act]}))
        if act[0] == "stop":
            return act[1]
        if act[0] == "done":
            return "all_channels_done"
        if act[0] == "start_record" and pump and not dry_run:
            pump.open(out / "recordings" / f"rec_{time.strftime('%Y%m%d_%H%M%S')}.jsonl")
        if act[0] == "tap":
            if not tv_nav.allowed(act[1], act[2], classifier.man):
                return f"tap_not_allowed:{act[1]}"
            if not dry_run:
                tap(*act[2])
        sleep(NAV_PERIOD_S)
    return "minutes"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--minutes", type=float, default=60.0)
    ap.add_argument("--max-replays", type=int, default=10 ** 6)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--process", nargs="+", help="offline: recordings to process into --out")
    ap.add_argument("--channel")
    a = ap.parse_args()
    out = Path(a.out)
    if a.process:
        for p in a.process:
            print(json.dumps({k: v for k, v in process(Path(p), out, a.channel).items() if k != "identity"}))
        return 0
    import tv_nav
    classifier = tv_nav.Classifier()
    missing = tv_nav.missing_templates(classifier.man)
    if missing and not a.dry_run:
        raise SystemExit(f"templates missing (capture pass first, tv_templates.py): {missing}")
    sys.path.insert(0, str(tv_nav.LIVE))
    import live_play as lp
    from ladder_nav import grab as ladder_grab
    lines, stop = rc.device_lines()
    pump = ReaderPump(lines)

    def tap(x, y):
        lp.adb("shell", f"input tap {int(x)} {int(y)}")
    try:
        why = run(lambda: ladder_grab(lp.ADB), tap, pump, classifier, out, a.minutes, a.max_replays, a.dry_run)
    finally:
        stop()
    print(json.dumps({"stop": why}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
