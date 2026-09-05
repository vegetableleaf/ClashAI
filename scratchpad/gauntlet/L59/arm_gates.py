"""L59 arm gates: session-independent m5k/m10k/m20k reads for the radius-reward arms (G, G+E, E).

    cd icebow; nohup .venv/Scripts/python.exe ../scratchpad/gauntlet/L59/arm_gates.py --run armG_20260905 \
        > data/bench/armG_gates.out 2>&1 &

At each gate: snapshot data/policy_<run>.pt -> data/bench/<kind>_m<k>k.pt (the run keeps overwriting it),
then on the SNAPSHOT: place_probe (L55, greedy card+cell, seeds 0/1/2 -> distinct cells per card, tesla
cell shares) and tools/gate_prior_probe.py (P(play) by elixir bucket, config/gate_prior_p6.json), plus the
run's own geo_* ledger lines from the log tail. Writes scratchpad/gauntlet/L59/reads_<run>_m<k>k.txt and
posts a short Discord report. Counter semantics: --resume restarts the trainer's match counter at 0, so
"m5k" here = 5k matches AFTER c2r_best (absolute ~m41k).
"""
from __future__ import annotations
import os, re, sys, json, time, shutil, subprocess

ROOT = r"C:\Users\benpe\ClashBot\icebow"
PY = os.path.join(ROOT, r".venv\Scripts\python.exe")
L59 = r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L59"
RUN = sys.argv[sys.argv.index("--run") + 1]
KIND, DATE = RUN.split("_", 1)
LOG = os.path.join(ROOT, r"data\bench\%s_run_%s.log" % (KIND, DATE))
PROG = os.path.join(ROOT, r"data\bench\%s_run_%s.progress" % (KIND, DATE))
CKPT = os.path.join(ROOT, r"data\policy_%s.pt" % RUN)
GATES = [5000, 10000, 20000]
STATE = os.path.join(L59, "gates_%s.progress" % RUN)
EP_RE = re.compile(r"^\[train-sim-ppo\] (\d+) episodes:", re.M)


def log(msg):
    print("[%s] %s" % (time.strftime("%H:%M"), msg), flush=True)


def tail(path, n=400_000):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2); size = f.tell(); f.seek(max(0, size - n)); return f.read()
    except FileNotFoundError:
        return ""


def episodes():
    m = EP_RE.findall(tail(LOG)); return int(m[-1]) if m else 0


def run_dead():
    return os.path.exists(PROG) and "exit=" in open(PROG, encoding="utf-8", errors="replace").read()


def snapshot(k):
    dst = os.path.join(ROOT, r"data\bench\%s_m%dk.pt" % (KIND, k // 1000))
    for _ in range(6):
        try:
            shutil.copyfile(CKPT, dst)
            import torch; torch.load(dst, map_location="cpu", weights_only=False); return dst
        except Exception as e:  # noqa: BLE001
            log("snapshot retry: %s" % type(e).__name__); time.sleep(20)
    raise RuntimeError("could not snapshot")


def sh(args, cwd=ROOT):
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONIOENCODING="utf-8")
    r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout + ("\n[stderr tail]\n" + r.stderr[-1500:] if r.returncode else "")


def grade(k, snap):
    rel = snap.replace("\\", "/")
    out = [f"# {RUN} m{k//1000}k read  {time.strftime('%F %T')}  snapshot {rel}", ""]
    summ = []
    for seed in (0, 1, 2):
        o = sh([PY, os.path.join(L59, "..", "L55", "place_probe.py"), rel, str(seed)])
        out += [f"## place_probe seed {seed}", o]
        for line in o.splitlines():
            m = re.match(r"(\S+)\s+n=\s*(\d+) distinct=\s*(\d+) top=(.*)", line)
            if m and m.group(1) in ("tesla", "x_bow", "skeletons", "ice_wizard", "knight"):
                summ.append(f"s{seed} {m.group(1)} n={m.group(2)} distinct={m.group(3)} top={m.group(4)[:60]}")
    gl = []
    for seed in (0, 1):
        o = sh([PY, os.path.join(L59, "geo_ledger_probe.py"), rel, str(seed), "greedy", "data/bench/%s_run.yaml" % KIND])
        out += [f"## geo_ledger_probe seed {seed} (arm yaml, geometry ON)", o]
        gl += [l[:200] for l in o.splitlines() if l.startswith("geo ledger") or "tesla " in l or "x_bow " in l or "skeletons " in l][:4]
    g = sh([PY, "tools/gate_prior_probe.py", rel, "--prior", "config/gate_prior_p6.json"])
    out += ["## gate_prior_probe", g]
    gsum = [l for l in g.splitlines() if "P(play)" in l or "mean cost" in l][:3]
    # the run's own reward ledger (geo_* keys) from the log tail
    t = tail(LOG, 200_000)
    geo = [l for l in t.splitlines() if "geo_" in l][-6:]
    out += ["## log tail geo_* ledger lines", *geo]
    txt = "\n".join(out)
    open(os.path.join(L59, "reads_%s_m%dk.txt" % (RUN, k // 1000)), "w", encoding="utf-8").write(txt)
    rep = [f"**ARM GATE {RUN} m{k//1000}k** (counter after c2r_best; snapshot `{os.path.basename(snap)}`)",
           "**place_probe (greedy card+cell, 6 envs x 400 steps, 3 seeds):**", *summ[:15],
           "**geo_ledger_probe (seeds 0/1):**", *gl,
           "**gate_prior_probe:**", *gsum,
           "**ledger (log tail):**", *[l[:160] for l in geo[-3:]],
           f"full read: scratchpad/gauntlet/L59/reads_{RUN}_m{k//1000}k.txt"]
    p = os.path.join(L59, "_gate_report_%s_m%dk.md" % (RUN, k // 1000))
    open(p, "w", encoding="utf-8").write("\n".join(rep))
    subprocess.run([PY, "tools/gauntlet_report.py", "--file", p], cwd=ROOT)


def main():
    done = set()
    if os.path.exists(STATE):
        done = {int(m) for m in re.findall(r"^m(\d+) done", open(STATE, encoding="utf-8").read(), re.M)}
    for k in GATES:
        if k in done:
            continue
        while episodes() < k:
            if run_dead():
                log("run exited before m=%d; gates stop" % k); return
            time.sleep(600)
        log("gate m=%d reached" % k)
        snap = snapshot(k); grade(k, snap)
        open(STATE, "a", encoding="utf-8").write("m%d done %s\n" % (k, time.strftime("%F %T")))
    log("all gates done")


if __name__ == "__main__":
    main()
