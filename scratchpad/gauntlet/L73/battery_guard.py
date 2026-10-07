"""Owner 2026-10-06 night: "make sure the battery doesn't die (pause gpu heavy tasks for a bit if battery drops below 10%)".

Every 60 s: on battery below 10% -> suspend the GPU-heavy training/sim processes (psutil.suspend; a step launched
while paused is suspended on the next scan); resume when plugged in or back at 25%. Below 5% on battery the live run
also gets its STOP file (it stops between matches, so no match is abandoned mid-way). Discord on every transition.
Run: icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L73/battery_guard.py   (log: battery_guard.log)
"""
import re
import subprocess
import time
from pathlib import Path

import psutil

REPO = Path(__file__).resolve().parents[3]
HEAVY = re.compile(r'pipeline\.rl_royale|_train_every_epoch|run_screen|pipeline\.search_s0|train_branch|model_counterfactual|pipeline\.dataset_gen')
STOP = REPO / 'scratchpad/gauntlet/L70/live/STOP'
LOG = Path(__file__).with_suffix('.log')
PAUSE_BELOW, RESUME_AT, LIVE_STOP_BELOW = 10, 25, 5


def log(msg):
    line = f"{time.strftime('%F %T')} {msg}"
    with LOG.open('a') as f:
        f.write(line + '\n')
    msg_file = REPO / 'scratchpad/gauntlet/L73/discord/_battery.txt'
    msg_file.write_text('ClashAI battery guard: ' + msg)
    subprocess.run([str(REPO / 'icebow/.venv/Scripts/python.exe'), str(REPO / 'scratchpad/gauntlet/L69/discord/post.py'),
                    str(msg_file)], cwd=REPO, capture_output=True)


def heavy():
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            if (p.info['name'] or '').lower().startswith('python') and HEAVY.search(' '.join(p.info['cmdline'] or [])):
                yield p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def main():
    paused, held = False, {}          # pid -> Process we suspended (suspend once, resume once: Windows counts them)
    while True:
        b = psutil.sensors_battery()
        low = b is not None and not b.power_plugged and b.percent < PAUSE_BELOW
        if low and not paused:
            log(f'battery {b.percent}% on battery -> pausing GPU-heavy jobs')
            paused = True
        if paused:
            for p in heavy():
                if p.pid not in held:
                    try:
                        p.suspend(); held[p.pid] = p
                        with LOG.open('a') as f:
                            f.write(f"{time.strftime('%F %T')} suspended {p.pid}\n")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            if b is not None and not b.power_plugged and b.percent < LIVE_STOP_BELOW and not STOP.exists():
                STOP.touch(); log(f'battery {b.percent}% -> live STOP file set (stops between matches)')
            if b is not None and (b.power_plugged or b.percent >= RESUME_AT):
                for p in held.values():
                    try:
                        p.resume()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                log(f'battery {b.percent}% plugged={b.power_plugged} -> resumed {len(held)} GPU-heavy process(es)')
                paused, held = False, {}
        time.sleep(60)


if __name__ == '__main__':
    log('started (pause below 10% on battery, resume at 25% or plugged in)')
    main()
