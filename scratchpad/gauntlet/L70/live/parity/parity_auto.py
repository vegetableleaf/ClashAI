"""Owner 10-20: autopilot for the classic-challenge parity battles. Taps ONLY the challenge's Battle button and the
results OK button (ladder_nav's template classifier finds both); never taps an unknown screen. One live_play run per
battle (parity_battles.sh options: CLX, generic options, frames + phase-3 captures).

Stops by itself after the challenge's 3rd loss (the re-entry screen can spend gems: the owner re-enters), after N
battles, on the STOP file, or when a screen stays unknown for 90 s (Discord alert).
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L70/live/parity/parity_auto.py DECKTAG [N] [LOSSES_SO_FAR]
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
LR = REPO / "scratchpad/gauntlet/L68/live_reader"
sys.path.insert(0, str(LR))
import ladder_nav as ln  # noqa: E402

ADB = [r"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe", "-s", "127.0.0.1:16384"]
L = REPO / "scratchpad/gauntlet/L70/live"
STOP = L / "STOP"
OK_XY = tuple(int(v) for v in __import__('os').environ['OK_XY'].split(',')) if __import__('os').environ.get('OK_XY') else None


def say(msg):
    print(time.strftime("%H:%M:%S ") + msg, flush=True)


def alert(msg):
    say(msg)
    m = L / "parity" / "_alert.txt"
    m.write_text("[parity battles] " + msg, encoding="utf-8")
    subprocess.run([sys.executable, str(REPO / "scratchpad/gauntlet/L69/discord/post.py"), str(m)], capture_output=True,
                   timeout=60)


def tap(pt):
    subprocess.run(ADB + ["shell", "input", "tap", str(int(pt[0])), str(int(pt[1]))], capture_output=True, timeout=20)


def screen(clf):
    img = ln.grab(ADB)
    return clf.classify(img) if img is not None else {"screen": "nograb"}


def wait_for(clf, wanted, limit_s=90):
    """Poll until the screen is one of ``wanted`` (-> its dict) or ``limit_s`` passes on other screens (-> None)."""
    t0 = time.time()
    while time.time() - t0 < limit_s:
        s = screen(clf)
        if s["screen"] in wanted:
            return s
        time.sleep(1.5)
    return None


def live_pids():
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                        "Where-Object {$_.CommandLine -like '*live_play.py*'} | ForEach-Object { $_.ProcessId }"],
                       capture_output=True, text=True)
    return [int(x) for x in r.stdout.split() if x.isdigit()]


def newest_log():
    logs = sorted(LR.glob("live_play_*.jsonl"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def result_of(log):
    for line in reversed(log.read_text(encoding="utf-8").splitlines()):
        if '"event": "end"' in line:
            return (json.loads(line).get("towers") or {}).get("won")
    return None


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "deck"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    losses = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    clf = ln.Classifier()
    if live_pids():                                    # resume: a battle is running (an earlier autopilot's bot)
        lg = newest_log()
        say(f"{tag}: resuming -- waiting for the running battle ({lg.name if lg else None}) to end")
        t0 = time.time()
        while time.time() - t0 < 1500 and lg is not None and '"event": "end"' not in lg.read_text(encoding="utf-8", errors="replace"):
            time.sleep(3)
        won = result_of(lg) if lg is not None else None
        losses += won is False
        time.sleep(5)
        for pid in live_pids():
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        say(f"{tag}: resumed battle done: won={won}  challenge losses={losses}/3")
        if losses >= 3:
            alert(f"{tag}: 3 challenge losses -- please re-enter the challenge (I stopped)"); return
        t0 = time.time()
        while time.time() - t0 < 120 and screen(clf)["screen"] != "main":
            if OK_XY and time.time() - t0 > 4:
                tap(OK_XY)
            time.sleep(3)
    for i in range(1, n + 1):
        if STOP.exists():
            say("STOP file: done"); return
        s = wait_for(clf, {"main"})
        if s is None:
            alert(f"{tag}: challenge home (Battle button) not found for 90 s before battle {i}; stopped, nothing tapped")
            return
        before = newest_log()
        bot = subprocess.Popen([r"C:\Program Files\Git\bin\bash.exe",str(L / "parity/parity_battles.sh"), "1", tag], cwd=str(REPO),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out = L / "parity" / f"parity_{tag}.out"
        n0 = out.read_text(encoding="utf-8", errors="replace").count("capture-p3: ready") if out.exists() else 0
        t0 = time.time()
        while time.time() - t0 < 180:                  # the bot must be listening before the battle starts
            if out.exists() and out.read_text(encoding="utf-8", errors="replace").count("capture-p3: ready") > n0:
                break
            time.sleep(2)
        else:
            alert(f"{tag}: the bot did not get ready within 180 s (battle {i}); stopped"); bot.kill(); return
        time.sleep(3)
        s = screen(clf)
        if s["screen"] != "main":
            alert(f"{tag}: home screen changed before battle {i} ({s['screen']}); stopped"); bot.kill(); return
        say(f"{tag}: battle {i}/{n}: tapping Battle")
        tap(s["battle"])
        t0 = time.time()                               # live_play lingers after the match (video render): watch its log
        log = None
        while time.time() - t0 < 1500:
            lg = newest_log()
            if lg is not None and lg != before and '"event": "end"' in lg.read_text(encoding="utf-8", errors="replace"):
                log = lg
                break
            time.sleep(3)
        time.sleep(5)
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(bot.pid)], capture_output=True)
        for pid in live_pids():                        # the python children taskkill /T may miss (Git Bash spawns)
            subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        won = result_of(log) if log is not None and log != before else None
        losses += won is False
        say(f"{tag}: battle {i} done: won={won}  challenge losses={losses}/3  log={log.name if log else None}")
        # results -> OK (the challenge results screen: results_ok / bottom OK), back to the challenge home
        t0, asked = time.time(), False
        while time.time() - t0 < 600:
            s = screen(clf)
            if s["screen"] == "main":
                break
            ok = s.get("ok") if s["screen"] in ("results", "trophy_road") else None
            if ok is None and OK_XY and time.time() - t0 > 4:   # the challenge results: ONE OK button (owner 10-20)
                ok = OK_XY
            if ok:
                tap(ok)
            elif not asked and time.time() - t0 > 8:
                png = L / "parity" / f"results_{tag}_{i}.png"
                subprocess.run(ADB + ["exec-out", "screencap", "-p"], stdout=open(png, "wb"), timeout=30)
                alert(f"{tag}: battle {i} over -- please tap OK once on the results screen (screenshot saved for the lead)")
                asked = True
            time.sleep(2)
        else:
            alert(f"{tag}: stuck after battle {i} (no OK / home for 120 s); stopped, nothing else tapped"); return
        if losses >= 3:
            alert(f"{tag}: 3 challenge losses after {i} battles -- please re-enter the challenge (I stopped)"); return
    say(f"{tag}: {n} battles done")


if __name__ == "__main__":
    main()
