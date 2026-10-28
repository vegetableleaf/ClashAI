"""ENG-FIX planted checks for mech_rules.bb_presses (SME_BB_RISE). python -I bb_test.py -> 'ok N'."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mech_rules as M  # noqa: E402
SIDES = {0: {'deck': ['Knight', 'BossBandit', 'Log', 'Xbow', 'Rocket', 'Tornado', 'Skeletons', 'IceWizard']}, 1: {'deck': ['Knight'] * 8}}
NOBB = {0: {'deck': ['Knight'] * 8}, 1: SIDES[1]}


def log(frames):
    """frames: [(tick, state, cast_timer, buff (remaining, duration) or None)] of one Boss Bandit (gen 7, side 0)."""
    f = tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False)
    for t, s, c, b in frames:
        u = {'side': 0, 'name': 'BossBandit', 'generation': 7, 'ability': {'cast_timer_ms_raw': c},
             'buffs': [{'name': 'BossBandit_ability_buff', 'address': 'a1', 'remaining_ms_raw': b[0], 'duration_ms_raw': b[1]}] if b else []}
        f.write(json.dumps({'event': 'frame', 'tick': t, 'phase2': {'units': [u]}, 'ents_state': [[s, 0, 16, 7]]}) + '\n')
    f.close()
    return f.name


n = 0


def check(c, what):
    global n
    assert c, what
    n += 1


died = log([(3513, 2, 0, None), (3515, 2, 0, None), (3517, 10, 2, None)])            # 091720: rise, no buff, dead
buffed = log([(805, 2, 0, None), (807, 10, 3, None), (811, 10, 0, (1950, 2000))])    # buff start 811 - 1 = 810 = 807 + 3
plays = [dict(side=0, kind='play', card='BossBandit', tick=100)]
out = M.bb_presses(died, plays, SIDES)
add = [p for p in out if p.get('source') == 'bb_rise']
check(len(add) == 1 and add[0]['tick'] == 3515 and add[0]['run_ticks'] == [3514, 3516], 'rise without buff: R = t + c - 4')
check(add[0]['unit_index'] == 0 and add[0]['deck_index'] == 1 and add[0]['bb_rise'] == [3517, 2], 'fields')
check(M.bb_presses(buffed, plays, SIDES) is plays, 'rise with its buff: buff_casts dates it, nothing added')
check([r[4] for r in M.bb_rises(buffed)] == [810], 'buff start = rise + cast_timer')
check(M.bb_presses(died, plays, NOBB) is plays, 'no Boss Bandit in the deck: nothing')
nocast = log([(3513, 2, 0, None), (3517, 10, None, None)])
check(M.bb_presses(nocast, plays, SIDES) is plays, 'no cast_timer: nothing')
held = log([(3513, 10, 2, None), (3515, 10, 2, None)])
check(len([p for p in M.bb_presses(held, plays, SIDES) if p.get('source') == 'bb_rise']) == 1, 'one rise, one press')
for f in (died, buffed, nocast, held):
    os.unlink(f)
print('ok', n)
