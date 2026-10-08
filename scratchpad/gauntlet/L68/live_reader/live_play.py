"""L68 live player: generalist pilots a Clash Royale match on MuMu from the memory reader. Owner-run.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/live_play.py [--dry-run]

Loop: reader frame (100 ms) -> pipeline.live_gen_v2.GenPilot (public inputs only) -> if it plays,
two ordinary Android taps (hand slot, board) -> receipt from the NEXT frames: the tapped hand slot rotated (the
elixir-drop half of upstream card_receipt is dropped: regen hid cheap plays). No game-memory writes. Taps follow upstream's ScreenLayout
(native X kept on screen for side 1; arena shifted one tile from the Cannon read-back). Each confirmed troop's
spawn position is compared with the intended cell -> tap-calibration error in tiles.
Stops: battle over / tick stalled 3 s, 5 unconfirmed taps, --max-seconds. Log: live_play_<ts>.jsonl here.
--matches N --friend NAME: N matches back to back; between them friend_nav.py starts the next friendly 1v1 against
that friend's bot (allowlisted taps only; see its docstring and --nav-dry-run). Default N = 1: no navigation.
--ladder --matches N: N Trophy Road matches back to back; between them ladder_nav.py taps Play Again (or, after the
day's 4th win, OK -> opens the daily chests -> Battle). --clip-every S: record only one match every S seconds and post a
60-s overlaid clip of it to Discord (discord_clip.py); the other matches are not recorded. --stop-file: stop between
matches once that file exists.
--menu-guard (OPT-IN since 2026-09-30): classify a full screencap every <= 2 s during the match and stop on any menu.
Off by default: those PNG screencaps saturated adb live (live_play_20260930_184444: tap_ms median 3021 / max 5407,
frame backlog 72, 5 of 17 taps unconfirmed, the bot leaked). The tick-advance gate and first-frame rule stay on.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline.live_gen_v2 import GenPilot  # noqa: E402
from pipeline.obs_contract import _catalog_names  # noqa: E402
from hero_button import HeroButton, hero_ids, should_press  # noqa: E402
from friend_nav import MenuGuard  # noqa: E402

# adb.exe directly (same device pin as adb.sh): from Python, "bash" resolves to WSL's System32 bash, which cannot
# run the Windows adb -> empty output.
ADB = [r"C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe", "-s", "127.0.0.1:16384"]
ENV = dict(os.environ)
RVA, ROOT_CTX = "0x1aeef98", "0x18"
UI_READY_MIN_TICK = 150
# 2026-10-03 reader v2 (scratchpad/gauntlet/L70/reader/FINDINGS.md): v1 DROPPED evolved bodies (evolution-form card
# ids); v2 --extended keeps them (+ per-entity evo, projectiles, effects). v1 checkpoints fold the form id to the base
# card via the catalog. Rollback: --reader v1.
READERS = {"v1": ("/data/local/tmp/live_sampler", ""), "v2": ("/data/local/tmp/re_live_sampler2", " --extended")}
CONFIRM_TICKS = 60       # a tap is "unconfirmed" only after 60 GAME ticks (3 s) without registering -- never wall clock
READER_SILENT_S = 10.0   # no reader line at all this long after the clock ran -> stop (a reader restart takes ~1-2 s)
GUARD_BLIND_S = 30.0     # menu guard without a successful screen classification this long -> stop (taps block at 8 s);
                         # 10 -> 30 s: live_play_20260930_184048 stopped guard_blind after 16 s with adb saturated


def clock_verdict(tick: int, last_tick: int, idle_s: float) -> str:
    """wait | stall | proceed. 2026-09-30: the reader emits active+coherent frames at game_tick 0 (loading screen /
    countdown); the old guard counted that flat 0 as a stall and exited after 3 s. Tick 0 = the clock has not
    started: keep waiting, never decide. Only while the clock has NEVER run (last_tick < 0); a tick 0 after it ran
    (reader glitch) is an ordinary non-advancing tick and stalls after 3 s like any other."""
    if tick <= 0 and last_tick < 0:
        return "wait"
    return "proceed" if tick > last_tick or idle_s <= 3 else "stall"


def adb(*args: str, timeout: float = 5, strict: bool = False) -> str:
    try:   # 2026-09-30: a saturated adb timed out the cleanup `pkill` and crashed the run at match end
        return subprocess.run(ADB + list(args), capture_output=True, text=True, timeout=timeout, env=ENV).stdout
    except subprocess.TimeoutExpired:
        print(f"[live] adb timed out after {timeout:.0f} s: {' '.join(args)[:60]}", flush=True)
        if strict:                                        # the caller must know (in-match input, sampler kill)
            raise
        return ""


# In-match inputs (2026-09-30 verifier F1): a slow `adb shell input tap` can still EXECUTE on the device seconds
# after the host call returned or timed out (live_play_20260930_185829: one landed ~6 s late, tap_ms up to 7059). A
# late board tap after the nav tapped results-OK could hit the main menu (249/1378 board taps fall inside the Battle
# button). So: a timed-out input ends that match's tapping (why=tap_timeout), and the nav starts only after every
# input call returned + NAV_QUIET_S of quiet (+ a best-effort `pkill -f "input tap"` when one timed out).
NAV_QUIET_S = 10.0
INPUTS = {"in_flight": 0, "last_t": 0.0, "timed_out": False}


def input_cmd(cmd: str, timeout: float = 5) -> bool:
    """One in-match `input` shell command. False = it timed out (it may still run on the device later)."""
    INPUTS["in_flight"] += 1
    INPUTS["last_t"] = time.time()
    try:
        adb("shell", cmd, timeout=timeout, strict=True)
        return True
    except subprocess.TimeoutExpired:
        INPUTS["timed_out"] = True
        return False
    finally:
        INPUTS["last_t"] = time.time()                    # quiet counts from the LATER of issue / return
        INPUTS["in_flight"] -= 1


def wait_inputs_quiet(quiet_s: float | None = None) -> None:
    """Before the nav's first tap: no in-match input in flight, NAV_QUIET_S since the last one; after a timed-out
    input also a best-effort `pkill -f "input tap"` and the quiet period again."""
    quiet_s = NAV_QUIET_S if quiet_s is None else quiet_s
    while INPUTS["in_flight"]:
        time.sleep(0.1)
    if INPUTS["timed_out"]:
        print('[live] an in-match tap timed out -- killing any pending `input tap` on the device', flush=True)
        adb("shell", 'pkill -f "input tap"')
        INPUTS["timed_out"], INPUTS["last_t"] = False, time.time()
    wait = INPUTS["last_t"] + quiet_s - time.time()
    if wait > 0:
        print(f"[live] waiting {wait:.1f} s after the last in-match input before navigating (NAV_QUIET_S)",
              flush=True)
        time.sleep(wait)


from pipeline.live_gen import EVEN_BUILDINGS  # noqa: E402  {"Tesla"}: the only 2x2 building -> the only tap offset


class Layout:
    """upstream native_core/mumu_live_actions.ScreenLayout.from_size, taking OUR board frame (me at the bottom,
    side 1 rotated 180 deg) instead of a canonical cell."""
    def __init__(self, w: int, h: int):
        vw = min(float(w), h * 9 / 16) if w / h > 0.8 else float(w)
        left = (w - vw) / 2
        self.w, self.h = w, h
        self.ax0, self.ax1 = left + vw * .055, left + vw * .945
        self.ay0, self.ay1 = h * (.105 - .685 / 32), h * (.790 - .685 / 32)
        self.hand_y, self.hand_x = h * .890, [left + vw * f for f in (.31, .50, .69, .88)]

    def board(self, xy: tuple[float, float], side: int, even: bool = False) -> tuple[int, int]:
        # screen x = 1 - our-frame x on BOTH sides (2026-09-30 side-0 match: every troop landed mirrored left/right,
        # intended 0.861 -> spawned 0.139, 0.139 -> 0.861, 0.806 -> 0.194; side 1 was already right). Side 1's screen
        # keeps native X (our frame rotated it); side 0's screen is native rotated 180 while our frame only flips y.
        fx = 1.0 - xy[0]
        fy = xy[1]
        if even:   # a 2x2 building takes its tapped tile's ARENA lower-left corner (RoyaleSim placement.SNAP_EVEN_CORNER);
            # a tap ON the corner snapped 1 tile left 34/35 times (L68 hog-pull audit) -> tap a quarter tile inside,
            fx += 0.25 / 18 if side == 1 else -0.25 / 18   # +x native: side 1's screen x runs with native x, side 0's against
            fy += 0.25 / 32 if side == 1 else -0.25 / 32   # +y native: side 1's screen y runs with native y, side 0's against
        return round(self.ax0 + fx * (self.ax1 - self.ax0)), round(self.ay0 + fy * (self.ay1 - self.ay0))

    def hand(self, pos: int) -> tuple[int, int]:
        return round(self.hand_x[pos]), round(self.hand_y)


def screen_size() -> tuple[int, int]:
    # An adb SERVER restart (e.g. another adb version on the PC) drops the TCP device 127.0.0.1:16384 while MuMu keeps
    # running (2026-09-25 02:3x: `devices` listed only emulator-5554). Reconnect first; fail readably if still gone.
    subprocess.run([ADB[0], "connect", ADB[2]], capture_output=True, text=True, timeout=10, env=ENV)
    if adb("shell", "id -u").strip() != "0":               # MuMu restarts reset adbd to the shell user; the reader
        adb("root")                                        # needs root for /proc/PID/mem. `adb root` restarts adbd,
        time.sleep(2)                                      # which drops the TCP device -> reconnect.
        subprocess.run([ADB[0], "connect", ADB[2]], capture_output=True, text=True, timeout=10, env=ENV)
    sizes = re.findall(r"(\d+)x(\d+)", adb("shell", "wm size"))
    if not sizes:
        raise SystemExit(f"MuMu not reachable at {ADB[2]} (adb connect failed). Is MuMu running? "
                         f"`bash scratchpad/gauntlet/L68/live_reader/adb.sh devices -l` shows what adb sees.")
    w, h = sizes[-1]                                        # an Override size, if any, is listed last
    return int(w), int(h)


def my_frame_xy(e: dict, side: int) -> tuple[float, float]:
    x, y = (18000 - e["x"], 32000 - e["y"]) if side == 1 else (e["x"], e["y"])
    return x / 18000, 1 - y / 32000


class ScreenRec:
    """Device-side `screenrecord` in back-to-back segments (Android caps one run at 180 s; a match with overtime is
    longer). Each segment logs /proc/uptime just before recording starts -- the same clock as the reader's
    sample_monotonic_us -- so overlay_replay.py can align boxes to video. Stopped with SIGINT so the mp4 finalises."""
    SEG_S = 170

    def __init__(self, stamp: str):
        import threading
        self.stamp, self.segments, self.stop_flag = stamp, [], False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        i = 0
        while not self.stop_flag:
            remote = f"/sdcard/lp_{self.stamp}_{i}.mp4"
            p = subprocess.Popen(ADB + ["shell", f"cat /proc/uptime; exec screenrecord --time-limit {self.SEG_S} "
                                                 f"--bit-rate 6000000 {remote}"],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, env=ENV)
            up = (p.stdout.readline() or "0").split()[0]
            self.segments.append([remote, float(up)])
            p.wait()
            i += 1

    def stop(self) -> list:
        """Finish the segment in progress, pull every segment to OUT_DIR/raw, delete it from the device."""
        self.stop_flag = True
        adb("shell", "pkill -INT screenrecord")
        self.thread.join(timeout=10)
        raw = REPO / "icebow" / "data" / "overlayed_replays" / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        out = []
        for remote, t0 in self.segments:
            local = raw / Path(remote).name
            subprocess.run(ADB + ["pull", remote, str(local)], capture_output=True, timeout=120, env=ENV)
            adb("shell", f"rm -f {remote}")
            if local.is_file():
                out.append([str(local), t0])
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    from pipeline.decision_options import add_arguments, config_from_args
    add_arguments(ap)
    ap.add_argument("--ckpt", help="explicit checkpoint; otherwise use the selected CKPT_OVERRIDE (never newest file)")
    ap.add_argument("--check", action="store_true", help="load the selected model and report settings offline, without ADB or taps")
    ap.add_argument("--tau", type=float, default=0.35)
    ap.add_argument("--tau-alternate", type=float, nargs=2, default=None, metavar=("TAU_A", "TAU_B"),
                    help="owner 2026-10-07: A/B the play threshold match by match (counter in --tau-alternate-state "
                         "survives supervisor restarts; each match logs its tau in the start event)")
    ap.add_argument("--tau-alternate-state", default=str(REPO / "scratchpad/gauntlet/L70/live/tau_alternate.json"))
    ap.add_argument("--ckpt-alternate", nargs=2, default=None, metavar=("CKPT_A", "CKPT_B"),
                    help="owner 2026-10-07: A/B two checkpoints match by match (both loaded at startup; counter in "
                         "--ckpt-alternate-state survives supervisor restarts; each match's start event logs the chosen "
                         "ckpt + ckpt_sha256). Bypasses CKPT_OVERRIDE; refused together with --ckpt or --tau-alternate")
    ap.add_argument("--ckpt-alternate-state", default=str(REPO / "scratchpad/gauntlet/L70/live/ckpt_alternate.json"))
    ap.add_argument("--leak", type=float, default=9.5, help=argparse.SUPPRESS)
    leak = ap.add_mutually_exclusive_group()
    leak.add_argument("--anti-leak", action="store_true",
                      help="OPT-IN forced spend, the SIM's anti-stall rule (e1_eval.anti_stall): at int(elixir) >= "
                           "--anti-leak-elixir and >= --anti-leak-seconds of game time since my last CONFIRMED play (or the "
                           "first decision), play the model's card + cell even when the gate says wait. Off by default")
    leak.add_argument("--no-anti-leak", action="store_true", default=True,
                      help="compatibility no-op: anti-leak is off unless --anti-leak")
    ap.add_argument("--anti-leak-elixir", type=float, default=9.0)
    ap.add_argument("--anti-leak-seconds", type=float, default=12.0)
    ap.add_argument("--public-audit", action="store_true", default=True,
                    help="log public board/targets and model decisions, including WAIT, independently of video")
    ap.add_argument("--interval-ms", type=int, default=100)
    ap.add_argument("--max-seconds", type=float, default=400,
                    help="PER-MATCH wall-clock cap (reset each match): overtime ends by 6,000 ticks = 300 s of "
                         "game time, + loading/countdown. Hitting it stops the whole run")
    ap.add_argument("--dry-run", action="store_true", help="decide and log, never tap")
    ap.add_argument("--reader", choices=tuple(READERS), default="v2",
                    help="memory reader: v2 (default since 2026-10-03: evolved units, projectiles, effects) or v1")
    ap.add_argument("--overlay", choices=("both", "detector", "reader"), default="both",
                    help="replay style: detector = play.py-style YOLO boxes only (cosmetic, e.g. for posts), "
                         "reader = memory-reader markers + taps, both")
    ap.add_argument("--no-record", action="store_true",
                    help="skip the overlaid replay (default: screenrecord + reader boxes -> "
                         "icebow/data/overlayed_replays/live_<stamp>.mp4)")
    ap.add_argument("--device", default="cpu", choices=("auto", "cuda", "cpu"),
                    help="default CPU with four threads, leaving the GPU for training; auto selects CUDA when available")
    ap.add_argument("--extrapolate", type=int, default=26,
                    help="decide on the board this many ticks ahead, where the card lands (~26 live; 0 = off). "
                         "Screen (HANDOFF L68as): +3.4 pp gen / +6.9 pp v6lat vs no extrapolation at delay 26")
    ap.add_argument("--no-legal-guard", action="store_true",
                    help="owner 2026-10-07 'one tile left/right': by default the model's cell is chosen only among cells "
                         "the card lands on AS TAPPED (not on my own building/tower, not across the river in a lane "
                         "whose enemy princess stands -- the game moved such taps >= 1 tile 77/81 times, tap_audit.py). "
                         "This flag restores the plain argmax (= SIM's rule)")
    ap.add_argument("--predict-drops", action="store_true",
                    help="OPT-IN (needs --extrapolate): an observed enemy Skeleton Barrel balloon disappearance adds its 7 "
                         "skeletons to the look-ahead board 12 ticks later (pipeline/extrapolate.py DropTracker). Off = unchanged")
    ap.add_argument("--no-opp-counter", action="store_true",
                    help="feed the model opponent elixir = unknown instead of the public-events counter")
    ap.add_argument("--menu-guard", action="store_true",
                    help="OPT-IN in-match menu guard: a screencap every <= 2 s is classified; any menu stops the match "
                         "and taps wait for a fresh non-menu classification. Off by default: its screencaps saturated "
                         "adb live (2026-09-30). Needs a 900x1600 screen")
    ap.add_argument("--no-menu-guard", action="store_true",
                    help="no-op, kept for compatibility (the menu guard is off unless --menu-guard)")
    ap.add_argument("--invite-wait", type=float, default=20.0,
                    help="friend loop: seconds to wait on the Social tab for the friend's invite before sending ours "
                         "(owner 2026-09-30: 20 s); a random 5-20 s re-delay is used only after crossed invites")
    ap.add_argument("--no-ability", action="store_true",
                    help="never press the hero ability button (default: pressed by hero_button.should_press when the "
                         "deck holds a hero and the button reads ready)")
    ap.add_argument("--matches", type=int, default=1,
                    help="play this many matches back to back (default 1 = one match, no navigation). > 1 needs "
                         "--friend: between matches friend_nav.py starts the next FRIENDLY 1v1 against that friend's "
                         "bot; the previous match's overlay renders in the background")
    ap.add_argument("--friend", help="the friend to play when --matches > 1; must be the friend the nav templates "
                                     "were cropped for")
    ap.add_argument("--ladder", action="store_true",
                    help="with --matches > 1: re-queue Trophy Road matches via ladder_nav.py (Play Again; after the "
                         "day's 4th win OK -> open the chests -> Battle) instead of friendlies")
    ap.add_argument("--wins-today", type=int, default=None,
                    help="ladder: set today's win count (daily chests come with wins 1-4); default = ladder_state.json")
    ap.add_argument("--no-trophy-log", action="store_true",
                    help="ladder: do not read the trophy counter / per-match trophy change (passive logging, default on)")
    ap.add_argument("--clip-every", type=float, default=0.0,
                    help="seconds; > 0: record ONLY the first match and then one match every this many seconds, and post a 60-s "
                         "overlaid clip of it to Discord (discord_clip.py) -- all other matches unrecorded")
    ap.add_argument("--stop-file", type=Path, help="stop the run between matches once this file exists")
    ap.add_argument("--no-iw-pro-gate", action="store_true",
                    help="Hero Ice Wizard: skip the pro-timing gate (ability_ice_wizard.py) and use the freeze-value rule alone")
    ap.add_argument("--ckpt-override-file", type=Path, default=REPO / "scratchpad/gauntlet/L70/live/CKPT_OVERRIDE",
                    help="default checkpoint selection; explicit --ckpt wins. A changed selection ends a default-selected run between matches")
    ap.add_argument("--nav-dry-run", action="store_true",
                    help="play nothing: run ONE between-match navigation that classifies the live screens and logs "
                         "the tap it WOULD make, never tapping (navigate by hand to test it)")
    a = ap.parse_args()
    try:                                     # owner 2026-10-07: live play gets the CPU before training / sim jobs
        import psutil
        psutil.Process().nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
    except Exception as exc:                 # never block live play on a priority call
        print(f"[live] priority not raised: {exc}", flush=True)
    decision_cfg = config_from_args(a)
    if a.matches < 1:
        print("refusing: --matches must be >= 1")
        return 2
    if a.predict_drops and not a.extrapolate:
        print("refusing: --predict-drops adds its skeletons to the look-ahead board, which needs --extrapolate > 0 "
              "(it would silently do nothing)")
        return 2
    if (a.matches > 1 or a.nav_dry_run) and not (a.friend or a.ladder):
        print("refusing: --matches > 1 and --nav-dry-run need --friend NAME or --ladder")
        return 2
    if a.ckpt_alternate and (a.tau_alternate or a.ckpt):
        print("refusing: --ckpt-alternate cannot be combined with --tau-alternate or --ckpt (one A/B variable at a time)")
        return 2
    selected, arms, pilots = None, None, None
    if a.ckpt_alternate:                         # the pair bypasses resolve_checkpoint / CKPT_OVERRIDE
        try:
            arms = [alternate_arm(p) for p in a.ckpt_alternate]
        except (OSError, ValueError) as exc:
            print(f"[live] {exc}", flush=True)
            return 2
        for i, (path, sha) in enumerate(arms):
            print(f"[live] checkpoint {'AB'[i]}: {path}\n[live] SHA256 {'AB'[i]}: {sha}", flush=True)
        if arms[0][1] == arms[1][1]:
            print("refusing: --ckpt-alternate got the same checkpoint twice")
            return 2
        a.ckpt, a.ckpt_source, a.ckpt_sha256 = arms[0][0], "--ckpt-alternate", arms[0][1]
        if a.check:
            loaded = [load_pilot(a, decision_cfg, ckpt=path) for path, _ in arms]
            print(json.dumps(dict(check='LIVE_CHECK_PASS', checkpoints=[
                dict(checkpoint=path, sha256=sha, feature_version=pl.feature_version)
                for (path, sha), (_, pl) in zip(arms, loaded)], device=loaded[0][0], tau=a.tau, **anti_leak_log(a),
                public_audit=a.public_audit, legal_guard=not getattr(a, 'no_legal_guard', False), predict_drops=a.predict_drops,
                decision_options=vars(loaded[0][1].decision_options))))
            return 0
    else:
        from pipeline.live_checkpoint import resolve_checkpoint
        try:
            selected = resolve_checkpoint(a.ckpt, a.ckpt_override_file, REPO)
        except (OSError, ValueError) as exc:
            print(f"[live] {exc}", flush=True)
            return 2
        a.ckpt, a.ckpt_source, a.ckpt_sha256 = str(selected.path), selected.source, selected.sha256
        print(f"[live] checkpoint: {a.ckpt}\n[live] selected by: {a.ckpt_source}\n[live] SHA256: {a.ckpt_sha256}", flush=True)
    if a.check:
        device, pilot = load_pilot(a, decision_cfg)
        print(json.dumps(dict(check='LIVE_CHECK_PASS', checkpoint=a.ckpt, sha256=a.ckpt_sha256,
              feature_version=pilot.feature_version, device=device, tau=a.tau, **anti_leak_log(a),
              public_audit=a.public_audit, legal_guard=getattr(pilot, 'legal_guard', None), predict_drops=a.predict_drops,
              decision_options=vars(pilot.decision_options))))
        return 0
    nav = None
    if a.matches > 1 or a.nav_dry_run:
        if a.ladder:
            from ladder_nav import LadderNavRunner
            nav = LadderNavRunner(ADB, dry_run=a.nav_dry_run, wins_today=a.wins_today,
                                  trophy_log=not a.no_trophy_log)
        else:
            from friend_nav import FriendNav
            nav = FriendNav(ADB, a.friend, dry_run=a.nav_dry_run,   # validates the template-bound friend name
                            invite_wait=a.invite_wait)
        if screen_size() != (900, 1600):
            print("refusing: the nav templates are 900x1600; the device screen differs")
            return 2
        if a.nav_dry_run:
            return 0 if nav.run()[0] else 1
    lay = Layout(*screen_size())
    if a.menu_guard and (lay.w, lay.h) != (900, 1600):
        print(f"refusing: the in-match menu guard needs a 900x1600 screen (got {lay.w}x{lay.h}); fix the emulator "
              f"resolution, or run without --menu-guard")
        return 2
    if arms:                                     # two models in memory; each match picks one (~2x RAM, one forward per tick)
        loaded = [load_pilot(a, decision_cfg, ckpt=path) for path, _ in arms]
        device, pilots = loaded[0][0], [pl for _, pl in loaded]
        pilot = pilots[0]
    else:
        device, pilot = load_pilot(a, decision_cfg)
    renders: list = []                                   # background overlay renders of matches 1..N-1
    rc = 0                                               # 1 = the run stopped for any non-normal reason
    last_clip, no_start = -1e18, 0
    try:
        for k in range(a.matches):
            if selected is not None and selected.changed():
                print("[live] new checkpoint deployed or selection unavailable -- ending this run between matches",
                      flush=True)
                break
            if a.stop_file and a.stop_file.exists():
                print(f"[live] stop file {a.stop_file} found -- ending the run before match {k + 1}", flush=True)
                break
            # match 1 of a friend loop: launched on a menu -> navigate to start it; a battle already running -> play it
            navigated = bool(k) or (nav is not None and nav.probe() is not None)
            if navigated:
                wait_inputs_quiet()                      # no late in-match tap may land during the nav
                ok, why = nav.run()                      # results -> Social -> invite/accept -> battle loading
                if not ok:
                    print(f"[nav] run stopped before match {k + 1}: {why}", flush=True)
                    rc = 1
                    if why.startswith("ANOTHER_DEVICE"):    # owner's phone has the account: pause, don't restart
                        if a.stop_file:
                            a.stop_file.touch()
                        msg = HERE / "_pause_msg.txt"
                        msg.write_text(f"ClashAI live run PAUSED {time.strftime('%H:%M')}: Clash Royale was opened on "
                                       f"another device (Connection lost). The bot will not kick it. Ask Claude to "
                                       f"resume (press RELOAD, delete the STOP file, restart the supervisor).")
                        print(msg.read_text(), flush=True)
                        # owner 2026-10-06: restore the Discord pause alert (Codex had removed it)
                        subprocess.run([sys.executable, str(REPO / "scratchpad/gauntlet/L69/discord/post.py"), str(msg)],
                                       capture_output=True, timeout=60)
                    elif why.startswith("TROPHY_ROAD_ALERT") and a.stop_file:   # the nav already posted its screenshot:
                        a.stop_file.touch()                     # pause, don't let the supervisor retry an unknown screen
                    break
                if not pilots:
                    pilot.reset_match()                  # same loaded model, fresh history / opp counter
            if pilots:                                   # BEFORE the caption / play_match: everything per-match uses this pilot
                (a.ckpt, a.ckpt_sha256), pilot = pick_alternate(Path(a.ckpt_alternate_state), arms, pilots)
            record, caption, prev_clip = not a.no_record, None, last_clip
            if a.clip_every > 0:                         # owner 2026-10-02: replays off, one clip per --clip-every
                record = time.time() - last_clip >= a.clip_every
                if record:
                    last_clip = time.time()
                    st = getattr(nav, "st", {})
                    caption = (f"ClashAI live ladder clip -- match {k + 1}, {time.strftime('%H:%M')} -- "
                               f"{Path(a.ckpt).stem}, tau {a.tau} -- session W{st.get('W', 0)} L{st.get('L', 0)} "
                               f"D{st.get('D', 0)} before this match")
            if a.tau_alternate:                          # owner 2026-10-07 threshold A/B: alternate per match
                a.tau = pilot.gate_tau = next_alternate_tau(Path(a.tau_alternate_state), a.tau_alternate)
            why = play_match(a, pilot, lay, device, renders if k + 1 < a.matches else None,
                             start_timeout=180 if a.ladder else (60 if navigated else None),   # ladder: matchmaking;
                             # also on launch: an unrecognised screen then goes back to the nav, not a 600-s wait
                             record=record, clip_caption=caption)
            if why not in MATCH_OVER and caption is not None:
                last_clip = prev_clip                    # no match was played: the clip stays due (Codex review F9)
            if why == "no_battle_start" and a.ladder and k + 1 < a.matches and no_start < 2:
                no_start += 1                            # the queue never started: let the nav find the screen
                print(f"[live] no battle start after match {k} ({no_start}) -- re-navigating (max 2 in a row)", flush=True)
                continue
            no_start = 0
            if why not in MATCH_OVER:
                rc = 1
                if k + 1 < a.matches:
                    print(f"[live] run stopped after match {k + 1}: {why}", flush=True)
                    break
    finally:
        for p, name in renders:                          # stopping is safe: let the background renders finish
            try:
                p.wait(timeout=900)                      # a hung renderer must not hold the supervisor forever
            except subprocess.TimeoutExpired:
                p.kill()
            if p.returncode:
                print(f"[overlay] render failed (exit {p.returncode}); re-render with overlay_replay.py {name}")
                rc = 1
    return rc


def next_alternate(state: Path, arms):
    """The next arm of a match-by-match A/B; the counter lives in ``state`` so a restarted supervisor keeps alternating."""
    n = json.loads(state.read_text()).get("n", 0) if state.exists() else 0
    state.write_text(json.dumps({"n": n + 1}))
    return arms[n % 2]


def next_alternate_tau(state: Path, arms) -> float:
    return float(next_alternate(state, arms))


def alternate_arm(path: str):
    """(absolute path, sha256) of one --ckpt-alternate checkpoint; ValueError when the file is missing."""
    import hashlib
    p = Path(path).expanduser()
    p = (REPO / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.is_file():
        raise ValueError(f"--ckpt-alternate checkpoint does not exist: {p}")
    with p.open("rb") as stream:
        return str(p), hashlib.file_digest(stream, "sha256").hexdigest()


def pick_alternate(state: Path, arms, pilots):
    """The next match's (arm, pilot) with its per-match state cleared; the swap happens before play_match."""
    i = next_alternate(state, [0, 1])
    pilots[i].reset_match()                              # fresh history / opp counter / decision seed for this match
    return arms[i], pilots[i]


