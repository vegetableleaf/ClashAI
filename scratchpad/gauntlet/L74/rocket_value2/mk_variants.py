"""The scout variant table -> variants.json (name -> DecisionOptions kwargs) and arms.txt lines (name -> CLI flags).
   python mk_variants.py OUT_DIR"""
import json, os, sys

V = {}


def add(name, **kw): V[name] = kw


add('rv9', rocket_value=9.0)                                                  # iteration 1, V = 9 (parity with the 159 first fires of diag1)
add('rv11', rocket_value=11.0)
add('dc9', rocket_value=9.0, rocket_value_mode='damage')                       # one change from rv9: the value
add('ce9', rocket_value=9.0, rocket_value_hitbox='edge')                       # one change from rv9: the hitbox
for v in (7, 8, 9, 10, 11, 12, 13):
    add(f'de{v}', rocket_value=float(v), rocket_value_mode='damage', rocket_value_hitbox='edge')
for e in (8, 9, 9.5):
    add(f'de9_e{e}', rocket_value=9.0, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_min_elixir=float(e))
for v in (7, 8):
    add(f'de{v}_e9', rocket_value=float(v), rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_min_elixir=9.0)
for v in (7, 9):
    add(f'de{v}_idle', rocket_value=float(v), rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_idle='on')
add('de9_idle_e8', rocket_value=9.0, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_idle='on', rocket_value_min_elixir=8.0)
for v in (5, 6, 7, 8, 9):
    add(f'ke{v}', rocket_value=float(v), rocket_value_mode='kill', rocket_value_hitbox='edge')
for v, y in ((9, 21), (7, 21), (9, 23), (7, 23)):
    add(f'de{v}_y{y}', rocket_value=float(v), rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_min_y=float(y))
for v in (9, 11):
    add(f'de{v}_lead', rocket_value=float(v), rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_lead='on')
add('de7_y21_e8', rocket_value=7.0, rocket_value_mode='damage', rocket_value_hitbox='edge', rocket_value_min_y=21.0, rocket_value_min_elixir=8.0)


def flags(kw):
    out = []
    for k, v in kw.items():
        out += ['--' + k.replace('_', '-'), str(int(v)) if isinstance(v, float) and v == int(v) else str(v)]
    return ' '.join(out)


if __name__ == '__main__':
    d = sys.argv[1]
    json.dump(V, open(os.path.join(d, 'variants.json'), 'w'), indent=0)
    with open(os.path.join(d, 'arms_all.txt'), 'w') as f:
        f.write('base\n')
        for k, kw in V.items():
            f.write(f'{k} {flags(kw)}\n')
    print(len(V), 'variants')
