"""Deployed live decision options (the LIVE_OPTIONS file), applied the way CKPT_OVERRIDE selects the checkpoint.

The file holds decision-option flags (pipeline.decision_options.add_arguments only), shell-quoted, '#' comments.
Every decision-option flag the command line sets explicitly wins; ``--no-live-options`` ignores the file; an absent
file leaves the plain defaults. A flag the file does not know refuses the run (argparse exit 2).
"""
import argparse
import shlex
from pathlib import Path

from .decision_options import add_arguments

_UNSET = object()


def _decision_parser(prog):
    parser = argparse.ArgumentParser(prog=prog, add_help=False)
    add_arguments(parser)
    return parser


def decision_dests():
    return [a.dest for a in _decision_parser('decision')._actions]


def add_live_options_arguments(parser, default_file):
    parser.add_argument('--live-options-file', type=Path, default=Path(default_file),
                        help='deployed decision options, applied to every decision-option flag the command line '
                             'does not set (explicit flags win)')
    parser.add_argument('--no-live-options', action='store_true', help='ignore --live-options-file: plain defaults')


def parse_with_live_options(parser, argv=None):
    """-> (args, record). ``record`` (logged): file (None = not applied), from_file, explicit, ignored."""
    dests = decision_dests()
    unset = lambda: argparse.Namespace(**{d: _UNSET for d in dests})  # noqa: E731
    args = parser.parse_args(argv, namespace=unset())
    explicit = sorted(d for d in dests if getattr(args, d) is not _UNSET)
    path, from_file = Path(args.live_options_file), {}
    applied = not args.no_live_options and path.is_file()
    if applied:
        tokens = shlex.split(path.read_text(encoding='utf-8-sig'), comments=True)
        parsed = _decision_parser(str(path)).parse_args(tokens, namespace=unset())
        from_file = {d: getattr(parsed, d) for d in dests
                     if getattr(parsed, d) is not _UNSET and d not in explicit}
    for d in dests:
        if getattr(args, d) is _UNSET:
            setattr(args, d, from_file.get(d, parser.get_default(d)))
    record = dict(file=str(path) if applied else None, from_file={d: getattr(args, d) for d in sorted(from_file)},
                  explicit=explicit, ignored=bool(args.no_live_options))
    return args, record
