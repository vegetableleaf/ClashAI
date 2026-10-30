"""arms_watch.py -- exit (printing a summary) when every running arm has plateaued or one reaches the bar.

Reads out/lead_d3.log (scored [16.635.3] blocks) and each arm's current update from its pod log. Owner rule 10-29: an arm
plateaus when its best CLXIII D3 win has not improved by >= 2 pp for >= 50 updates. Bar (strength part): CLXIII <= 50%.
Polls every 10 min. Usage: icebow/.venv/Scripts/python.exe arms_watch.py   (no pod writes; read-only ssh)"""
import re, subprocess, sys, time
from pathlib import Path

LOG = Path(__file__).parent / "out" / "lead_d3.log"
ARMS = {  # run -> (pod, training log) for the arms still running
    "oplc_ftR_l001_a10": (33308, "/workspace/oplc/logs/oplc_ftR_l001_a10.out"),
    "oplc_ftR_l003_a10_tpg32m": (33308, "/workspace/oplc/logs/oplc_ftR_l003_a10_tpg32m.log"),
    "oplc_ftR_l0003_a10b": (30408, "/workspace/oplm/logs/oplc_ftR_l0003_a10b.out"),
    "oplc_ftR_l0001_a10": (33903, "/workspace/oplm/logs/oplc_ftR_l0001_a10.out"),
}
LINE = re.compile(r"(\S+)_u(\d{4}) \[16\.635\.3\] CLXIII W (\d+) / (\d+)")


def scores():
    out = {}
    for m in LINE.finditer(LOG.read_text(encoding="utf-8", errors="replace")):
        run, u, w, n = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        if n >= 400:                                   # skip crashed / short blocks
            out.setdefault(run, {})[u] = 100.0 * w / n
    return out


def current_update(pod, log):
    cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "-i", str(Path.home() / ".ssh/runpod_clashbot"),
           "-p", str(pod), "root@157.157.221.29", f"grep -o '\\[rl\\] u[0-9]*' {log} | tail -n 1"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    m = re.search(r"u(\d+)", r.stdout)
    return int(m.group(1)) if m else None


def verdict(pts, now):
    """(best_u, best, plateaued): best = lowest CLXIII win; a new best must beat the old by >= 2 pp to count."""
    best_u, best = None, None
    for u in sorted(pts):
        if best is None or pts[u] <= best - 2.0:
            best_u, best = u, pts[u]
    return best_u, best, (now is not None and best_u is not None and now - best_u >= 50 and max(pts) > best_u)


if __name__ == "__main__":
    while True:
        sc, lines, done = scores(), [], True
        for run, (pod, log) in ARMS.items():
            pts = sc.get(run, {})
            now = current_update(pod, log)
            bu, b, plat = verdict(pts, now)
            lines.append(f"{run}: now u{now} best {b if b is None else round(b, 1)}% @u{bu} plateau={plat} pts={ {k: round(v, 1) for k, v in sorted(pts.items())} }")
            if pts and min(pts.values()) <= 50.0:
                print("BAR CANDIDATE (CLXIII <= 50%):\n" + "\n".join(lines)); sys.exit(0)
            done &= plat
        if done:
            print("ALL ARMS PLATEAUED:\n" + "\n".join(lines)); sys.exit(0)
        time.sleep(600)
