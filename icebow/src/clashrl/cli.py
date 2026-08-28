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
    import_cards(Config.load(args.config), write=bool(getattr(args, "write", False)),
                 force_fields=tuple(getattr(args, "force_field", None) or ()))


def _cmd_train_bc(args) -> None:
    try:
        from .train_bc import train_bc
    except ImportError as exc:
        print(f"[train-bc] PyTorch is required ({exc}).\n"
              "Install the CUDA build:\n"
              "  pip install torch --index-url https://download.pytorch.org/whl/cu121")
        return
    train_bc(Config.load(args.config), init=args.init, iterations=args.iterations,
             data=args.data, val_frac=args.val_frac, patience=args.patience)


def _cmd_replay_bc(args) -> None:
    try:
        from .replay_bc import build_replay_bc
    except ImportError as exc:
        print(f"[replay-bc] OpenCV/NumPy are required ({exc}).")
        return
    build_replay_bc(Config.load(args.config), replays=args.replays, weights=args.weights,
                    jobs=getattr(args, "jobs", 1),
                    conf=args.conf, stride=args.stride, out=args.out, min_hand=args.min_hand,
                    limit=args.limit, preview=args.preview)


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
    cfg = _sized_config(args)
    if getattr(args, "out", None):
        # SEPARATE CHECKPOINTS PER ARM. Both arms of an A/B write train.sim_ppo_checkpoint, so
        # running them at the same time means each finishes by overwriting the other's policy --
        # and the comparison would be between one run and itself.
        cfg = _KeyOverride(cfg, ("train", "sim_ppo_checkpoint"), str(args.out))
        print(f"[train-sim-ppo] checkpoint -> {args.out}")
    if getattr(args, "drill_only", None):
        cfg = _KeyOverride(cfg, ("sim", "drill_only"),
                           [x.strip() for x in str(args.drill_only).split(",") if x.strip()])
        print(f"[train-sim-ppo] DRILL-ONLY: {args.drill_only}")
    if getattr(args, "drill_frac", None) is not None:
        # A/B THE DRILL MIX FROM THE COMMAND LINE. The whole point of the mixing ratio is that it
        # gets measured against 0.0 rather than assumed, and an override that needs a config edit
        # between the two arms is an override that quietly never gets tested.
        cfg = _DrillFracOverride(cfg, float(args.drill_frac))
        _t = float(args.drill_frac)
        # drill_frac is a share of STEPS, not of episodes -- a drill is ~20 steps against a match's
        # ~272, so 0.3 of steps is ~85% of EPISODES. The old banner said "of episodes" and was
        # wrong by that whole factor, which is how "drills 86% of eps" read as a bug for a while.
        _p = 0.0 if _t <= 0 else _t * 272.0 / (20.0 * (1.0 - _t) + _t * 272.0)
        print(f"[train-sim-ppo] drill mix: {_t:.0%} of STEPS are DRILLS "
              f"(~{_p:.0%} of episodes)")
    train_sim_ppo(cfg, matches=args.matches, resume=args.resume,
                  workers=getattr(args, "workers", None),
                  seed=args.seed, envs=args.envs, init=args.init, device=args.device,
                  reset_gate=args.reset_gate,
                  distill_corpus=getattr(args, "distill_corpus", None),
                  distill_coef=float(getattr(args, "distill_coef", 0.0) or 0.0),
                  distill_batch=int(getattr(args, "distill_batch", 256) or 256))


class _KeyOverride:
    """Wraps a Config so ONE key reads back as an override, leaving everything else on disk."""

    def __init__(self, cfg, key, value):
        self._cfg = cfg
        self._key = tuple(key)
        self._value = value

    def get(self, *keys, **kw):
        if tuple(keys) == self._key:
            return self._value
        return self._cfg.get(*keys, **kw)

    def __getattr__(self, name):
        return getattr(self._cfg, name)


class _DrillFracOverride:
    """Wraps a Config so `sim.drill_frac` reads back as the command-line value.

    A thin proxy rather than a mutation: the rollout workers each re-read the config, and a value
    written into the object here has to survive being handed to them, while everything else about
    the config must stay exactly what was loaded from disk.
    """

    def __init__(self, cfg, frac: float):
        self._cfg = cfg
        self._frac = float(frac)

    def get(self, *keys, **kw):
        if tuple(keys) == ("sim", "drill_frac"):
            return self._frac
        return self._cfg.get(*keys, **kw)

    def __getattr__(self, name):
        return getattr(self._cfg, name)