def load_pilot(a, decision_cfg, ckpt=None):
    import torch
    from pipeline.decision_options import options_from_config
    torch.set_num_threads(4)
    device = ("cuda" if torch.cuda.is_available() else "cpu") if a.device == "auto" else a.device
    pilot = GenPilot(ckpt or a.ckpt, device=device, gate_tau=a.tau, use_counter=not a.no_opp_counter,
                     extrapolate_ticks=a.extrapolate, decision_options=options_from_config(decision_cfg),
                     decision_seed=a.decision_seed, public_audit=a.public_audit,
                     **({"predict_drops": True} if getattr(a, "predict_drops", False) else {}))
    pilot.legal_guard = not getattr(a, 'no_legal_guard', False)
    if getattr(a, "anti_leak", False):          # default: the class's None = off, the decision rule unchanged
        pilot.anti_leak_elixir, pilot.anti_leak_seconds = a.anti_leak_elixir, a.anti_leak_seconds
    return device, pilot


def anti_leak_log(a) -> dict:
    """anti_leak + its parameters, for the start event and the --check JSON."""
    on = bool(getattr(a, "anti_leak", False))
    return dict(anti_leak=on, anti_leak_elixir=getattr(a, "anti_leak_elixir", None) if on else None,
                anti_leak_seconds=getattr(a, "anti_leak_seconds", None) if on else None)


