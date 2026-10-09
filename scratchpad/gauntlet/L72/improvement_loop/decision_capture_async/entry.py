"""Explicit bounded capture successor entry; production startup is unchanged."""
import argparse
import json
import sys
import types
from pathlib import Path

from common import HERE, ROOT, original, sha, manifest, source_bindings, load_old


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--capture-dir')
    parser.add_argument('--capture-character-identity', action='store_true')
    custom, rest = parser.parse_known_args()
    if custom.capture_dir and not custom.capture_character_identity:
        raise ValueError('qualified capture requires the isolated identity entry')
    registration = json.loads((HERE / 'registration.json').read_text())
    if registration['sources'] != source_bindings():
        raise ValueError('registered source changed')
    old_entry = load_old('entry')
    source = old_entry.transformed_source(old_entry.CANONICAL.read_text(encoding='utf-8'))
    sys.path.insert(0, str(old_entry.CANONICAL.parent))
    module = types.ModuleType('isolated_async_capture_entry')
    module.__file__ = str(old_entry.CANONICAL)
    sys.modules[module.__name__] = module
    exec(compile(source, str(old_entry.CANONICAL), 'exec'), module.__dict__)
    session = None

    def capture_actual_decision(pilot, frame):
        return session.decide(pilot, frame) if session is not None else pilot.decide(frame)

    module.capture_actual_decision = capture_actual_decision
    original_load = module.load_pilot

    def load(args, options):
        nonlocal session
        device, pilot = original_load(args, options)
        if custom.capture_dir:
            q = json.loads((HERE / 'qualified.json').read_text())
            v = json.loads((HERE / 'replayed.json').read_text())
            current = manifest(pilot, args.ckpt)
            if (sha(args.ckpt) != original.CHECKPOINT_SHA or not q['latency_pass']
                    or v['qualified_sha256'] != sha(HERE / 'qualified.json') or current != q['manifest']):
                raise ValueError('unqualified capture checkpoint/settings/environment')
            if not args.check:
                from async_capture import AsyncCaptureStore
                session = AsyncCaptureStore(Path(custom.capture_dir), current)
        return device, pilot

    module.load_pilot = load
    if custom.capture_character_identity:
        sys.path.insert(0, str(HERE.parent / 'reader_character_identity'))
        from live_play_identity import IdentityPilot, install_catalog
        install_catalog()
        module.GenPilot = IdentityPilot
        from pipeline import reader_config
        module.READERS = {'v3': reader_config.reader('v3')}   # local-only reader config
        if not any(v == '--reader' or v.startswith('--reader=') for v in rest):
            rest += ['--reader', 'v3']
    sys.argv = [str(old_entry.CANONICAL)] + rest
    try:
        return module.main()
    finally:
        if session is not None:
            closed = session.close(timeout=2)
            try:
                print(json.dumps({'event': 'decision_capture_final', **dict(closed)}, sort_keys=True),
                      file=sys.stderr, flush=True)
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
