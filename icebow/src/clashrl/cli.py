"""Command-line interface for the learning bot.

Subcommands (built incrementally):
  record         capture your PC play (screen + mouse) for imitation data  [ready]
  hand-templates extract deck-card templates from a recording (identity)    [ready]
  label          turn recorded sessions into an (obs, hand, card, cell) set [ready]
  outcomes       auto-detect win/loss per match from the results scoreboard [ready]
  train-bc       behaviour-cloning pretrain of the CNN policy               [ready]
  train-rl       RL fine-tune with tower/crown/win rewards                  [ready]
  play           let the trained policy play live                          [ready]
"""
from __future__ import annotations

import argparse

from .config import Config


def _cmd_record(args) -> None:
    from .record import record
    record(Config.load(args.config))


def _cmd_verify(args) -> None:
    from .verify import verify
    verify(Config.load(args.config), args.session, args.towers, args.hand, args.spells, args.threats,
           args.clock, args.all)


def _cmd_hand_templates(args) -> None:
    from .hand_templates import build_hand_templates
    build_hand_templates(Config.load(args.config), args.session, only_new=not args.include_known)


def _cmd_label(args) -> None:
    from .label import label
    label(Config.load(args.config), args.session, args.all, args.debug)


def _cmd_outcomes(args) -> None:
    from .outcome import outcomes
    outcomes(Config.load(args.config), args.session, args.all, args.debug)


def _cmd_cards(args) -> None:
    from .cards import CardDB
    db = CardDB(Config.load(args.config))
    sm = db.stats_meta or {}
    print(f"[cards] {len(db.cards)} cards | stats source: {sm.get('source', 'none')} "
          f"({sm.get('generated', 'n/a')}, level {sm.get('level', '?')})")
    print(f"[cards] deck '{db.deck_name()}' (avg elixir {db.deck_avg_elixir()}):")
    for c in db.deck():
        evo = " (Evo)" if c.get("evolved") else ""
        elx = c.get("elixir")
        bits = [f"{elx if elx is not None else '?'} elixir", str(c.get("kind"))]
        if c.get("hitpoints") is not None:
            bits.append(f"hp {c['hitpoints']}")
        if c.get("damage") is not None:
            bits.append(f"dmg {c['damage']}")
        if c.get("kind") == "spell" and c.get("damage") is not None:
            twr = c.get("crown_tower_damage", c.get("damage"))
            bits.append(f"tower {twr}")     # spells deal reduced (or full) damage to towers
        if c.get("dps") is not None:
            bits.append(f"dps {c['dps']}")
        print(f"   - {c['display']}{evo}: " + ", ".join(bits))
    no_stats = sorted(k for k, v in db.cards.items()
                      if v.get("hitpoints") is None and v.get("damage") is None)
    have = len(db.cards) - len(no_stats)
    print(f"[cards] combat stats present for {have}/{len(db.cards)} cards.")
    if no_stats:
        print(f"[cards] no stats yet for {len(no_stats)} (newest cards / curated-only): "
              + ", ".join(no_stats[:12]) + (" ..." if len(no_stats) > 12 else ""))
    print("[cards] refresh after balance updates: run.py cards-import.")


def _cmd_cards_import(args) -> None:
    from .card_import import import_cards
    import_cards(Config.load(args.config))


def _cmd_train_bc(args) -> None:
    try:
        from .train_bc import train_bc
    except ImportError as exc:
        print(f"[train-bc] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu121")
        return
    train_bc(Config.load(args.config), init=args.init, iterations=args.iterations)


