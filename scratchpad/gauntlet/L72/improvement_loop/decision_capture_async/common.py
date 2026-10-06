"""Successor provenance. Frozen synchronous evidence stays untouched."""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'decision_capture'
ROOT = HERE.parents[4]
sys.path.insert(0, str(OLD))
sys.path.insert(0, str(ROOT))
import support as original

sha = original.sha
save_json = original.save_json
CKPT = original.CKPT


def source_bindings():
    result = original.sources()
    paths = list(HERE.glob('*.py')) + [HERE / 'PLAN.md', HERE / 'METRICS.md']
    result.update({str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in paths})
    return result


def manifest(pilot, checkpoint=CKPT):
    value = original.manifest(pilot, checkpoint)
    value['sources'] = source_bindings()
    value['capture_id'] = 'public-decision-capture-async-20261006'
    return value


def load_old(name):
    spec = importlib.util.spec_from_file_location('capture_original_' + name, OLD / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
