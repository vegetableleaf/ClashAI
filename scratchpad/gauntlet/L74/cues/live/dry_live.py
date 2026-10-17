"""Dry run of the REAL live entry (live_play.main: its parser, LIVE_OPTIONS, refusals, checkpoint resolution,
load_pilot) on RECORDED merged-reader frames, with every device path patched to raise (no ADB, no taps, no capture).

    python dry_live.py OUT.json LOG.jsonl [LOG ...] -- <live_play args, e.g. --ckpt X --cue-inputs on --device cpu>

play_match is replaced by a replay that does what the live loop does with the pilot (cues.observe on every line,
observe on every frame, decide from tick 150 on every 4th frame) and a TWIN pilot (same args, its cue rows forced
to 0 = cue-blind) on the same frames, to show how much the cues move the decisions. Below-normal priority, 1 thread.
"""
import ctypes
import json
import sys
import time
from pathlib import Path

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL
HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[5]
LR = REPO / "scratchpad/gauntlet/L68/live_reader"
sys.path[:0] = [str(LR), str(REPO), str(HERE)]
import live_play as lp                                     # noqa: E402
from logframes import full_frames                          # noqa: E402

out_path, rest = Path(sys.argv[1]), sys.argv[2:]
cut = rest.index("--")
logs, argv = rest[:cut], rest[cut + 1:]


def no_device(*a, **k):
    raise RuntimeError("dry_live: a device call was attempted")


lp.adb = no_device
lp.input_cmd = no_device
lp.subprocess.Popen = no_device
lp.screen_size = lambda: (900, 1600)
lp.other_live_plays = lambda procs=None: []


class NoCapture:
    KIND, mod, why, sha = "p3", None, "dry_live: no capture", ""

    def __init__(self, *a, **k):
        pass


lp.P2Capture = lp.P3Capture = NoCapture
import psutil                                               # noqa: E402
psutil.Process = lambda *a, **k: type("P", (), {"nice": lambda self, v: None})()
RESULT = {}


def replay(a, pilot, lay, device, renders, start_timeout=None, record=False, clip_caption=None):
    import numpy as np
    import torch
    torch.set_num_threads(1)
    from pipeline.model_gen import CUE_N
    twin = None
    if getattr(pilot, "cues", None) is not None:
        from pipeline.decision_options import config_from_args
        _, twin = lp.load_pilot(a, config_from_args(a))
        twin.cues.rows = lambda frame, prev, tok, mask, side: (np.zeros((len(tok), CUE_N), np.float32), dict(blind=True))
        torch.set_num_threads(1)
    res = RESULT.setdefault("logs", [])
    for log in logs:
        for p in (pilot, twin):
            if p is not None:
                p.reset_match()
        rows, n_fr, t_dec, t_twin = [], 0, 0.0, 0.0
        for i, f in enumerate(full_frames(log)):
            n_fr += 1
            for p in (pilot, twin):
                if p is None:
                    continue
                if getattr(p, "cues", None) is not None:
                    p.cues.observe(f)
                p.observe(f)
            if f["game_tick"] < lp.UI_READY_MIN_TICK or i % 4:
                continue
            t = time.perf_counter()
            d = pilot.decide(f)
            t_dec += time.perf_counter() - t
            r = dict(tick=f["game_tick"], play=bool(d["play"]), p=round(float(d["p_play"]), 4), hand_pos=d["hand_pos"],
                     name=d.get("name"), xy=d.get("xy"), cue=d.get("cue"))
            if twin is not None:
                t = time.perf_counter()
                e = twin.decide(f)
                t_twin += time.perf_counter() - t
                r.update(twin=dict(play=bool(e["play"]), p=round(float(e["p_play"]), 4), hand_pos=e["hand_pos"],
                                   name=e.get("name"), xy=e.get("xy")))
            rows.append(r)
        res.append(dict(log=Path(log).name, frames=n_fr, decisions=len(rows), ms_per_decision=round(1000 * t_dec / max(1, len(rows)), 1),
                        ms_per_twin=round(1000 * t_twin / max(1, len(rows)), 1), rows=rows))
        print(Path(log).name, n_fr, len(rows), flush=True)
    RESULT.update(ckpt=a.ckpt, sha=a.ckpt_sha256, cue_inputs=getattr(a, "cue_inputs", None), reader=a.reader,
                  cues_attached=getattr(pilot, "cues", None) is not None, feature_version=pilot.feature_version,
                  live_options=a.live_options.get("from_file"))
    return "battle_over_hands_visible"


lp.play_match = replay
sys.argv = ["live_play.py"] + argv
rc = lp.main()
RESULT["rc"] = rc
out_path.write_text(json.dumps(RESULT))
print("rc", rc, "->", out_path)
