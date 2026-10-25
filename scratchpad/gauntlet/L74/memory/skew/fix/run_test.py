"""Run fix/test_memory_zero_empty.py against the working-tree pipeline.model_gen (``before``) or against the patched copy
fix/model_gen.py injected as pipeline.model_gen (``after``), without touching the working tree.
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/memory/skew/fix/run_test.py before|after"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO))
if sys.argv[1] == 'after':
    import pipeline
    spec = importlib.util.spec_from_file_location('pipeline.model_gen', HERE / 'model_gen.py')
    mod = importlib.util.module_from_spec(spec)
    sys.modules['pipeline.model_gen'] = mod
    pipeline.model_gen = mod
    spec.loader.exec_module(mod)
import pytest  # noqa: E402

tests = sys.argv[2:] or [str(HERE / 'test_memory_zero_empty.py')]
raise SystemExit(pytest.main(['-q', '-p', 'no:cacheprovider', *tests, '--rootdir', str(REPO)]))
