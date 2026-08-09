r"""Detector gating eval (`run.py detect-eval`) -- the numbers that decide the obs-channel flip.

Ultralytics' own summary averages only over classes that happen to have val instances, at its own
confidence point, and treats every class as equally important. None of that matches how the policy
CONSUMES detections, so this module measures the three things that actually gate the pipeline:

1. PRESENCE recall (class-agnostic, IoU>=0.5): "is there a box on that unit at all", ignoring the
   name. This is the gate for the detector-rendered obs CANVAS, which only needs position + team.
   Reported twice -- over ALL boxes and over UNITS ONLY (troops/buildings), because a spell
   projectile mid-flight is not something the policy can act on (see the role split below).
2. WHITELIST identity recall (base-folded): the mean over `observation.detector_cards`, i.e. the
   cards that actually fire the identity/threat block. Variants (_evo/_hero/_ability) fold into
   their base via card_threat.base_key, so `knight_hero` counts as `knight`.
3. Per-ROLE deck gates. Detection roles are NOT equally valuable:
     UNIT        (troop/building)  -- persistent + actionable; a miss blinds the policy for many
                                     consecutive frames  ->  the >=0.80 gate applies here
     PROJECTILE  (spell, in flight) -- transient and UN-ACTIONABLE (you cannot answer a rocket
                                     already in the air); what matters is being seen at least ONCE
                                     per cast so the opponent-memory learns "they run this spell",
                                     not per-frame recall  ->  reported, NOT gated
     AOE         (`*_aoe` decal)   -- the persistent, actionable part of a spell (blast/pull zone)
   Roles are derived from the card KB (card_threat.profile), not a hardcoded list.

Confidence is a free parameter that must be RE-SWEPT per detector generation (board-13 wanted 0.45,
board-10 wanted 0.50) -- `--sweep` prints the whole curve so the operating point is chosen, not
inherited.
"""
from __future__ import annotations

import glob
import os
from collections import defaultdict
from pathlib import Path

import yaml

_UNIT_GATE = 0.80          # persistent, actionable classes: the real bar
_PRESENCE_GATE = 0.85      # class-agnostic presence recall -> the obs-canvas flip gate
_WHITELIST_GATE = 0.70     # mean identity recall over observation.detector_cards


def _iou(a, b):
    ax0, ay0, ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2, a[0] + a[2] / 2, a[1] + a[3] / 2
    bx0, by0, bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
    ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
    iy = max(0.0, min(ay1, by1) - max(ay0, by0))
    inter = ix * iy
    ua = a[2] * a[3] + b[2] * b[3] - inter
    return inter / ua if ua > 0 else 0.0


def _role_of(name: str, db) -> str:
    """UNIT (troop/building) | PROJECTILE (spell in flight) | AOE (ground decal)."""
    from .card_threat import base_key, profile
    if name.endswith("_aoe"):
        return "AOE"
    p = profile(db, base_key(name))
    return "PROJECTILE" if p.spell else "UNIT"


def _match(frames, gate, class_aware, keep=None):
    """Greedy conf-descending IoU>=0.5 matching. keep = optional predicate on the GT base name,
    so presence can be measured over a SUBSET (e.g. units only) without re-running inference."""
    tp = defaultdict(int); fp = defaultdict(int); fn = defaultdict(int)
    a_tp = a_fp = a_fn = 0
    for gt_all, preds_all in frames:
        gt = [g for g in gt_all if keep is None or keep(g[0])]
        preds = [p for p in preds_all if p[0] >= gate and (keep is None or keep(p[1]))]
        used = [False] * len(gt)
        for conf, pb, pbox in sorted(preds, key=lambda t: -t[0]):
            best, bi = 0.5, -1
            for i, (gb, gbox) in enumerate(gt):
                if used[i] or (class_aware and gb != pb):
                    continue
                v = _iou(pbox, gbox)
                if v >= best:
                    best, bi = v, i
            if bi >= 0:
                used[bi] = True; tp[gt[bi][0]] += 1; a_tp += 1
            else:
                fp[pb] += 1; a_fp += 1
        for i, (gb, _) in enumerate(gt):
            if not used[i]:
                fn[gb] += 1; a_fn += 1
    return tp, fp, fn, a_tp, a_fp, a_fn


