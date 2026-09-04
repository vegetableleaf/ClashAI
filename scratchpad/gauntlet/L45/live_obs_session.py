"""Idle-gated, foreground-guarded LIVE OBSERVATION session (HANDOFF 5cr; owner rules 2026-09-03 21:1x).

Runs `train-rl` in-process on the LIVE-OBS yaml (epsilon 0, learning off, isolated checkpoint path) from a given
init checkpoint, for N completed matches, and stops between matches. Refuses to start unless the owner has been
idle >= --idle-min (GetLastInputInfo) and the Clash Royale window exists and can be brought to the foreground.
Aborts HARD if the foreground window is not Clash Royale for 3 consecutive polls (= the owner took the PC back).
Never navigates any other window. pyautogui FAILSAFE stays on (mouse to a corner aborts).
"""
import argparse, ctypes, ctypes.wintypes as w, glob, os, sys, threading, time, _thread
ROOT = r"C:\Users\benpe\ClashBot\icebow"
os.chdir(ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
u = ctypes.windll.user32; k32 = ctypes.windll.kernel32

def idle_seconds():
    class LII(ctypes.Structure): _fields_ = [("cbSize", w.UINT), ("dwTime", w.DWORD)]
    li = LII(); li.cbSize = ctypes.sizeof(LII); u.GetLastInputInfo(ctypes.byref(li))
    return (k32.GetTickCount() - li.dwTime) / 1000.0

def cr_hwnd(title_part="Clash Royale"):
    found = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(h, l):
        if u.IsWindowVisible(h):
            n = u.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u.GetWindowTextW(h, b, n + 1)
            if title_part in b.value and "Visual Studio" not in b.value and "Discord" not in b.value: found.append(h)
        return True
    u.EnumWindows(cb, 0); return found[0] if found else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", required=True); ap.add_argument("--matches", type=int, default=2)
    ap.add_argument("--config", default="data/bench/live_obs.yaml"); ap.add_argument("--idle-min", type=float, default=15.0)
    ap.add_argument("--tag", default="obs"); ap.add_argument("--force-idle", action="store_true")
    a = ap.parse_args()
    log = open(os.path.join(ROOT, "data", "bench", "live_obs", f"session_{a.tag}_{time.strftime('%Y%m%d_%H%M%S')}.log"), "a")
    def say(*x):
        s = time.strftime("%H:%M:%S ") + " ".join(str(i) for i in x); print(s, flush=True); log.write(s + "\n"); log.flush()
    idle = idle_seconds(); say(f"owner idle {idle/60:.1f} min (need {a.idle_min})")
    if idle < a.idle_min * 60 and not a.force_idle:
        say("REFUSED: owner not idle long enough"); return 2
    h = cr_hwnd()
    if not h: say("REFUSED: no Clash Royale window"); return 3
    if u.IsIconic(h): u.ShowWindow(h, 9)     # SW_RESTORE only when minimised: on a MAXIMIZED window it un-maximizes + moves it (5cr.8.5)
    u.SetForegroundWindow(h); time.sleep(0.3)
    if u.GetForegroundWindow() != h: say("REFUSED: could not bring Clash Royale to the foreground"); return 4
    r = w.RECT(); u.GetWindowRect(h, ctypes.byref(r)); say(f"CR hwnd ok, rect {r.left},{r.top},{r.right-r.left}x{r.bottom-r.top}; init {a.init}; matches {a.matches}")
    stats_dir = os.path.join(ROOT, "data", "reward_stats"); before = set(glob.glob(os.path.join(stats_dir, "live_*.jsonl")))
    t0 = time.time(); state = {"done": 0, "abort": None}
    def watcher():
        miss = 0
        while state["abort"] is None:
            time.sleep(2.0)
            fg = u.GetForegroundWindow()
            miss = miss + 1 if fg != h else 0
            if miss >= 3:
                state["abort"] = "foreground left Clash Royale (owner took over)"; say("ABORT:", state["abort"])
                _thread.interrupt_main(); time.sleep(1.0); _thread.interrupt_main(); return
            new = [f for f in glob.glob(os.path.join(stats_dir, "live_*.jsonl")) if f not in before]
            n = sum(sum(1 for _ in open(f)) for f in new) if new else 0
            if n != state["done"]:
                state["done"] = n; say(f"match {n} complete ({(time.time()-t0)/60:.1f} min)")
            if n >= a.matches:
                state["abort"] = "done"; say("stop requested between matches"); _thread.interrupt_main(); return
    threading.Thread(target=watcher, daemon=True).start()
    from clashrl.config import Config
    from clashrl.train_rl import train_rl
    cfg = Config.load(os.path.join(ROOT, a.config))
    # OBS DUMP: wrap env.step so every decision's observation (image + hand/next/elixir/threat vectors), the
    # chosen action, the EXECUTED action (after aim assists / wheels), reward and elixir are written to an npz
    # per session -- the sim/live comparison instrument (HANDOFF 5cr). Pure read-only hook on the live env.
    import numpy as np
    from clashrl import env as _envmod
    dump = {"obs": [], "hand": [], "next": [], "elixir_vec": [], "threat": [], "chosen": [], "exec": [],
            "reward": [], "elixir": [], "t": [], "match": []}
    _orig_step = _envmod.Env.step if hasattr(_envmod, "Env") else None
    _cls = next(c for n, c in vars(_envmod).items() if isinstance(c, type) and hasattr(c, "step") and hasattr(c, "_update_threat"))
    _orig_step = _cls.step
    dump_path = os.path.join(ROOT, "data", "bench", "live_obs", f"obs_{a.tag}_{time.strftime('%Y%m%d_%H%M%S')}.npz")
    def _step(self, action):
        pre = (np.array(self._last_obs, copy=True), self.hand_vec.copy(), self.next_vec.copy(),
               self.elixir_vec.copy(), self.threat_vec.copy(), float(self.elixir))
        out = _orig_step(self, action)
        # capture-region audit (5cr.8): s1b's main-loop reads were FROZEN (hand empty, elixir 9.19 x299) while the
        # perception thread's own capture saw the game -- log both regions every 50 decisions to catch a stale lock.
        if len(dump["t"]) % 50 == 0:
            _pr = getattr(getattr(self, "_ploop", None), "_region", None)
            say(f"regions: main {getattr(self.capture, 'region', None)} locked={getattr(self.capture, '_render_locked', None)} | perception {_pr} | hand_ids {getattr(self, 'hand_ids', None)} elixir {self.elixir}")
        ex = getattr(self, "_last_exec_action", None)
        dump["obs"].append(pre[0]); dump["hand"].append(pre[1]); dump["next"].append(pre[2])
        dump["elixir_vec"].append(pre[3]); dump["threat"].append(pre[4]); dump["elixir"].append(pre[5])
        dump["chosen"].append(np.array(tuple(action) if action is not None else (-1, -1, -1)))
        dump["exec"].append(np.array(tuple(ex) if ex is not None else (-1, -1, -1)))
        dump["reward"].append(float(out[1])); dump["t"].append(time.time()); dump["match"].append(state["done"])
        if len(dump["t"]) % 50 == 0:
            np.savez_compressed(dump_path, **{k: np.array(v) for k, v in dump.items()})
        return out
    _cls.step = _step
    # REGION RE-LOCK at match start (5cr.8.5, measured): a WindowCapture built while the MATCH_END screen shows locks
    # 38 px SHORT (its bottom band is dark -> _render_area's bottom-black-bar trim), and never re-scans after a
    # successful lock. On an in-match frame that short lock reads hand [-1,1,-1,-1] / next -1 / elixir 9.22 -- the
    # exact s1b/s3 "frozen" signature. So: whenever reset() sees IN_MATCH, re-scan BOTH captures (main loop +
    # perception thread) on the live match frame before the original reset reads anything. Launcher-only hook;
    # the env/perception code is untouched (the perception loop's cap_factory test hook exposes its capture).
    from clashrl import perception as _pmod
    from clashrl.states import GameState as _GS
    _orig_pinit = _pmod.PerceptionLoop.__init__
    def _pinit(self, *pa, **pk):
        _orig_pinit(self, *pa, **pk)
        if getattr(self, "_cap_factory", None) is None:
            from clashrl.capture import WindowCapture as _WC
            def _factory(_self=self):
                _self._cap_obj = _WC(_self._title, _self._region_cfg)
                return _self._cap_obj
            self._cap_factory = _factory
    _pmod.PerceptionLoop.__init__ = _pinit
    _orig_reset = _cls.reset
    def _reset(self, *ra, **rk):
        # reset() loops internally until IN_MATCH, so the relock has to sit on the grab INSIDE that loop: the first
        # frame that reads IN_MATCH triggers a re-scan of both captures and the frame is re-grabbed from the new region.
        done = {"v": False}
        orig_grab = self.capture.grab
        def grab():
            fr = orig_grab()
            try:
                if fr is not None and not done["v"] and self.vision.detect_state(fr) == _GS.IN_MATCH:
                    done["v"] = True
                    old = self.capture.region
                    self.capture.refresh_region()
                    pc = getattr(getattr(self, "_ploop", None), "_cap_obj", None)
                    pold = getattr(pc, "region", None)
                    if pc is not None:
                        pc.refresh_region()
                    say(f"relock at match start: main {old} -> {self.capture.region} locked={getattr(self.capture, '_render_locked', None)} | perception {pold} -> {getattr(pc, 'region', None)}")
                    fr2 = orig_grab()
                    if fr2 is not None:
                        fr = fr2
            except Exception as e:  # noqa: BLE001
                say(f"relock failed: {e!r}")
            return fr
        self.capture.grab = grab
        try:
            return _orig_reset(self, *ra, **rk)
        finally:
            self.capture.grab = orig_grab
            # STOP-PATH FIX (5cs): count match starts; once the Nth match is under way, make the env's
            # stop_requested() read True so the end-of-match "Play Again" tap is skipped (env.py) and the
            # next reset() returns None -> train_rl exits cleanly. Before this, the watcher only saw the
            # match in the stats jsonl AFTER the tap, so every session threw one ladder match.
            state["starts"] = state.get("starts", 0) + 1
            if state["starts"] >= a.matches and not state.get("stop_armed"):
                state["stop_armed"] = True
                _prev = self.stop_requested
                self.stop_requested = lambda: True if state.get("stop_armed") else (bool(_prev()) if _prev else False)
                say(f"match {state['starts']} is the last: stop armed (no Play Again re-queue at its end)")
    _cls.reset = _reset
    try:
        train_rl(cfg, init=a.init)
    except KeyboardInterrupt:
        say("train_rl interrupted")
    if dump["t"]:
        np.savez_compressed(dump_path, **{k: np.array(v) for k, v in dump.items()}); say(f"obs dump {len(dump['t'])} decisions -> {dump_path}")
    say(f"session end: {state['abort']}  matches {state['done']}  wall {(time.time()-t0)/60:.1f} min")
    return 0

if __name__ == "__main__":
    sys.exit(main())
