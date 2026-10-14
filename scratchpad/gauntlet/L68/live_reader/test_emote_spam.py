"""--emote-spam (owner 2026-10-10): the scheduler rules and the live_play wiring (fake adb, no device)."""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import emote_spam as es  # noqa: E402
import live_play as lp  # noqa: E402
from test_fast_input import Pilot, play, rframe  # noqa: E402

EMOTE = "input tap 88 1365; sleep 0.15; input tap 710 1195"
CARD = "input tap 279 1424; sleep 0.05; input tap 450 791"


@pytest.fixture(autouse=True)
def isolated_emote_clock(monkeypatch, request):
    monkeypatch.setattr(es, "CLOCK", es.EmoteClock())
    if "reactive" not in request.node.name:       # the 10-10 wiring tests: no start reaction, idle = the bottom-right emote
        monkeypatch.setattr(es, "REACTIONS", dict(es.REACTIONS, start=[()]))
        monkeypatch.setattr(es, "EMOTES", {"br": es.EMOTES["br"]})
        monkeypatch.setattr(es, "IDLE_ROLL_S", 0.0)


class WaitPilot(Pilot):
    """WAIT before tick `play_from`, a play from then on; p_play / gate_tau as given."""
    gate_tau = 0.35

    def __init__(self, play_from=10 ** 9, p_play=0.0):
        super().__init__()
        self.play_from, self.p_play, self.times = play_from, p_play, []

    def decide(self, f):
        self.times.append(time.time())
        if f["game_tick"] >= self.play_from:
            return super().decide(f)
        return {"play": False, "p_play": self.p_play, "gate_tau": self.gate_tau, "public_audit": {}}


def spam(monkeypatch, tmp_path, pilot, **kw):
    kw = dict(dict(emote_spam="on", emote_interval_s=0.3, emote_gap_ms=150, emote_guard=0.75, emote_idle_p=1.0), **kw)
    cmds, ev = play(monkeypatch, tmp_path, pilot=pilot, pace=0.02, tap_gap_ms=50, **kw)
    return cmds, ev


# ---- pure scheduler ----------------------------------------------------------------------------------------------
def test_due_only_on_wait_with_nothing_pending_after_the_interval():
    due = lambda **k: es.emote_due(**dict(dict(now=10.0, last_t=8.0, interval_s=1.35, play=False, busy=False,  # noqa: E731
                                              p_play=0.0, tau=0.35, guard=0.75), **k))
    assert due()
    assert not due(play=True)                         # a play decision never emotes
    assert not due(busy=True)                         # a follow-up / pending play / ability tap outstanding
    assert not due(now=9.3) and due(now=9.4)         # the interval, measured from the last first tap
    assert due(last_t=float("-inf"))


def test_guard_skips_a_near_play_and_zero_disables_it():
    due = lambda p, g: es.emote_due(10.0, 0.0, 1.35, False, False, p, 0.4, g)  # noqa: E731
    assert due(0.29, 0.75) and not due(0.31, 0.75) and not due(0.5, 0.75)   # p_play >= 0.75 x 0.4
    assert due(0.5, 0)


def test_hold_runs_from_the_first_tap_for_0_6_s():
    assert abs(es.hold_s(10.2, 10.0) - 0.4) < 1e-9 and es.hold_s(10.6, 10.0) == 0 and es.hold_s(11, 10.0) == 0
    assert es.hold_s(5.0, float("-inf")) == 0


def test_cmd_is_the_calibrated_two_taps_and_scales():
    assert es.emote_cmd(900, 1600, 150) == EMOTE
    assert es.emote_cmd(900, 1600, 0) == "input tap 88 1365; input tap 710 1195"
    assert es.emote_cmd(450, 800, 150) == "input tap 44 682; sleep 0.15; input tap 355 598"


# ---- play_match wiring ---------------------------------------------------------------------------------------------
def test_off_sends_nothing_and_logs_nothing_new(monkeypatch, tmp_path):
    cmds, ev = play(monkeypatch, tmp_path, pilot=WaitPilot(), pace=0.01)       # all WAIT, flag absent
    assert cmds == [] and not any(e["event"].startswith("emote") for e in ev)
    assert not any(k.startswith("emote") for e in ev for k in e)


