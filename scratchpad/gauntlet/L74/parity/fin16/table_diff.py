"""table_diff.py OLD.json NEW.json: every leaf that differs between two card-table JSONs (path, old, new). A1c: which 10-19
values could reach pipeline/sim_unit_state.py (it reads hit_speed_ms, hides_when_not_attacking, idle_buff, buff rows /
durations, projectile target_buff, spell area life_duration_ms)."""
import json
import sys


def walk(a, b, p):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            yield from walk(a.get(k), b.get(k), f'{p}.{k}')
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            name = x.get('name') if isinstance(x, dict) else None
            yield from walk(x, y, f'{p}[{name or i}]')
    elif a != b:
        yield p, a, b


for p, a, b in walk(json.load(open(sys.argv[1], encoding='utf-8')), json.load(open(sys.argv[2], encoding='utf-8')), ''):
    print(p, '|', json.dumps(a)[:80], '->', json.dumps(b)[:80])
