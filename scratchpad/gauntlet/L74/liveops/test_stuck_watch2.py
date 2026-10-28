"""Offline checks of stuck_watch2.py: synthetic cases + a replay over the REAL overnight.out (78k lines).
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/liveops/test_stuck_watch2.py
Nothing here touches adb, the emulator or live processes (screenshots / process scan are stubbed or off)."""
import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stuck_watch2 as w  # noqa: E402

OV = w.L / "overnight.out"
SUP = w.L / "supervisor.log"
OLD = re.compile(r"\] unknown:|tap_through:")


def old_rule_windows(lines):
    """stuck_watch.sh rule: >= 6 of the last 12 lines match `] unknown:|tap_through:` (every 12-line window)."""
    hit = [bool(OLD.search(x)) for x in lines]
    cs = [0]
    for h in hit:
        cs.append(cs[-1] + h)
    return sum(cs[i + 12] - cs[i] >= 6 for i in range(len(lines) - 11))


def synthetic():
    d = w.Detector(0.0)
    stop = "[nav] run stopped before match 7: screenshots failing for 60 s"
    # benign handoff transition lines never alert, however many
    benign = ["[ladder] unknown: ('wait', 'unknown')", "[ladder] unknown: ('handoff', 'menus left after Battle / Play Again: battle loading')",
              "[ladder] HANDOFF: menus left after Battle / Play Again: battle loading", "[ladder] tap_through: input tap 450 450",
              "[ladder] loading: ('wait', 'loading')", "[live] stop file scratchpad\\gauntlet\\L70\\live\\STOP found -- ending the run before match 9"]
    assert all(d.feed(x, 1.0) == [] for x in benign * 50)
    a = d.feed(stop, 2.0)
    assert len(a) == 1 and a[0].startswith("STOP[adb_down]"), a
    # the same class again within 20 min: counted; reported again at the 3rd, 6th, 9th
    got = [bool(d.feed(stop, 100.0 * i)) for i in range(3, 12)]          # stops 2..10 of this burst
    assert got == [False, True, False, False, True, False, False, True, False], got
    # a different class is its own alert
    assert d.feed("[nav] run stopped before match 2: 40 tap-throughs and still no known screen", 5000.0)[0].startswith("STOP[unknown_screen]")
    assert d.feed("[nav] run stopped before match 1: ANOTHER_DEVICE: the account was opened on another device (Connection lost)", 5001.0)[0].startswith("STOP[another_device]")
    assert d.feed("[nav] run stopped before match 1: something new", 5002.0)[0].startswith("STOP[other]")
    # a burst ends after 20 quiet minutes: the next stop of that class alerts again
    assert d.feed(stop, 12000.0)[0].startswith("STOP[adb_down]")
    # supervisor give-up
    assert d.feed("ClashAI live run stopped 05:20 (rc 1): ... Restart limit 10 reached -- NOT restarting. State {}", 9.0, "supervisor")[0].startswith("GAVE_UP")
    assert d.feed("[sup] exit 1 Wed Oct 28 12:15:17 EDT 2026: [nav] run stopped before match 7: screenshots failing for 60 s", 9.0, "supervisor") == []
    # no progress: 12 min with a live process; a played line / result line resets; a stop file or a dead process never fires it
    d = w.Detector(0.0)
    assert d.tick(700.0, True, False) == [] and d.tick(721.0, True, False)[0].startswith("NO_PROGRESS") and d.tick(900.0, True, False) == []
    d.feed('{"played": 50, "confirmed": 49, "fails": 1, "log": "x"}', 1000.0)
    assert d.tick(1700.0, True, False) == [] and d.tick(1721.0, True, False)[0].startswith("NO_PROGRESS")
    d = w.Detector(0.0)
    assert d.tick(5000.0, True, True) == []                                # STOP file present: silent, clock restarted
    assert d.tick(5100.0, True, False) == []
    d = w.Detector(0.0)
    assert d.tick(100.0, False, False) == [] and d.tick(699.0, False, False) == [] and d.tick(701.0, False, False)[0].startswith("PROC_GONE")
    assert d.tick(2000.0, False, False) == []                              # once per episode
    d.feed('{"played": 1}', 2090.0)
    assert d.tick(2100.0, True, False) == [] and d.tick(2200.0, False, False) == []   # recovered, a new episode starts
    # a stop alert restarts the no-progress window (the stop is the news)
    d = w.Detector(0.0)
    d.feed(stop, 600.0)
    assert d.tick(1200.0, True, False) == [] and d.tick(1321.0, True, False)[0].startswith("NO_PROGRESS")
    print("synthetic checks passed")