def test_on_emotes_on_wait_at_the_interval(monkeypatch, tmp_path):
    pilot = WaitPilot()
    cmds, ev = spam(monkeypatch, tmp_path, pilot)
    n = sum(e["event"] == "emote" for e in ev)
    span = pilot.times[-1] - pilot.times[0]                   # the wall time the decisions covered
    assert cmds == [EMOTE] * n and 2 <= n <= span / 0.3 + 1, (n, span, cmds)   # one per 0.3 s at most, and it does fire
    e = next(e for e in ev if e["event"] == "emote")
    assert e["guard"] == 0.0 and e["tick"] >= 150
    assert next(e for e in ev if e["event"] == "start")["emote_spam"] == "on"
    end = next(e for e in ev if e["event"] == "end")
    assert end["emotes"] == n and end["emote_holds"] == 0


def test_guard_blocks_when_the_model_is_about_to_play(monkeypatch, tmp_path):
    cmds, _ = spam(monkeypatch, tmp_path, WaitPilot(p_play=0.3))              # 0.3 >= 0.75 x 0.35
    assert cmds == []
    (tmp_path / "b").mkdir()
    cmds, ev = spam(monkeypatch, tmp_path / "b", WaitPilot(p_play=0.3), emote_guard=0)
    assert cmds and next(e for e in ev if e["event"] == "emote")["guard"] == round(0.3 / 0.35, 3)


def test_a_play_right_after_an_emote_is_held(monkeypatch, tmp_path):
    cmds, ev = spam(monkeypatch, tmp_path, WaitPilot(play_from=156), emote_interval_s=5)
    assert cmds[0] == EMOTE and CARD in cmds                  # one emote, then the play on the same channel, in order
    assert cmds.index(CARD) > cmds.index(EMOTE)
    holds = [e for e in ev if e["event"] == "emote_hold"]
    assert holds and 0 < holds[0]["held_ms"] <= 600
    assert next(e for e in ev if e["event"] == "end")["emote_holds"] == len(holds)


def test_dry_run_logs_but_sends_nothing(monkeypatch, tmp_path):
    orig = lp.play_match
    monkeypatch.setattr(lp, "play_match", lambda a, *r, **k: (setattr(a, "dry_run", True), orig(a, *r, **k))[1])
    cmds, ev = spam(monkeypatch, tmp_path, WaitPilot())
    assert cmds == [] and any(e["event"] == "emote" and e.get("dry_run") for e in ev)


def test_check_passes_with_emote_spam_on(monkeypatch, tmp_path, capsys):
    ck = tmp_path / "m.pt"
    ck.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--ckpt", str(ck), "--emote-spam", "on"])
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4,
                                                                           decision_options=kw["decision_options"]))
    assert lp.main() == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["check"] == "LIVE_CHECK_PASS" and (out["emote_spam"], out["emote_interval_s"], out["emote_gap_ms"],
                                                 out["emote_guard"]) == ("on", 3.0, 150, 0.75)


def test_below_the_cooldown_is_refused(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--no-live-options", "--emote-spam", "on",
                                      "--emote-interval-s", "1.0"])
    assert lp.main() == 2 and "cooldown" in capsys.readouterr().out


def test_deployable_from_live_options(monkeypatch, tmp_path, capsys):
    from pipeline.live_options import EXTRA_LIVE_FLAGS
    flags = dict(EXTRA_LIVE_FLAGS)
    assert flags["--emote-spam"] == dict(choices=("off", "on"), default="off") and set(flags) >= {
        "--emote-interval-s", "--emote-gap-ms", "--emote-guard"}
    f, ck = tmp_path / "LIVE_OPTIONS", tmp_path / "m.pt"
    f.write_text("--emote-spam on\n--emote-gap-ms 120\n")
    ck.write_bytes(b"x")
    monkeypatch.setattr(sys, "argv", ["live_play.py", "--check", "--live-options-file", str(f), "--ckpt", str(ck)])
    monkeypatch.setattr(lp, "GenPilot", lambda path, **kw: SimpleNamespace(feature_version=4,
                                                                           decision_options=kw["decision_options"]))
    assert lp.main() == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (out["emote_spam"], out["emote_gap_ms"], out["emote_interval_s"], out["emote_guard"]) == ("on", 120, 3.0, 0.75)


