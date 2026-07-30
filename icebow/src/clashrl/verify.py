"""Sanity-check a recorded session: overlay logged mouse clicks on video frames.

Confirms three things before we build the full labeler:
  1. the screen capture actually recorded the game,
  2. clicks are time-aligned to frames,
  3. screen->region coordinate mapping is correct (markers land where you tapped).
"""
from __future__ import annotations

import bisect
import json
from pathlib import Path

import cv2


def _latest_session(root: Path):
    sessions = [p for p in root.glob("*") if (p / "meta.json").exists()]
    return max(sessions, key=lambda p: p.name) if sessions else None


def _load_events(session: Path):
    path = session / "events.jsonl"
    events = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    return events


def verify(cfg, session_arg=None, towers=False, hand=False, spells=False, threats=False,
           clock=False, all_sessions=False) -> None:
    root = cfg.path(cfg.get("record", "out_dir", default="data/sessions"))
    if all_sessions:                          # run the requested overlay over EVERY recorded session
        sessions = sorted(p for p in root.glob("*") if (p / "meta.json").exists())
        if not sessions:
            print(f"[verify] no sessions found under {root}")
            return
        for s in sessions:
            print(f"\n[verify] ===== session {s.name} =====")
            verify(cfg, str(s), towers, hand, spells, threats, clock, all_sessions=False)
        return
    session = Path(session_arg) if session_arg else _latest_session(root)
    if session is None or not Path(session).exists():
        print(f"[verify] no session found under {root}")
        return
    session = Path(session)

    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    region = meta["region"]          # [left, top, w, h]
    frame_times = meta.get("frame_times", [])
    fps = float(meta.get("fps", 12))

    clicks = [e for e in _load_events(session)
              if e.get("type") == "click" and e.get("pressed")]

    video = next((session / n for n in ("video.mp4", "video.avi")
                  if (session / n).exists()), None)
    if video is None:
        print("[verify] no video found in session")
        return

    if towers:
        _verify_towers(cfg, session, meta, video)
        return
    if threats:
        _verify_threats(cfg, session, meta, video)
        return
    if hand:
        _verify_hand(cfg, session, video)
        return
    if spells:
        _verify_spells(cfg, session, video)
        return
    if clock:
        _verify_clock(cfg, session, meta, video)
        return

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_times[-1] if frame_times else (total / fps if fps else 0.0)

    inside = sum(1 for c in clicks
                 if 0 <= c["x"] - region[0] < region[2]
                 and 0 <= c["y"] - region[1] < region[3])

    out_dir = session / "annotated"
    out_dir.mkdir(exist_ok=True)
    saved = 0
    for i, c in enumerate(clicks):
        fi = bisect.bisect_left(frame_times, c["t"]) if frame_times else int(c["t"] * fps)
        fi = max(0, min(fi, max(total - 1, 0)))
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        fx, fy = c["x"] - region[0], c["y"] - region[1]
        cv2.drawMarker(frame, (fx, fy), (0, 0, 255), cv2.MARKER_TILTED_CROSS, 26, 2)
        cv2.circle(frame, (fx, fy), 18, (0, 255, 255), 2)
        cv2.putText(frame, f"click {i}  t={c['t']:.2f}s  ({c['button']})", (8, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.imwrite(str(out_dir / f"click_{i:03d}.png"), frame)
        saved += 1
    cap.release()

    eff_fps = (total / duration) if duration else 0.0
    print(f"[verify] session:  {session}")
    print(f"[verify] frames:   {total}   duration: {duration:.1f}s   effective fps: {eff_fps:.1f}")
    print(f"[verify] clicks:   {len(clicks)} (pressed)   inside game region: {inside}")
    print(f"[verify] saved {saved} annotated frames to {out_dir}")
    if clicks and inside == 0:
        print("[verify] WARNING: no clicks landed inside the region — check window.region / DPI.")


def _verify_spells(cfg, session: Path, video: Path) -> None:
    """Overlay enemy-troop-mass detection on in-match frames to calibrate the spell +
    patience rewards. Red tint = pixels counted as enemy troops; enemy_mass is the
    arena troop fraction. Tune env.arena_region / enemy_quiet_frac / spell_radius so
    troops read as red while towers and background do not.
    """
    from .reward import _ANCHOR_HALF, _anchors, _arena_region, _red_mask, enemy_mass
    from .vision import Vision

    vision = Vision(cfg)
    quiet = float(cfg.get("env", "enemy_quiet_frac", default=0.02))
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_dir = session / "annotated_spells"
    out_dir.mkdir(exist_ok=True)
    saved = 0
    for k in range(30):
        fi = int((k + 0.5) / 30 * total)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        if vision.detect_state(frame).name != "IN_MATCH":
            continue
        h, w = frame.shape[:2]
        m = enemy_mass(frame, cfg)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        red = _red_mask(hsv)
        _, enemy_a, _ = _anchors(cfg)
        for nx, ny in enemy_a:
            x0, x1 = int((nx - _ANCHOR_HALF[0]) * w), int((nx + _ANCHOR_HALF[0]) * w)
            y0, y1 = int((ny - _ANCHOR_HALF[1]) * h), int((ny + _ANCHOR_HALF[1]) * h)
            red[max(0, y0):y1, max(0, x0):x1] = 0
        frame[red > 0] = (0, 0, 255)                        # red = pixels counted as enemy troops
        ax0, ay0, ax1, ay1 = _arena_region(cfg)
        cv2.rectangle(frame, (int(ax0 * w), int(ay0 * h)), (int(ax1 * w), int(ay1 * h)), (0, 255, 255), 2)
        state = "QUIET" if m < quiet else "active"
        cv2.putText(frame, f"enemy_mass={m:.3f}  ({state}, quiet<{quiet})", (8, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imwrite(str(out_dir / f"spells_{fi:06d}.png"), frame)
        saved += 1
        if saved >= 16:
            break
    cap.release()
    print(f"[verify] spells: saved {saved} annotated in-match frames to {out_dir}")
    print("[verify] red = enemy-troop pixels (enemy_mass); yellow box = arena region. Tune "
          "env.arena_region / enemy_quiet_frac so troops read red (towers/background don't); "
          "the reward keys on the enemy-mass DROP at a spell's target.")


def _verify_clock(cfg, session: Path, meta: dict, video: Path) -> None:
    """Calibrate the 2x/3x elixir CLOCK badge. Samples in-match frames and reports the match score of
    templates/elixir_2x.png + elixir_3x.png, so you can confirm they FIRE on real double/triple-elixir
    frames (high score) and NOT on single-elixir frames (low). Writes annotated_clock/. If the badge
    templates don't exist yet, the clock falls back to TIME-based reading (works live, no calibration).
    """
    from .vision import Vision
    from .clock import ElixirClock

    vision = Vision(cfg)
    clock = ElixirClock(cfg, vision)
    x2, x3, thr = clock.x2_tpl, clock.x3_tpl, clock.badge_threshold

    def score(frame, name):
        tmpl = vision._templates.get(name) if name else None
        if tmpl is None:
            return None
        work = vision._work(frame)
        if work.shape[0] < tmpl.shape[0] or work.shape[1] < tmpl.shape[1]:
            return None
        return float(cv2.matchTemplate(work, tmpl, cv2.TM_CCOEFF_NORMED).max())

    if not ((x2 and x2 in vision._templates) or (x3 and x3 in vision._templates)):
        print(f"[verify] clock: no badge templates found (templates/{x2} , templates/{x3}).")
        print("[verify] clock: the reader will use TIME-based reading -- works live with NO calibration:")
        print(f"[verify] clock:   elapsed < {clock.double_t:.0f}s = 1x, < {clock.triple_t:.0f}s = 2x, else 3x.")
        print("[verify] clock: to make it screen-accurate, crop the on-screen x2 / x3 badge from a")
        print(f"[verify] clock:   double / triple-elixir frame -> templates/{x2} , templates/{x3}, then re-run.")
        return

    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_dir = session / "annotated_clock"
    out_dir.mkdir(exist_ok=True)
    saved = hits2 = hits3 = 0
    for k in range(40):
        fi = int((k + 0.5) / 40 * total)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok or vision.detect_state(frame).name != "IN_MATCH":
            continue
        s2, s3 = score(frame, x2), score(frame, x3)
        mult = 3 if (s3 is not None and s3 >= thr) else 2 if (s2 is not None and s2 >= thr) else 1
        hits2 += int(s2 is not None and s2 >= thr)
        hits3 += int(s3 is not None and s3 >= thr)
        txt = f"x{mult}"
        if s2 is not None:
            txt += f"  2x={s2:.2f}"
        if s3 is not None:
            txt += f"  3x={s3:.2f}"
        txt += f"  (thr {thr})"
        color = (0, 255, 0) if mult == 1 else (0, 165, 255) if mult == 2 else (0, 0, 255)
        cv2.putText(frame, txt, (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.imwrite(str(out_dir / f"clock_{fi:06d}.png"), frame)
        saved += 1
    cap.release()
    print(f"[verify] clock: saved {saved} annotated in-match frames to {out_dir}")
    print(f"[verify] clock: x2 badge crossed {thr} in {hits2} frame(s), x3 in {hits3}.")
    print("[verify] clock: the score should be HIGH only on real double/triple-elixir frames + LOW "
          "otherwise -- if it's always high or never fires, re-crop the badge or adjust elixir.badge_threshold.")


def _verify_hand(cfg, session: Path, video: Path) -> None:
    """Overlay hand-card recognition on in-match frames to calibrate identity actions.

    Green box = a deck card was recognized (its key + match score are shown); red =
    unrecognized. If cards are wrong or missing, rebuild templates with
    `run.py hand-templates` or tune hand.card_w / card_h / match_threshold.
    """
    from .vision import Vision

    vision = Vision(cfg)
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_dir = session / "annotated_hand"
    out_dir.mkdir(exist_ok=True)
    saved = 0
    for k in range(30):
        fi = int((k + 0.5) / 30 * total)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        if vision.detect_state(frame).name != "IN_MATCH":
            continue
        h, w = frame.shape[:2]
        for cx, cy in vision.hand_slots:
            idx, score = vision.match_card(vision.hand_crop(frame, cx, cy))
            x0, x1 = int((cx - vision.card_w) * w), int((cx + vision.card_w) * w)
            y0, y1 = int((cy - vision.card_h) * h), int((cy + vision.card_h) * h)
            name = vision.deck_keys[idx] if 0 <= idx < len(vision.deck_keys) else "?"
            color = (0, 200, 0) if idx >= 0 else (0, 0, 255)
            cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)
            cv2.putText(frame, f"{name} {score:.2f}", (x0, max(12, y0 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)
        if vision.next_slot:                 # next-card preview -- calibrate this box
            nx, ny = vision.next_slot
            x0, x1 = int((nx - vision.next_card_w) * w), int((nx + vision.next_card_w) * w)
            y0, y1 = int((ny - vision.next_card_h) * h), int((ny + vision.next_card_h) * h)
            if any(vision._next_tpls):
                nidx, nscore = vision.match_card(frame[max(0, y0):y1, max(0, x0):x1],
                                                 top_frac=vision.next_top_frac, tpls=vision._next_tpls)
                nname = vision.deck_keys[nidx] if 0 <= nidx < len(vision.deck_keys) else "?"
                label = f"next: {nname} #{nidx} {nscore:.2f}"
            else:
                nidx, label = -1, "next: (no templates/next - run hand-templates)"
            ncolor = (255, 255, 0) if nidx >= 0 else (0, 0, 255)   # cyan if recognized, red if not
            cv2.rectangle(frame, (x0, y0), (x1, y1), ncolor, 2)
            if vision.next_top_frac < 1.0:   # the region ABOVE this line is what gets matched
                yb = y0 + int((y1 - y0) * vision.next_top_frac)
                cv2.line(frame, (x0, yb), (x1, yb), ncolor, 1)
            cv2.putText(frame, label, (x0, max(12, y0 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, ncolor, 1)
        cv2.imwrite(str(out_dir / f"hand_{fi:06d}.png"), frame)
        saved += 1
        if saved >= 16:
            break
    cap.release()
    print(f"[verify] hand: saved {saved} annotated in-match frames to {out_dir}")
    print("[verify] green = recognized card (key + match score), red = unrecognized, "
          "cyan = next-card preview. Rebuild templates (`hand-templates`) or tune "
          "hand.card_w / card_h / match_threshold (or next_slot / next_card_w / next_card_h) if wrong.")


def _overlay_card_threats(out, frame, model, db, conf, card_profile, troop_red_mask) -> int:
    """Draw each detected unit's card identity + FULL KB attribute profile onto ``out``.

    Enemy units (red tint inside the box) are the threats -> drawn red with their
    counter-relevant attributes (roles: win_condition / siege / spell / air / swarm / tank /
    splash / death_damage / building_targeting) plus elixir / hp / dps / tower-damage; your
    own units are drawn blue. Best-effort -- only as accurate as the current detector.
    Returns the number of ENEMY units drawn.
    """
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    res = model.predict(frame, conf=conf, verbose=False)[0]
    enemies = 0
    for box, cls in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist()):
        x0, y0, x1, y1 = (int(v) for v in box)
        p = card_profile(db, model.names[int(cls)])
        sub = hsv[max(0, y0):y1, max(0, x0):x1]
        is_enemy = sub.size > 0 and float(troop_red_mask(sub).mean()) / 255.0 > 0.05
        enemies += is_enemy
        color = (40, 40, 235) if is_enemy else (235, 160, 40)
        cv2.rectangle(out, (x0, y0), (x1, y1), color, 2)
        cv2.putText(out, f"{p.name} [{','.join(p.roles())}]", (x0, max(10, y0 - 14)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1)
        stats = []
        if p.elixir is not None:
            stats.append(f"{p.elixir}e")
        if p.hitpoints is not None:
            stats.append(f"{p.hitpoints}hp")
        if p.dps is not None:
            stats.append(f"{p.dps}dps")
        if p.tower_damage is not None:
            stats.append(f"twr{p.tower_damage}")
        if p.attack_range:
            stats.append(p.attack_range)
        if stats:
            cv2.putText(out, " ".join(stats), (x0, max(22, y0 - 2)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    return enemies


def _verify_threats(cfg, session: Path, meta: dict, video: Path) -> None:
    """Overlay the enemy-threat read on in-match frames to calibrate reactive play.

    Two layers are drawn:
      * BEHAVIOURAL (always): green tint = enemy troops; the label shows the pixel-classified
        threat type (colour / size / count / lane / depth / speed / siege / projectile / win-cond).
      * CARD IDENTITY (only when a trained detector exists): each detected unit is boxed and
        labelled with its card identity + KB attribute profile (win_condition / siege / spell /
        air / swarm / tank / splash / death_damage + elixir / hp / dps / tower-damage), resolved
        through ``card_threat.profile``. Enemy units (red tint) are the threats.

    NOTE: this is the CALIBRATION VIEW of the identity-grounded threat features -- it does NOT
    itself drive the policy. The model reads the threat VECTOR in its observation; wiring these
    card attributes there (so it counters by type) is the retrain-time integration step. Tune the
    behavioural thresholds in ``clashrl.threats``; retrain the detector (``detect-import`` ->
    ``tools/detect/train.py``) to sharpen the identity layer.
    """
    from .reward import _red_mask
    from .threats import ThreatTracker, annotate, _troop_red_mask
    from .cards import load as load_cards
    from .card_threat import profile as card_profile
    from .detect import _resolve_weights

    db = load_cards(cfg)
    model = None                                    # optional card-identity layer (needs a trained detector)
    wpath, _ = _resolve_weights(cfg, None)
    if wpath is not None and wpath.exists():
        try:
            from ultralytics import YOLO
            model = YOLO(str(wpath))
        except Exception:
            try:
                from ultralytics import RTDETR
                model = RTDETR(str(wpath))
            except Exception:
                model = None
    det_conf = float(cfg.get("detect", "preview_conf", default=0.25))

    times = meta.get("frame_times", [])
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_dir = session / "annotated_threats"
    out_dir.mkdir(exist_ok=True)
    saved = 0
    for k in range(24):
        fi = int((k + 0.5) / 24 * total)
        tk = ThreatTracker(cfg)                 # a few consecutive frames -> motion history
        thr = None
        for j in range(max(0, fi - 4), fi + 1):
            cap.set(cv2.CAP_PROP_POS_FRAMES, j)
            ok, frame = cap.read()
            if not ok:
                break
            if float(_red_mask(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)).mean()) / 255.0 > 0.15:
                thr = None                      # red menu / searching / results -> skip
                break
            thr = tk.update(frame, times[j] if j < len(times) else j / 12.0)
        if thr is None:
            continue
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        out = annotate(frame, thr, cfg)
        if model is not None:
            _overlay_card_threats(out, frame, model, db, det_conf, card_profile, _troop_red_mask)
        cv2.imwrite(str(out_dir / f"threats_{fi:06d}.png"), out)
        saved += 1
    cap.release()
    layer = ("behavioural + card-identity" if model is not None
             else "behavioural only -- no trained detector found; train one to add card attributes")
    print(f"[verify] threats: saved {saved} annotated in-match frames to {out_dir}  [{layer}]")
    print("[verify] green tint = enemy troops; label = behavioural threat type; yellow cross = centroid; "
          "magenta arrow = projectile.")
    if model is not None:
        print("[verify] red boxes = detected ENEMY cards with their KB attributes "
              "(roles + elixir/hp/dps/tower-dmg); blue = your units. Accuracy tracks the detector.")


def _verify_towers(cfg, session: Path, meta: dict, video: Path) -> None:
    """Overlay the RL tower-detection anchors on in-match frames to calibrate shaping.

    Green box = tower read ALIVE, red = read destroyed. If boxes miss the towers
    or the flags look wrong, adjust `env.enemy_towers` / `env.my_towers` and
    `env.tower_alive_frac` in config, then re-run.
    """
    from .reward import ANCHOR_HALF, tower_readings
    from .tower_hp import DigitReader, _boxes, _crop
    from .vision import Vision

    vision = Vision(cfg)
    reader = DigitReader()
    enemy_boxes, my_boxes = _boxes(cfg)
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out_dir = session / "annotated_towers"
    out_dir.mkdir(exist_ok=True)

    saved = 0
    for k in range(30):
        fi = int((k + 0.5) / 30 * total)
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ok, frame = cap.read()
        if not ok:
            continue
        if vision.detect_state(frame).name != "IN_MATCH":
            continue
        h, w = frame.shape[:2]
        for label, nx, ny, frac, alive, _enemy in tower_readings(frame, cfg):
            x0, x1 = int((nx - ANCHOR_HALF[0]) * w), int((nx + ANCHOR_HALF[0]) * w)
            y0, y1 = int((ny - ANCHOR_HALF[1]) * h), int((ny + ANCHOR_HALF[1]) * h)
            color = (0, 200, 0) if alive else (0, 0, 255)
            cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)
            cv2.putText(frame, f"{label} {frac:.2f}", (x0, max(12, y0 - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        # HP-number crops (yellow) + the digit-CNN read, to calibrate hp boxes
        king_box = cfg.get("env", "enemy_king_hp_box", default=None)
        my_king_box = cfg.get("env", "my_king_hp_box", default=None)
        hp_boxes = ([(f"E{i + 1}", b) for i, b in enumerate(enemy_boxes)]
                    + [(f"M{i + 1}", b) for i, b in enumerate(my_boxes)]
                    + ([("EK", king_box)] if king_box else [])
                    + ([("MK", my_king_box)] if my_king_box else []))
        for label, box in hp_boxes:
            bx0, by0, bx1, by1 = int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)
            cv2.rectangle(frame, (bx0, by0), (bx1, by1), (0, 255, 255), 1)
            val, conf = reader.read(_crop(frame, box))
            txt = f"{val}" if val is not None else "--"
            cv2.putText(frame, f"{label}:{txt} {conf:.2f}", (bx0, min(h - 4, by1 + 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.imwrite(str(out_dir / f"towers_{fi:06d}.png"), frame)
        saved += 1
        if saved >= 16:
            break
    cap.release()
    print(f"[verify] towers: saved {saved} annotated in-match frames to {out_dir}")
    print("[verify] green = read ALIVE, red = read destroyed. Tune env.enemy_towers / "
          "env.my_towers / env.tower_alive_frac if the boxes miss towers or flags look wrong.")
    print("[verify] yellow = HP-number crops (value + CNN confidence). Tune "
          "env.enemy_tower_hp_boxes / env.my_tower_hp_boxes if a number is misboxed.")