def loop_rearms():
    """run(): reads appended lines, alerts, keeps running after an alert (re-armed), --once exits after the first."""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "overnight.out").write_text("old line\n[nav] run stopped before match 1: transition over 300 s\n")   # history: ignored
        (d / "supervisor.log").write_text("")
        clock = {"t": 1000.0}
        script = [
            ["[ladder] unknown: ('wait', 'unknown')", "[ladder] HANDOFF: x"],
            ["[nav] run stopped before match 3: screenshots failing for 60 s"],
            ["[ladder] result: LOSS (session)", "[nav] run stopped before match 1: 40 tap-throughs and still no known screen"],
            ["[nav] run stopped before match 1: partial line without newline"],
        ]
        state = {"i": 0}

        def sleep(_):
            clock["t"] += 30
            i = state["i"]
            state["i"] += 1
            if i < len(script):
                txt = "\n".join(script[i]) + ("" if i == 3 else "\n")
                with open(d / "overnight.out", "a") as f:
                    f.write(txt)
            if i == 4:                                                     # the partial line gets its newline
                with open(d / "overnight.out", "a") as f:
                    f.write("\n")
            if i == 5:
                with open(d / "supervisor.log", "a") as f:
                    f.write("ClashAI live run stopped 05:20 (rc 1): x. Restart limit 10 reached -- NOT restarting. State {}\n")
        out = []
        a = argparse.Namespace(once=False, no_screenshot=True, poll=0)
        w.run(a, live_dir=d, max_iter=8, clock=lambda: clock["t"], sleep=sleep, running=lambda: True,
              out=lambda s, flush=False: out.append(s))
        kinds = [re.search(r"(STOP\[\w+\]|GAVE_UP)", x).group(1) for x in out]
        assert kinds == ["STOP[adb_down]", "STOP[unknown_screen]", "STOP[other]", "GAVE_UP"], (kinds, out)
        # --once exits at the first alert
        (d / "overnight.out").write_text("")
        clock["t"], state["i"] = 1000.0, 0
        out.clear()
        script[:] = [["[nav] run stopped before match 3: screenshots failing for 60 s"], ["[nav] run stopped before match 1: transition over 300 s"]]
        a = argparse.Namespace(once=True, no_screenshot=True, poll=0)
        w.run(a, live_dir=d, max_iter=8, clock=lambda: clock["t"], sleep=sleep, running=lambda: True,
              out=lambda s, flush=False: out.append(s))
        assert len(out) == 1 and state["i"] == 1, (out, state)
    print("run loop checks passed (re-arms after each alert; --once exits)")


def replay_real():
    lines = OV.read_text(encoding="utf-8", errors="replace").splitlines()
    n_stop = sum(bool(w.STOP_RE.match(x)) for x in lines)
    # replay: every line +0.1 s; a stop line +330 s (the supervisor's restart cycle) -- bursts stay one burst
    d, now, alerts, by_line = w.Detector(0.0), 0.0, [], []
    for i, ln in enumerate(lines):
        now += 330.0 if w.STOP_RE.match(ln) else 0.1
        a = d.feed(ln, now)
        if a:
            assert w.STOP_RE.match(ln), (i + 1, ln, a)                    # only STOP lines ever alert
            alerts += a
            by_line.append(i + 1)
    assert d.stops == n_stop and len(alerts) <= n_stop and len(alerts) >= 5
    by_class = {}
    for a in alerts:
        by_class[re.match(r"STOP\[(\w+)\]", a).group(1)] = by_class.get(re.match(r"STOP\[(\w+)\]", a).group(1), 0) + 1
    old = old_rule_windows(lines)
    print(f"replay of overnight.out ({len(lines)} lines): STOP lines {n_stop}; new watcher alerts {len(alerts)} {by_class}; "
          f"0 alerts on any other line; old stuck_watch.sh rule fires in {old} 12-line windows")
    # the 2026-10-28 12:15 incident (screenshots failing) = exactly one alert, from its own slice
    k = max(i for i, x in enumerate(lines) if "[nav] run stopped before match 7: screenshots failing for 60 s" in x)
    d2 = w.Detector(0.0)
    sl = [a for x in lines[k - 40:k + 1] for a in d2.feed(x, 1.0)]
    assert len(sl) == 1 and sl[0].startswith("STOP[adb_down]"), sl
    # a normal stretch (10-28 11:45 .. 12:14: 5 matches, 6 handoffs) is silent
    sl = [a for x in lines[k - 120:k - 3] for a in w.Detector(0.0).feed(x, 1.0)]
    assert sl == [], sl
    return old


if __name__ == "__main__":
    synthetic()
    loop_rearms()
    old = replay_real()
    print("stuck_watch2 self-checks passed; old rule windows =", old)