def _cmd_drills(args) -> None:
    from .sim import scenarios as _sc
    from .sim.drill_env import report as _report
    n = _sc.load_all()
    if not n:
        print("[drills] no scenarios registered (expected src/clashrl/sim/drills_<deck>.py)")
        return
    names = [s.strip() for s in str(args.only).split(",") if s.strip()] if args.only else None
    if args.tier:
        names = [s.name for s in _sc.by_tier(args.tier) if not names or s.name in names]
    pol = None
    if args.policy:
        _smv = getattr(args, "spell_min_value", None)
        if _smv is None:
            _smv = Config.load(args.config).get("sim", "ppo_spell_min_value", default=0.0)
        pol = _drill_policy_from_checkpoint(args.policy, args.device,
                                           spell_min_value=float(_smv or 0.0))
    rows = _report(Config.load(args.config), names=names, reps=args.reps, seed=args.seed,
                   policy=pol, level=args.level, reward_mode=bool(getattr(args, "reward", False)))
    if getattr(args, "outcomes", False):
        from .sim.drill_env import outcomes as _outcomes
        _outcomes(Config.load(args.config), names=names, reps=args.reps, seed=args.seed,
                  level=args.level)
        return
    if getattr(args, "reward", False):
        gaps = [r for r in rows if str(r.get("verdict", "")).startswith("UNPRICED")]
        if gaps:
            print("")
            print("%d UNPRICED interaction(s) -- drilling these cannot teach them, "
                  "because passing earns no more than failing:" % len(gaps))
            for r in gaps:
                print("   %-30s graded_by %s" % (r["name"], ", ".join(r["graded_by"]) or "-"))
        return
    bad = [r for r in rows if r["verdict"].startswith("NOT DISCRIMINATING")]
    if bad:
        print("\n%d drill(s) NOT DISCRIMINATING -- doing nothing scores what the doctrine scores, "
              "so they are measuring the board, not the play:" % len(bad))
        for r in bad:
            print("   %-28s nothing %.0f%%  doctrine %.0f%%"
                  % (r["name"], 100 * r["baseline"], 100 * r["doctrine"]))