class FakeClock:
    def __init__(self):
        self.now, self.wall_offset = 1000.0, 10000.0

    def monotonic(self):
        return self.now

    def time(self):
        return self.now + self.wall_offset

    def sleep(self, seconds):
        self.now += seconds


@pytest.mark.parametrize("outcome", [True, False, "raise"])
def test_attempt_clock_guards_failures_two_taps_and_wall_jumps(monkeypatch, outcome):
    clock, limiter, starts, taps = FakeClock(), es.EmoteClock(), [], []
    monkeypatch.setattr(es, "time", clock)

    def send(cmd):
        assert cmd == EMOTE
        starts.append(clock.now)
        taps.append(("chat", clock.now))
        clock.sleep(0.15)
        taps.append(("emote", clock.now))
        if outcome == "raise":
            raise OSError("failed tap")
        return outcome

    def attempt(**kw):
        return limiter.attempt(send, EMOTE, 3.0, **dict(dict(busy=False, p_play=0.0, tau=.35, guard=.75), **kw))

    def fire():
        if outcome == "raise":
            with pytest.raises(OSError):
                attempt()
        else:
            assert attempt() is outcome

    fire()
    assert limiter.hold() == pytest.approx(.45)     # hold starts at chat dispatch, not command completion
    clock.now = 1002.999
    clock.wall_offset += 3600                       # a wall-clock jump cannot release the limiter
    assert attempt() is None
    clock.now = 1003.0
    assert attempt(p_play=.3) is None and attempt(busy=True) is None
    assert limiter.last_t == 1000.0                 # skips do not reset or consume the attempt clock
    fire()                                         # exactly the start + interval, not end + interval
    clock.wall_offset -= 7200
    clock.now = 1005.999
    assert attempt() is None
    clock.now = 1006.0
    fire()
    assert starts == [1000.0, 1003.0, 1006.0]
    emotes = [t for kind, t in taps if kind == "emote"]
    assert all(b - a >= 3.0 for a, b in zip(emotes, emotes[1:]))


def clocked_match(monkeypatch, tmp_path, clock, offsets, pilot=None, **options):
    """Drive the actual match loop synchronously: no threads, device, model, or real sleeps."""
    import queue
    import threading

    base = clock.now
    frames = iter((base + dt, rframe(150 + i * 2)) for i, dt in enumerate(offsets))

    class Frames:
        def get(self, timeout=None):
            item = next(frames, None)
            if item is None:
                return None
            at, line = item
            clock.now = max(clock.now, at)
            return clock.time(), line

        def empty(self):
            return True

        def qsize(self):
            return 0

    monkeypatch.setattr(queue, "Queue", Frames)
    monkeypatch.setattr(threading, "Thread", lambda **kw: SimpleNamespace(start=lambda: None, join=lambda **kw: None))
    monkeypatch.setattr(es, "time", clock)
    monkeypatch.setattr(lp, "time", SimpleNamespace(time=clock.time, monotonic=clock.monotonic, sleep=clock.sleep,
                                                   strftime=lambda fmt: "fake"))
    return play(monkeypatch, tmp_path, pilot=pilot or WaitPilot(), **options)


