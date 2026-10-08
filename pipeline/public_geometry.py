"""Source-backed geometry for lead-reviewed labels; no policy action rules."""
from functools import lru_cache
import json, math
from .obs_contract import REPO

CALIBRATION_PATH=REPO/'scratchpad/gauntlet/L70/gen_v31/xbow_reach_public.json'

def load_calibration(path):
    stat=path.stat()
    return _read_calibration(str(path),stat.st_mtime_ns,stat.st_size)

@lru_cache(maxsize=4)
def _read_calibration(path,mtime_ns,size):
    from pathlib import Path
    path=Path(path)
    data=json.loads(path.read_text())
    approved=(data.get('status')=='R1_FINAL_LEAD_APPROVED' and data.get('approval_rule')=='R1-FINAL'
              and bool(data.get('lead_rulings_sha256')) and bool(data.get('calibration_report_sha256')))
    if (not data.get('modal_offensive') or
            not approved and (data.get('status')!='R1_REVISED_CALIBRATION_PASS' or data.get('overlap',1)>.15)):
        raise ValueError('R1-REVISED calibration has not passed the lead gate')
    reach=float(data['reach_milli'])
    if not math.isfinite(reach) or reach<=0:raise ValueError('Invalid calibrated reach')
    return reach

@lru_cache(maxsize=1)
def constants():
    path=REPO/'research/ext/Royale/RoyaleSim/data/derived/cards.json'
    data=json.loads(path.read_text())
    bow=next(c for c in data['cards'] if c['name']=='Xbow')
    rocket=next(c for c in data['cards'] if c['name']=='Rocket')
    return dict(source=str(path.relative_to(REPO)),xbow_range=bow['range_milli'],xbow_lifetime_ms=bow['lifetime_ms'],
        rocket_radius=rocket['area_damage_radius_milli'],
        # rolling spells: (half-width, half-depth, roll range) of the rolling projectile, milli
        rolling={c['name']:tuple((r:=c['projectile']['spawn_projectile'])[k] for k in
                 ('projectile_radius_milli','projectile_radius_y_milli','projectile_range_milli'))
                 for c in data['cards'] if c['name'] in ('Log','BarbLog')},
        tower_radius={c['name']:c['collision_radius_milli'] for c in data['towers']})

def in_xbow_range(p,t,reach=None):
    if reach is None and CALIBRATION_PATH.is_file():reach=load_calibration(CALIBRATION_PATH)
    if reach is not None:return math.hypot(p['x']-t['x'],p['y']-t['y'])<=reach
    c=constants();kind='KingTower' if t['kind']=='king' else 'PrincessTower'
    return math.hypot(p['x']-t['x'],p['y']-t['y'])-c['tower_radius'][kind]<=c['xbow_range']

def defensive_xbow(p,frame,reach=None):
    if frame is None:return None
    offensive=any(t['side']!=p['side'] and t['hp']>0 and in_xbow_range(p,t,reach) for t in frame['towers'])
    own_half=p['y']<=16000 if p['side']==0 else p['y']>=16000
    return not offensive and own_half
