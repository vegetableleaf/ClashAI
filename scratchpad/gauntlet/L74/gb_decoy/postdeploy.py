"""Re-run the evo Goblin Barrel measurement on every FINISHED live log started at/after the decoy deploy (default 20261028_114500).
Steps: scan.py's work() per log (public frame data only) -> post/results/casts_post.jsonl -> measure.py (printed + post/results/measure_post.txt)
-> newlogs.py flags (post/results/newlogs_post.txt). Laptop-light: below-normal priority, 2 workers, one directory listing.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/gb_decoy/postdeploy.py [AFTER_STAMP]
Pre-deploy reference (CLXIII, 559 casts): evo first answer in the real lane 30/50, plain 446/467; replay with the fix 43/50."""
import json
import os
import re
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scan import LIVE, low, work  # noqa: E402


def finished(path: str) -> bool:
    with open(path, "rb") as f:
        f.seek(max(0, os.path.getsize(path) - 65536))
        return b'{"event": "end"' in f.read()


if __name__ == "__main__":
    after = sys.argv[1] if len(sys.argv) > 1 else "20261028_114500"
    names = sorted(e.name for e in os.scandir(LIVE) if re.fullmatch(r"live_play_\d{8}_\d{6}\.jsonl", e.name) and e.name[10:25] >= after)
    files = [os.path.join(LIVE, n) for n in names if finished(os.path.join(LIVE, n))]
    out = HERE / "post" / "results"
    out.mkdir(parents=True, exist_ok=True)
    low()
    n = 0
    with Pool(2, initializer=low) as pool, open(out / "casts_post.jsonl", "w") as f:
        for rows in pool.imap(work, files, chunksize=2):
            for r in rows:
                f.write(json.dumps(r) + "\n")
                n += 1
    print(len(files), "finished logs since", after, "->", n, "casts")
    r = subprocess.run([sys.executable, str(HERE / "measure.py"), "results/casts_post.jsonl"], cwd=HERE / "post", capture_output=True, text=True)
    (out / "measure_post.txt").write_text(r.stdout)
    print(r.stdout[:2500], r.stderr[-500:])
    r = subprocess.run([sys.executable, str(HERE / "newlogs.py"), after], capture_output=True, text=True)
    (out / "newlogs_post.txt").write_text(r.stdout)
    print("newlogs flags:", len(r.stdout.splitlines()), "logs;", "barrel_decoy not True in",
          sum(" barrel_decoy True " not in l for l in r.stdout.splitlines()), "; errors seen:",
          sum(("'err" in l or "exc" in l) for l in r.stdout.splitlines()))
