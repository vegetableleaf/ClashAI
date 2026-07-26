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
    verify(Config.load(args.config), args.session, args.towers, args.hand, args.spells, args.threats)


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
    train_bc(Config.load(args.config))


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


def _cmd_diag(args) -> None:
    from .diagnose import diagnose
    diagnose(Config.load(args.config))


def _cmd_analyze(args) -> None:
    from .analyze import analyze
    analyze(Config.load(args.config), args.session, args.all, args.window, args.debug)


def _cmd_autolabel(args) -> None:
    from .detect import autolabel
    autolabel(Config.load(args.config), args.session, args.all, args.preview)


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
    tbc.set_defaults(func=_cmd_train_bc)

    trl = sub.add_parser("train-rl", help="RL fine-tune the policy on live matches (tower/win rewards)")
    trl.set_defaults(func=_cmd_train_rl)

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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
