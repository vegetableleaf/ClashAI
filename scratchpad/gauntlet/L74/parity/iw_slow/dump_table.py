"""Dump every Ice Wizard / slow-buff row from a royalesim wheel's embedded 160402017 card table.
Usage: python dump_table.py <unpacked wheel dir>"""
import json, sys
sys.path.insert(0, sys.argv[1])
import royalesim as sim

t = json.loads(sim.EMBEDDED_CARDS_160402017_JSON)
print('top keys', list(t)[:20])


def walk(o, path=''):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f'{path}/{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, f'{path}[{i}]')
    else:
        yield path, o


for p, v in walk(t):
    if any(s in p.lower() or (isinstance(v, str) and s in v.lower()) for s in ('icewizard', 'ice_wizard', 'slowdown')):
        print(p, '=', v)