def _drill_policy_from_checkpoint(path: str, device: str = None, spell_min_value: float = 0.0):
    """Wrap a trained checkpoint as a drill policy (obs, env) -> action, or None if torch is absent.

    GREEDY, and masked exactly the way training masks: a card must be in hand and affordable. An
    unmasked argmax measures the head's raw preference rather than the policy, and would read as
    "it plays nonsense" whenever its favourite card is simply not in hand.
    """
    try:
        import numpy as _np
        import torch
        from .model import PolicyNet
    except ImportError as exc:
        print(f"[drills] --policy needs PyTorch ({exc}); running baseline + doctrine only")
        return None
    try:
        ck = torch.load(path, map_location="cpu")
        dev = torch.device(device or "cpu")
        net = PolicyNet(int(ck.get("in_ch", 3)), int(ck["n_cards"]), int(ck["n_cells"]),
                        threat_dim=int(ck.get("threat_dim", 14))).to(dev)
        net.load_state_dict(ck["model"])
        net.eval()
    except Exception as exc:  # noqa: BLE001 -- a bad path must not kill the report
        print(f"[drills] could not load {path}: {exc}")
        return None

    # THE GATE HEAD, if the checkpoint carries one (every PPO checkpoint does). A drill report that
    # ignores it is not reporting the policy.
    gate = None
    try:
        import torch.nn as _nn
        if "gate" in ck:
            gate = _nn.Linear(net.embed_dim, 2)
            gate.load_state_dict(ck["gate"])
            gate.eval()
    except Exception:  # noqa: BLE001 -- a checkpoint without a gate still measures card+cell
        gate = None
    # `sim.ppo_gate_threshold`, read from the default config -- this helper takes no cfg, and the
    # threshold is what separates "the policy" from "a policy that plays on every affordable step".
    try:
        gate_tau = float(Config.load(None).get("sim", "ppo_gate_threshold", default=0.25))
    except Exception:  # noqa: BLE001
        gate_tau = 0.25

    def _t(v):
        return torch.as_tensor(_np.asarray(v)[None], dtype=torch.float32, device=dev)

    def _policy(obs, env):
        with torch.no_grad():
            x = _t(_np.asarray(obs, dtype=_np.float32).transpose(2, 0, 1)) \
                if _np.asarray(obs).ndim == 3 else _t(obs)
            # forward_parts gives the embedding the GATE reads plus the PER-CARD cell maps. The old
            # `net(...)` two-tuple discarded the embedding and returned cells as (B, n_cards,
            # n_cells), which the caller then argmaxed FLAT -- an index over cards x cells, not a
            # cell.
            z, cards, cells = net.forward_parts(x, _t(env.hand_vec), _t(env.next_vec),
                                                _t(env.elixir_vec), _t(env.threat_vec))
            # SAME MASK AS TRAINING: in hand and affordable. Without it this measures the head's
            # raw preference, not the policy that would actually be executed.
            playable = [i for i in env._hand_ids()
                        if 0 <= i < len(env.specs)
                        and float(env.eng.elixir[0]) >= float(env.specs[i].elixir)]
            if not playable:
                return (0, 0, 0)
            # SPELL CARD VETO -- the same rule train_sim_ppo applies in sampling and in its greedy
            # benchmark. It has to be HERE too: this is a THIRD greedy implementation (the drill
            # report's own), and a drill run that skipped the veto would grade a policy the shipped
            # one does not play. Off at 0.0, which is the shipped default.
            if spell_min_value > 0.0 and hasattr(env, "spell_card_ok"):
                kept = []
                for _ci in playable:
                    try:
                        _ok, _w = env.spell_card_ok(int(_ci), spell_min_value)
                    except Exception:  # noqa: BLE001 -- never break a drill
                        _ok = True
                    if _ok:
                        kept.append(_ci)
                playable = kept
                if not playable:
                    return (0, 0, 0)
            # THE GATE DECIDES WHETHER TO PLAY AT ALL, exactly as the trainer's greedy benchmark
            # does: threshold the play PROBABILITY at sim.ppo_gate_threshold. Without this the
            # column measured a policy that plays on every affordable step, which is not what any
            # checkpoint does -- and it reported 0% on drills the real policy passes 8/8.
            if gate is not None:
                g = gate(z)[0]
                if float(torch.softmax(g, dim=0)[1]) <= gate_tau:
                    return (0, 0, 0)
            keep = torch.full_like(cards[0], float("-inf"))
            for i in playable:
                keep[i] = cards[0][i]
            card = int(torch.argmax(keep).item())
            # PER-CARD map, then the same cell mask training applies: every cell for an "anywhere"
            # card (spells, miner), the deployable set otherwise.
            row = cells[0, card].clone()
            if card not in getattr(env, "anywhere_ids", set()):
                dep = _np.asarray(env.actions.deployable_mask(False), dtype=bool)
                row[~torch.as_tensor(dep, device=row.device)] = float("-inf")
            cell = int(torch.argmax(row).item())
        return (1, card, cell)
    return _policy


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
                overwrite_templates=args.overwrite_templates)


def _cmd_calibrate(args) -> None:
    from .calibrate import calibrate
    calibrate(Config.load(args.config), session_arg=args.session, dry_run=args.dry_run)


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
                subdir=args.subdir, model_version=args.model_version, reoffer=args.reoffer)


def _cmd_detect_merge(args) -> None:
    from .detect import detect_merge
    detect_merge(Config.load(args.config), sources=args.sources, out=args.out, dry_run=args.dry_run)


def _cmd_detect_adopt(args) -> None:
    from .detect import detect_adopt
    detect_adopt(Config.load(args.config), args.json, images_dir=args.images,
                 prefix=args.prefix, dry_run=args.dry_run)


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


