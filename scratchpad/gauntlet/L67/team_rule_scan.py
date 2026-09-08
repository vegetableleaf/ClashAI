"""L67g: how much does the deck-aware team rule actually change? One detector pass, real session frames.

Owner ruling 2026-09-08: a detection whose class my deck cannot produce is not mine. Counts, per session:
  * detections by team tag (mine / enemy / unknown), which is what the colour vote produced
  * of the UNKNOWN ones, how many carry a class outside mine_classes -> the rule resolves them to enemy
  * of the MINE-tagged ones, how many carry an impossible class -> those are colour-vote ERRORS the rule
    does NOT touch (it only fires on unknown), reported so the owner can decide whether to extend it.

usage: python scratchpad/gauntlet/L67/team_rule_scan.py <session_dir>... --out <json> [--every 12] [--limit 400]
"""
from __future__ import annotations
import argparse, collections, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--deck", default="icebow")
    ap.add_argument("--every", type=int, default=12)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--raw-only", action="store_true")
    a = ap.parse_args()

    import cv2
    from clashrl.config import Config
    from clashrl.cards import CardDB
    from clashrl.replay_mine import TeamTracker, load_detector, own_card_bases
    from pipeline import vocab
    from pipeline.obs_contract import load_deck, mine_classes

    cfg = Config.load()
    det = load_detector(cfg)
    if not det.available:
        raise SystemExit("detector weights not found")
    deck = load_deck(a.deck)
    # The LIVE path does not consume raw colour votes: play.py runs TeamTracker.tag() (with its deck
    # veto, replay_mine._claim) over every detection first. Both are counted here, because "20/42 barrels
    # unknown" was measured on the RAW detector and must not be reported as a live-path number.
    db = CardDB(path=deck.config.parent / "cards.yaml")
    tracker = TeamTracker(own_cards=own_card_bases(db)) if not a.raw_only else None
    allowed = mine_classes(deck)
    conf_thr = float(cfg.get("observation", "detector_conf", default=0.35))

    rows = []
    for sess in a.sessions:
        cap = cv2.VideoCapture(str(sess / "video.mp4"))
        if not cap.isOpened():
            print(f"skip {sess}", flush=True)
            continue
        tags = collections.Counter()
        tagged = collections.Counter()          # after TeamTracker.tag(), i.e. what play.py actually sees
        tagged_bad = collections.Counter()      # impossible class STILL not enemy after the tracker
        flip = collections.Counter()          # unknown + impossible class -> now enemy
        mine_bad = collections.Counter()      # tagged mine but impossible class
        if tracker is not None:
            tracker.reset()
        fi, used = -1, 0
        while used < a.limit:
            ok, frame = cap.read()
            if not ok:
                break
            fi += 1
            if fi % a.every:
                continue
            used += 1
            dets = det.detect(frame, conf=conf_thr)
            raw = [str(d.team) for d in dets]
            if tracker is not None:
                tracker.tag(dets, fi / 12.0)     # sampled cadence stands in for wall time
                for d in dets:
                    tagged[str(d.team)] += 1
                    if str(d.team) != "enemy" and vocab.base_key(str(d.cls)) not in allowed:
                        tagged_bad[str(d.cls)] += 1
            for d, t in zip(dets, raw):
                tags[t] += 1
                poss = vocab.base_key(str(d.cls)) in allowed
                if t == "unknown" and not poss:
                    flip[str(d.cls)] += 1
                if t == "mine" and not poss:
                    mine_bad[str(d.cls)] += 1
        cap.release()
        n = sum(tags.values())
        rows.append({"session": sess.name, "frames": used, "dets": n, "raw_tags": dict(tags),
                     "tagged_by_TeamTracker": dict(tagged),
                     "impossible_class_not_enemy_after_tracker": sum(tagged_bad.values()),
                     "top_still_wrong": tagged_bad.most_common(6),
                     "unknown_resolved": sum(flip.values()),
                     "unknown_resolved_frac_of_dets": round(sum(flip.values()) / max(n, 1), 4),
                     "unknown_resolved_frac_of_unknown": round(sum(flip.values()) / max(tags["unknown"], 1), 4),
                     "top_resolved": flip.most_common(8),
                     "mine_tagged_impossible": sum(mine_bad.values()),
                     "top_mine_impossible": mine_bad.most_common(8)})
        print(json.dumps(rows[-1]), flush=True)
    a.out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
