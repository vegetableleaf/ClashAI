r"""Detached alert watchdog: battery drain + trainer death -> Discord. Alert-only, kills nothing.

Exists because in-session watchers (Claude's Monitor / cron jobs) die when the session closes --
measured 2026-08-13: the battery drained 92% -> 81% during a day-long unmonitored gap. This runs
as its OWN detached process (survives Claude, terminals, logouts short of a reboot):

    Start-Process -WindowStyle Hidden icebow\.venv\Scripts\pythonw.exe icebow\tools\alert_watchdog.py

Behaviour (poll every --poll seconds, default 120):
  * battery flips to DISCHARGING -> one Discord alert, then another per 10% lost; recovery post
    when charging resumes. Reads root/wmi BatteryStatus via powershell (DischargeRate/PowerOnline).
  * train-sim-ppo / train-rl process count drops to zero -> one alert per disappearance
    (a deliberate stop also triggers it -- that is fine, better one spurious ping than silence).
  * webhook from data/discord_webhook.txt (the project's secret location); if missing, log-only.
  * everything wrapped so it NEVER crashes; state in data/alert_watchdog.log.
Stop it:  Get-CimInstance Win32_Process | ? { $_.CommandLine -like '*alert_watchdog*' } | % { Stop-Process -Id $_.ProcessId }
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "data" / "alert_watchdog.log"
HOOK = ROOT / "data" / "discord_webhook.txt"


def log(msg: str) -> None:
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%m-%d %H:%M:%S}  {msg}\n")
    except OSError:
        pass


def post(msg: str) -> None:
    log(f"POST {msg}")
    try:
        url = HOOK.read_text(encoding="utf-8").strip()
        req = urllib.request.Request(
            url, json.dumps({"content": msg}).encode("utf-8"),
            {"Content-Type": "application/json", "User-Agent": "clashbot-alert-watchdog"})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as exc:  # noqa: BLE001 -- alerting must never kill the watchdog
        log(f"post failed: {exc}")


def ps(cmd: str) -> str:
    try:
        out = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30, creationflags=0x08000000)  # no window
        return out.stdout or ""
    except Exception as exc:  # noqa: BLE001
        log(f"ps failed: {exc}")
        return ""


def battery() -> dict:
    raw = ps("$b = Get-CimInstance -Namespace root/wmi -ClassName BatteryStatus; "
             "$c = Get-CimInstance Win32_Battery; "
             "@{online=$b.PowerOnline; disch=$b.Discharging; rate=$b.DischargeRate; "
             "pct=$c.EstimatedChargeRemaining} | ConvertTo-Json")
    try:
        d = json.loads(raw)
        return {"online": bool(d.get("online")), "disch": bool(d.get("disch")),
                "rate": int(d.get("rate") or 0), "pct": int(d.get("pct") or -1)}
    except Exception:  # noqa: BLE001
        return {}


def trainers() -> int:
    raw = ps("@(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -like '*train-sim-ppo*' -or "
             "$_.CommandLine -like '*train-rl*' }).Count")
    try:
        return int(raw.strip() or 0)
    except ValueError:
        return -1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll", type=int, default=120)
    ap.add_argument("--once", action="store_true", help="one poll, print state, no loop (test)")
    args = ap.parse_args()

    log(f"watchdog START poll={args.poll}s")
    was_discharging = False
    last_alert_pct = 999
    had_trainers = trainers() > 0
    if args.once:
        print(battery(), "trainers:", trainers())
        return
    while True:
        b = battery()
        if b:
            if b.get("disch") or not b.get("online"):
                pct = b.get("pct", -1)
                if not was_discharging or pct <= last_alert_pct - 10:
                    post(f":rotating_light: **battery draining**: {pct}% "
                         f"(rate {b.get('rate', 0)/1000:.1f} W, AC={'yes' if b.get('online') else 'NO'}). "
                         f"Heaviest loads are the game/GPU, the sim trainer, and the Play Games emulator.")
                    was_discharging, last_alert_pct = True, pct
            elif was_discharging:
                post(f":battery: charging again at {b.get('pct', -1)}%.")
                was_discharging, last_alert_pct = False, 999
        n = trainers()
        if n == 0 and had_trainers:
            post(":rotating_light: **no trainer running** (train-sim-ppo / train-rl gone). "
                 "If unintended, restart: `run.py train-sim-ppo --matches 100000 --envs 32 --init <ckpt>`")
            had_trainers = False
        elif n > 0:
            had_trainers = True
        time.sleep(max(30, args.poll))


if __name__ == "__main__":
    main()
