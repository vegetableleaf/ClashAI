"""REAL RUN instrument gates (PPO_RUN_SPEC addendum 4d): paired reads at m=5k/10k/20k.

Detached (nohup) so it outlives the gauntlet session. At each gate it snapshots the checkpoint
(the run keeps overwriting it), runs the three instruments on the SNAPSHOT, posts a Discord report,
and -- if regret has risen at TWO consecutive reads -- posts it as a --questions alert (owner ping)
instead of silently training on. Exits when all gates are done or the run's progress file shows
an exit line (the run died; the watchdog owns that alert).

    nohup .venv/Scripts/python.exe tools/real_run_gates.py > data/bench/real_run_gates.out 2>&1 &
"""
from __future__ import annotations
import os, re, shutil, subprocess, sys, time

ROOT = r"C:\Users\benpe\ClashBot\icebow"
PY = os.path.join(ROOT, r".venv\Scripts\python.exe")
LOG = os.path.join(ROOT, r"data\bench\real_run_20260901.log")
PROG = os.path.join(ROOT, r"data\bench\real_run_20260901.progress")
CKPT = os.path.join(ROOT, r"data\policy_real_20260901.pt")
GATES = [5000, 10000, 20000]
STATE = os.path.join(ROOT, r"data\bench\real_run_gates.progress")
EP_RE = re.compile(r"^\[train-sim-ppo\] (\d+) episodes:", re.M)
REGRET_RE = re.compile(r"regret mean ([0-9.]+)")


def log(msg: str) -> None:
    print("[%s] %s" % (time.strftime("%H:%M"), msg), flush=True)


def episodes() -> int:
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - 400_000))
            m = EP_RE.findall(f.read())
        return int(m[-1]) if m else 0
    except FileNotFoundError:
        return 0


def run_dead() -> bool:
    return os.path.exists(PROG) and "exit=" in open(PROG, encoding="utf-8", errors="replace").read()


def snapshot(k: int) -> str:
    dst = os.path.join(ROOT, r"data\bench\real_m%dk.pt" % (k // 1000))
    for _ in range(6):                      # the run may be mid-write; retry
        try:
            shutil.copyfile(CKPT, dst)
            import torch; torch.load(dst, map_location="cpu", weights_only=False)
            return dst
        except Exception as e:              # noqa: BLE001
            log("snapshot retry: %s" % type(e).__name__); time.sleep(20)
    raise RuntimeError("could not snapshot checkpoint")


def sh(args: list[str], out: str) -> str:
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    r = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with open(out, "a", encoding="utf-8") as f:
        f.write("$ %s\n%s\n%s\n" % (" ".join(args), r.stdout, r.stderr[-3000:]))
    return r.stdout


def grade(k: int, snap: str) -> dict:
    out = os.path.join(ROOT, r"data\bench\real_gate_m%dk.log" % (k // 1000))
    rel = os.path.relpath(snap, ROOT).replace("\\", "/")
    res: dict = {}
    o = sh([PY, "tools/regret_corpus.py", "eval", "--ckpt", rel], out)
    b = sh([PY, "tools/regret_corpus.py", "eval", "--dir", "data/bench/regret_corpus_belief", "--ckpt", rel], out)
    res["regret_oracle"] = float(REGRET_RE.search(o).group(1)) if REGRET_RE.search(o) else None
    res["regret_belief"] = float(REGRET_RE.search(b).group(1)) if REGRET_RE.search(b) else None
    res["waits"] = "; ".join(re.findall(r"waited \d+ \(missed-play \d+%\)", o + b))
    p = sh([PY, "tools/xbow_probe.py", "--matches", "24", "--ckpt", rel], out)
    res["probe"] = "\n".join(l for l in p.splitlines() if "x-bows in" in l or "PLACEMENT" in l)
    c = sh([PY, "tools/continuation_report.py", "--matches", "16", "--ckpt", rel], out)
    res["cont"] = "\n".join(l for l in c.splitlines() if "plays=" in l or "after x_bow" in l)
    return res


def post(text: str, questions: bool) -> None:
    p = os.path.join(ROOT, r"data\bench\real_gate_report.md")
    open(p, "w", encoding="utf-8").write(text)
    args = [PY, "tools/gauntlet_report.py", "--file", p] + (["--questions"] if questions else [])
    subprocess.run(args, cwd=ROOT)


def main() -> None:
    hist: list[tuple[int, float | None]] = []
    done = set()
    if os.path.exists(STATE):
        for line in open(STATE, encoding="utf-8"):
            m = re.match(r"m(\d+) regret_oracle=([0-9.]+|None)", line)
            if m:
                done.add(int(m.group(1)))
                hist.append((int(m.group(1)), None if m.group(2) == "None" else float(m.group(2))))
    for k in GATES:
        if k in done:
            continue
        while episodes() < k:
            if run_dead():
                log("run exited before m=%d; gates stop (watchdog owns the death alert)" % k); return
            time.sleep(600)
        log("gate m=%d reached; snapshot + grade" % k)
        snap = snapshot(k)
        res = grade(k, snap)
        hist.append((k, res["regret_oracle"]))
        with open(STATE, "a", encoding="utf-8") as f:
            f.write("m%d regret_oracle=%s regret_belief=%s\n" % (k, res["regret_oracle"], res["regret_belief"]))
        # sustained regression = regret rose at TWO consecutive reads (needs 3 points)
        vals = [v for _, v in hist if v is not None]
        regress = len(vals) >= 3 and vals[-1] > vals[-2] > vals[-3]
        hrs = max((time.time() - os.path.getctime(LOG)) / 3600.0, 1e-6)
        pace = k / hrs
        text = ("**REAL RUN instrument gate m=%d** (snapshot data/bench/real_m%dk.pt)\n"
                "**Pace (measured since launch)** %.0f matches/hr -> 40k ETA ~%.1f h from launch (%.1f h remaining)\n"
                % (k, k // 1000, pace, 40000 / pace, (40000 - k) / pace)
                + "**Regret** oracle %s | belief %s   (prior gates: %s)\n"
                "**Waits** %s\n**X-bow probe (24 matches)**\n```\n%s\n```\n**Continuations (16 matches)**\n```\n%s\n```\n"
                "%s" % (res["regret_oracle"], res["regret_belief"],
                        ", ".join("m%d=%s" % (a, b) for a, b in hist[:-1]) or "none",
                        res["waits"], res["probe"], res["cont"],
                        "**SUSTAINED REGRESSION: regret rose at two consecutive reads -- decide: continue, or stop and inspect.**"
                        if regress else "No sustained regression rule fired; training continues."))
        post(text, regress)
        log("gate m=%d posted (regress=%s)" % (k, regress))
    log("all gates done")


if __name__ == "__main__":
    sys.exit(main())
