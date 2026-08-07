r"""Re-cut the IN_MATCH screen template from your own recording.

Why this exists: the shipped `templates/in_match*.png` were cut from one specific
client -- one window shape, one interface language. On a differently sized window,
or a client that says "Restzeit" where the template says "Time left", the match
score never reaches the threshold, `detect_state` returns UNKNOWN for the whole
video, and everything downstream quietly produces nothing: `label` finds no plays,
`outcomes` no matches, `deck-detect` no cards.

Nothing about that needs guessing, because the recording already says which frames
were in a match: you only click while playing. So frames around your logged clicks
are in-match, frames far away from any click are not, and the template can be cut
from the region that (a) stays still during play and (b) differs most from the
non-match frames. That is language independent by construction -- it does not care
what the text says, only that this part of the screen looks like this while playing.

    .\\.venv\\Scripts\\python.exe run.py calibrate            # newest recording
    .\\.venv\\Scripts\\python.exe run.py calibrate --dry-run  # only report, write nothing
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

CAND_W = 96          # candidate template size at work scale (px)
CAND_H = 22
STRIDE = 6


def _latest_session(root: Path) -> Optional[Path]:
    found = [p for p in root.glob("*") if (p / "video.mp4").exists() or (p / "video.avi").exists()]
    return max(found, key=lambda p: p.name) if found else None


def _click_times(session: Path) -> List[float]:
    f = session / "events.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "click" and e.get("pressed") and e.get("t") is not None:
            out.append(float(e["t"]))
    return sorted(out)


def _frame_times(session: Path) -> List[float]:
    meta = session / "meta.json"
    if meta.exists():
        try:
            d = json.loads(meta.read_text(encoding="utf-8"))
            ft = d.get("frame_times")
            if ft:
                return [float(t) for t in ft]
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return []


def _grab(cap, idx: int):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
    ok, f = cap.read()
    return f if ok else None


def calibrate(cfg, session_arg: Optional[str] = None, dry_run: bool = False,
              near_s: float = 2.0, away_s: float = 2.0, lead_in_s: float = 15.0,
              max_frames: int = 40) -> None:
    from .vision import Vision

    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    session = Path(session_arg) if session_arg else _latest_session(root)
    if session is None or not Path(session).exists():
        print(f"[calibrate] no recording under {root}. Run `record` first.")
        return
    session = Path(session)
    video = next((session / n for n in ("video.mp4", "video.avi") if (session / n).exists()), None)
    if video is None:
        print(f"[calibrate] no video in {session}")
        return

    clicks = _click_times(session)
    if not clicks:
        print(f"[calibrate] {session.name} contains no logged clicks. Without them there is no way to tell "
              "which frames came from a match. Record a round in which you actually play.")
        return
    ftimes = _frame_times(session)
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if not ftimes:
        fps = cap.get(cv2.CAP_PROP_FPS) or 12.0
        ftimes = [i / fps for i in range(total)]
    n = min(total, len(ftimes))

    def near_click(t: float) -> float:
        return min(abs(t - c) for c in clicks)

    first, last = clicks[0], clicks[-1]
    # Positive: well INSIDE the match. The opening is skipped because the menu and the
    # loading screen sit between the Battle click and the first move. Pauses in the MIDDLE
    # of a match are not counterexamples: nobody plays a card every four seconds.
    # Negative: everything before the first click (menu) and after the last (result screen).
    in_idx = [i for i in range(n)
              if ftimes[i] >= first + lead_in_s and near_click(ftimes[i]) <= near_s]
    out_idx = [i for i in range(n)
               if ftimes[i] < first - 0.2 or ftimes[i] > last + away_s]
    if len(in_idx) < 5 or len(out_idx) < 5:
        print(f"[calibrate] not enough material: {len(in_idx)} frames in a match, {len(out_idx)} "
              "outside one.")
        print("[calibrate] Best input: a recording that starts in the MENU, shows a full match and "
              "keeps running a few seconds past the result screen.")
        cap.release()
        return
    in_idx = [in_idx[i] for i in np.linspace(0, len(in_idx) - 1, min(max_frames, len(in_idx))).astype(int)]
    out_idx = [out_idx[i] for i in np.linspace(0, len(out_idx) - 1, min(max_frames, len(out_idx))).astype(int)]

    vision = Vision(cfg)
    ins = [vision._work(f) for f in (_grab(cap, i) for i in in_idx) if f is not None]
    outs = [vision._work(f) for f in (_grab(cap, i) for i in out_idx) if f is not None]
    cap.release()
    if not ins or not outs:
        print("[calibrate] could not read the frames.")
        return

    print(f"[calibrate] {session.name}: {len(ins)} frames from the match (near your clicks), "
          f"{len(outs)} outside it. Working size {ins[0].shape[1]}x{ins[0].shape[0]}.", flush=True)

    # Wie gut schlagen sich die mitgelieferten Templates? Das ist die Diagnose.
    before = sum(1 for f in ins if vision.detect_state(_upscale(f)).name == "IN_MATCH")
    best_shipped = 0.0
    for name in ("in_match.png", "in_match_v2.png"):
        tm = vision._templates.get(name)
        if tm is None:
            continue
        for f in ins[:10]:
            if f.shape[0] >= tm.shape[0] and f.shape[1] >= tm.shape[1]:
                best_shipped = max(best_shipped, float(cv2.matchTemplate(
                    f, tm, cv2.TM_CCOEFF_NORMED).max()))
    thr = float((cfg.get("states", "in_match", default={}) or {}).get("threshold", 0.8))
    print(f"[calibrate] shipped templates: best score {best_shipped:.3f} against threshold {thr:.2f} "
          f"-> {before}/{len(ins)} match frames recognised", flush=True)

    gi = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in ins])
    go = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32) for f in outs])
    mean_in, std_in, mean_out = gi.mean(0), gi.std(0), go.mean(0)
    H, W = mean_in.shape
    if H < CAND_H or W < CAND_W:
        print("[calibrate] frame smaller than the search window.")
        return

    # Wanted: a window that stays still DURING the match (low spread) and differs clearly
    # from the non-match frames. Integral images keep the search from taking forever.
    diff = np.abs(mean_in - mean_out)
    s_diff = cv2.integral(diff)
    s_std = cv2.integral(std_in)
    s_var = cv2.integral(cv2.Laplacian(mean_in, cv2.CV_32F) ** 2)   # structure, not an empty surface

    def box(sumimg, y, x):
        return float(sumimg[y + CAND_H, x + CAND_W] - sumimg[y, x + CAND_W]
                     - sumimg[y + CAND_H, x] + sumimg[y, x]) / (CAND_W * CAND_H)

    # First stage: a rough shortlist. A region is only useful if it differs from the menu
    # AND stays still while playing. The arena itself does not, which is why movement
    # enters the score squared.
    cands = []
    for y in range(0, H - CAND_H, STRIDE):
        for x in range(0, W - CAND_W, STRIDE):
            d, s, v = box(s_diff, y, x), box(s_std, y, x), box(s_var, y, x)
            if v < 5.0:                       # too flat, it would match anywhere
                continue
            cands.append((d / (1.0 + s) ** 2, y, x, d, s, v))
    if not cands:
        print("[calibrate] no usable region found.")
        return
    cands.sort(reverse=True)

    # Second stage: actually measure the shortlist. What matters is the DISTANCE between
    # the worst match frame and the best non-match frame; only that yields a threshold
    # which holds in both directions.
    gi_u = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in ins]
    go_u = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in outs]
    probe_in, probe_out = gi_u[::max(1, len(gi_u) // 10)], go_u[::max(1, len(go_u) // 10)]

    def separation(y, x, pin, pout):
        ref = mean_in[y:y + CAND_H, x:x + CAND_W].astype(np.uint8)
        si = [float(cv2.matchTemplate(f, ref, cv2.TM_CCOEFF_NORMED).max()) for f in pin]
        so = [float(cv2.matchTemplate(f, ref, cv2.TM_CCOEFF_NORMED).max()) for f in pout]
        return min(si) - max(so), si, so

    scored = []
    for _pre, y, x, d, s, v in cands[:120]:
        m, si, _so = separation(y, x, probe_in, probe_out)
        scored.append((m, min(si), y, x, d, s, v))
    # A narrow margin is not enough: the region has to be hit clearly by EVERY match frame,
    # otherwise the smallest deviation flips the detection. So among the candidates with a
    # safe margin, take the one whose worst hit is highest.
    safe = [c for c in scored if c[0] >= 0.15]
    pick = max(safe, key=lambda c: c[1]) if safe else max(scored, key=lambda c: c[0])
    margin, worst_hit, y, x, d, s, v = pick
    print(f"[calibrate] best region at x={x} y={y} ({CAND_W}x{CAND_H}): "
          f"difference from the menu {d:.1f}, movement during play {s:.1f}, separation {margin:+.3f}",
          flush=True)

    ref_gray = mean_in[y:y + CAND_H, x:x + CAND_W].astype(np.uint8)
    med = ins[len(ins) // 2][y:y + CAND_H, x:x + CAND_W].copy()
    _m, sc_in, sc_out = separation(y, x, gi_u, go_u)
    # A single in-match frame is allowed to be an outlier (a card icon in the way, an
    # emote): hence the 10th-percentile. For the non-match frames the HIGHEST value
    # counts instead, because a false positive would let the bot start playing in a menu.
    lo_in = float(np.quantile(sc_in, 0.10))
    hi_out = max(sc_out)
    print(f"[calibrate] new region: match frames {min(sc_in):.3f}..{max(sc_in):.3f} "
          f"(10th percentile {lo_in:.3f}), non-match {min(sc_out):.3f}..{max(sc_out):.3f}",
          flush=True)
    if lo_in <= hi_out + 0.03:
        print("[calibrate] The two groups are too close together for a safe threshold, "
              "so nothing was written.")
        print("[calibrate] This works most reliably with a recording that starts in the menu, "
              "shows a full match and keeps running past the result screen.")
        return
    new_thr = round(hi_out + 0.5 * (lo_in - hi_out), 2)
    hit = sum(1 for vv in sc_in if vv >= new_thr)
    print(f"[calibrate] threshold {new_thr:.2f}: hits {hit}/{len(sc_in)} match frames and "
          f"0/{len(sc_out)} non-match frames", flush=True)
    if dry_run:
        print("[calibrate] --dry-run: nothing was written.")
        return

    tdir = cfg.path("templates")
    tdir.mkdir(parents=True, exist_ok=True)
    out_png = tdir / "in_match_local.png"
    cv2.imwrite(str(out_png), med)
    from .config_edit import EditError, patch_scalar, backup
    import yaml
    cfg_path = cfg.path("config/config.yaml")
    text = cfg_path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    spec = dict(data.get("states", {}).get("in_match", {}) or {})
    tpls = list(spec.get("templates") or ([spec["template"]] if spec.get("template") else []))
    entry = {"template": "in_match_local.png", "threshold": float(new_thr)}
    tpls = [t for t in tpls if not (isinstance(t, dict) and t.get("template") == "in_match_local.png")]
    tpls.insert(0, entry)                     # eigener Ausschnitt zuerst
    spec["templates"] = tpls
    spec.pop("template", None)
    data["states"]["in_match"] = spec
    try:
        new_text = _write_states_block(text, spec)
        yaml.safe_load(new_text)
    except (EditError, yaml.YAMLError) as exc:
        print(f"[calibrate] the config could not be written safely ({exc}). "
              f"The region is saved at {out_png}; add it under states.in_match by hand.")
        return
    bak = backup(cfg_path, cfg.path("data/config_backups"))
    cfg_path.write_text(new_text, encoding="utf-8")
    print(f"[calibrate] {out_png.name} saved and registered in config.yaml under states.in_match "
          f"(backup: {Path(bak).name}).")
    print("[calibrate] Check: `run.py label --all` should now find far more samples.")


def _upscale(work):
    return work


def _write_states_block(text: str, spec: dict) -> str:
    """Replace the states.in_match block, keeping the rest of the file byte for byte."""
    lines = text.split("\n")
    head = None
    for i, ln in enumerate(lines):
        if ln.startswith("  in_match:") or ln.startswith("  in_match: "):
            head = i
            break
    if head is None:
        raise ValueError("states.in_match not found")
    j = head + 1
    while j < len(lines):
        ln = lines[j]
        if ln.strip() and not ln.startswith("    ") and not ln.lstrip().startswith("#"):
            break
        j += 1
    block = ["  in_match:", f"    threshold: {spec.get('threshold', 0.8)}", "    templates:"]
    for t in spec["templates"]:
        if isinstance(t, dict):
            inner = ", ".join(f"{k}: {json.dumps(v) if isinstance(v, str) else v}"
                              for k, v in t.items())
            block.append(f"      - {{{inner}}}")
        else:
            block.append(f'      - "{t}"')
    return "\n".join(lines[:head] + block + lines[j:])