@pytest.mark.parametrize("fast", [False, True])
@pytest.mark.parametrize("fail_first", [False, True])
def test_match_boundaries_failed_taps_and_transports_share_clock(monkeypatch, tmp_path, fast, fail_first):
    import fast_input
    clock, starts = FakeClock(), []

    class Shell:
        def __init__(self, *a):
            pass

        def run(self, cmd, **kw):
            if cmd == "true":
                return True
            assert cmd == EMOTE
            starts.append(clock.now)
            clock.sleep(.15)                         # the chat-button + emote command
            return not (fail_first and len(starts) == 1)

        def close(self):
            pass

    if fast:
        monkeypatch.setattr(fast_input, "PersistentShell", Shell)
    else:
        monkeypatch.setattr(lp, "input_cmd", Shell().run)
    options = dict(emote_spam="on", emote_interval_s=3.0, emote_gap_ms=150, emote_guard=.75, emote_idle_p=1.0,
                   fast_input=fast)
    _, first = clocked_match(monkeypatch, tmp_path, clock, [0, 0], **options)
    assert any(e["event"] == "stop" and e["why"] == "tap_timeout" for e in first) == fail_first
    clock.now = 1000.25
    second_dir = tmp_path / "next"
    second_dir.mkdir()
    _, second = clocked_match(monkeypatch, second_dir, clock, [0, 0, 2.749, 2.75, 5.749, 5.75], **options)
    assert starts == [1000.0, 1003.0, 1006.0]
    events = [e for e in first + second if e["event"] == "emote"]
    assert [e["attempt_monotonic_s"] for e in events] == starts
    assert [e["n"] for e in events] == [1, 1, 2]       # counts reset, the cooldown does not


def test_slow_emote_logging_cannot_shorten_dispatch_gap(monkeypatch, tmp_path):
    clock, starts = FakeClock(), []
    dumps = json.dumps

    def slow_log(obj, **kw):
        if obj.get("event") == "emote" and len(starts) <= 1:
            clock.sleep(.8)
        return dumps(obj, **kw)

    monkeypatch.setattr(lp.json, "dumps", slow_log)
    monkeypatch.setattr(lp, "input_cmd", lambda cmd: starts.append(clock.now) or True)
    clocked_match(monkeypatch, tmp_path, clock, [0, 0, 2.999, 3, 5.999, 6],
                  emote_spam="on", emote_interval_s=3.0, emote_gap_ms=150, emote_guard=.75, emote_idle_p=1.0)
    assert starts == [1000.0, 1003.0, 1006.0]


def test_explicit_off_is_byte_identical_and_never_uses_emote_clock(monkeypatch, tmp_path):
    class ForbiddenClock:
        def __getattribute__(self, name):
            pytest.fail("emote-spam off touched the emote clock")

    monkeypatch.setattr(es, "CLOCK", ForbiddenClock())
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    cmds, _ = clocked_match(monkeypatch, baseline, FakeClock(), [0, .1, .2, .3], pilot=WaitPilot(play_from=154))
    off_cmds, _ = clocked_match(monkeypatch, tmp_path, FakeClock(), [0, .1, .2, .3], pilot=WaitPilot(play_from=154),
                               emote_spam="off", emote_interval_s=3.0, emote_gap_ms=150, emote_guard=.75)
    assert cmds == off_cmds and CARD in cmds
    assert (baseline / "live_play_fake.jsonl").read_bytes() == (tmp_path / "live_play_fake.jsonl").read_bytes()


# ---- owner 2026-10-14: reactive emotes ---------------------------------------------------------------------------------
TOWERS = [(0, 9000, 3000, 12, 7032), (0, 3500, 6500, 13, 4424), (0, 14500, 6500, 13, 4424),
          (1, 9000, 29000, 12, 7032), (1, 3500, 25500, 13, 4424), (1, 14500, 25500, 13, 4424)]


def board(hp=None, gone=(), extra=()):
    """Six crown towers (address 't<i>'), hp overrides by index, indices in `gone` absent, plus extra bodies."""
    hp = hp or {}
    ents = [dict(side=s, x=x, y=y, card_id=-1, kind=k, hp=hp.get(i, m), max_hp=m, address=f"t{i}")
            for i, (s, x, y, k, m) in enumerate(TOWERS) if i not in gone]
    return {"entities": ents + list(extra)}


