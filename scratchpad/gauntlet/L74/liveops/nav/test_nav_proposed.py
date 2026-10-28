"""Offline checks of the PROPOSED navigator changes (ladder_nav_proposed.py): the Claim All screen and the no-screenshot diagnosis.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/nav/test_nav_proposed.py
Builds a temp tree (proposed ladder_nav.py + the live templates + claim_all.png) and never touches the live files, adb, MuMu or any
process: adb calls and the clock are faked. Recorded screens come from L68/live_reader/ladder_unknown + ladder_stop_*.png (read-only)."""
import json
import random
import shutil
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

import cv2
import numpy as np

H = Path(__file__).resolve().parent
G = H.parents[2]                                      # scratchpad/gauntlet
ROOT = G.parents[1]
LR = G / "L68" / "live_reader"
LIVE_T = G / "L70" / "ladder_nav" / "templates"
RAW = G / "L70" / "ladder_nav" / "raw"


def build_tree(tmp: Path) -> Path:
    """tmp/gauntlet/L68/live_reader/{ladder_nav.py (proposed), test_ladder_nav.py (the live self-test)} + merged templates."""
    lr = tmp / "gauntlet" / "L68" / "live_reader"
    tdir = tmp / "gauntlet" / "L70" / "ladder_nav" / "templates"
    lr.mkdir(parents=True)
    shutil.copy(H / "ladder_nav_proposed.py", lr / "ladder_nav.py")
    shutil.copy(LR / "test_ladder_nav.py", lr / "test_ladder_nav.py")
    shutil.copytree(LIVE_T, tdir)
    man = json.loads((tdir / "manifest.json").read_text())
    man["templates"].update(json.loads((H / "manifest_fragment.json").read_text()))
    (tdir / "manifest.json").write_text(json.dumps(man, indent=1))
    shutil.copy(H / "templates" / "claim_all.png", tdir / "claim_all.png")
    return lr


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


def fake_adb(calls, devices="List of devices attached\n127.0.0.1:16384\toffline\n"):
    def run(cmd, capture_output=False, text=False, timeout=None, **k):
        calls.append(list(cmd))
        if "devices" in cmd:
            out = devices
        elif "connect" in cmd:
            out = "connected to 127.0.0.1:16384"
        else:
            out = "" if text else b""
        err = "" if text else b"error: device offline"
        return subprocess.CompletedProcess(cmd, 1 if "screencap" in cmd else 0, stdout=out, stderr=err)
    return run


def run_nav(nav, frames, seq, tmp, dry_run=False):
    clock, calls = Clock(), []
    nav.subprocess = types.SimpleNamespace(run=fake_adb(calls), TimeoutExpired=subprocess.TimeoutExpired,
                                           CompletedProcess=subprocess.CompletedProcess)
    nav.time = types.SimpleNamespace(time=clock.time, sleep=clock.sleep, strftime=time.strftime, perf_counter=time.perf_counter)
    it = iter(seq)
    nav.grab = lambda adb: frames[next(it)]
    r = nav.LadderNavRunner(["adb", "-s", "127.0.0.1:16384"], dry_run=dry_run, log_dir=tmp, state_path=tmp / "state.json",
                            trophy_log=False, alert=lambda *a: False)
    ok, why = r.run()
    log = sorted(tmp.glob("ladder_nav_*.jsonl"))[-1]
    ev = [json.loads(x) for x in log.read_text().splitlines()]
    log.unlink()
    return ok, why, calls, ev


