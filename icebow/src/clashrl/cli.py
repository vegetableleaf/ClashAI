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
    play(_sized_config(args), init=args.init)


def _cmd_train_sim(args) -> None:
    try:
        from .train_sim import train_sim
    except ImportError as exc:
        print(f"[train-sim] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return
    train_sim(_sized_config(args), matches=args.matches, resume=args.resume,
              seed=args.seed, envs=args.envs, resume_from=args.resume_from)


def _cmd_train_sim_ppo(args) -> None:
    try:
        from .train_sim_ppo import train_sim_ppo
    except ImportError as exc:
        print(f"[train-sim-ppo] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu128")
        return
    train_sim_ppo(_sized_config(args), matches=args.matches, resume=args.resume,
                  seed=args.seed, envs=args.envs, init=args.init, device=args.device)


def _cmd_sim_bench(args) -> None:
    try:
        from .sim_bench import sim_bench
    except ImportError as exc:
        print(f"[sim-bench] PyTorch is required ({exc}).")
        return
    sim_bench(Config.load(args.config), envs=args.envs, seconds=args.seconds, seed=args.seed,
              out=args.out, warmup=args.warmup, auto=args.auto, apply=args.apply)


def _cmd_sim_view(args) -> None:
    try:
        from .sim_view import sim_view
    except ImportError as exc:
        print(f"[sim-view] OpenCV is required ({exc}).")
        return
    sim_view(_sized_config(args), matches=args.matches, width=args.width, fps=args.fps,
             seed=args.seed, policy=args.policy, out=args.out, window=not args.no_window,
             grid=not args.no_grid)


def _cmd_policy_stats(args) -> None:
    try:
        from .policy_stats import policy_stats
    except ImportError as exc:
        print(f"[policy-stats] PyTorch is required ({exc}).")
        return
    policy_stats(_sized_config(args), ckpt=args.ckpt, matches=args.matches, envs=args.envs,
                 seed=args.seed, epsilon=args.epsilon, out=args.out)


def _cmd_decks_import(args) -> None:
    from .deck_import import import_decks
    import_decks(Config.load(args.config), limit=args.limit, players=args.players)


def _cmd_cards_art(args) -> None:
    from .card_art import import_card_art
    import_card_art(Config.load(args.config), only_missing=not args.refresh, limit=args.limit)


def _cmd_deck_detect(args) -> None:
    from .deck_detect import detect_deck
    detect_deck(Config.load(args.config), session_arg=args.session, samples=args.samples,
                per_face=args.per_face, player_tag=args.player_tag, out=args.out,
                write_templates=args.write_templates,
                overwrite_templates=args.overwrite_templates,
                deck_only=args.deck_only)


def _cmd_detect_train(args) -> None:
    """Train the VISION network (the board detector).

    Thin wrapper around tools/detect/train.py, which stays the single implementation --
    this exists so the detector is startable the same way every other job is (and so the
    launcher can run it), rather than being the one model you had to train by hand.
    """
    import subprocess
    import sys
    root = Config.load(args.config).root
    script = root / "tools" / "detect" / "train.py"
    if not script.exists():
        print(f"[detect-train] missing {script}")
        return
    argv = [sys.executable, str(script)]
    if args.resume:
        argv += ["--resume"] + ([args.resume] if args.resume != "auto" else [])
    else:
        argv += ["--model", args.model, "--epochs", str(args.epochs), "--imgsz", str(args.imgsz)]
        if args.batch:
            argv += ["--batch", str(args.batch)]
        if args.status_aug:
            argv.append("--status-aug")
    raise SystemExit(subprocess.run(argv, cwd=str(root)).returncode)


def _cmd_calibrate(args) -> None:
    from .calibrate import calibrate
    calibrate(Config.load(args.config), session_arg=args.session, dry_run=args.dry_run)


def _cmd_ui(args) -> None:
    try:
        from .ui.app import serve
    except ImportError as exc:
        print(f"[ui] Flask is required ({exc}).\n"
              "Install it with:\n"
              "  .\\.venv\\Scripts\\python.exe -m pip install flask")
        return
    serve(Config.load(args.config), port=args.port, open_browser=not args.no_browser,
          native_window=not (args.no_browser or args.no_window))


def _cmd_import_from(args) -> None:
    from .migrate import import_from
    import_from(Config.load(args.config), args.old, dry_run=args.dry_run,
                overwrite=args.overwrite, with_sessions=not args.no_sessions,
                with_config=args.with_config)


def _cmd_diag(args) -> None:
    from .diagnose import diagnose
    diagnose(Config.load(args.config))


def _cmd_analyze(args) -> None:
    from .analyze import analyze
    analyze(Config.load(args.config), args.session, args.all, args.window, args.debug)


def _cmd_autolabel(args) -> None:
    from .detect import autolabel
    autolabel(Config.load(args.config), args.session, args.all, args.preview)


def _cmd_preannotate(args) -> None:
    try:
        from .preannotate import preannotate
    except ImportError as exc:
        print(f"[pre-annotate] ultralytics is required ({exc}).")
        return
    preannotate(Config.load(args.config), weights=args.weights, conf=args.conf,
                device=args.device, limit=args.limit, out=args.out, classes=args.classes,
                subdir=args.subdir, model_version=args.model_version)


def _cmd_detect_merge(args) -> None:
    from .detect import detect_merge
    detect_merge(Config.load(args.config), sources=args.sources, out=args.out, dry_run=args.dry_run)


def _cmd_detect_adopt(args) -> None:
    from .detect import detect_adopt
    detect_adopt(Config.load(args.config), args.json, images_dir=args.images,
                 prefix=args.prefix, dry_run=args.dry_run)


def _cmd_detect_check(args) -> None:
    from .detect_check import detect_check
    detect_check(Config.load(args.config), n=args.n, split=args.split, cls=args.cls,
                 out=args.out, seed=args.seed, min_boxes=args.min_boxes, scale=args.scale)


def _cmd_detect_import(args) -> None:
    from .detect import detect_import
    detect_import(Config.load(args.config), args.export, args.val_frac, dry_run=args.dry_run)


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


def _cmd_katacr_segments(args) -> None:
    from .katacr_segments import katacr_segments
    katacr_segments(Config.load(args.config), src=args.src, scale=args.scale,
                    dry_run=args.dry_run)


def _cmd_katacr_boxes(args) -> None:
    from .katacr_boxes import katacr_boxes
    katacr_boxes(Config.load(args.config), src=args.src, dry_run=args.dry_run, limit=args.limit)


def _cmd_models(args) -> None:
    from .models import models
    models(Config.load(args.config))


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
    tsi.add_argument("--resume", action="store_true", help="continue an existing checkpoint instead of training from scratch")
    tsi.add_argument("--resume-from", choices=["best", "latest"], default="best",
                     help="WHICH checkpoint --resume continues: 'best' = policy_sim_best.pt, the "
                          "highest benchmark ever reached (default); 'latest' = policy_sim.pt, "
                          "exactly where the last run stopped, which can be worse")
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
    tsp.add_argument("--device", choices=["cpu", "cuda"], default=None,
                     help="override train.device. CPU is MEASURED FASTER for this trainer (1.0 vs 0.2 "
                          "match/s) -- the match engine is CPU-bound and the net is tiny -- and it frees "
                          "the GPU entirely, so PPO can run alongside a detector train")
    tsp.set_defaults(func=_cmd_train_sim_ppo)

    sbn = sub.add_parser("sim-bench",
                         help="measures training throughput (matches/s) at different --envs on THIS "
                              "machine -> data/sim_bench.json (never writes policy_sim.pt)")
    sbn.add_argument("--auto", action="store_true",
                     help="finds the best value on its own: doubles it until throughput stops "
                          "rising or memory runs short")
    sbn.add_argument("--apply", action="store_true",
                     help="write the recommended value straight into config.yaml (with a backup)")
    sbn.add_argument("--envs", default=None,
                     help="comma list of values to measure (default: derived from the hardware)")
    sbn.add_argument("--seconds", type=float, default=45.0, help="measurement time per setting")
    sbn.add_argument("--warmup", type=float, default=8.0,
                     help="discarded warm-up run (CUDA context); 0 turns it off")
    sbn.add_argument("--seed", type=int, default=0, help="RNG seed, the same for every measurement")
    sbn.add_argument("--out", default=None, help="output JSON (default: data/sim_bench.json)")
    sbn.set_defaults(func=_cmd_sim_bench)

    svw = sub.add_parser("sim-view",
                         help="VISUAL DEBUGGER: watch a sim match rendered from ENGINE state at physics "
                              "resolution (units, HP, status, spell flight, tornado pull, tower fire). "
                              "Read-only -- never writes a checkpoint. SPACE pause, '.' step, Q quit.")
    svw.add_argument("--matches", type=int, default=1, help="how many matches to play out")
    svw.add_argument("--policy", default=None,
                     help="checkpoint to drive YOUR side greedily (e.g. data/policy_sim_ppo_best.pt); "
                          "default = random legal actions, which still exercises every mechanic")
    svw.add_argument("--fps", type=int, default=20,
                     help="playback rate; the sim ticks at sim.sub_dt (0.1s) so 10 = real time, 20 = 2x")
    svw.add_argument("--width", type=int, default=460, help="render width in pixels")
    svw.add_argument("--seed", type=int, default=0, help="RNG seed (same seed = same match)")
    svw.add_argument("--out", default=None, help="also write an mp4 here (e.g. data/sim_debug.mp4)")
    svw.add_argument("--no-window", action="store_true",
                     help="headless: only write --out (for a machine with no display)")
    svw.add_argument("--no-grid", action="store_true",
                     help="hide the placement-grid overlay (action.grid over action.arena_box)")
    svw.add_argument("--size", choices=sorted(_GRID_SIZES), default=None,
                     help="override action.grid (must match the --policy checkpoint's n_cells)")
    svw.set_defaults(func=_cmd_sim_view)

    pst = sub.add_parser("policy-stats",
                         help="measures WHAT the policy plays in the simulator: card frequency, "
                              "placement heatmap, wait-gate rate -> data/policy_stats.json")
    pst.add_argument("--ckpt", default=None,
                     help="checkpoint (default: data/policy_sim_best.pt, else policy_sim.pt)")
    pst.add_argument("--matches", type=int, default=60, help="how many greedy matches to play")
    pst.add_argument("--envs", type=int, default=8, help="matches running in parallel")
    pst.add_argument("--seed", type=int, default=4242, help="RNG seed of the simulator")
    pst.add_argument("--epsilon", type=float, default=0.0,
                     help="share of random moves (0 = purely greedy, the real behaviour)")
    pst.add_argument("--out", default=None, help="output JSON (default: data/policy_stats.json)")
    pst.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution; has to match the checkpoint")
    pst.set_defaults(func=_cmd_policy_stats)

    dki = sub.add_parser("decks-import",
                         help="import the current top meta decks from the official CR API into config/meta_decks.yaml")
    dki.add_argument("--limit", type=int, default=1000, help="how many top DISTINCT decks to keep (default 1000)")
    dki.add_argument("--players", type=int, default=120, help="how many top-ladder players' battle logs to scan")
    dki.set_defaults(func=_cmd_decks_import)

    car = sub.add_parser("cards-art",
                         help="downloads one reference picture per card from the Fandom wiki into "
                              "templates/cardart/ (basis for automatic deck recognition)")
    car.add_argument("--refresh", action="store_true",
                     help="re-download pictures that are already there")
    car.add_argument("--limit", type=int, default=None, help="only the first N cards (for a quick test)")
    car.set_defaults(func=_cmd_cards_art)

    ddt = sub.add_parser("deck-detect",
                         help="recognises the eight deck cards from a recording and "
                              "proposes them for confirmation (replaces renaming the crops by hand)")
    ddt.add_argument("--session", default=None, help="recording (default: the newest)")
    ddt.add_argument("--samples", type=int, default=400, help="how many video frames to sample")
    ddt.add_argument("--per-face", type=int, default=6, dest="per_face",
                     help="how many views of one card face are averaged (more is safer)")
    ddt.add_argument("--player-tag", default=None, dest="player_tag",
                     help="player tag (e.g. #ABC123): reads the card levels from your account "
                          "through the official API; needs a token in CLASHRL_CR_API_TOKEN")
    ddt.add_argument("--out", default=None, help="output JSON (default: data/deck_detect.json)")
    ddt.add_argument("--write-templates", action="store_true", dest="write_templates",
                     help="save every confidently recognised card as a hand template under "
                          "templates/cards/<card>.png, which removes the renaming step")
    ddt.add_argument("--overwrite-templates", action="store_true", dest="overwrite_templates",
                     help="also replace templates that already exist")
    ddt.add_argument("--deck-only", action="store_true", dest="deck_only",
                     help="identify each tray card against only the deck already in cards.yaml "
                          "instead of every card in the game. Far more reliable once the deck is "
                          "correct -- use it to fill in missing hand templates.")
    ddt.set_defaults(func=_cmd_deck_detect)

    dtr = sub.add_parser("detect-train",
                         help="train the VISION network (board detector) on your labelled frames")
    # 'auto', NOT a fixed backbone. train.py reads 'auto' as "continue the detector we have, and
    # only fall back to a sized backbone if there is none" -- and the panel has always passed
    # 'auto'. Naming yolo11s.pt here made the two entry points disagree in the worst possible
    # direction: the same job, started from a terminal instead of the panel, silently THREW AWAY
    # the trained model and began again from COCO weights, while printing nothing to say so.
    dtr.add_argument("--model", default="auto",
                     help="'auto' continues the detector you have (and picks a backbone sized to "
                          "your GPU only if there is none); or name yolo11n/s/m/l/x.pt to start "
                          "from that instead")
    dtr.add_argument("--epochs", type=int, default=120, help="training epochs (early-stops on its own)")
    dtr.add_argument("--imgsz", type=int, default=960, help="training image size")
    dtr.add_argument("--batch", type=int, default=None,
                     help="images per batch; empty auto-sizes to your GPU")
    dtr.add_argument("--status-aug", action="store_true", dest="status_aug",
                     help="extra augmentation for status effects (slow/rage tint, spell haze)")
    dtr.add_argument("--resume", nargs="?", const="auto", default=None, metavar="RUN",
                     help="continue an interrupted run instead of starting a new one")
    dtr.set_defaults(func=_cmd_detect_train)

    cal = sub.add_parser("calibrate",
                         help="re-cut the match detection from YOUR recording (needed for a different "
                              "window size or a different game language)")
    cal.add_argument("--session", default=None, help="recording (default: the newest)")
    cal.add_argument("--dry-run", action="store_true", dest="dry_run",
                     help="report only, write nothing")
    cal.set_defaults(func=_cmd_calibrate)

    ply = sub.add_parser("play", help="run the trained policy live (needs torch + a trained policy)")
    ply.add_argument("--init", default=None, metavar="CKPT",
                     help="which checkpoint to play, e.g. data/policy_sim_best.pt. "
                          "Default: data/policy_rl.pt if present, else data/policy.pt")
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

    pan = sub.add_parser("pre-annotate",
                         help="run the CURRENT detector over the unlabelled queue and write a Label "
                              "Studio TASKS file with its boxes as PRE-ANNOTATIONS, so hand-labelling "
                              "becomes CORRECTING boxes instead of drawing them. Copies no images -- "
                              "the tasks point at images/<queue> where the frames already live")
    pan.add_argument("--conf", type=float, default=0.20,
                     help="detection floor. RECALL-FIRST and deliberately below the live gate (0.40): "
                          "deleting a wrong box is one keypress, drawing a missed one takes seconds")
    pan.add_argument("--weights", default=None,
                     help="best.pt (default: THE vision model, runs/detect/vision/weights/best.pt)")
    pan.add_argument("--device", default=None,
                     help="torch device, e.g. cpu -- use cpu while a training run owns the GPU")
    pan.add_argument("--limit", type=int, default=None, help="only do the first N queue frames (trial)")
    pan.add_argument("--classes", default=None,
                     help="comma list to pre-draw only these classes (default: all)")
    pan.add_argument("--subdir", default=None,
                     help="queue folder under images/ (default: detect.label_queue_subdir). Also the "
                          "path written into the task's ?d= reference, so it must match what Label "
                          "Studio serves")
    pan.add_argument("--model-version", dest="model_version", default=None,
                     help="label the predictions with this (default: the run folder, e.g. board-16) "
                          "so you can tell WHICH detector guessed when reviewing")
    pan.add_argument("--out", default=None,
                     help="tasks JSON path (default: <dataset_dir>/preannot_tasks.json)")
    pan.set_defaults(func=_cmd_preannotate)

    din = sub.add_parser("detect-import",
                         help="import a Label Studio JSON or YOLO export into the training dataset (remaps classes by name + train/val split)")
    din.add_argument("--export", required=True, help="path to the LS export: a JSON file / folder (recommended on Windows), or a YOLO export folder (classes.txt + labels/)")
    din.add_argument("--val-frac", type=float, default=None, help="validation fraction (default: detect.val_frac)")
    din.add_argument("--dry-run", action="store_true",
                     help="report what would be imported, which classes do not map, and which of "
                          "YOUR frames the export would push out of the split -- writes nothing. "
                          "Use this first for any dataset you did not label yourself")
    din.set_defaults(func=_cmd_detect_import)

    dad = sub.add_parser("detect-adopt",
                         help="ADOPT someone else's export + image folder into the labelling queue, "
                              "renaming around filename COLLISIONS automatically (a helper's generic "
                              "frame_0005.png restarts every batch and would otherwise overwrite the "
                              "previous batch's images, silently repointing its annotations)")
    dad.add_argument("--json", required=True, help="their Label Studio JSON export")
    dad.add_argument("--images", default=None,
                     help="folder holding their image files (default: auto-detect under data/detect)")
    dad.add_argument("--prefix", default=None,
                     help="rename prefix to apply on collision (default: the json's stem, e.g. batch4_)")
    dad.add_argument("--dry-run", action="store_true",
                     help="report what WOULD happen and write nothing")
    dad.set_defaults(func=_cmd_detect_adopt)

    dmg = sub.add_parser("detect-merge",
                         help="fuse several Label Studio exports into ONE combined json (deduped by "
                              "image, richest annotation wins) -- a single self-contained artifact "
                              "instead of a growing pile of batch*.json")
    dmg.add_argument("--sources", default=None,
                     help="comma list of exports (default: every batch*.json in the dataset dir, "
                          "skipping *.raw.json.bak and the output itself)")
    dmg.add_argument("--out", default=None, help="output path (default: data/detect/batch_all.json)")
    dmg.add_argument("--dry-run", action="store_true", help="report the merge and write nothing")
    dmg.set_defaults(func=_cmd_detect_merge)

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

    # The counterpart to detect-preview: that one shows what the MODEL predicts, this one shows
    # what the LABELS claim. A dataset can pass every count-based check with every box in the
    # wrong place, and looking is the only way to find that.
    dck = sub.add_parser("detect-check",
                         help="draw the GROUND-TRUTH boxes onto frames and save a contact sheet "
                              "-- verify a dataset (especially an imported one) with your eyes")
    dck.add_argument("--class", dest="cls", default=None,
                     help="only frames containing this class, and highlight it. The point of the "
                          "tool: a class with 1 box is where a single mislabel is 100%% of it")
    dck.add_argument("--n", type=int, default=6, help="how many frames to show")
    dck.add_argument("--split", default="train", choices=("train", "val", "both"))
    dck.add_argument("--min-boxes", type=int, default=1, help="skip frames with fewer boxes")
    dck.add_argument("--scale", type=float, default=0.5, help="tile scale (1.0 = native size)")
    dck.add_argument("--seed", type=int, default=None, help="repeat the same sample")
    dck.add_argument("--out", default=None, help="output image (default: data/detect_check.jpg)")
    dck.set_defaults(func=_cmd_detect_check)

    kseg = sub.add_parser("katacr-segments",
                          help="import KataCR's MIT-licensed segment library into the sprite bank "
                               "(maps their singular/hyphenated names onto our taxonomy and RESCALES "
                               "to our arena -- synth pastes at native size)")
    kseg.add_argument("--src", required=True,
                      help="their Clash-Royale-Detection-Dataset folder (or its images/segment)")
    kseg.add_argument("--scale", default="auto",
                      help="'auto' measures the factor from classes both banks share, or give a number")
    kseg.add_argument("--dry-run", action="store_true", help="report the mapping and write nothing")
    kseg.set_defaults(func=_cmd_katacr_segments)

    kbox = sub.add_parser("katacr-boxes",
                          help="import KataCR's hand-labelled DETECTION frames (images/part2) into "
                               "images/train -- val is left untouched so the next detector stays "
                               "comparable to the current one")
    kbox.add_argument("--src", required=True,
                      help="their Clash-Royale-Detection-Dataset folder (or its images/part2)")
    kbox.add_argument("--limit", type=int, default=0, help="stop after N frames (for a quick trial)")
    kbox.add_argument("--dry-run", action="store_true",
                      help="report the mapping and the per-class gain, and write nothing")
    kbox.set_defaults(func=_cmd_katacr_boxes)

    mdl = sub.add_parser("models",
                         help="which NETWORKS exist and which one each path actually uses -- there "
                              "are two (the VISION detector and the PLAYING policy) and they share "
                              "nothing; also checks the pin resolves and inference imgsz matches training")
    mdl.set_defaults(func=_cmd_models)

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
                         help="local control panel (start/stop, live log, progress, deck and config "
                              "editor); opens as its own window if pywebview is installed, otherwise "
                              "a browser tab; binds to 127.0.0.1 only")
    uip.add_argument("--port", type=int, default=8765, help="port (default 8765)")
    uip.add_argument("--no-window", action="store_true", dest="no_window",
                     help="use a browser tab instead of the native window, even if pywebview is installed")
    uip.add_argument("--no-browser", action="store_true", dest="no_browser",
                     help="do not open anything automatically (server only); implies --no-window")
    uip.set_defaults(func=_cmd_ui)

    imp = sub.add_parser("import-from",
                         help="take checkpoints, recordings and templates from an older "
                              "installation of this project")
    imp.add_argument("old", help="path to the old folder (repository root or the icebow folder)")
    imp.add_argument("--dry-run", action="store_true", dest="dry_run",
                     help="only list what would be copied")
    imp.add_argument("--overwrite", action="store_true",
                     help="also replace files that already exist here")
    imp.add_argument("--no-sessions", action="store_true", dest="no_sessions",
                     help="skip the recordings (they are the large part)")
    imp.add_argument("--with-config", action="store_true", dest="with_config",
                     help="also take cards.yaml and config.yaml, which decide the deck and the "
                          "screen calibration")
    imp.set_defaults(func=_cmd_import_from)

    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        # Ctrl+C (or the launcher's stop button) during a phase the command does not guard
        # itself -- most visibly while the env pool is still being built. Nothing has been
        # trained yet, so there is nothing to save; exit quietly instead of dumping a
        # traceback and a Windows control-C exit code that looks like a crash.
        print("\n[clashrl] aborted.", flush=True)
        raise SystemExit(130)


if __name__ == "__main__":
    main()