# ordinary match ends: nav may go on (a results screen seen by the menu guard is the game's own end of match)
MATCH_OVER = {"battle_over_hands_visible", "battle_inactive", "tick_stalled", "menu_screen:results"}


def play_match(a, pilot, lay, device, renders: list | None, start_timeout: float | None = None,
               record: bool = True, clip_caption: str | None = None) -> str:
    """One match (the whole pre---matches main loop). renders=None: overlay rendered here before returning, as a
    single match always was; a list: rendered in a background process appended to it. start_timeout: stop if the
    battle clock never runs within this many seconds (after a nav handoff). -> the stop reason."""
    stamp = time.strftime('%Y%m%d_%H%M%S')
    log = open(HERE / f"live_play_{stamp}.jsonl", "w", encoding="utf-8")
    import queue
    import threading
    _wlock = threading.Lock()
    stop: dict = {"why": "reader_stream_ended"}

    def W(**k):                                          # called from the main loop AND the reader thread
        if k.get("event") == "stop":
            stop["why"] = k["why"]
        with _wlock:
            log.write(json.dumps(k, default=str) + "\n")
            log.flush()
    W(event="start", screen=[lay.w, lay.h], tau=a.tau, leak=a.leak, dry_run=a.dry_run, ckpt=a.ckpt,
      extrapolate=a.extrapolate, opp_counter=not a.no_opp_counter, device=device, **anti_leak_log(a),
      ckpt_source=a.ckpt_source, ckpt_sha256=a.ckpt_sha256,
      decision_options=vars(pilot.decision_options), decision_seed=pilot.match_seed,
      feature_version=pilot.feature_version, public_audit=a.public_audit, legal_guard=getattr(pilot, "legal_guard", None),
      **({"predict_drops": True} if getattr(a, "predict_drops", False) else {}))
    rec = ScreenRec(stamp) if record else None
    # Menu guard (2026-09-30 verifier): card taps are gated only by reader flags, and 249/1378 past board taps fall
    # inside the main screen's Battle button -> the SCREEN is classified every <= 2 s; any menu stops the match.
    # It FAILS CLOSED: no input until it has classified a post-arming screenshot as not-a-menu (MenuGuard.clear).
    guard = MenuGuard(ADB) if a.menu_guard else None    # OPT-IN (module docstring: adb saturation)
    if guard is None:
        W(event="menu_guard_off", screen=[lay.w, lay.h])

    def guard_clear() -> bool:
        return guard is None or guard.clear(time.time())
    blocked_logged = False
    button = None if a.no_ability else HeroButton(ADB, lay.w, lay.h, HERE / "ability_crops", period_s=2.0,
                                                  on_frame=guard.feed if guard else None)
    ab_pending, last_bstate = None, None
    sampler, extra = READERS[a.reader]
    cmd = (f"{sampler} $(pidof com.supercell.clashroyale) {a.interval_ms} {RVA} {ROOT_CTX} "
           f"--unified 0{extra}")
    procs: list = []
    stopping, spawn_lock = threading.Event(), threading.Lock()

    def stream():
        """Reader lines; the 2026-09-25 01:55 run lost the stream silently at tick 953, so a closed stream is now
        logged (exit code + stderr) and the reader restarted, at most 3 times -- never after the match's own kill
        (it restarted a sampler that outlived the match: verifier 2026-09-30)."""
        for attempt in range(4):
            with spawn_lock:                             # the `finally` sets `stopping` under the same lock
                if stopping.is_set():
                    return
                p = subprocess.Popen(ADB + ["shell", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                     env=ENV)
                procs.append(p)
            yield from p.stdout
            if stopping.is_set():
                return
            try:
                rc = p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rc = None
            W(event="reader_closed", attempt=attempt, rc=rc, stderr=(p.stderr.read() or "")[-500:],
              last_tick=last_tick)
            time.sleep(0.5)
        W(event="stop", why="reader_closed_4x")

    t0, pending, fails, played, confirmed, last_tick, last_adv = time.time(), None, 0, 0, 0, -1, time.time()
    fails_run = 0   # CONSECUTIVE unconfirmed taps: 5 in a row = real malfunction (5 slow taps over a match under load is not)
    seen_active, both_vis, warmed, waiting_logged = False, 0, False, False
    from collections import deque
    dec_times: deque = deque(maxlen=20)
    warned_at = 0.0
    last_audit_tick = -10
    # 2026-09-25 18:32 friendly match: the reader stream stalled for up to 5.4 s (adb saturated by the hero-button
    # screenshots, ~330-430 ms each every 0.5 s), then the loop worked through the backlog IN ORDER and decided on
    # frames up to ~20 s old -> long "pending" leaks, then dumps. Now a thread pumps the stream into a queue; every
    # frame still feeds the counter / log / confirmations in order, but the model only DECIDES on the newest frame.
    q: queue.Queue = queue.Queue()

    def pump():
        for ln in stream():
            q.put(ln)
        q.put(None)
    pump_t = threading.Thread(target=pump, daemon=True)
    pump_t.start()
    try:
        while True:
            try:
                line = q.get(timeout=1.0)                # a silent reader must not hang the start / stall checks
            except queue.Empty:
                line = ""
            if line is None:
                break
            newest = q.empty()                           # decide only on the newest frame available
            now = time.time()
            if guard and guard.menu:                     # the screen shows a menu: no further taps, ever
                print(f"[live] menu screen {guard.menu!r} during the match -- stopping it", flush=True)
                W(event="stop", why=f"menu_screen:{guard.menu}", last_tick=last_tick); break
            if guard and guard.blind_s(now) > GUARD_BLIND_S:  # screenshots keep failing: we cannot see the screen
                print(f"[live] menu guard blind for {guard.blind_s(now):.0f} s -- stopping the match", flush=True)
                W(event="stop", why="guard_blind", blind_s=round(guard.blind_s(now), 1), last_tick=last_tick); break
            if now - t0 > a.max_seconds:
                live = last_tick >= 0 and now - last_adv <= 3        # clock still running: a cap, not an end
                print(f"[live] --max-seconds {a.max_seconds:.0f} hit at tick {last_tick} "
                      f"({'battle clock STILL ADVANCING -- capped mid-match' if live else 'clock not advancing'}); "
                      f"stopping the run", flush=True)
                W(event="stop", why="max_seconds", clock_advancing=live, last_tick=last_tick,
                  max_seconds=a.max_seconds); break
            if start_timeout and last_tick < 0 and now - t0 > start_timeout:
                W(event="stop", why="no_battle_start"); break
            if not line:
                if last_tick >= 0 and now - last_adv > READER_SILENT_S:
                    W(event="stop", why="reader_silent", last_tick=last_tick); break
                continue
            try:
                f = json.loads(line)
            except ValueError:
                continue
            if not (f.get("battle_active") and f.get("coherent")):
                if seen_active and now - last_adv > 3:
                    W(event="stop", why="battle_inactive"); break
                continue
            tick = int(f["game_tick"])
            verdict = clock_verdict(tick, last_tick, now - last_adv)
            if verdict == "wait":                        # battle clock still at 0: no decisions, no stall clock
                if not waiting_logged:
                    print("[live] battle clock at tick 0 -- waiting for the match to start", flush=True)
                    W(event="waiting_clock", tick=tick)
                    waiting_logged = True
                continue
            if verdict == "stall":
                W(event="stop", why="tick_stalled", tick=tick); break
            # only a frame whose clock MOVED since an earlier frame of THIS match may decide / tap: a frozen battle
            # object (stale reader) can never produce an input -- not even its first frame (last_tick starts at -1)
            advanced = last_tick >= 0 and tick > last_tick
            if tick > last_tick:
                last_tick, last_adv = tick, now
            seen_active = True
            if guard and not guard.armed:                # the clock runs: from now on any menu on screen stops us
                guard.arm()
            # Both hands visible = the results / replay screen (upstream mumu_live_controller never controls then).
            # 2026-09-25: deciding on such a frame raised in my_side_of and killed the run before the overlay render.
            vis = [p["side"] for p in f["players"] if any(i >= 0 for i in p["hand_deck_indices"])]
            if len(vis) != 1:
                both_vis += 1
                if both_vis >= 20:                       # ~2 s of it: the match is over
                    W(event="stop", why="battle_over_hands_visible", tick=tick); break
                continue
            both_vis = 0
            opp_est = pilot.observe(f)                   # public-events opp-elixir counter: EVERY active+coherent frame
            if not warmed:                               # the first CUDA forward took 1.6 s (2026-09-26 22:04) -- pay it
                try:                                     # before the 150-tick input guard, not on the first real play
                    pilot.decide(f)
                except Exception:                        # noqa: BLE001 -- warm-up only; the real decision retries
                    pass
                pilot.last_play_tick = None              # the anti-leak clock starts at the first REAL decision
                warmed = True
            if tick < UI_READY_MIN_TICK:
                continue
            side = next(p["side"] for p in f["players"] if any(i >= 0 for i in p["hand_deck_indices"]))
            me = next(p for p in f["players"] if p["side"] == side)
            t_dev = f["sample_monotonic_us"] / 1e6
            if rec:                                          # what the model perceived, for overlay_replay.py
                opp = next(p for p in f["players"] if p["side"] != side)
                # ents: side, x, y, card_id, hp, max_hp, kind, address (address/kind = the opp-elixir counter's play
                # detection). opp_elixir_true_EVAL_ONLY grades that counter offline; it is never fed to the model.
                W(event="frame", t_dev=t_dev, tick=tick, my_side=side, elixir=me["elixir_raw"] / 1e4, backlog=q.qsize(),
                  opp_elixir_true_EVAL_ONLY=opp["elixir_raw"] / 1e4, opp_elixir_est=opp_est,
                  ents=[[e["side"], e["x"], e["y"], e["card_id"], e["hp"], e["max_hp"], e["kind"], e["address"]]
                        for e in f["entities"]])
            hids = hero_ids(me)
            if button:                                   # screenshot only after the hero was played (not in hand)
                button.want = bool(hids) and any(i not in me["hand_deck_indices"] for i, fl in
                                                 enumerate(me.get("deck_form_flags") or []) if int(fl) == 2)
            if button and hids:
                st = button.fresh_state()
                if st != last_bstate:                    # every transition logged: the calibration evidence
                    W(event="button", tick=tick, state=st, blue=round(button.blue, 3), grey=round(button.grey, 3))
                    last_bstate = st
                if ab_pending:
                    spent = ab_pending["elixir_raw"] - me["elixir_raw"]
                    moved = button.ts > ab_pending["t"] + 0.3 and st in ("grey", "absent")
                    if spent > 0 or moved:
                        W(event="ability_confirmed", tick=tick, elixir_drop=spent / 1e4, button_after=st,
                          latency_s=round(now - ab_pending["t"], 3))
                        for hid in hids:    # gen_v3.1 own-ability readiness = own CONFIRMED presses (no-op for v1-v3)
                            pilot.record_ability(_catalog_names().get(int(hid), str(hid)), ab_pending["tick"])
                        ab_pending = None
                    elif tick - ab_pending["tick"] > CONFIRM_TICKS:
                        W(event="ability_unconfirmed", tick=tick, button_after=st)
                        ab_pending = None
                elif st == "ready" and not pending and newest and advanced and guard_clear():
                    press, why = should_press(f, side, hids, pilot=None if a.no_iw_pro_gate else pilot)
                    if press:
                        W(event="ability", tick=tick, t_dev=t_dev, why=why, tap=list(button.point),
                          elixir=me["elixir_raw"] / 1e4)
                        if not a.dry_run and guard_clear():
                            if not input_cmd(f"input tap {button.point[0]} {button.point[1]}"):
                                W(event="stop", why="tap_timeout", tick=tick, input="ability"); break
                            ab_pending = {"t": now, "tick": tick, "elixir_raw": me["elixir_raw"]}
            if pending:
                old = pending["me"]
                pos = pending["d"]["hand_pos"]
                rotated = me["hand_deck_indices"][pos] != old["hand_deck_indices"][pos]
                dropped = old["elixir_raw"] - me["elixir_raw"]     # logged only: regen during the ~28-tick landing
                if rotated:   # (~1 elixir in 2x, ~1.5 in 3x) outgrows a Skeletons' cost, so "elixir dropped" missed
                    # 16 of 23 real plays and stopped matches (L68 2026-09-29); a slot rotates only when its card is played
                    d = pending["d"]
                    cid = me["deck_card_ids"][d["deck_index"]]
                    new = [e for e in f["entities"] if e["side"] == side and e["card_id"] == cid
                           and e["address"] not in pending["addrs"]]
                    err = None
                    if new:
                        ex, ey = my_frame_xy(new[0], side)
                        err = round(((ex - d["xy"][0]) * 18) ** 2 + ((ey - d["xy"][1]) * 32) ** 2, 4) ** 0.5
                    # stamp the LANDING time (this confirmation frame), as training rows do -- the decision frame's
                    # time made the model's "seconds since my play" ~1.3 s too large (T9 worker finding, 2026-09-25)
                    pilot.record_play(d["card"], d["form"], d["xy"], tick * 0.05)
                    confirmed += 1
                    fails_run = 0
                    W(event="confirmed", tick=tick, name=d["name"], intended=d["xy"], elixir_drop=dropped / 1e4,
                      spawn=[my_frame_xy(e, side) for e in new[:1]], err_tiles=err, latency_s=round(now - pending["t"], 3))
                    pending = None
                elif tick - pending["tick"] > CONFIRM_TICKS:
                    fails += 1
                    fails_run += 1
                    W(event="unconfirmed", tick=tick, name=pending["d"]["name"], intended=pending["d"]["xy"],
                      p_play=pending["d"]["p_play"], elixir=old["elixir_raw"] / 1e4, fails=fails)
                    pending = None
                    if fails_run >= 5:
                        W(event="stop", why="5_unconfirmed"); break
                continue
            if not newest or not advanced:               # stale frame: newer ones queued / the clock did not move
                continue
            t_dec = time.time()
            d = pilot.decide(f)
            decide_ms = round((time.time() - t_dec) * 1000)
            dec_times.append(decide_ms)
            # 2026-09-26: every bad live match that evening ran with the CPU loaded (training / screens / low-battery
            # throttle): decisions took 176-347 ms instead of ~40 ms, the loop fell behind, the bot leaked. Say so.
            if len(dec_times) >= 10 and sorted(dec_times)[len(dec_times) // 2] > 100 and now - warned_at > 30:
                msg = (f"CPU-STARVED: median decision {sorted(dec_times)[len(dec_times) // 2]} ms over the last "
                       f"{len(dec_times)} decisions (normal ~40 ms), backlog {q.qsize()} frames -- close heavy jobs "
                       f"(training, screens) and plug in; play quality will be poor until then")
                print(msg, flush=True)
                W(event="cpu_starved", tick=tick, median_decide_ms=sorted(dec_times)[len(dec_times) // 2],
                  backlog=q.qsize())
                warned_at = now
            el = me["elixir_raw"] / 1e4
            # forced = the anti-leak played although the gate said wait (SIM why == 'stall'); False when it is off
            forced = bool(d["play"] and d.get("stalled") and d["p_play"] <= d.get("gate_tau", pilot.gate_tau))
            if a.public_audit and (d['play'] or tick-last_audit_tick >= 10):
                W(event='decision', tick=tick, t_dev=t_dev, decide_ms=decide_ms,
                  backlog=q.qsize(), forced=forced,
                  decision={k:d[k] for k in ('play','p_play','no_affordable','hand_pos','name','card','form','xy','gate_tau',
                                             'xy_unguarded','stalled') if k in d},
                  public=d['public_audit'])
                last_audit_tick = tick
            if not d["play"]:
                continue
            if not guard_clear():                        # the guard has not (freshly) seen a battle screen
                if not blocked_logged:
                    W(event="tap_blocked", tick=tick, name=d["name"], why="menu guard not clear",
                      guard_ok_age_s=None if guard.ok_ts is None else round(time.time() - guard.ok_ts, 1))
                    blocked_logged = True
                continue
            blocked_logged = False
            hand, board = lay.hand(d["hand_pos"]), lay.board(d["xy"], side, even=d["name"] in EVEN_BUILDINGS)
            W(event="play", tick=tick, t_dev=t_dev, name=d["name"], p_play=round(d["p_play"], 4), forced=forced, elixir=el,
              hand_pos=d["hand_pos"], xy=[round(v, 4) for v in d["xy"]], tap_hand=hand, tap_board=board)
            played += 1
            if a.dry_run or not guard_clear():           # re-checked right before the input
                continue
            t_tap = time.time()
            if not input_cmd(f"input tap {hand[0]} {hand[1]}; sleep 0.05; input tap {board[0]} {board[1]}"):
                print("[live] an input tap timed out -- no more taps this match (it may still land late)", flush=True)
                W(event="stop", why="tap_timeout", tick=tick, tap_ms=round((time.time() - t_tap) * 1000)); break
            W(event="tap_timing", tick=tick, decide_ms=decide_ms, tap_ms=round((time.time() - t_tap) * 1000),
              frame_age_backlog=q.qsize())
            pending = {"d": d, "me": me, "t": now, "tick": tick, "addrs": {e["address"] for e in f["entities"]}}
    finally:
        with spawn_lock:
            stopping.set()                               # the pump may not start another sampler from here on
        if guard:
            guard.stop()
        for p in procs:
            p.terminate()
        for i, to in enumerate((5, 15)):                 # F2: a saturated adb timed this out -> one longer retry
            try:
                adb("shell", "pkill -f live_sampler", timeout=to, strict=True)
                break
            except subprocess.TimeoutExpired:
                if i:
                    W(event="sampler_kill_failed", why="pkill -f live_sampler timed out twice (5 s, 15 s)")
        pump_t.join(timeout=10)                          # no sampler / pump of this match survives into the next
        if button:
            button.stop()
        if rec:
            W(event="recording", segments=rec.stop())
        W(event="end", played=played, confirmed=confirmed, fails=fails, seconds=round(time.time() - t0, 1))
        log.close()
        print(json.dumps({"played": played, "confirmed": confirmed, "fails": fails, "log": log.name}))
        if rec and clip_caption is not None:             # owner 2026-10-06: restore the 60-s Discord clip (Codex removed it)
            try:
                p = subprocess.Popen([sys.executable, str(HERE / "discord_clip.py"), log.name, "--caption", clip_caption,
                                      "--overlay", a.overlay],
                                     env=dict(ENV, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2"),
                                     creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
                if renders is not None:
                    renders.append((p, log.name))
                elif p.wait():
                    print(f"[clip] failed (exit {p.returncode}); retry: discord_clip.py {log.name}")
            except Exception as exc:                     # noqa: BLE001 -- never mask the original error
                print(f"[clip] could not start: {exc!r}")
        elif rec and renders is not None:                # a next match follows: render in a separate low-priority
            try:                                         # process (no GIL/CPU fight with its decisions)
                renders.append((subprocess.Popen(   # detector on the CPU (2 threads): the GPU is the next match's
                    [sys.executable, str(HERE / "overlay_replay.py"), log.name, "--overlay", a.overlay],
                    env=dict(ENV, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="2"),
                    creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)), log.name))
            except Exception as exc:                     # noqa: BLE001 -- never mask the original error
                print(f"[overlay] render failed: {exc!r}; re-render with overlay_replay.py {log.name}")
        elif rec:                                        # in `finally`: a crash above must not lose the replay
            try:
                from overlay_replay import render
                render(Path(log.name), overlay=a.overlay)
            except Exception as exc:                     # noqa: BLE001 -- never mask the original error
                print(f"[overlay] render failed: {exc!r}; re-render with overlay_replay.py {log.name}")
    return stop["why"]


if __name__ == "__main__":
    raise SystemExit(main())
