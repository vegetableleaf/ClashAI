"""auto_stop.py LOG OUT_DIR HOURS -- owner 10-30 pilot stop rule, run ON THE POD beside the training run.

Writes OUT_DIR/STOP (rl_royale finishes the update in progress, saves, FINAL) at the first of:
- HOURS wall hours since this script started (owner: 6 h hard cap);
- 50 updates with no improvement: the 10-update rolling training win rate vs the frozen pool has not set a new best by
  >= 0.5 pp for 50 updates (b: a proxy; at 2,048 matches/update one update's win rate has SE ~1 pp, a 10-update mean ~0.35).
Logs its readings to OUT_DIR/auto_stop.log. Self-check: python auto_stop.py --selftest"""
import re, sys, time
from pathlib import Path

LINE = re.compile(r"^\[rl\] u(\d+) W/L/D (\d+)/(\d+)/(\d+)")


def decide(wins, window=10, patience=50, margin=0.5):
    """wins: list of per-update win %. Returns (best, best_at, stop) by the rolling-mean rule."""
    best, best_at = None, None
    for i in range(window - 1, len(wins)):
        m = sum(wins[i - window + 1:i + 1]) / window
        if best is None or m >= best + margin:
            best, best_at = m, i
    return best, best_at, best_at is not None and len(wins) - 1 - best_at >= patience


def selftest():
    assert decide([50.0] * 70)[2] is True                      # flat for 61 rolling points -> stop
    assert decide([50.0 + i * 0.1 for i in range(70)])[2] is False   # rising 1 pp per 10 updates -> keep going
    assert decide([50.0] * 30)[2] is False                     # too few updates to judge
    print("auto_stop selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest(); sys.exit(0)
    log, out, hours = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3])
    t0, rep = time.time(), out / "auto_stop.log"
    while True:
        wins = []
        if log.exists():
            for ln in log.read_text(errors="replace").splitlines():
                m = LINE.match(ln)
                if m:
                    w, l, d = (int(m.group(k)) for k in (2, 3, 4))
                    wins.append(100.0 * w / max(1, w + l + d))
        best, at, stop = decide(wins)
        el = (time.time() - t0) / 3600
        with rep.open("a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} updates {len(wins)} best10 {best} @ {at} elapsed {el:.2f} h stop {stop}\n")
        if stop or el >= hours:
            (out / "STOP").write_text(f"auto_stop: {'no improvement 50 updates' if stop else f'{hours} h cap'}\n")
            sys.exit(0)
        time.sleep(120)