def main():
    tmp = Path(tempfile.mkdtemp(prefix="nav_proposed_"))
    try:
        lr = build_tree(tmp)
        # 0. the live self-test (every original assertion) against the proposed module + merged templates
        r = subprocess.run([sys.executable, str(lr / "test_ladder_nav.py")], capture_output=True, text=True,
                           env={**__import__("os").environ, "PYTHONPATH": str(LR)})
        assert r.returncode == 0 and "nograb checks passed" in r.stdout and "reward reveal checks passed" in r.stdout, (r.stdout, r.stderr[-800:])
        print("0. the live test_ladder_nav.py passes unchanged on the proposed module:", r.stdout.strip().replace("\n", " | "))

        sys.path.insert(0, str(lr))
        import ladder_nav as nav
        assert Path(nav.__file__).resolve().parent == lr.resolve()
        clf = nav.Classifier()
        assert "claim_all" in clf.t
        src = cv2.imread(str(H / "source_support_claim.png"))

        # 1. classifier on the recorded Claim All screens and on screens that must NOT be one
        c = clf.classify(src)
        assert c["screen"] == "claim_all" and c["scores"]["claim_all"] >= 0.99, c["scores"]
        cmd = nav.command_for("claim_all", c["claim"])
        assert cmd == f"input tap {round(c['claim'][0])} {round(c['claim'][1])}" and 430 <= c["claim"][0] <= 470, (cmd, c["claim"])
        rows = json.loads((H / "results" / "claim_all_corpus.json").read_text())
        hits = [x for x in rows if x["claim_all"] >= 0.85]
        sample_hits = [x for x in hits if "stuck_0258" in x["file"]] + [x for x in hits if "20261028_0255" in x["file"]][::5] + hits[::25]
        negs = [x for x in rows if x["claim_all"] < 0.85]
        sample_negs = random.Random(0).sample(negs, 50)
        bad = []
        for x in sample_hits:
            s = clf.classify(cv2.imread(str(ROOT / x["file"])))["screen"]
            if s != "claim_all":
                bad.append((x["file"], s))
        for x in sample_negs:
            s = clf.classify(cv2.imread(str(ROOT / x["file"])))["screen"]
            if s == "claim_all":
                bad.append((x["file"], s))
        for p in sorted(RAW.glob("*.png")):                                     # every raw navigator capture is not a Claim All
            s = clf.classify(cv2.imread(str(p)))["screen"]
            if s == "claim_all":
                bad.append((p.name, s))
        assert not bad, bad[:5]
        stalls = sorted({Path(x["file"]).name[:15] for x in hits})
        print(f"1. classifier: source frame -> claim_all (score {c['scores']['claim_all']}, tap {cmd!r}); corpus 2,897 frames: "
              f"{len(hits)} hits (>=0.85) in {len(stalls)} stall runs {stalls}, highest non-hit "
              f"{max(x['claim_all'] for x in negs)}; classified {len(sample_hits)} hits + {len(sample_negs)} sampled non-hits "
              f"+ {len(list(RAW.glob('*.png')))} raw captures through the FULL classifier: 0 wrong")

        # 2. planner
        scr = {"screen": "claim_all", "claim": c["claim"], "scores": {}}
        n = nav.LadderNav(0.0, {})
        assert n.plan(scr, 1)[:2] == ("act", "claim_all")
        for i in range(n.CLAIM_MAX):
            n.acted("claim_all", 2 + i)
        p = n.plan(scr, 20)
        assert p[0] == "stop" and p[1].startswith("claim_all tapped"), p
        n = nav.LadderNav(0.0, {})                                              # a Claim All ends an unknown episode; unknown after it waits again
        unk = {"screen": "unknown", "scores": {}}
        assert n.plan(unk, 1)[0] == "wait" and n.plan(scr, 2)[1] == "claim_all" and n.plan(unk, 3)[0] == "wait"
        for bad_pt in ((450, 450), (60, 1500), (450, 1530)):                    # allowlist: only the button area
            try:
                nav.command_for("claim_all", bad_pt)
                raise AssertionError(f"claim_all {bad_pt} allowed")
            except nav.NavViolation:
                pass
        print("2. planner: act claim_all, stop after CLAIM_MAX taps, allowlist refuses off-button points")

        # 3. runner (fake adb, fake clock): the 10-28 stall replayed. Before the change the same frames were tapped at (450, 450) x40.
        main_img = cv2.imread(str(RAW / "main4.png"))
        frames = {"claim": src, "main": main_img, "unk": np.zeros((1600, 900, 3), np.uint8), "none": None}
        ok, why, calls, ev = run_nav(nav, frames, ["claim"] * 4 + ["main"] * 8 + ["unk"] * 12, tmp)
        taps = [x[-1] for x in calls if x[-2:-1] == ["shell"]]
        assert ok and why.startswith("menus left"), (ok, why)
        assert taps[:2] == [cmd, cmd] and taps[-1] == "input tap 460 1219", taps
        assert [e["target"] for e in ev if e["event"] == "input"] == ["claim_all", "claim_all", "battle"]
        print("3. runner: Claim All screen -> 2 taps on the button, then main -> Battle -> handoff:", taps)
        ok, why, calls, ev = run_nav(nav, frames, ["claim"] * 200, tmp)
        taps = [x[-1] for x in calls if x[-2:-1] == ["shell"]]
        assert (not ok) and why.startswith("claim_all tapped 6 times") and taps == [cmd] * 6, (why, taps)
        print("   a tap that never lands: stops after 6 taps with:", why)

        # 4. no-screenshot diagnosis + `adb connect`
        ok, why, calls, ev = run_nav(nav, frames, ["none"] * 6 + ["claim"] * 2 + ["main"] * 8 + ["unk"] * 12, tmp)
        diag = [e for e in ev if e["event"] == "nograb_diag"]
        assert ok and len(diag) == 1 and diag[0]["n"] == 4 and "connected to" in diag[0]["connect"], diag
        assert "offline" in diag[0]["devices"] and diag[0]["screencap"]["rc"] == 1 and "offline" in diag[0]["screencap"]["stderr"]
        assert ["adb", "connect", "127.0.0.1:16384"] in calls
        first_tap = next(i for i, x in enumerate(calls) if x[-2:-1] == ["shell"])
        assert calls.index(["adb", "connect", "127.0.0.1:16384"]) < first_tap          # no input before the repair attempt
        print("4. nograb x6 then recovery: 1 nograb_diag event (n=4: devices / connect / screencap rc+stderr), connect called before any input")
        ok, why, calls, ev = run_nav(nav, frames, ["none"] * 400, tmp)
        diag = [e for e in ev if e["event"] == "nograb_diag"]
        assert (not ok) and why == "screenshots failing for 60 s" and 5 <= len(diag) <= 7, (why, len(diag))
        assert not [x for x in calls if x[-2:-1] == ["shell"]]                           # never a blind tap
        print(f"   60 s of failed grabs: {len(diag)} diagnoses (one per 10 s), no tap, then the unchanged stop: {why!r}")
        print("nav proposed self-checks passed")
    finally:
        sys.path = [p for p in sys.path if not p.startswith(str(tmp))]
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
