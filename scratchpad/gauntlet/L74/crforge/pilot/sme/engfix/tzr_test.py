"""ENG-FIX4 planted checks for SME_TZ_REACH (mech_rules.tower_zaps names= / tables=) on FRESH4 235834@4612 (laptop, no SIM):
    python -I tzr_test.py   -> 'ok N' or an AssertionError naming the plant.   (MECH_DIR=dir: mech_rules from there)"""
import copy, json, math, os, sys
H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get('MECH_DIR') or os.path.dirname(H))
import mech_rules as M  # noqa: E402
L = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/live_play_20261028_235834.jsonl'
T = 'C:/Users/benpe/ClashBot/.foreman/scratch/reader_torn/sme/tables/16.635.3'
x = next(json.loads(s) for s in open(H + '/r6/fresh4_on.jsonl') if '235834' in s)
SIDES = {int(k): v for k, v in x['sides'].items()}
PLAYS = [p for p in x['plays'] if p.get('mech') != 'tower_zap']
FR, NM = M.raw_frames(L), M.tz_names(L)
TW = (1, 14500, 25500)
n = 0


def run(fr=FR, nm=NM, flat=False):
    r = M.tower_zaps(fr, PLAYS, SIDES, x.get('reader_hidden') or (), **({} if flat else dict(names=nm, tables=T)))
    return [e for e in r[1] if e['t'] == 4612], [e['why'] for e in r[2] if e['t'] == 4612]


def check(name, ok):
    global n
    assert ok, name
    n += 1


def body(fr, t, name, side):
    """(frame, ent) of the listed body of that name and side nearest the tower at tick t."""
    f = next(f for f in fr if f[0] == t)
    return f, min((q for q in f[1] if q[0] == side and NM[t].get(q[7]) == name), key=lambda q: math.hypot(q[1] - TW[1], q[2] - TW[2]))


def plant(name, side, d, rename=None, ticks=(4610,)):
    """Copies with that body put d units below the tower's centre (on the given ticks), optionally renamed."""
    fr, nm = copy.deepcopy(FR), copy.deepcopy(NM)
    for t in ticks:
        _, q = body(fr, t, name, side)
        q[1], q[2] = TW[1], TW[2] - d
        if rename is not False:
            nm[t][q[7]] = rename if rename is not None else name
    return fr, nm


# 1. the real case fires once under the flag: R 4611, window [4610, 4611], at the tower's centre
f, b = run()
check('real fires', len(f) == 1 and f[0]['R'] == 4611 and f[0]['run_ticks'] == [4610, 4611] and f[0]['tower'] == list(TW))
# 2. flag off (no names): the old flat TZ_BODY block, unchanged
f, b = run(flat=True)
check('flat blocks enemy_body', not f and b == ['enemy_body'])
# 3. MUST NOT FIRE: an opponent Skeleton (reach 500 + 500 + 1000 + 1000 = 3000) at 2,900 units -> enemy_body
f, b = run(*plant('Skeleton', 0, 2900))
check('skeleton in reach blocks', not f and b == ['enemy_body'])
# 4. the same Skeleton at 3,100 units (outside its reach, inside the old 12,000) still fires
f, b = run(*plant('Skeleton', 0, 3100))
check('skeleton out of reach fires', len(f) == 1)
# 5. MUST NOT FIRE: the body renamed to a Mortar (11500 + 600 + 2000 = 14100 > the old 12,000) at 13,500 -> enemy_body
f, b = run(*plant('Skeleton', 0, 13500, rename='Mortar'))
check('mortar reach beyond 12000 blocks', not f and b == ['enemy_body'])
# 6. MUST NOT FIRE: a body with no table row keeps the flat TZ_BODY (11,000 < 12,000) -> enemy_body
f, b = run(*plant('Skeleton', 0, 11000, rename='NoSuchRow'))
check('unknown row keeps flat reach', not f and b == ['enemy_body'])
# 7. MUST NOT FIRE: a multi-target row (Hunter-like MultipleProjectiles / Electro chains) keeps TZ_BODY
mt = next(k for k, r in json.load(open(T + '/characters.json'))['rows'].items()
          if r.get('columns', {}).get('Range') and r['columns'].get('MultipleTargets'))
f, b = run(*plant('Skeleton', 0, 11000, rename=mt))
check('multi-target row keeps flat reach', not f and b == ['enemy_body'])
# 8. MUST NOT FIRE: our hero Ice Wizard at 2,990 units on frame t (inside ZAP_R + 500) -> own_body_in_reach
f, b = run(*plant('IceWizardHero', 1, 2990, ticks=(4612,)))
check('own body in the Zap circle blocks', not f and b == ['own_body_in_reach'])
# 9. the real Ice Wizard distances: 3,150 (tp) / 3,032 (t), outside 3,000 (that is why case 1 fires)
d = [math.hypot(body(FR, t, 'IceWizardHero', 1)[1][1] - TW[1], body(FR, t, 'IceWizardHero', 1)[1][2] - TW[2]) for t in (4610, 4612)]
check('ice wizard outside the circle', all(3000 < v < 3200 for v in d))
# 10. MUST NOT FIRE: our body renamed to a building (Tesla, square test) at 3,400 keeps the flat TZ_OWN (3,500)
f, b = run(*plant('IceWizardHero', 1, 3400, rename='Tesla', ticks=(4612,)))
check('own building keeps flat TZ_OWN', not f and b == ['own_body_in_reach'])
print('ok', n)