class Rng:
    """random.Random stand-in: choice takes alternative `pick`, random() returns `r`."""
    def __init__(self, pick=0, r=0.0):
        self.pick, self.r = pick, r

    def choice(self, seq):
        return seq[self.pick % len(seq)]

    def random(self):
        return self.r


def drain(r, now=0.0):
    out = []
    while r.queue:
        out.append(r.pick(now))
    return out


def started(rng=None, idle_p=0.0):
    r = es.Reactions(idle_p, rng or Rng())
    r.observe(board(), 0, 150, [], 0.0)
    assert drain(r) == [("start", "good_luck"), ("start", "bl")]    # "Good luck!" then the bottom-left emote
    return r


def test_reactive_layout_matches_the_calibrated_emote_and_the_owner_grid():
    assert es.EMOTES["br"] == (710, 1195) and es.emote_cmd(900, 1600, 150) == EMOTE    # the live-verified tap
    assert sorted({x for x, _ in es.EMOTES.values()}) == [234, 393, 551, 710]
    assert sorted({y for _, y in es.EMOTES.values()}) == [1060, 1195]
    assert es.emote_cmd(900, 1600, 0, "wow") == "input tap 88 1365; input tap 765 1382"


def test_reactive_start_tower_events_and_damage():
    r = started()
    r.observe(board({1: 4000}), 0, 160, [], 1.0)
    r.observe(board({1: 3700}), 0, 200, [], 1.0)                       # 724 lost in one push: nothing yet
    assert not r.queue
    r.observe(board({1: 3600}), 0, 250, [], 1.0)                       # 824 with gaps <= 5 s -> bottom 3rd
    assert drain(r, 1.0) == [("tower_damage", "b3")]
    r.observe(board({1: 3000}), 0, 400, [], 2.0)                       # 150 ticks later: a new push, 600 so far
    assert not r.queue
    for t in (410, 412):
        r.observe(board(gone={2, 4}), 0, t, [], 3.0)                   # 2 frames without the towers: not yet
    assert not r.queue
    r.observe(board(gone={2, 4}), 0, 414, [], 3.0)
    assert drain(r, 3.0) == [("tower_lost", "tl"), ("tower_taken", "b2")]
    r2 = started(Rng(pick=1))
    for t in (160, 162, 164):
        r2.observe(board(gone={5}), 0, t, [], 1.0)
    assert drain(r2, 1.0) == [("tower_taken", "well_played")]


def test_reactive_tower_lost_replaces_a_queued_damage_reaction_and_glitches_do_not_count():
    r = started()
    r.observe(board({1: 3500}), 0, 160, [], 1.0)
    assert [q[:2] for q in r.queue] == [["tower_damage", "b3"]]
    for t in (162, 164, 166):
        r.observe(board(gone={1}), 0, t, [], 1.0)
    assert drain(r, 1.0) == [("tower_lost", "tl")]
    for t in (170, 172, 174, 176):
        r.observe(board(gone={0, 3, 4, 5}), 0, t, [], 1.0)             # kings missing = an unreadable frame
    assert not r.queue


def test_reactive_big_card_and_x_bow_lock_alternate_with_their_phrase():
    for pick, want in ((0, "wow"), (1, "t2")):
        r = started(Rng(pick=pick))
        r.observe(board(), 0, 160, [{"card": "Knight"}], 1.0)          # 3 elixir: nothing
        assert not r.queue
        r.observe(board(), 0, 162, [{"card": "Knight"}, {"card": "Golem"}], 1.0)
        assert drain(r, 1.0) == [("big_card", want)]
    xbow = dict(side=0, x=3500, y=14500, card_id=27000008, kind=0, hp=1000, max_hp=1000, address="xb")
    for pick, want in ((0, "thanks"), (1, "t3")):
        r = started(Rng(pick=pick))
        for i, t in enumerate((160, 170, 180, 190)):
            r.observe(board({4: 4400 - 30 * i}, extra=[xbow]), 0, t, [], 1.0)
        assert drain(r, 1.0) == [("xbow_lock", want)]
        r.observe(board({4: 4000}, extra=[xbow]), 0, 200, [], 1.0)
        assert not r.queue                                              # once per X-Bow
    far = dict(xbow, y=9000, address="xb2")                            # defensive X-Bow: out of reach of the tower
    r = started()
    for i, t in enumerate((160, 170, 180, 190)):
        r.observe(board({4: 4400 - 30 * i}, extra=[far]), 0, t, [], 1.0)
    assert not r.queue


