"""Deployed live decision options (the LIVE_OPTIONS file), applied the way CKPT_OVERRIDE selects the checkpoint.

The file holds decision-option flags (pipeline.decision_options.add_arguments) plus EXTRA_LIVE_FLAGS, shell-quoted, '#' comments,
full flag names, each flag at most once. Every decision-option flag the command line sets explicitly wins;
``--no-live-options`` ignores the file; an ABSENT file runs the plain defaults and says so loudly (status 'ABSENT').
An unknown, abbreviated or repeated flag in the file refuses the run (argparse exit 2).
"""
import argparse
import shlex
from pathlib import Path

from .decision_options import add_arguments

_UNSET = object()


# Live-only switches the file may also deploy (owner 2026-10-08: "switch it on" for own_effects). Each must also be a
# live_play.py flag with the same name and action; explicit command-line use still wins.
EXTRA_LIVE_FLAGS = (('--own-effects', dict(action='store_true')),
                    ('--iw-press-pstar', dict(type=float, default=None)),   # owner 2026-10-08: IW higher bar
                    ('--hero-ability-spec', dict(choices=('off', 'supplement'), default='off')),   # L74 econ2 Hero IW token
                    # L74 latency (owner-tested 2026-10-08): input path, affordability hold window, refused-tap release,
                    # look-ahead horizon -- deployable together so the horizon can follow the measured latency
                    ('--fast-input', dict(action='store_true')),
                    ('--tap-gap-ms', dict(type=int)),
                    ('--afford-ticks', dict(type=int)),
                    ('--early-release-margin', dict(type=int)),
                    ('--extrapolate', dict(type=int)),
                    ('--identity-ext', dict(choices=('off', 'on'), default='off')),   # L74 identity extension
                    ('--emote-spam', dict(choices=('off', 'on'), default='off')),   # L74 emote spam during WAIT (owner 2026-10-10)
                    ('--emote-interval-s', dict(type=float)),
                    ('--emote-gap-ms', dict(type=int)),
                    ('--emote-guard', dict(type=float)),
                    ('--follow-up-taps', dict(action='store_true')))   # L74 latency2; --rocket-tornado on|only needs it (live_play refuses without)


def _decision_parser(prog, allow_abbrev=True):
    parser = argparse.ArgumentParser(prog=prog, add_help=False, allow_abbrev=allow_abbrev)
    add_arguments(parser)
    for flag, kw in EXTRA_LIVE_FLAGS:
        parser.add_argument(flag, **kw)
    return parser


def decision_dests():
    return [a.dest for a in _decision_parser('decision')._actions]


def add_live_options_arguments(parser, default_file):
    parser.add_argument('--live-options-file', type=Path, default=Path(default_file),
                        help='deployed decision options, applied to every decision-option flag the command line '
                             'does not set (explicit flags win)')
    parser.add_argument('--no-live-options', action='store_true', help='ignore --live-options-file: plain defaults')


def _read_file(path, dests, unset):
    parser = _decision_parser(str(path), allow_abbrev=False)
    tokens = shlex.split(path.read_text(encoding='utf-8-sig'), comments=True)
    seen = {}
    for token in tokens:
        action = parser._option_string_actions.get(token.split('=', 1)[0]) if token.startswith('--') else None
        if action is not None:
            if action.dest in seen:
                parser.error(f'{token.split("=", 1)[0]} given twice (also as {seen[action.dest]})')
            seen[action.dest] = token.split('=', 1)[0]
    return parser.parse_args(tokens, namespace=unset())


def parse_with_live_options(parser, argv=None):
    """-> (args, record). ``record`` (logged): status applied | ABSENT | ignored, path, file (None = not applied),
    from_file, explicit, ignored, message (the line live_play prints)."""
    dests = decision_dests()
    unset = lambda: argparse.Namespace(**{d: _UNSET for d in dests})  # noqa: E731
    args = parser.parse_args(argv, namespace=unset())
    explicit = sorted(d for d in dests if getattr(args, d) is not _UNSET)
    path, from_file = Path(args.live_options_file), {}
    status = 'ignored' if args.no_live_options else 'applied' if path.is_file() else 'ABSENT'
    if status == 'applied':
        parsed = _read_file(path, dests, unset)
        from_file = {d: getattr(parsed, d) for d in dests
                     if getattr(parsed, d) is not _UNSET and d not in explicit}
    for d in dests:
        if getattr(args, d) is _UNSET:
            setattr(args, d, from_file.get(d, parser.get_default(d)))
    message = {'applied': f'LIVE_OPTIONS applied from {path}: {sorted(from_file)}; explicit flags: {explicit}',
               'ABSENT': f'LIVE_OPTIONS not found at {path}: running with PLAIN decision defaults '
                         f'(explicit flags only: {explicit})',
               'ignored': f'--no-live-options: {path} ignored, PLAIN decision defaults (explicit flags only: {explicit})'}
    record = dict(status=status, path=str(path), file=str(path) if status == 'applied' else None,
                  from_file={d: getattr(args, d) for d in sorted(from_file)}, explicit=explicit,
                  ignored=bool(args.no_live_options), message=message[status])
    return args, record


def tau_check(args):
    """-> (refusal or None, note or None). tau_phase replaces the plain gate tau (live_gen_v2: gate_taus), so an
    --tau-alternate A/B would play identical arms and a plain --tau is not the gate threshold."""
    phase = getattr(args, 'tau_phase', None)
    if phase is None:
        return None, None
    phase = tuple(float(t) for t in phase)
    if getattr(args, 'tau_alternate', None):
        return ('refusing: --tau-alternate alternates the plain gate tau, but tau_phase %s (from LIVE_OPTIONS or '
                '--tau-phase) replaces it in every match -- both arms would play the same thresholds. For a plain-tau '
                'A/B add --no-live-options (and pass the other decision flags you want explicitly, e.g. --xbow-class '
                'class_sample --xbow-class-floor 0.3 --spell-aim rocket_area)' % (phase,)), None
    tau = float(getattr(args, 'tau', phase[0]))
    return None, ('note: tau_phase 1x/2x/OT = %s sets the play threshold; --tau %g is not used by the gate%s'
                  % (phase, tau, ' (it equals the 1x value)' if tau == phase[0] else ''))
