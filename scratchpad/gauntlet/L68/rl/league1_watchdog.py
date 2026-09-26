"""Overnight watchdog for the league1 RL run (owner 2026-09-25: "if there is no space on GPU, use CPU").

Polls the run's python process; when it exits:
  * the launch log shows a CUDA out-of-memory error -> relaunch ONCE with --resume on CPU (learner + actors);
  * anything else (a stop rule, the STOP file, max_updates, a non-memory crash) -> do nothing, log why.
Detached-launched; writes league1_watchdog.log beside itself. Never kills or touches other processes.
"""
import os
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PY = REPO / "research" / "ext" / "Royale" / ".venv" / "Scripts" / "python.exe"
LOG = HERE / "league1_watchdog.log"
BASE = ["-m", "pipeline.rl_royale", "--config", "pipeline/rl_royale.yaml", "--run", "league1"]
OVERRIDES = ["init=icebow/data/pipeline/gen_v1_s0/gen_s0.pt", "league=true", "noise_off=all", "opp_elixir=counter",
             "action_delay_ticks=26", "extrapolate_ticks=26", "max_updates=5000", "screen_seeds=[0]"]
OOM = ("out of memory", "OutOfMemoryError", "CUBLAS_STATUS_ALLOC_FAILED", "CUDA error: out of memory")


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")


def alive(pid: int) -> bool:
    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
    return str(pid) in out


def run_pid(launch_out: Path) -> int | None:
    for line in launch_out.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("[rl] START league1 pid "):
            return int(line.split("pid ")[1].split()[0])
    return None


def watch(launch_out: Path) -> str:
    pid = None
    while pid is None:
        pid = run_pid(launch_out)
        time.sleep(10)
    log(f"watching pid {pid} ({launch_out.name})")
    while alive(pid):
        time.sleep(60)
    text = launch_out.read_text(encoding="utf-8", errors="replace")
    err = launch_out.with_name(launch_out.name + ".err")
    text += err.read_text(encoding="utf-8", errors="replace") if err.exists() else ""
    return "oom" if any(k in text for k in OOM) else "other"


def main() -> None:
    first = HERE / "league1_launch.out"
    why = watch(first)
    log(f"run exited: {why}; last lines: {first.read_text(encoding='utf-8', errors='replace').splitlines()[-2:]}")
    if why != "oom":
        log("not an out-of-memory exit -> no relaunch")
        return
    out = HERE / "league1_cpu_launch.out"
    args = BASE + ["--resume"] + OVERRIDES + ["learner_device=cpu", "actor_device=cpu"]
    with open(out, "w", encoding="utf-8") as o, open(str(out) + ".err", "w", encoding="utf-8") as e:
        p = subprocess.Popen([str(PY)] + args, cwd=str(REPO), stdout=o, stderr=e,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    log(f"GPU out of memory -> resumed on CPU, launcher pid {p.pid}, log {out.name}")
    why = watch(out)
    log(f"CPU run exited: {why}")


if __name__ == "__main__":
    main()