def test_reactive_stale_drop_and_idle_is_random_among_the_8():
    r = started(Rng(r=0.0), idle_p=0.5)
    r.observe(board(), 0, 160, [{"card": "Golem"}], 1.0)
    assert r.pick(1.0 + es.STALE_S + 0.1)[0] == "idle"                 # the reaction went stale; idle rolled instead
    assert r.pick(1.0 + es.STALE_S + 0.5) is None                      # one roll per second
    r.rng = Rng(r=0.9)
    assert r.pick(20.0) is None                                        # 0.9 >= idle_p
    rr = es.Reactions(1.0, random.Random(0))
    assert {rr.pick(t)[1] for t in range(200)} == set(es.EMOTES)


def test_reactive_result_from_crowns_then_lowest_tower():
    r = started()
    r.observe(board(gone={4}), 0, 300, [], 1.0)
    assert r.result() == "win"
    r.observe(board(gone={1, 2}), 0, 302, [], 1.0)
    assert r.result() == "loss"
    r.observe(board({1: 100, 4: 200}), 0, 304, [], 1.0)
    assert r.result() == "loss"
    r.observe(board(gone={3, 4, 5}), 1, 306, [], 1.0)                 # seen from side 1: its king is gone
    assert r.result() == "loss"


def tframe(tick, gone=(), both=False):
    f = json.loads(rframe(tick))
    f["entities"] = board(gone=gone)["entities"]
    if both:
        f["players"][1]["hand_deck_indices"] = [1, 2, 3, 4]
    return json.dumps(f) + "\n"


def test_reactive_match_keeps_3_s_between_all_emotes_and_sends_the_end_emote(monkeypatch, tmp_path):
    import queue
    import threading
    clock, sent = FakeClock(), []
    monkeypatch.setattr(lp, "input_cmd", lambda cmd: sent.append((clock.now, cmd)) or True)
    frames = iter([tframe(t, gone={4} if t >= 200 else ()) for t in range(150, 230, 2)] +
                  [tframe(232 + 2 * i, gone={4}, both=True) for i in range(25)])

    class Frames:
        def get(self, timeout=None):
            ln = next(frames, None)
            if ln is None:
                return None
            clock.now += 0.2
            return clock.time(), ln

        def empty(self):
            return True

        def qsize(self):
            return 0

    monkeypatch.setattr(queue, "Queue", Frames)
    monkeypatch.setattr(threading, "Thread", lambda **kw: SimpleNamespace(start=lambda: None, join=lambda **kw: None))
    monkeypatch.setattr(es, "time", clock)
    monkeypatch.setattr(lp, "time", SimpleNamespace(time=clock.time, monotonic=clock.monotonic, sleep=clock.sleep,
                                                   strftime=lambda fmt: "fake"))
    _, ev = play(monkeypatch, tmp_path, pilot=WaitPilot(), emote_spam="on", emote_interval_s=3.0, emote_gap_ms=150,
                 emote_guard=.75, emote_idle_p=0.0)
    got = [(e["kind"], e["target"]) for e in ev if e["event"] == "emote"]
    assert got[:2] == [("start", "good_luck"), ("start", "bl")] and got[-1] == ("win", "br"), got
    assert got[2] in (("tower_taken", "b2"), ("tower_taken", "well_played")) and len(got) == 4, got
    assert sent[-1][1] == EMOTE                                         # the win emote is the bottom-right one
    times = [t for t, _ in sent]
    assert len(times) == 4 and all(b - a >= 3.0 for a, b in zip(times, times[1:])), times
