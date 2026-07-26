"""Mine recorded sessions for reactive-play patterns.

Answers: *which card do you play against which kind of enemy threat, and where?*
For every card play (paired from your click stream by :func:`label._extract_plays`),
this reads the enemy threat in a short window ending at the play -- the push you were
reacting to -- classifies it by colour / size / count / lane / depth / speed and any
projectile in flight (see :mod:`clashrl.threats`), notes WHERE you placed the card
relative to the threat and the towers, and aggregates it all.

Output: a readable report on stdout plus ``data/analysis/patterns.json`` (per-play
records + per-card summaries) that the training phase consumes to bias the policy
toward your habits.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

import cv2

from .label import _extract_plays, _load
from .reward import _anchors
from .threats import ThreatTracker, Threat, annotate
from .vision import Vision


def _near(nx, ny, ax, ay, r=0.12) -> bool:
    return abs(nx - ax) <= r and abs(ny - ay) <= r


def _placement_zone(nx: float, ny: float, thr: Threat, cfg) -> str:
    """Classify WHERE a card was played relative to the towers + the threat."""
    mine_a, enemy_a, _ = _anchors(cfg)
    if len(enemy_a) >= 2 and (_near(nx, ny, *enemy_a[0]) or _near(nx, ny, *enemy_a[1])):
        return "enemy_princess"
    if len(enemy_a) >= 3 and _near(nx, ny, *enemy_a[2]):
        return "enemy_king"
    if len(mine_a) >= 3 and _near(nx, ny, *mine_a[2], r=0.10):
        return "my_king"
    if len(mine_a) >= 2 and (_near(nx, ny, *mine_a[0], r=0.10) or _near(nx, ny, *mine_a[1], r=0.10)):
        return "my_princess"
    if thr.centroid is not None:
        cx, cy = thr.centroid
        if abs(nx - cx) <= 0.14 and abs(ny - cy) <= 0.14:
            return "on_threat"
        if ny > cy + 0.05:                      # deeper than the threat = between it and your king
            return "behind_threat"
    lane = "left" if nx < 0.37 else "right" if nx > 0.63 else "center"
    half = "my_half" if ny >= 0.5 else "enemy_half"
    return f"{half}_{lane}"


def _window_threat(cap, fi: int, times, cfg, window: int):
    """Threat at the play instant + the peak push in the preceding window + any
    projectile seen in flight during the window."""
    tk = ThreatTracker(cfg)
    start = max(0, fi - window)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    at: Optional[Threat] = None
    peak: Optional[Threat] = None
    proj = None
    for k in range(start, fi + 1):
        ok, frame = cap.read()
        if not ok:
            break
        t = times[k] if k < len(times) else k / 12.0
        thr = tk.update(frame, t)
        at = thr
        if peak is None or thr.my_side_mass > peak.my_side_mass:
            peak = thr
        if thr.proj is not None and (proj is None or thr.proj.toward_tower):
            proj = thr.proj
    return at, peak, proj


def analyze_session(cfg, session: Path, window: int, debug: bool, records: list) -> int:
    meta, events, video = _load(session)
    if video is None:
        print(f"[analyze] no video in {session.name}")
        return 0
    region = meta["region"]
    times = meta["frame_times"]
    import bisect

    slots = cfg.get("hand", "slots", default=[])
    click_r = float(cfg.get("hand", "click_radius", default=0.06))
    pair_timeout = float(cfg.get("label", "pair_timeout", default=3.0))
    a_top = float(cfg.get("label", "arena_top", default=0.10))
    a_bot = float(cfg.get("label", "arena_bottom", default=0.86))
    plays = _extract_plays(events, region, slots, click_r, pair_timeout, a_top, a_bot)

    vision = Vision(cfg)
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    dbg_dir = session / "analyzed"
    if debug:
        dbg_dir.mkdir(exist_ok=True)
    n = 0
    for k, p in enumerate(plays):
        fi = max(0, min(bisect.bisect_left(times, p["t"]), max(total - 1, 0)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        hand_ids = vision.recognize_hand(frame)
        card = hand_ids[p["slot"]] if 0 <= p["slot"] < len(hand_ids) else -1
        if card < 0:
            continue
        name = vision.deck_keys[card] if card < len(vision.deck_keys) else f"card{card}"
        at, peak, proj = _window_threat(cap, fi, times, cfg, window)
        if at is None:
            continue
        zone = _placement_zone(p["nx"], p["ny"], at, cfg)
        rec = {
            "session": session.name, "t": round(p["t"], 2), "card": name,
            "nx": round(p["nx"], 3), "ny": round(p["ny"], 3), "zone": zone,
            "threat": at.type_label(), "peak_threat": peak.type_label() if peak else "quiet",
            "size": at.size_label(), "color": at.color_label(), "lane": at.lane_label(),
            "depth": round(at.depth, 2), "speed": at.speed_label(),
            "my_side_mass": round(at.my_side_mass, 4), "count": at.count,
            "siege": bool(at.siege), "behind_mass": round(at.behind_mass, 4),
            "projectile": None if proj is None else {"target": proj.target,
                                                     "toward_tower": proj.toward_tower},
        }
        records.append(rec)
        n += 1
        if debug:
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, f = cap.read()
            if ok:
                img = annotate(f, at, cfg)
                cv2.putText(img, f"{name} -> {zone}", (8, img.shape[0] - 12),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.imwrite(str(dbg_dir / f"play_{k:03d}_{name}.png"), img)
    cap.release()
    print(f"[analyze] {session.name}: {len(plays)} plays -> {n} analyzed"
          + (f"  (annotated in {dbg_dir.name}/)" if debug else ""))
    return n


def _report(records: list) -> dict:
    """Aggregate per-card threat/placement habits and print a readable report."""
    per_card: dict = defaultdict(lambda: {"plays": 0, "threats": Counter(),
                                           "placements": Counter(), "projectile": 0})
    for r in records:
        c = per_card[r["card"]]
        c["plays"] += 1
        c["threats"][r["threat"]] += 1
        c["placements"][r["zone"]] += 1
        if r["projectile"] is not None:
            c["projectile"] += 1

    proactive = sum(1 for r in records if r["threat"] == "quiet")
    print("\n" + "=" * 68)
    print(f"REPLAY ANALYSIS  --  {len(records)} plays  "
          f"({len(records) - proactive} reactive, {proactive} proactive)")
    print("=" * 68)
    for name, c in sorted(per_card.items(), key=lambda kv: -kv[1]["plays"]):
        print(f"\n{name}  ({c['plays']} plays)")
        threats = ", ".join(f"{t}×{n}" for t, n in c["threats"].most_common(5))
        places = ", ".join(f"{z}×{n}" for z, n in c["placements"].most_common(4))
        print(f"    vs threats : {threats}")
        print(f"    placed     : {places}")
        if c["projectile"]:
            print(f"    * {c['projectile']} play(s) responded to a projectile in flight")

    # foresight highlights: reactions to a projectile, a sitting behind-bridge siege, or a fast/deep push
    hi = [r for r in records if r["projectile"] is not None or r.get("siege")
          or (r["speed"] == "fast" and r["depth"] >= 0.4)]
    if hi:
        print("\n" + "-" * 68)
        print("FORESIGHT MOMENTS (projectile / siege / fast deep push -> your response):")
        for r in hi[:20]:
            tag = " proj->{}".format(r["projectile"]["target"]) if r["projectile"] else (" SIEGE" if r.get("siege") else "")
            print(f"  t={r['t']:>6}  {r['card']:<16} {r['threat']:<22} -> {r['zone']}{tag}")

    summary = {name: {"plays": c["plays"], "threats": dict(c["threats"]),
                      "placements": dict(c["placements"]), "projectile": c["projectile"]}
               for name, c in per_card.items()}
    return summary


def analyze(cfg, session_arg=None, do_all=False, window=12, debug=False) -> None:
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    if do_all:
        sessions = sorted(p for p in root.glob("*") if (p / "meta.json").exists())
    else:
        from .label import _latest_session
        one = Path(session_arg) if session_arg else _latest_session(root)
        sessions = [one] if one else []
    if not sessions:
        print(f"[analyze] no sessions under {root}")
        return

    records: list = []
    for s in sessions:
        analyze_session(cfg, Path(s), window, debug, records)
    if not records:
        print("[analyze] no analyzable plays found.")
        return
    summary = _report(records)

    out_dir = cfg.path("data/analysis")
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "patterns.json"
    out.write_text(json.dumps({"cards": summary, "records": records}, indent=2), encoding="utf-8")
    print(f"\n[analyze] wrote {out} ({len(records)} play records)")
