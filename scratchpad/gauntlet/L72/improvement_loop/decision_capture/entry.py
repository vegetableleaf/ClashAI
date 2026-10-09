"""Optional capture entry. No import starts live play; canonical sources stay intact."""
import argparse
import json
import sys
import types
from pathlib import Path

from support import HERE, ROOT, manifest, sha

CANONICAL = ROOT / 'scratchpad/gauntlet/L68/live_reader/live_play.py'


def dispatch(session, pilot, frame):
    return session.decide(pilot, frame) if session is not None else pilot.decide(frame)


def transformed_source(source):
    original = '            d = pilot.decide(f)\n'
    if source.count(original) != 1 or source.count('                    pilot.decide(f)\n') != 1:
        raise ValueError('canonical real decision/warmup call changed')
    return source.replace(original, '            d = capture_actual_decision(pilot, f)\n')


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--capture-dir')
    ap.add_argument('--capture-character-identity', action='store_true')
    args, rest = ap.parse_known_args()
    if args.capture_dir and not args.capture_character_identity:
        raise ValueError('capture qualification requires --capture-character-identity')
    expected = __import__('json').loads((HERE / 'registration.json').read_text())['sources']
    if any(sha(ROOT / path) != digest for path, digest in expected.items()):
        raise ValueError('source changed after registration')
    sys.path.insert(0, str(CANONICAL.parent))
    entry = types.ModuleType('isolated_decision_capture_entry')
    entry.__file__ = str(CANONICAL)
    sys.modules[entry.__name__] = entry
    exec(compile(transformed_source(CANONICAL.read_text(encoding='utf-8')), str(CANONICAL), 'exec'), entry.__dict__)
    session = None

    def actual(pilot, frame):
        return dispatch(session, pilot, frame)

    entry.capture_actual_decision = actual
    original_load = entry.load_pilot

    def load(a, config):
        nonlocal session
        device, pilot = original_load(a, config)
        if args.capture_dir:
            current = manifest(pilot, a.ckpt)
            qualified = json.loads((HERE / 'qualified.json').read_text())
            replayed = json.loads((HERE / 'replayed.json').read_text())
            if (not qualified['latency_pass'] or replayed['qualified_sha256'] != sha(HERE / 'qualified.json')
                    or current != qualified['manifest']):
                raise ValueError('capture checkpoint/settings/environment are unqualified')
            if not getattr(a, 'check', False):
                from capture import CaptureStore
                session = CaptureStore(Path(args.capture_dir), current)
        return device, pilot

    entry.load_pilot = load
    if args.capture_character_identity:
        sys.path.insert(0, str(HERE.parent / 'reader_character_identity'))
        from live_play_identity import IdentityPilot, install_catalog
        install_catalog()
        entry.GenPilot = IdentityPilot
        from pipeline import reader_config
        entry.READERS = {'v3': reader_config.reader('v3')}   # local-only reader config
        if not any(x == '--reader' or x.startswith('--reader=') for x in rest):
            rest += ['--reader', 'v3']
    sys.argv = [str(CANONICAL)] + rest
    return entry.main()


if __name__ == '__main__':
    raise SystemExit(main())
