"""Self-check of sme_live.iw_pending (SME_IWPEND9). python -I iwpend_test.py"""
import os, sys
os.environ['SME_IWPEND9'] = '1'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sme_live

hero = {'side': 1, 'kind': 'play', 'card': 'IceWizard', 'tick': 3236, 'run_ticks': [3236, 3236]}
cast = {'side': 1, 'kind': 'ability', 'card': 'IceWizard', 'tick': 3333, 'run_ticks': [3333, 3333], 'source': 'cast_seen'}
none = {t: {0: False, 1: False} for t in range(3237, 3340, 2)}
out = sme_live.iw_pending(cast, none, [hero, cast], 0)
assert out['run_ticks'] == [3237, 3333] and out['tick'] == 3333, out              # 171753: no valid target since the hero
vt = dict(none); vt[3301] = {0: False, 1: True}
assert sme_live.iw_pending(cast, vt, [hero, cast], 0)['run_ticks'] == [3301, 3333]   # held since its last valid frame
vt = dict(none); vt[3331] = {0: False, 1: True}
assert sme_live.iw_pending(cast, vt, [hero, cast], 0) == cast                     # valid on the frame before: cast = press
vt = dict(none); vt[3331] = {0: True, 1: False}
assert sme_live.iw_pending(cast, vt, [hero, cast], 0)['run_ticks'][0] == 3237      # the other side's buff does not count
assert sme_live.iw_pending(cast, none, [hero, cast], 1) == cast                   # our own presses keep their dating
assert sme_live.iw_pending(dict(cast, source='pending_rise'), none, [hero, cast], 0)['source'] == 'pending_rise'
assert sme_live.iw_pending(cast, none, [cast], 0) == cast                         # no hero play before it
sme_live.IWPEND9 = 0
assert sme_live.iw_pending(cast, none, [hero, cast], 0) == cast                   # flag off
print('ok')
