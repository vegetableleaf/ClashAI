"""Local-only stand-in for `gymnasium` (the icebow venv lacks it; the VM has the real one). royalegym.protocol / rust_engine /
the pipeline's RoyaleSelfPlayEnv never call gymnasium; only royalegym's __init__ imports its gym-env modules. Any attribute
resolves to a dummy class so those imports succeed. Not used for anything that is measured."""
import sys, types


class _Meta(type):
    def __getattr__(cls, attr):
        return cls


class _Dummy(metaclass=_Meta):
    def __init__(self, *a, **k): pass
    def __class_getitem__(cls, item): return cls


def _mod(name):
    m = types.ModuleType(name)
    m.__getattr__ = lambda attr, _n=name: (_Dummy if attr[:1].isupper() else (lambda *a, **k: _Dummy()))
    m.__path__ = []
    sys.modules[name] = m
    return m


for n in ('pettingzoo', 'pettingzoo.utils', 'pettingzoo.utils.env', 'gymnasium', 'gymnasium.spaces', 'gymnasium.utils', 'gymnasium.utils.seeding', 'gymnasium.vector', 'gymnasium.vector.utils'):
    _mod(n)
sys.modules['gymnasium'].spaces = sys.modules['gymnasium.spaces']
sys.modules['gymnasium'].utils = sys.modules['gymnasium.utils']
sys.modules['gymnasium'].vector = sys.modules['gymnasium.vector']
sys.modules['gymnasium'].registry = {}
sys.modules['gymnasium'].register = lambda **k: None
sys.modules['gymnasium.utils'].seeding = sys.modules['gymnasium.utils.seeding']
sys.modules['gymnasium.vector'].utils = sys.modules['gymnasium.vector.utils']
