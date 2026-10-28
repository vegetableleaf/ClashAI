"""ENG-FIX planted checks for mech_rules.tomb_presses (SME_TOMB_HERO). python -I tomb_test.py -> 'ok N'."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mech_rules as M  # noqa: E402

DECK = {0: {'deck': ['Knight', 'Tombstone', 'Log', 'Xbow', 'Rocket', 'Tornado', 'Skeletons', 'IceWizard']},
        1: {'deck': ['Valkyrie', 'Tombstone', 'Fireball', 'HogRider', 'Musketeer', 'IceGolemite', 'Log', 'IceWizard']}}
NO_TOMB = {0: DECK[0], 1: {'deck': ['Valkyrie', 'Knight', 'Fireball', 'HogRider', 'Musketeer', 'IceGolemite', 'Log', 'IceWizard']}}


def log(frames):
    """frames: [(tick, [(side, name, generation)])] -> a raw live log path."""
    f = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for t, us in frames:
        f.write(json.dumps({'event': 'frame', 'tick': t, 'phase2': {'units': [
            {'side': s, 'name': n, 'generation': g} for s, n, g in us]}}) + '\n')
    f.close()
    return f.name


P, A, B, D, BD = 'TombstoneHero_Monster_Passive', 'TombstoneHero_Monster_Active', 'TombstoneHero', \
    'TombstoneHero_visual_dummy', 'TombstoneHero_broken_visual_dummy'
standing = log([(1303, [(1, D, 7), (1, B, 8), (1, P, 9)]), (1305, [(1, D, 7), (1, B, 8), (1, P, 9)]),
                (1308, [(1, BD, 7), (1, B, 8), (1, A, 9)]), (1310, [(1, BD, 7), (1, A, 9)]), (1312, [(1, A, 9)])])
lingering = log([(935, [(1, BD, 7), (1, P, 9)]), (937, [(1, BD, 7), (1, P, 9)]), (939, [(1, BD, 7), (1, A, 9)])])
death = log([(2335, [(1, D, 7), (1, B, 8), (1, P, 9)]), (2337, [(1, BD, 7), (1, P, 9)]), (2387, [(1, BD, 7)]), (2389, [])])
two = log([(100, [(1, B, 8), (1, P, 9)]), (102, [(1, A, 9)]), (200, [(1, B, 18), (1, P, 19)]), (203, [(1, A, 19)]),
           (205, [(1, A, 19)])])
active_only = log([(500, [(1, A, 9)]), (502, [(1, A, 9)])])   # no passive row ever read: no swap seen, no press
cast = dict(side=1, kind='ability', card='Tombstone', deck_index=1, name='Tombstone', form=0, run_ticks=[1713, 1714],
            tick=1713, source='cast_seen')
other = dict(side=1, kind='ability', card='Valkyrie', deck_index=0, name='Valkyrie', form=0, run_ticks=[90, 90], tick=90,
             source='cast_seen')
play = dict(side=1, kind='play', card='Tombstone', deck_index=1, name='Tombstone', form=2, run_ticks=[954, 954], tick=954,
            source='first_seen', x=9500, y=22500)
n = 0


def check(cond, what):
    global n
    assert cond, what
    n += 1


# 1. a swap while the building stands -> one press, R = t - 2, window [tp, t - 1], unit 2, standing flag 1
out = M.tomb_presses(standing, [play], DECK)
pr = [p for p in out if p.get('source') == 'tomb_active']
check(len(pr) == 1 and pr[0]['tick'] == 1306 and pr[0]['run_ticks'] == [1305, 1307], 'standing press dated')
check(pr[0]['unit_index'] == 2 and pr[0]['deck_index'] == 1 and pr[0]['side'] == 1 and pr[0]['tomb_swap'] == [1305, 1308, 1],
      'standing press fields')
# 2. a swap after the building's death (lingering passive monster) -> a press too, standing flag 0
pr = [p for p in M.tomb_presses(lingering, [play], DECK) if p.get('source') == 'tomb_active']
check(len(pr) == 1 and pr[0]['tick'] == 937 and pr[0]['run_ticks'] == [937, 938] and pr[0]['tomb_swap'][2] == 0, 'lingering press')
# 3. the building's death with no swap -> no press; the same plays object back
plays = [play, other]
check(M.tomb_presses(death, plays, DECK) is plays, 'death: no press, same object')
# 4. a cast_seen Tombstone ability (the active monster's death area) is dropped; other heroes' casts kept
out = M.tomb_presses(death, [play, cast, other], DECK)
check(cast not in out and other in out and play in out and len(out) == 2, 'cast_seen Tombstone dropped')
# 5. two monsters of two plays -> two presses, each on its own swap (the 3-tick gap: window [200, 202], R 201)
pr = [p for p in M.tomb_presses(two, [play], DECK) if p.get('source') == 'tomb_active']
check([(p['tick'], p['run_ticks']) for p in pr] == [(100, [100, 101]), (201, [200, 202])], 'two presses')
# 6. a side without a Tombstone in its deck -> no press
check(M.tomb_presses(standing, plays, NO_TOMB) is plays, 'no Tombstone in the deck')
# 7. an active monster never read passive -> no press
check(M.tomb_presses(active_only, plays, DECK) is plays, 'active only: no press')
# 8. SME_TOMB_PIN window = [R, R]; SME_TOMB_LAG moves R
M.TOMB_PIN, M.TOMB_LAG = 1, 3
pr = [p for p in M.tomb_presses(standing, [play], DECK) if p.get('source') == 'tomb_active']
check(pr[0]['tick'] == 1305 and pr[0]['run_ticks'] == [1305, 1305], 'pin + lag')
M.TOMB_PIN, M.TOMB_LAG = 0, 2
# 9. the flag is off by default
check(int(os.environ.get('SME_TOMB_HERO', '0')) == M.TOMB_HERO, 'flag read from the environment')
for f in (standing, lingering, death, two, active_only):
    os.unlink(f)
print('ok', n)
