"""Command-line interface for the bot."""
from __future__ import annotations

import argparse

from .bot import ClashBot
from .capture import WindowCapture
from .config import Config
from .controller import Controller
from .learning import make_learner
from .vision import Vision


def _build(cfg: Config):
    capture = WindowCapture(
        cfg.get("window", "title_contains", default=None),
        cfg.get("window", "region", default=None),
    )
    vision = Vision(cfg)
    controller = Controller(capture, cfg)
    learner = make_learner(cfg)
    return capture, vision, controller, learner


def _cmd_run(args) -> None:
    cfg = Config.load(args.config)
    capture, vision, controller, learner = _build(cfg)
    ClashBot(capture, vision, controller, learner, cfg).run()


def _cmd_calibrate(args) -> None:
    from .calibrate import calibrate
    calibrate(Config.load(args.config))


def _cmd_capture(args) -> None:
    from .calibrate import capture_template
    capture_template(Config.load(args.config), args.name, cards=args.card)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clashbot",
        description="Educational Clash Royale 2v2 spell-cycle bot.",
    )
    parser.add_argument("--config", default=None, help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("run", help="start the bot").set_defaults(func=_cmd_run)
    sub.add_parser("calibrate", help="live overlay to tune coordinates").set_defaults(func=_cmd_calibrate)

    cap = sub.add_parser("capture-template", help="save a template image for detection")
    cap.add_argument("name", help="output name, e.g. home_menu or fireball")
    cap.add_argument("--card", action="store_true", help="save under templates/cards/")
    cap.set_defaults(func=_cmd_capture)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