def _cmd_train_rl(args) -> None:
    try:
        from .train_rl import train_rl
    except ImportError as exc:
        print(f"[train-rl] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return
    train_rl(Config.load(args.config))


def _cmd_play(args) -> None:
    from .play import play
    play(Config.load(args.config))


def _cmd_train_sim(args) -> None:
    try:
        from .train_sim import train_sim
    except ImportError as exc:
        print(f"[train-sim] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return
    train_sim(Config.load(args.config), matches=args.matches, resume=args.resume,
              seed=args.seed, envs=args.envs)


def _cmd_decks_import(args) -> None:
    from .deck_import import import_decks
    import_decks(Config.load(args.config), limit=args.limit, players=args.players)


def _cmd_diag(args) -> None:
    from .diagnose import diagnose
    diagnose(Config.load(args.config))


def _cmd_analyze(args) -> None:
    from .analyze import analyze
    analyze(Config.load(args.config), args.session, args.all, args.window, args.debug)


def _cmd_autolabel(args) -> None:
    from .detect import autolabel
    autolabel(Config.load(args.config), args.session, args.all, args.preview)


def _cmd_detect_import(args) -> None:
    from .detect import detect_import
    detect_import(Config.load(args.config), args.export, args.val_frac)


def _cmd_detect_frames(args) -> None:
    from .detect import add_frames
    add_frames(Config.load(args.config), args.session, args.count, args.val_frac)


def _cmd_detect_timelapse(args) -> None:
    from .detect import add_timelapse_frames
    add_timelapse_frames(Config.load(args.config), args.video, args.per_video,
                         val_frac=args.val_frac, recent=args.recent)


def _cmd_detect_preview(args) -> None:
    from .detect import detect_preview
    detect_preview(Config.load(args.config), args.session, args.count, args.weights, args.conf)


def _cmd_detect_obs(args) -> None:
    from .detect_obs import detect_obs_preview
    detect_obs_preview(Config.load(args.config), args.session, args.count, args.weights, args.conf)


def _cmd_card_roles(args) -> None:
    from .card_threat import roles_report
    roles_report(Config.load(args.config), args.all, args.card)


def _cmd_mine_replays(args) -> None:
    from .replay_mine import mine_replays
    mine_replays(Config.load(args.config), args.replays, args.weights, args.conf, args.stride)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clashrl",
        description="Learning Clash Royale bot (imitation learning -> RL).",
    )
    parser.add_argument("--config", default=None, help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="record your PC play (screen + mouse) for imitation data")
    rec.set_defaults(func=_cmd_record)

    ver = sub.add_parser("verify", help="overlay logged clicks on a recorded session to sanity-check it")
    ver.add_argument("--session", default=None, help="session folder (default: latest)")
    ver.add_argument("--towers", action="store_true",
                     help="overlay RL tower-detection anchors on in-match frames to calibrate shaping")
    ver.add_argument("--hand", action="store_true",
                     help="overlay hand-card recognition on in-match frames to calibrate identity actions")
    ver.add_argument("--spells", action="store_true",
                     help="overlay enemy-troop-mass detection to calibrate spell + patience rewards")
    ver.add_argument("--threats", action="store_true",
                     help="overlay the enemy-threat read (color/size/count/lane + projectiles) to calibrate reactive play")
    ver.add_argument("--clock", action="store_true",
                     help="check the 2x/3x elixir badge (templates/elixir_2x.png,elixir_3x.png) match scores on in-match frames")
    ver.add_argument("--all", action="store_true",
                     help="run the chosen overlay over EVERY recorded session (not just one)")
    ver.set_defaults(func=_cmd_verify)

    lab = sub.add_parser("label", help="build an (observation, action) dataset from recordings")
    lab.add_argument("--session", default=None, help="session folder (default: latest)")
    lab.add_argument("--all", action="store_true", help="label every recorded session")
    lab.add_argument("--debug", action="store_true", help="save annotated frames of each extracted play")
    lab.set_defaults(func=_cmd_label)

    hnd = sub.add_parser("hand-templates",
                         help="extract deck-card templates from a recording (for identity recognition)")
    hnd.add_argument("--session", default=None, help="session folder (default: latest)")
    hnd.add_argument("--include-known", action="store_true",
                     help="also surface cards already covered by existing templates (default: only new)")
    hnd.set_defaults(func=_cmd_hand_templates)

    out = sub.add_parser("outcomes", help="auto-detect win/loss per match from the results scoreboard")
    out.add_argument("--session", default=None, help="session folder (default: latest)")
    out.add_argument("--all", action="store_true", help="score every recorded session")
    out.add_argument("--debug", action="store_true", help="verbose per-frame detection")
    out.set_defaults(func=_cmd_outcomes)

    crd = sub.add_parser("cards", help="show the card knowledge base + your deck")
    crd.set_defaults(func=_cmd_cards)

    cri = sub.add_parser("cards-import",
                         help="import/refresh card stats from RoyaleAPI open data (game-derived)")
    cri.set_defaults(func=_cmd_cards_import)

    tbc = sub.add_parser("train-bc", help="behaviour-cloning pretrain of the CNN policy (needs torch)")
    tbc.add_argument("--init", metavar="CKPT", default=None,
                     help="warm-start from a checkpoint (e.g. data/policy_sim.pt) and fine-tune it on your "
                          "recordings instead of random init -- combines the sim prior with your play")
    tbc.add_argument("--iterations", type=int, default=1, metavar="N",
                     help="run N successive BC passes in one command, each warm-starting from the previous "
                          "(fresh optimizer each pass, not just more epochs); saves data/policy.pt after every pass")
    tbc.set_defaults(func=_cmd_train_bc)

    trl = sub.add_parser("train-rl", help="RL fine-tune the policy on live matches (tower/win rewards)")
    trl.set_defaults(func=_cmd_train_rl)

    tsi = sub.add_parser("train-sim",
                         help="train the policy in the headless SIMULATOR (thousands of matches, from scratch, no vision)")
    tsi.add_argument("--matches", type=int, default=2000, help="max matches to play before stopping")
    tsi.add_argument("--resume", action="store_true", help="continue data/policy_sim.pt instead of training from scratch")
    tsi.add_argument("--seed", type=int, default=0, help="RNG seed for the simulator")
    tsi.add_argument("--envs", type=int, default=None,
                     help="parallel (vectorized) match instances feeding one learner (default: sim.envs)")
    tsi.set_defaults(func=_cmd_train_sim)

    dki = sub.add_parser("decks-import",
                         help="import the current top meta decks from the official CR API into config/meta_decks.yaml")
    dki.add_argument("--limit", type=int, default=1000, help="how many top DISTINCT decks to keep (default 1000)")
    dki.add_argument("--players", type=int, default=120, help="how many top-ladder players' battle logs to scan")
    dki.set_defaults(func=_cmd_decks_import)

    ply = sub.add_parser("play", help="run the trained policy live (needs torch + a trained policy)")
    ply.set_defaults(func=_cmd_play)

    dia = sub.add_parser("diag", help="diagnose menu navigation: state-template match scores on the current screen")
    dia.set_defaults(func=_cmd_diag)

    ana = sub.add_parser("analyze",
                         help="mine recordings for which card you play vs which enemy-threat type (color/size/count)")
    ana.add_argument("--session", default=None, help="session folder (default: latest)")
    ana.add_argument("--all", action="store_true", help="analyze every recorded session")
    ana.add_argument("--window", type=int, default=12,
                     help="frames before each play to read the threat over (motion + projectile)")
    ana.add_argument("--debug", action="store_true", help="save annotated frames of each analyzed play")
    ana.set_defaults(func=_cmd_analyze)

    atl = sub.add_parser("autolabel",
                         help="bootstrap a YOLO detection dataset: auto-box your own troops + export frames to hand-label")
    atl.add_argument("--session", default=None, help="session folder (default: latest)")
    atl.add_argument("--all", action="store_true", help="use every recorded session")
    atl.add_argument("--preview", action="store_true",
                     help="save overlays of the auto (own-troop) boxes to sanity-check them")
    atl.set_defaults(func=_cmd_autolabel)

    din = sub.add_parser("detect-import",
                         help="import a Label Studio YOLO export into the training dataset (remaps classes by name + train/val split)")
    din.add_argument("--export", required=True, help="path to the unzipped Label Studio YOLO export folder")
    din.add_argument("--val-frac", type=float, default=None, help="validation fraction (default: detect.val_frac)")
    din.set_defaults(func=_cmd_detect_import)

    dfr = sub.add_parser("detect-frames",
                         help="add more in-match frames from a session to data/detect for hand-labelling (non-destructive)")
    dfr.add_argument("--session", default=None, help="session folder name or path (default: latest)")
    dfr.add_argument("--count", type=int, default=120, help="how many new frames to add")
    dfr.add_argument("--val-frac", type=float, default=None, dest="val_frac",
                     help="fraction of the added frames to place in val (default: detect.val_frac = 0.15)")
    dfr.set_defaults(func=_cmd_detect_frames)

    dtl = sub.add_parser("detect-timelapse",
                         help="add frames from training TIMELAPSE videos to data/detect for hand-labelling (non-destructive)")
    dtl.add_argument("--video", default=None, help="a single timelapse .mp4 (default: ALL in train.timelapse_dir)")
    dtl.add_argument("--per-video", type=int, default=12, help="max NEW frames to sample per timelapse (deduped)")
    dtl.add_argument("--recent", type=int, default=0, help="only sample the N most-recent timelapses (0 = all)")
    dtl.add_argument("--val-frac", type=float, default=None, dest="val_frac",
                     help="fraction of the added frames to place in val (default: detect.val_frac = 0.15)")
    dtl.set_defaults(func=_cmd_detect_timelapse)

    dpv = sub.add_parser("detect-preview",
                         help="run the trained detector on RANDOM in-match frames and save annotated images (gauge accuracy, unbiased)")
    dpv.add_argument("--session", default=None, help="restrict to one session (default: sample across ALL sessions)")
    dpv.add_argument("--count", type=int, default=24, help="how many random frames to annotate")
    dpv.add_argument("--weights", default=None, help="path to best.pt (default: latest runs/detect/*/weights/best.pt)")
    dpv.add_argument("--conf", type=float, default=0.25, help="confidence threshold for shown detections")
    dpv.set_defaults(func=_cmd_detect_preview)

    dob = sub.add_parser("detect-obs",
                         help="preview the Stage-3 semantic obs (detector -> enemy/ally/building/spell channels) on real frames")
    dob.add_argument("--session", default=None, help="restrict to one session (default: sample across ALL)")
    dob.add_argument("--count", type=int, default=12, help="how many frames to preview")
    dob.add_argument("--weights", default=None, help="best.pt (default: latest runs/detect/*/weights/best.pt)")
    dob.add_argument("--conf", type=float, default=0.3, help="detector confidence threshold")
    dob.set_defaults(func=_cmd_detect_obs)

    crl = sub.add_parser("card-roles",
                         help="review the strategic role (win condition / siege / spell / ...) derived from the KB for every detector class")
    crl.add_argument("--all", action="store_true", help="dump every class, not just the categorized summary")
    crl.add_argument("--card", default=None, help="inspect a single card / detected class name")
    crl.set_defaults(func=_cmd_card_roles)

    mrp = sub.add_parser("mine-replays",
                         help="distil strong-player replay videos into strategy priors (needs the trained detector; Stage 4)")
    mrp.add_argument("--replays", default=None, help="folder of replay videos (default: replay_mine.replays_dir)")
    mrp.add_argument("--weights", default=None, help="detector weights (default: latest runs/detect/*/weights/best.pt)")
    mrp.add_argument("--conf", type=float, default=None, help="detector confidence threshold (default: replay_mine.detect_conf)")
    mrp.add_argument("--stride", type=int, default=None, help="sample every Nth frame (default: replay_mine.frame_stride)")
    mrp.set_defaults(func=_cmd_mine_replays)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
