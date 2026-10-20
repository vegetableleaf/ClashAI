"""SIM load probe (W9, 10-20): can the SIM runtime PLAY every card of its catalogue in every form, and does the body it
creates carry the card table's exact max_hp? Read-only use of the runtime (no fork edits).

For each catalogue card c and form f in {0, 1, 2}: a fresh Battle reset with side 1's one-card deck [c] in form f
(ValueError = the runtime refuses the form), mana topped up and the evo counter primed (as fights.form_record), one
play at (9, 22) tiles, 3 ticks stepped (first body), then to 60 ticks (spawned bodies). Records: refused / deploy reason / new entities (name, max_hp, kind) / hero unit
/ new effects+projectiles, and whether the first new body's max_hp is in unit_hitpoints(c, 11) (the table at level 11).

  PARITY_SIM_PATH=C:/Users/benpe/rt_wheels/royalesim-0.1.36 python sim_probe.py OUT.json
Single process; ~1 min.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.mechanics import load_edited  # noqa: E402

LEVEL, K = 11, 18


def probe(eng, name, form):
    b, cid = eng.b, eng.ids[name]
    try:
        b.reset(1, [[eng.ids['Knight']], [cid]], 0, 200, None, None, [], forms=[[0], [form]],
                levels=[[LEVEL], [LEVEL]], tower_levels=[LEVEL, LEVEL])
    except ValueError as e:
        return dict(refused=str(e)[:160])
    sv = json.loads(b.save()); after = json.loads(json.dumps(sv))
    for ev in after['players'][1]['evo']:
        ev['plays'] = ev['cycles'] if form == 1 else 0
    after['players'][1]['mana'] = after['calib']['max_mana'] * after['mana_unit']
    if after != sv:
        load_edited(b, sv, after)
    s0 = json.loads(b.save())
    n0 = len(s0['ents']['card'])
    st0 = json.loads(b.state_json())
    fx0 = len(st0.get('effects') or []) + len(st0.get('projectiles') or [])
    r = b.step([(1, 0, 9000 * K, 22000 * K)], 0)[0]
    reason = eng.sim.DEPLOY_REASONS[r[1]]
    b.step([], 3)
    s1 = json.loads(b.save())
    E = s1['ents']
    st1 = json.loads(b.state_json())
    new = [dict(max_hp=E['max_hp'][i], kind=E['kind'][i]) for i in range(n0, len(E['card']))]
    hero = [h for h in s1.get('hero_units') or [] if h['id']['index'] >= n0]
    b.step([], 57)                 # 60 ticks after the play: spawned bodies (Barb Log barbarians, Goblin Barrel goblins)
    E60 = json.loads(b.save())['ents']
    later = sorted({E60['max_hp'][i] for i in range(n0, len(E60['card']))})
    try:
        table = sorted({h for _, _, h in b.unit_hitpoints(cid, LEVEL)})
    except ValueError:
        table = []
    return dict(reason=reason, new=new[:12], n_new=len(new), n_new_60=len(E60['card']) - n0, hp_60=later[:12], hero_unit=bool(hero), table_hp_l11=table[:12],
                fx_new=len(st1.get('effects') or []) + len(st1.get('projectiles') or []) - fx0,
                hp_exact=None if not new else new[0]['max_hp'] in table)


def main(out):
    eng = F.Engine()
    res = dict(stamp=eng.stamp, cards={})
    for c in eng.cat:
        res['cards'][c['name']] = {f: probe(eng, c['name'], f) for f in (0, 1, 2)}
    Path(out).write_text(json.dumps(res, indent=1))
    ok = {f: sum(1 for v in res['cards'].values() if 'refused' not in v[f] and v[f]['reason'] == 'OK') for f in (0, 1, 2)}
    print(res['stamp'], len(res['cards']), 'cards; plays OK by form', ok, '->', out)


if __name__ == '__main__':
    main(sys.argv[1])