def detect_eval(cfg, weights: str | None = None, conf: float | None = None,
                sweep: bool = False, device: str | None = None,
                subset: str | None = None) -> None:
    try:
        from ultralytics import YOLO
    except ImportError as exc:  # noqa: BLE001
        print(f"[detect-eval] ultralytics required ({exc}).")
        return
    from .card_threat import base_key
    from .cards import CardDB

    root = Path(cfg.path(cfg.get("detect", "dataset_dir", default="data/detect")))
    names = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))["names"]
    if isinstance(names, dict):
        names = [names[k] for k in sorted(names)]
    db = CardDB(cfg)
    whitelist = set(cfg.get("observation", "detector_cards", default=[]) or [])
    live_conf = float(cfg.get("observation", "detector_conf", default=0.5)) if conf is None else conf
    deck = [base_key(k) for k in db.deck_identities()]
    seen = set()
    deck = [d for d in deck if not (d in seen or seen.add(d))]

    if weights is None:
        # Default to THE vision model, the one everything else loads; --weights is still how
        # you point this at an archived file to compare two of them.
        from .detect import _resolve_weights
        wpath, _ = _resolve_weights(cfg, None)
        if wpath is None:
            print("[detect-eval] no trained vision model at runs/detect/vision/weights/best.pt")
            return
        weights = str(wpath)
    imgs = sorted(glob.glob(str(root / "images" / "val" / "*.jpg")))
    if not imgs:
        print(f"[detect-eval] no val images under {root/'images'/'val'}")
        return
    if subset:
        # Restrict to a SNAPSHOT of val stems. Labelling grows the val set (new images hash into it),
        # so generation N+1 is scored on a SUPERSET of generation N's val -- the split manifest keeps
        # old images on their old side, but the totals still differ, and a 2pp move could be nothing but
        # the added images. Scoring both models on the shared snapshot removes that: neither trained on
        # those frames, so it is a like-for-like head-to-head.
        # utf-8-SIG: PowerShell's `Set-Content -Encoding utf8` writes a BOM, which would otherwise glue
        # itself to the first stem and silently drop that one image from the comparison.
        keep = {ln.strip() for ln in Path(subset).read_text(encoding="utf-8-sig").splitlines() if ln.strip()}
        have = {Path(p).stem for p in imgs}
        imgs = [p for p in imgs if Path(p).stem in keep]
        missing = keep - have
        print(f"[detect-eval] SUBSET {Path(subset).name}: {len(imgs)}/{len(keep)} stems present"
              + (f" ({len(missing)} no longer in val -- excluded from BOTH sides only if you"
                 f" re-run the other model with the same --subset)" if missing else ""))
        if not imgs:
            print("[detect-eval] subset matched nothing -- is it a stem list (no .jpg extension)?")
            return
    print(f"[detect-eval] weights {weights}")
    print(f"[detect-eval] val {len(imgs)} images (REAL only -- synth is never validated on)")

    model = YOLO(weights)
    # GROUND TRUTH is indexed in the DATASET's taxonomy (data.yaml); PREDICTIONS are indexed in the
    # taxonomy the WEIGHTS were trained with. Those are not the same list once classes are added or
    # removed -- board-16 carries 236 names against today's 225 -- so decoding both through `names`
    # renamed every predicted class from index 16 up and made this gate score garbage.
    from .detect import model_class_names
    pred_names = model_class_names(model)
    if pred_names and pred_names != list(names):
        print(f"[detect-eval] NOTE weights carry {len(pred_names)} classes, dataset has {len(names)}"
              " -- predictions decoded with the WEIGHTS' names and matched to GT by name")
    frames = []
    gt_total = 0
    for ip in imgs:
        lp = root / "labels" / "val" / (Path(ip).stem + ".txt")
        gt = []
        if lp.exists():
            for line in lp.read_text(encoding="utf-8").splitlines():
                p = line.split()
                if len(p) >= 5:
                    gt.append((base_key(names[int(float(p[0]))]), tuple(float(v) for v in p[1:5])))
        gt_total += len(gt)
        kw = {"conf": 0.05, "imgsz": 960, "verbose": False}
        if device:
            kw["device"] = device
        r = model.predict(ip, **kw)[0]
        frames.append((gt, [(float(b.conf[0]), base_key(pred_names[int(b.cls[0])]),
                             tuple(float(v) for v in b.xywhn[0].tolist())) for b in r.boxes]))
    print(f"[detect-eval] {gt_total} ground-truth boxes\n")

    roles = {}
    def role(nm):
        if nm not in roles:
            roles[nm] = _role_of(nm, db)
        return roles[nm]
    is_unit = lambda nm: role(nm) == "UNIT"   # noqa: E731

    gates = [0.75, 0.60, 0.50, 0.45, 0.40, 0.35, 0.30] if sweep else [live_conf]
    print("  conf | presence(all) R/P | presence(UNITS) R/P | whitelist R/P")
    for g in gates:
        _, _, _, tp_a, fp_a, fn_a = _match(frames, g, False)
        _, _, _, tp_u, fp_u, fn_u = _match(frames, g, False, keep=is_unit)
        tp, fp, fn, _, _, _ = _match(frames, g, True)
        wl = [b for b in sorted(set(list(tp) + list(fn))) if b in whitelist and (tp[b] + fn[b]) > 0]
        rs = [tp[b] / (tp[b] + fn[b]) for b in wl]
        ps = [tp[b] / max(1, tp[b] + fp[b]) for b in wl if (tp[b] + fp[b]) > 0]
        mark = " <- live" if abs(g - live_conf) < 1e-9 else ""
        print(f"  {g:.2f} |   {tp_a/max(1,tp_a+fn_a):.3f} / {tp_a/max(1,tp_a+fp_a):.3f}   "
              f"|    {tp_u/max(1,tp_u+fn_u):.3f} / {tp_u/max(1,tp_u+fp_u):.3f}    "
              f"|  {sum(rs)/max(1,len(rs)):.3f} / {sum(ps)/max(1,len(ps)):.3f}{mark}")

    # -- detailed tables at the LIVE gate -------------------------------------------------------
    tp, fp, fn, tp_a, fp_a, fn_a = _match(frames, live_conf, True)
    _, _, _, tp_u, fp_u, fn_u = _match(frames, live_conf, False, keep=is_unit)
    _, _, _, tp_all, fp_all, fn_all = _match(frames, live_conf, False)
    print(f"\n== deck @ conf {live_conf:.2f} (base-folded, by ROLE) ==")
    for r_name, gate_txt in (("UNIT", f">= {_UNIT_GATE:.2f} gate"),
                             ("PROJECTILE", "not gated -- once/cast is enough"),
                             ("AOE", "not gated")):
        rows = [(d, tp[d], tp[d] + fn[d]) for d in deck if role(d) == r_name and (tp[d] + fn[d]) > 0]
        if not rows:
            continue
        print(f"  -- {r_name} ({gate_txt})")
        for d, hit, n in rows:
            r = hit / n
            flag = "" if r_name != "UNIT" else ("  OK" if r >= _UNIT_GATE else "  BELOW")
            print(f"     {d:<14} R {r:.2f}  (n={n}){flag}")
    ungated = [d for d in deck if (tp[d] + fn[d]) == 0]
    if ungated:
        print(f"  -- no val instances: {', '.join(ungated)}")

    print(f"\n== all bases with n>=5 @ conf {live_conf:.2f} ==")
    rows = sorted(((tp[b] / (tp[b] + fn[b]), tp[b] + fn[b], b)
                   for b in set(list(tp) + list(fn)) if (tp[b] + fn[b]) >= 5), reverse=True)
    for r, n, b in rows:
        print(f"  {b:<18} R {r:.2f}  n={n:<4}{'*WL' if b in whitelist else ''}  [{role(b)[:4]}]")

    # -- verdict ---------------------------------------------------------------------------------
    pres_all = tp_all / max(1, tp_all + fn_all)
    pres_u = tp_u / max(1, tp_u + fn_u)
    wl = [b for b in sorted(set(list(tp) + list(fn))) if b in whitelist and (tp[b] + fn[b]) > 0]
    wl_r = sum(tp[b] / (tp[b] + fn[b]) for b in wl) / max(1, len(wl))
    units_ok = [d for d in deck if role(d) == "UNIT" and (tp[d] + fn[d]) > 0
                and tp[d] / (tp[d] + fn[d]) >= _UNIT_GATE]
    units_n = [d for d in deck if role(d) == "UNIT" and (tp[d] + fn[d]) > 0]
    def mark(v, g):
        return "PASS" if v >= g else "below"
    print(f"\n== OBS-CANVAS FLIP GATES @ conf {live_conf:.2f} ==")
    print(f"  presence UNITS  {pres_u:.3f}  vs {_PRESENCE_GATE:.2f}   {mark(pres_u, _PRESENCE_GATE)}"
          f"   (all boxes {pres_all:.3f})")
    print(f"  whitelist ident {wl_r:.3f}  vs {_WHITELIST_GATE:.2f}   {mark(wl_r, _WHITELIST_GATE)}")
    print(f"  deck UNITS      {len(units_ok)}/{len(units_n)} at >= {_UNIT_GATE:.2f}"
          f"   ({', '.join(d for d in units_n if d not in units_ok) or 'all pass'} below)")