def _cmd_katacr_segments(args) -> None:
    from .katacr_segments import katacr_segments
    katacr_segments(Config.load(args.config), src=args.src, src_width=args.src_width,
                    dry_run=args.dry_run)


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
                         help="import/refresh card stats from the Clash Royale Fandom wiki "
                              "(MediaWiki level-11 vardefines); DRY-RUN by default")
    mx = cri.add_mutually_exclusive_group()
    mx.add_argument("--dry-run", action="store_true", dest="dry_run",
                    help="scrape, diff against the existing config/cards_stats.json and write "
                         "NOTHING (this is the default behaviour)")
    mx.add_argument("--write", action="store_true",
                    help="apply: overwrite config/cards_stats.json (guarded -- refuses if a "
                         "pinned field would regress or a verified: true row would change)")
    cri.add_argument("--force-field", action="append", metavar="KEY.FIELD", dest="force_field",
                     default=None,
                     help="let this pinned/verified field change anyway (repeatable), e.g. "
                          "--force-field rocket.crown_tower_damage; update import_pins.json in "
                          "the same commit or the next run refuses again")
    cri.set_defaults(func=_cmd_cards_import)

    tbc = sub.add_parser("train-bc", help="behaviour-cloning pretrain of the CNN policy (needs torch)")
    tbc.add_argument("--init", metavar="CKPT", default=None,
                     help="warm-start from a checkpoint (e.g. data/policy_sim.pt) and fine-tune it on your "
                          "recordings instead of random init -- combines the sim prior with your play")
    tbc.add_argument("--iterations", type=int, default=1, metavar="N",
                     help="run N successive BC passes in one command, each warm-starting from the previous "
                          "(fresh optimizer each pass, not just more epochs); saves data/policy.pt after every pass")
    tbc.add_argument("--data", default=None, metavar="DIR",
                     help="dataset root to clone from (default: record.out_dir = your recordings). "
                          "Use data/replay_bc for the pro-replay samples built by `replay-bc`.")
    tbc.add_argument("--val-frac", type=float, default=0.0, dest="val_frac", metavar="F",
                     help="hold out this fraction for validation and EARLY-STOP on it (e.g. 0.2). "
                          "Strongly recommended when cloning replays: it is what stops the policy "
                          "memorising a small, detector-noisy set instead of generalising from it.")
    tbc.add_argument("--patience", type=int, default=3, metavar="N",
                     help="early-stop after N epochs without val-loss improvement (default 3)")
    tbc.set_defaults(func=_cmd_train_bc)

    rbc = sub.add_parser("replay-bc",
                         help="mine PRO replay videos into a train-bc dataset (detector -> canonical "
                              "re-render + semantic canvas; never the pro's pixels)")
    rbc.add_argument("--replays", default=None, metavar="DIR",
                     help="folder of replay videos (default: replay_mine.replays_dir)")
    rbc.add_argument("--weights", default=None, help="detector weights (default: the pinned detector)")
    rbc.add_argument("--conf", type=float, default=None, help="detector confidence (default: replay_mine.detect_conf)")
    rbc.add_argument("--stride", type=int, default=None,
                     help="sample every Nth frame (default: replay_mine.frame_stride)")
    rbc.add_argument("--out", default=None, metavar="DIR", help="output root (default: data/replay_bc)")
    rbc.add_argument("--min-hand", type=int, default=2, dest="min_hand", metavar="N",
                     help="skip a play unless at least N tray cards were recognised -- BC learns "
                          "'which card AMONG THESE', which needs a real hand (default 2)")
    rbc.add_argument("--limit", type=int, default=0, metavar="N",
                     help="stop after N samples per video (0 = no cap; handy for a quick trial)")
    rbc.add_argument("--jobs", type=int, default=1, metavar="N",
                     help="mine N VIDEOS concurrently, one process each (default 1). Videos are "
                          "independent and one video's pipeline is ~one core, so this is close to "
                          "linear wall-clock speedup up to the video count.")
    rbc.add_argument("--preview", action="store_true",
                     help="also save annotated frames of each mined play so you can EYEBALL what "
                          "was recovered before training on it")
    rbc.set_defaults(func=_cmd_replay_bc)

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
    tsp.add_argument("--reset-gate", action="store_true",
                     help="keep the warm-started TRUNK but start the wait/play gate FRESH. Use when the "
                          "source checkpoint's gate has COLLAPSED to always-play: measured P(play) 0.938 "
                          "with min 0.911 means it never holds at any threshold, elixir never passes 5, "
                          "and the 6-cost win conditions stay masked (= zero policy gradient) forever. "
                          "A fresh gate starts near P(play) 0.5, so the bar can climb and X-Bow/Rocket "
                          "become samplable again, while the trunk keeps everything it learned.")
    tsp.add_argument("--seed", type=int, default=0, help="RNG seed for the simulator")
    tsp.add_argument("--envs", type=int, default=None,
                     help="parallel (vectorized) match instances (default: sim.envs)")
    tsp.add_argument("--workers", type=int, default=None,
                     help="rollout WORKER PROCESSES (engine shards; 0/1 = classic in-process). The "
                          "engine is pure Python, so this is how the other 15 cores get used: "
                          "12 workers x 8+ envs measured ~10-20x the single-process throughput")
    tsp.add_argument("--size", choices=["576", "432"], default=None,
                     help="board resolution 576=[18,32] / 432=[18,24]; overrides action.grid for this run")
    tsp.add_argument("--device", choices=["cpu", "cuda"], default=None,
                     help="override train.device. CPU is MEASURED FASTER for this trainer (1.0 vs 0.2 "
                          "match/s) -- the match engine is CPU-bound and the net is tiny -- and it frees "
                          "the GPU entirely, so PPO can run alongside a detector train")
    tsp.add_argument("--out", default=None,
                     help="checkpoint path for THIS run (overrides train.sim_ppo_checkpoint). "
                          "Required when running two arms of an A/B at once, or each finishes by "
                          "overwriting the other.")
    tsp.add_argument("--drill-only", default=None,
                     help="train on ONLY these drills (comma list). Diagnostic: separates 'cannot "
                          "learn a drill' from '28 drills competing for one policy'.")
    tsp.add_argument("--drill-frac", type=float, default=None,
                     help="fraction of episodes that are DRILLS instead of full matches "
                          "(overrides sim.drill_frac; 0 = plain matches, 0.3 = suggested mix). "
                          "Use this to A/B the drill curriculum against a plain run.")
    tsp.add_argument("--distill-corpus", default=None, metavar="NPZ",
                     help="teacher corpus from research/sim_parity/scripts/distill_label.py. Adds a "
                          "CARD-HEAD cross-entropy toward the rollout-search teacher's card. Measured "
                          "on a held-out split BY MATCH: card agreement 0.4955 -> 0.8754 (+38pp over "
                          "the base policy). The GATE is deliberately NOT distilled -- it measured "
                          "0.5892 -> 0.6012, BELOW the always-WAIT floor of 0.7756, so the teacher's "
                          "timing edge is not recoverable from the student's observation.")
    tsp.add_argument("--distill-coef", type=float, default=0.0,
                     help="weight on the card-distillation term (0 = OFF, the default). UNTUNED: no "
                          "A/B has been run on this value, so treat any setting as arm 1 of an "
                          "experiment, not as a shipped default.")
    tsp.add_argument("--distill-batch", type=int, default=256,
                     help="teacher rows sampled per update for the distillation term")
    tsp.set_defaults(func=_cmd_train_sim_ppo)

    drl = sub.add_parser("drills",
                         help="run the segmented mini-sim DRILLS and report pass rates "
                              "(do-nothing baseline vs the doctrine oracle vs an optional policy)")
    drl.add_argument("--reps", type=int, default=25,
                     help="repetitions per drill per policy (more = tighter pass-rate estimate)")
    drl.add_argument("--seed", type=int, default=5, help="RNG seed, the same for every policy")
    drl.add_argument("--only", default=None, help="comma list of drill names (default: all)")
    drl.add_argument("--spell-min-value", type=float, default=None,
                     help="override sim.ppo_spell_min_value for THIS report (tower fractions; "
                          "0 = no spell CARD veto). Default: whatever config says.")
    drl.add_argument("--tier", default=None,
                     help="only this tier: foundational | compound | matchup")
    # DEFAULT None = roll each enemy's level from the ladder distribution the full sim uses
    # (sim.enemy_levels). It used to default to 11 while OUR deck plays at real account levels up to
    # 16 and match training rolls the enemy 13-16 -- so every drill was a fight against cards three
    # levels below the ones it was preparing for. Pass --level to PIN it (fair eval / diagnosis).
    drl.add_argument("--level", type=int, default=None,
                     help="PIN scripted spawns to this card level (default: roll 13-16 like the "
                          "ladder opponent the full sim uses)")
    drl.add_argument("--outcomes", action="store_true",
                     help="ACCEPTANCE TEST: per drill, the mean reward of each OUTCOME under the "
                          "trainer's own exploration. Passing must pay more than failing OR timing "
                          "out; where it does not, the drill teaches its own opposite.")
    drl.add_argument("--reward", action="store_true",
                     help="REWARD-GAP mode: per drill, the episode reward for doing nothing vs "
                          "for the correct play. Where they are equal the interaction is unpriced "
                          "and training on that drill cannot teach it.")
    drl.add_argument("--policy", default=None,
                     help="also score a trained checkpoint (e.g. data/policy_sim.pt)")
    drl.add_argument("--device", default=None, help="torch device for --policy")
    drl.set_defaults(func=_cmd_drills)

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
    ddt.set_defaults(func=_cmd_deck_detect)

    cal = sub.add_parser("calibrate",
                         help="re-cut the match detection from YOUR recording (needed for a different "
                              "window size or a different game language)")
    cal.add_argument("--session", default=None, help="recording (default: the newest)")
    cal.add_argument("--dry-run", action="store_true", dest="dry_run",
                     help="report only, write nothing")
    cal.set_defaults(func=_cmd_calibrate)

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

    pan = sub.add_parser("pre-annotate",
                         help="run the CURRENT detector over the unlabelled queue and write a Label "
                              "Studio TASKS file with its boxes as PRE-ANNOTATIONS, so hand-labelling "
                              "becomes CORRECTING boxes instead of drawing them. Copies no images -- "
                              "the tasks point at images/<queue> where the frames already live")
    pan.add_argument("--conf", type=float, default=0.20,
                     help="detection floor. RECALL-FIRST and deliberately below the live gate (0.40): "
                          "deleting a wrong box is one keypress, drawing a missed one takes seconds")
    pan.add_argument("--weights", default=None, help="best.pt (default: the pinned detect.weights)")
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
    pan.add_argument("--reoffer", action="store_true",
                     help="IGNORE the preannot_offered.txt ledger and rebuild tasks for every frame "
                          "not yet imported. By default a re-run emits ONLY frames added since the "
                          "last run, so importing it cannot duplicate tasks already in your Label "
                          "Studio project. Use this only when starting a FRESH project.")
    pan.set_defaults(func=_cmd_preannotate)

    din = sub.add_parser("detect-import",
                         help="import a Label Studio JSON or YOLO export into the training dataset (remaps classes by name + train/val split)")
    din.add_argument("--export", required=True, help="path to the LS export: a JSON file / folder (recommended on Windows), or a YOLO export folder (classes.txt + labels/)")
    din.add_argument("--val-frac", type=float, default=None, help="validation fraction (default: detect.val_frac)")
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

    kseg = sub.add_parser("katacr-segments",
                          help="import KataCR's MIT-licensed segment library into the sprite bank "
                               "(maps their singular/hyphenated names onto our taxonomy and tags the "
                               "segments with a measured source width so synth pastes them at size)")
    kseg.add_argument("--src", required=True,
                      help="their Clash-Royale-Detection-Dataset folder (or its images/segment)")
    kseg.add_argument("--src-width", default="auto",
                      help="effective frame width their segments were cut from, in px; 'auto' "
                           "measures it from the classes both banks share (needs a width-tagged bank)")
    kseg.add_argument("--dry-run", action="store_true", help="report the mapping and write nothing")
    kseg.set_defaults(func=_cmd_katacr_segments)

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
    spr.add_argument("--seed", type=int, default=0,
                     help="RNG seed for the --synth draw (default 0 = REPRODUCIBLE). Synth is ~40%% of the "
                          "training set, so an unseeded regeneration silently changes that much of the data "
                          "and makes any generation-to-generation comparison unattributable -- board-23's "
                          "-5.1pp vs board-21 could not be split between the sprite-scaling fix and the new "
                          "random draw. Vary it deliberately to MEASURE synth-draw noise.")
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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
