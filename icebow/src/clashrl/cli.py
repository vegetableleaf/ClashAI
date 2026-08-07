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
import os

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


# --- board-resolution presets: --size toggles action.grid without editing config.yaml -----------
_GRID_SIZES = {"576": [18, 32], "432": [18, 24]}   # n_cells -> [cols, rows] (18-wide CR tile lattice)


def _sized_config(args) -> "Config":
    """Load the config, applying a --size override of action.grid when the flag is present
    (576=[18,32] fine / 432=[18,24] coarse). Lets label / train-sim / play switch board resolution
    without hand-editing config.yaml -- use the SAME size everywhere + a matching dataset/checkpoint."""
    cfg = Config.load(args.config)
    size = getattr(args, "size", None)
    if size:
        cfg.data.setdefault("action", {})["grid"] = list(_GRID_SIZES[size])
        print(f"[cli] --size {size} -> action.grid {_GRID_SIZES[size]}")
    return cfg


def _cmd_label(args) -> None:
    from .label import label
    label(_sized_config(args), args.session, args.all, args.debug)


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
    train_rl(_sized_config(args), init=args.init)


def _cmd_play(args) -> None:
    from .play import play
    play(_sized_config(args))


def _cmd_train_sim(args) -> None:
    try:
        from .train_sim import train_sim
    except ImportError as exc:
        print(f"[train-sim] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return
    train_sim(_sized_config(args), matches=args.matches, resume=args.resume,
              seed=args.seed, envs=args.envs)


def _cmd_train_sim_ppo(args) -> None:
    try:
        from .train_sim_ppo import train_sim_ppo
    except ImportError as exc:
        print(f"[train-sim-ppo] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return
    train_sim_ppo(_sized_config(args), matches=args.matches, resume=args.resume,
                  seed=args.seed, envs=args.envs, init=args.init)


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


def _cmd_sprites(args) -> None:
    from .sprites import extract_sprites, synth_images, verify_sprites
    cfg = Config.load(args.config)
    if args.verify:
        verify_sprites(cfg, count=args.count, margin=args.margin)
    elif args.synth:
        synth_images(cfg, count=args.synth, paste_max=args.paste, classes_filter=args.classes,
                     seed=args.seed)
    else:
        extract_sprites(cfg, split=args.split, margin=args.margin, limit=args.limit,
                        append=args.append)


def _cmd_detect_eval(args) -> None:
    from .detect_eval import detect_eval
    detect_eval(Config.load(args.config), weights=args.weights, conf=args.conf,
                sweep=args.sweep, device=args.device, subset=args.subset)


def _cmd_label_queue(args) -> None:
    from .label_queue import label_queue
    label_queue(Config.load(args.config), classes=args.classes, n=args.n, weights=args.weights,
                lo=args.lo, hi=args.hi, device=args.device, limit=args.limit, copy=args.copy)


def _cmd_detect_obs(args) -> None:
    from .detect_obs import detect_obs_preview
    detect_obs_preview(Config.load(args.config), args.session, args.count, args.weights, args.conf)


def _cmd_card_roles(args) -> None:
    from .card_threat import roles_report
    roles_report(Config.load(args.config), args.all, args.card)


def _cmd_mine_replays(args) -> None:
    from .replay_mine import mine_replays
    mine_replays(Config.load(args.config), args.replays, args.weights, args.conf, args.stride)


def _cmd_ui(args) -> None:
    try:
        from .ui.app import serve
    except ImportError as exc:
        print(f"[ui] Flask wird benötigt ({exc}).\n"
              "Installieren:\n"
              "  .\\.venv\\Scripts\\python.exe -m pip install flask")
        return
    serve(Config.load(args.config), port=args.port, open_browser=not args.no_browser)


def _cmd_cards_art(args) -> None:
    from .card_art import import_card_art
    import_card_art(Config.load(args.config), only_missing=not args.refresh, limit=args.limit)


def _cmd_deck_detect(args) -> None:
    from .deck_detect import detect_deck
    detect_deck(Config.load(args.config), session_arg=args.session, samples=args.samples,
                per_face=args.per_face, player_tag=args.player_tag, out=args.out)


def _cmd_sim_bench(args) -> None:
    try:
        from .ui.bench import sim_bench
    except ImportError as exc:
        print(f"[sim-bench] PyTorch wird benötigt ({exc}).")
        return
    sim_bench(Config.load(args.config), envs=args.envs, seconds=args.seconds, seed=args.seed,
              out=args.out, warmup=args.warmup, auto=args.auto, apply=args.apply)


def _cmd_policy_stats(args) -> None:
    try:
        from .ui.rollout import policy_stats
    except ImportError as exc:
        print(f"[policy-stats] PyTorch wird benötigt ({exc}).")
        return
    policy_stats(_sized_config(args), ckpt=args.ckpt, matches=args.matches, envs=args.envs,
                 seed=args.seed, epsilon=args.epsilon, out=args.out)


def main() -> None:
    # The UI launches us in our own process group, where Windows can only deliver
    # Ctrl+Break -- whose default action kills us before any `finally: save()` runs.
    # Map it onto the normal Ctrl+C path. Env-gated, so a plain CLI run is unchanged.
    if os.environ.get("CLASHRL_UI_CHILD"):
        from .ui.child import install_stop_signal
        install_stop_signal()

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
    lab.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution 576=[18,32] (fine) / 432=[18,24] (coarse); overrides action.grid so the "
                          "rebuilt dataset is quantized at that resolution (match your sim/policy)")
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
    trl.add_argument("--init", default=None, metavar="CKPT",
                     help="checkpoint to warm-start from, e.g. data/policy_sim_best.pt to fine-tune the SIM policy "
                          "live. Default: data/policy_rl.pt if it exists, else data/policy.pt (the BC output).")
    trl.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution 576=[18,32] / 432=[18,24]; overrides action.grid so the action masks "
                          "match your --init checkpoint's grid (train-bc auto-follows the dataset, no --size there)")
    trl.set_defaults(func=_cmd_train_rl)

    tsi = sub.add_parser("train-sim",
                         help="train the policy in the headless SIMULATOR (thousands of matches, from scratch, no vision)")
    tsi.add_argument("--matches", type=int, default=2000, help="max matches to play before stopping")
    tsi.add_argument("--resume", action="store_true", help="continue data/policy_sim.pt instead of training from scratch")
    tsi.add_argument("--seed", type=int, default=0, help="RNG seed for the simulator")
    tsi.add_argument("--envs", type=int, default=None,
                     help="parallel (vectorized) match instances feeding one learner (default: sim.envs)")
    tsi.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution 576=[18,32] / 432=[18,24]; overrides action.grid for this run "
                          "(a from-scratch reset -- do NOT combine with --resume of the OTHER size)")
    tsi.set_defaults(func=_cmd_train_sim)

    tsp = sub.add_parser("train-sim-ppo",
                         help="PPO sibling of train-sim (on-policy clip+GAE; own checkpoint policy_sim_ppo.pt -- "
                              "the DDQN policy_sim.pt baseline is untouched)")
    tsp.add_argument("--matches", type=int, default=2000, help="max matches to play before stopping")
    tsp.add_argument("--resume", action="store_true",
                     help="continue data/policy_sim_ppo.pt instead of training from scratch")
    tsp.add_argument("--init", metavar="CKPT", default=None,
                     help="warm-start policy+gate from a checkpoint (e.g. data/policy_sim_best.pt -- Q-heads "
                          "read as logits = a Boltzmann start; the value head trains fresh)")
    tsp.add_argument("--seed", type=int, default=0, help="RNG seed for the simulator")
    tsp.add_argument("--envs", type=int, default=None,
                     help="parallel (vectorized) match instances (default: sim.envs)")
    tsp.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution 576=[18,32] / 432=[18,24]; overrides action.grid for this run")
    tsp.set_defaults(func=_cmd_train_sim_ppo)

    dki = sub.add_parser("decks-import",
                         help="import the current top meta decks from the official CR API into config/meta_decks.yaml")
    dki.add_argument("--limit", type=int, default=1000, help="how many top DISTINCT decks to keep (default 1000)")
    dki.add_argument("--players", type=int, default=120, help="how many top-ladder players' battle logs to scan")
    dki.set_defaults(func=_cmd_decks_import)

    ply = sub.add_parser("play", help="run the trained policy live (needs torch + a trained policy)")
    ply.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution 576=[18,32] / 432=[18,24]; overrides action.grid -- match your policy checkpoint")
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
                         help="import a Label Studio JSON or YOLO export into the training dataset (remaps classes by name + train/val split)")
    din.add_argument("--export", required=True, help="path to the LS export: a JSON file / folder (recommended on Windows), or a YOLO export folder (classes.txt + labels/)")
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

    spr = sub.add_parser("sprites",
                         help="cut annotated units out of their arena background (GrabCut) into a per-class RGBA "
                              "sprite bank under data/detect/sprites/ -- raw material for cross-arena copy-paste aug")
    spr.add_argument("--verify", action="store_true",
                     help="sample random boxes, cut them live, and save side-by-side quality panels "
                          "(source+box | checkerboard | dark | light) to sprites/_verify/ instead of extracting")
    spr.add_argument("--count", type=int, default=24, help="samples for --verify (default 24)")
    spr.add_argument("--split", choices=["train", "val", "all"], default="train",
                     help="which dataset split(s) to extract from (default train -- NEVER build a bank you will "
                          "--synth from over val: it pastes val pixels into the training set and inflates val recall)")
    spr.add_argument("--margin", type=float, default=0.25,
                     help="background context ring around each box GrabCut models as definite background (default 0.25)")
    spr.add_argument("--limit", type=int, default=None, help="stop after this many kept sprites (quick trial)")
    spr.add_argument("--append", action="store_true",
                     help="keep existing sprites instead of clearing them (a full rebuild resets the bank by default)")
    spr.add_argument("--synth", type=int, default=None, metavar="N",
                     help="COPY-PASTE compositor: synthesize N labeled training images by pasting bank sprites "
                          "onto labeled train frames -> data/detect/synth/ (auto-added to data.yaml train; "
                          "regenerates the whole set each run; val stays real-only)")
    spr.add_argument("--paste", type=int, default=4, help="max sprites pasted per synthetic image (default 4)")
    spr.add_argument("--classes", default=None,
                     help="comma list restricting --synth pasting to these classes (e.g. skeletons,ice_spirit,guards)")
    spr.add_argument("--seed", type=int, default=None, help="RNG seed for a reproducible --synth set")
    spr.set_defaults(func=_cmd_sprites)

    dev = sub.add_parser("detect-eval",
                         help="gating eval for the detector: class-agnostic PRESENCE recall (obs-canvas gate), "
                              "base-folded whitelist identity recall, and per-ROLE deck gates (units gated, "
                              "spell projectiles reported only)")
    dev.add_argument("--weights", default=None, help="best.pt (default: newest runs/detect/*/weights/best.pt)")
    dev.add_argument("--conf", type=float, default=None,
                     help="confidence gate to report in detail (default: observation.detector_conf)")
    dev.add_argument("--sweep", action="store_true",
                     help="also print the 0.75..0.30 confidence curve -- RE-SWEEP per detector generation "
                          "instead of inheriting the previous operating point")
    dev.add_argument("--device", default=None,
                     help="torch device for inference, e.g. cpu -- use cpu to evaluate WITHOUT touching a busy GPU")
    dev.add_argument("--subset", default=None,
                     help="file of val STEMS (one per line) to score instead of the whole val dir -- labelling "
                          "GROWS val, so pass the same snapshot to both generations for a like-for-like compare")
    dev.set_defaults(func=_cmd_detect_eval)

    lq = sub.add_parser("label-queue",
                        help="rank the UNLABELLED frames by how much labelling each would teach the "
                             "detector -- AMBIGUITY (two classes claim one box) and UNCERTAINTY "
                             "(mid-confidence detections), so scarce labelling time goes to the frames "
                             "that resolve a confusion instead of to boards it already reads")
    lq.add_argument("--classes", default=None,
                    help="comma list to focus on (e.g. wizard,valkyrie,musketeer); default = all classes")
    lq.add_argument("--n", type=int, default=150, help="how many frames to shortlist (default 150)")
    lq.add_argument("--weights", default=None, help="best.pt (default: newest runs/detect/*/weights/best.pt)")
    lq.add_argument("--lo", type=float, default=0.15, help="bottom of the 'uncertain' confidence band")
    lq.add_argument("--hi", type=float, default=0.60, help="top of the 'uncertain' confidence band")
    lq.add_argument("--device", default=None,
                    help="torch device, e.g. cpu -- use cpu while a training run owns the GPU")
    lq.add_argument("--limit", type=int, default=None, help="only scan the first N queue frames (quick trial)")
    lq.add_argument("--copy", action="store_true",
                    help="also COPY the shortlist into images/to_label_priority/ so Label Studio can "
                         "point at just those (originals are left in place)")
    lq.set_defaults(func=_cmd_label_queue)

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

    uip = sub.add_parser("ui",
                         help="lokale Launcher-Oberfläche im Browser (Start/Stop, Live-Log, "
                              "Dashboard, Deck-/Config-Editor) -- bindet nur an 127.0.0.1")
    uip.add_argument("--port", type=int, default=8765, help="Port (Default 8765)")
    uip.add_argument("--no-browser", action="store_true", dest="no_browser",
                     help="Browser nicht automatisch öffnen")
    uip.set_defaults(func=_cmd_ui)

    pst = sub.add_parser("policy-stats",
                         help="misst im Simulator, WAS die Policy spielt: Karten-Häufigkeit, "
                              "Platzierungs-Heatmap, Wait-Gate-Quote -> data/policy_stats.json")
    pst.add_argument("--ckpt", default=None,
                     help="Checkpoint (Default: data/policy_sim_best.pt, sonst policy_sim.pt)")
    pst.add_argument("--matches", type=int, default=60, help="wieviele greedy Matches gespielt werden")
    pst.add_argument("--envs", type=int, default=8, help="parallele Match-Instanzen")
    pst.add_argument("--seed", type=int, default=4242, help="RNG-Seed des Simulators")
    pst.add_argument("--epsilon", type=float, default=0.0,
                     help="Zufallsanteil (0 = rein greedy, also das echte Verhalten)")
    pst.add_argument("--out", default=None, help="Ziel-JSON (Default: data/policy_stats.json)")
    pst.add_argument("--size", choices=["576", "432"], default=None,
                     help="Board-Auflösung; muss zum Checkpoint passen")
    pst.set_defaults(func=_cmd_policy_stats)

    sbn = sub.add_parser("sim-bench",
                         help="misst die Trainingsgeschwindigkeit (Matches/s) bei verschiedenen "
                              "--envs auf DIESEM PC -> data/sim_bench.json (schreibt NICHT policy_sim.pt)")
    sbn.add_argument("--auto", action="store_true",
                     help="sucht die beste Env-Zahl selbst: verdoppelt sie, bis der Durchsatz nicht "
                          "mehr steigt oder der RAM knapp wird")
    sbn.add_argument("--apply", action="store_true",
                     help="schreibt die empfohlene Env-Zahl direkt in config.yaml (mit Sicherung)")
    sbn.add_argument("--envs", default=None,
                     help="Kommaliste zu messender Env-Zahlen (Default: aus der Hardware abgeleitet)")
    sbn.add_argument("--seconds", type=float, default=45.0, help="Messdauer pro Einstellung")
    sbn.add_argument("--warmup", type=float, default=8.0,
                     help="verworfener Aufwärmlauf (CUDA-Kontext); 0 = aus")
    sbn.add_argument("--seed", type=int, default=0, help="RNG-Seed (für alle Messungen gleich)")
    sbn.add_argument("--out", default=None, help="Ziel-JSON (Default: data/sim_bench.json)")
    sbn.set_defaults(func=_cmd_sim_bench)

    car = sub.add_parser("cards-art",
                         help="lädt je ein Referenzbild pro Karte vom Fandom-Wiki nach "
                              "templates/cardart/ (Grundlage der automatischen Deckerkennung)")
    car.add_argument("--refresh", action="store_true",
                     help="auch bereits vorhandene Bilder neu laden")
    car.add_argument("--limit", type=int, default=None, help="nur die ersten N Karten (Test)")
    car.set_defaults(func=_cmd_cards_art)

    ddt = sub.add_parser("deck-detect",
                         help="erkennt die acht Deckkarten automatisch aus einer Aufnahme und "
                              "schlägt sie zur Bestätigung vor (ersetzt das Umbenennen der Crops)")
    ddt.add_argument("--session", default=None, help="Aufnahme (Default: neueste)")
    ddt.add_argument("--samples", type=int, default=400, help="wieviele Videobilder abgetastet werden")
    ddt.add_argument("--per-face", type=int, default=6, dest="per_face",
                     help="wieviele Bilder je Kartengesicht gemittelt werden (mehr = sicherer)")
    ddt.add_argument("--player-tag", default=None, dest="player_tag",
                     help="Spieler-Tag (z.B. #ABC123) -- liest die Kartenlevel aus deinem Account "
                          "über die offizielle API; braucht einen Token in CLASHRL_CR_API_TOKEN")
    ddt.add_argument("--out", default=None, help="Ziel-JSON (Default: data/deck_detect.json)")
    ddt.set_defaults(func=_cmd_deck_detect)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
