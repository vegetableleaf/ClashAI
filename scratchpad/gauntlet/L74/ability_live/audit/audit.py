"""Hero Ice Wizard rule-press audit over the 10-16/17 live logs (Mark CXXXVIII + Mark CXXIV). Read-only.

Truth = the reader's named phase-2 / phase-3 blocks the live log itself carries on every frame (--log-frames + the merged
reader): own IceWizardHero ability state (FINDINGS_P2 enum: 2 Ready, 3 Deploying, 6 AllChargesConsumed, 7 Pending,
9 NotEnoughElixir), IceWizardHero_IceCube bodies, IceWizardHero_FreezeBuff on enemy bodies, attack targets.
Per press: (a) was the press possible (own IW, charge, state) and which body the rule took as the hero; (b) what the
freeze hit, whether those bodies died / reached a tower, elixir after. Plus a per-frame button-vs-truth table.
Out: press_rows.json, button_rows.json (same folder). Needs inventory.json (inventory.py)."""
import json, re, sys
from bisect import bisect_right
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
sys.path[:0] = [str(ROOT), str(LIVE)]
from pipeline.obs_contract import _catalog_names                     # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies      # noqa: E402

NAMES = _catalog_names()
VAL = json.loads((LIVE / 'unit_values.json').read_text(encoding='utf-8'))['value_per_unit']
# hero_button's constants (copied, not imported: importing it pulls cv2 + clashrl for nothing)
IW_RANGE, FREEZE_R, UNKNOWN = 5.5, 2.5, 0.5
BUILDINGS = {"Cannon", "Tesla", "InfernoTower", "BombTower", "Mortar", "Xbow", "Tombstone", "GoblinHut", "Furnace",
             "FirespiritHut", "BarbarianHut", "Elixir Collector", "GoblinCage", "GoblinDrill", "GoblinPartyHut"}
IDS = {26000023, 203000023}
MARKS = ('CXXXVIII', 'CXXIV')
PRE, POST = 20, 320                          # parsed window around each press (ticks)

EV = re.compile(rb'^\{"event": "([a-z_]+)"')
TICK = re.compile(rb'"tick": (\d+)')
P2OK = re.compile(rb'"phase2": \{"build": \d+, "valid": (true|false)')
IWU = re.compile(rb'"side": (\d), "definition_id": -?\d+, "name": "IceWizardHero", "buffs": \[[^\]]*\], "ability": '
                 rb'(?:null|\{"pending_on_body": (-?\d+), "cast_timer_ms_raw": (-?\d+), "own_action": (?:null|\{[^}]*'
                 rb'"charges_raw": (-?\d+), [^}]*"state_raw": (-?\d+)\}))')
CUBE = re.compile(rb'"side": (\d), "definition_id": -?\d+, "name": "IceWizardHero_IceCube"')
ELX = re.compile(rb'"elixir": ([0-9.]+)')
DEC = re.compile(rb'"decision": \{"play": (true|false), "p_play": ([0-9.e-]+), "no_affordable": (true|false)')


def tiles(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** .5 / 1000


def compact(j):
    """Parsed frame -> what the press analysis reads."""
    ents = []
    for e, s in zip(j['ents'], j.get('ents_state') or [[None] * 4] * len(j['ents'])):
        ents.append({'side': e[0], 'x': e[1], 'y': e[2], 'card_id': e[3], 'hp': e[4], 'max_hp': e[5], 'kind': e[6],
                     'category': s[3], 'bs': s[0]})
    p2 = j.get('phase2') or {}
    units = {}
    for u in p2.get('units', []) if p2.get('valid') else []:
        oa = ((u.get('ability') or {}).get('own_action')) or {}
        units[u['generation']] = (u['name'], u['side'], [b['name'] for b in u['buffs']], oa.get('state_raw'),
                                  oa.get('charges_raw'))
    att = {}
    p3 = j.get('phase3') or {}
    for b in p3.get('bodies', []) if p3.get('valid') else []:
        if b.get('attack'):
            att[b['generation']] = b['attack']['target_gen']
    return {'tick': j['tick'], 'elixir': j['elixir'], 'ents': ents, 'units': units, 'att': att, 'p2': bool(units)}


def scan(m):
    presses = sorted(e['tick'] for e in m['events'] if e['event'] == 'ability')
    wins = [(p - PRE, p + POST) for p in presses]
    bt = sorted((e['tick'], e['state'], e.get('blue'), e.get('grey')) for e in m['events'] if e['event'] == 'button')
    bticks = [b[0] for b in bt]
    frames, decs, rows = {}, [], []
    with open(LIVE / m['log'], 'rb') as f:
        for raw in f:
            g = EV.match(raw)
            if not g:
                continue
            ev = g.group(1)
            if ev == b'decision':
                t = int(TICK.search(raw).group(1))
                d = DEC.search(raw)
                if d:
                    decs.append((t, d.group(1) == b'true', float(d.group(2)), d.group(3) == b'true'))
                continue
            if ev != b'frame':
                continue
            t = int(TICK.search(raw).group(1))
            ok = P2OK.search(raw)
            ok = bool(ok and ok.group(1) == b'true')
            iw = [(int(st) if st else None, int(ch) if ch else None)
                  for s, _pe, _ct, ch, st in (IWU.findall(raw) if ok else []) if int(s) == m['side']]
            cube = ok and any(int(s) == m['side'] for s in CUBE.findall(raw))
            i = bisect_right(bticks, t) - 1
            b = bt[i] if i >= 0 else (None, 'none', None, None)
            el = ELX.search(raw)
            rows.append([t, ok, iw, cube, b[1], b[2], b[3], float(el.group(1)) if el else None])
            if any(a <= t <= z for a, z in wins):
                frames[t] = compact(json.loads(raw))
    return presses, frames, decs, rows


def iw_ok_states(iw):
    return [s for s, c in iw]


def analyse_press(m, P, why, ev_el, frames, decs, rows):
    side = m['side']
    my_half = (lambda y: y > 16000) if side == 1 else (lambda y: y < 16000)
    ticks = sorted(frames)
    f0t = max((t for t in ticks if t <= P), default=None)
    out = {'log': m['log'], 'mark': m['mark'], 'tick': P, 'why': why, 'kind': why.split()[0], 'elixir_at': ev_el}
    mm = re.search(r'n=(\d+) value=([0-9.]+) target=(\S+)', why)
    if mm:
        out.update(rule_n=int(mm.group(1)), rule_value=float(mm.group(2)), rule_target=mm.group(3))
    mw = re.search(r'iw_wincon (\S+)', why)
    if mw:
        out['rule_target'] = out.get('rule_target') or mw.group(1)
        out['wincon'] = mw.group(1)
    ma = re.search(r'age=([0-9.]+)s', why)
    out['age_logged'] = float(ma.group(1)) if ma else None
    if f0t is None or not frames[f0t]['p2']:
        out['truth'] = 'no_phase2'
        return out
    f0 = frames[f0t]
    out['frame_lag'] = P - f0t
    U = f0['units']
    ents = [e for e in f0['ents']]
    # --- the rule's hero, exactly as should_press finds it
    fd = dedupe_hero_bodies({'entities': ents})
    hero = next((e for e in fd['entities'] if e['side'] == side and int(e['card_id']) in IDS), None)
    out['rule_hero_name'] = U.get(hero['category'], ('?',))[0] if hero else None
    own_iw = [(g, u) for g, u in U.items() if u[0] == 'IceWizardHero' and u[1] == side]
    out['n_own_iw'] = len(own_iw)
    if not own_iw:
        out['truth'] = 'no_iw'
        return out
    epos = {e['category']: e for e in ents}
    if hero is not None:
        g_iw, u_iw = min(own_iw, key=lambda gu: tiles((epos.get(gu[0], hero)['x'], epos.get(gu[0], hero)['y']),
                                                      (hero['x'], hero['y'])))
    else:
        g_iw, u_iw = own_iw[0]
    iwe = epos.get(g_iw)
    st, ch = u_iw[3], u_iw[4]
    out.update(iw_gen=g_iw, iw_state=st, iw_charges=ch)
    out['truth'] = {2: 'ready', 3: 'deploying', 6: 'spent', 7: 'pending', 9: 'no_elixir'}.get(st, f'state{st}')
    if ch == 0 and st == 2:
        out['truth'] = 'spent'
    if iwe is None:
        return out
    iwp = (iwe['x'], iwe['y'])
    out['iw_pos'] = iwp
    out['iw_my_half'] = my_half(iwe['y'])
    out['rule_hero_off_t'] = round(tiles(iwp, (hero['x'], hero['y'])), 2) if hero else None
    # --- birth of this IW body (first sighting in rows is not kept per gen; use the earliest parsed frame or the log age)
    # --- rule target / rule freeze set (hero_button.ice_wizard_should_press geometry, on the rule's hero)
    foes = [e for e in ents if e['side'] != side and int(e['card_id']) >= 0]
    nm = lambda e: NAMES.get(int(e['card_id']), '')   # noqa: E731
    hp_ = (hero['x'], hero['y']) if hero else iwp
    inr = [e for e in foes if tiles((e['x'], e['y']), hp_) <= IW_RANGE]
    tgt = min(inr, key=lambda e: tiles((e['x'], e['y']), hp_)) if inr else None
    rule_frozen = [e for e in foes if tgt and tiles((e['x'], e['y']), (tgt['x'], tgt['y'])) <= FREEZE_R
                   and nm(e) not in BUILDINGS]
    out['rule_target_gen'] = tgt['category'] if tgt else None
    out['rule_target_is_building'] = bool(tgt and nm(tgt) in BUILDINGS)
    out['rule_target_dist_iw'] = round(tiles((tgt['x'], tgt['y']), iwp), 2) if tgt else None
    # --- the game's own target rule (tables: closest enemy CHARACTER carrying IceWizardHeroCold / IceWizardHeroSlow)
    marked = []
    for e in foes:
        u = U.get(e['category'])
        if u and nm(e) not in BUILDINGS and e['kind'] not in (12, 13) and \
                any(b in ('IceWizardHeroCold', 'IceWizardHeroSlow') for b in u[2]):
            marked.append(e)
    gt = min(marked, key=lambda e: tiles((e['x'], e['y']), iwp)) if marked else None
    out['n_marked'] = len(marked)
    out['game_target_gen'] = gt['category'] if gt else None
    out['rule_target_eq_game'] = bool(tgt and gt and tgt['category'] == gt['category'])
    # IW-centred count (the B6 head's feature: enemy bodies within the ability radius 2.5 t of the hero)
    near_iw = [e for e in foes if tiles((e['x'], e['y']), iwp) <= 2.5 and e['kind'] not in (12, 13)]
    out['head_n_near_iw'] = len(near_iw)
    out['head_val_near_iw'] = round(sum(VAL.get(nm(e), UNKNOWN) for e in near_iw), 2)
    # --- effect: the IW's state after the press, the IceCube, the frozen bodies
    later = [t for t in ticks if t > f0t]
    eff = next(((t, frames[t]['units'][g_iw][3]) for t in later if g_iw in frames[t]['units']
                and frames[t]['units'][g_iw][3] != st), None)
    gone = next((t for t in later if frames[t]['p2'] and g_iw not in frames[t]['units']), None)
    out['effect_tick'], out['effect_state'] = (eff if eff else (None, None))
    out['iw_gone_tick'] = gone
    out['spent_tick'] = next((t for t in later if g_iw in frames[t]['units'] and frames[t]['units'][g_iw][3] == 6), None)
    out['window_end'] = min(P + POST, rows[-1][0])
    out['truncated'] = rows[-1][0] < P + POST
    cubes0 = {g for g, u in U.items() if u[0] == 'IceWizardHero_IceCube'}
    cube = None
    for t in later:
        for g, u in frames[t]['units'].items():
            if u[0] == 'IceWizardHero_IceCube' and u[1] == side and g not in cubes0:
                ce = next((e for e in frames[t]['ents'] if e['category'] == g), None)
                if ce:
                    cube = (t, ce['x'], ce['y'], g)
                    break
        if cube:
            break
    if cube:
        cp = (cube[1], cube[2])
        out.update(cube_tick=cube[0], cube_pos=cp, cube_dist_iw=round(tiles(cp, iwp), 2),
                   cube_dist_rule_target=round(tiles(cp, (tgt['x'], tgt['y'])), 2) if tgt else None)
        ft = frames[cube[0]]
        iwn = next((e for e in ft['ents'] if e['category'] == g_iw), None)
        out['cube_dist_iw_now'] = round(tiles(cp, (iwn['x'], iwn['y'])), 2) if iwn else None
    frz = {}
    for t in later:
        fr = frames[t]
        for g, u in fr['units'].items():
            if u[1] != side and 'IceWizardHero_FreezeBuff' in u[2]:
                e = next((x for x in fr['ents'] if x['category'] == g), None)
                if e is None:
                    continue
                r = frz.setdefault(g, {'first': t, 'name': NAMES.get(int(e['card_id']), u[0]), 'hp0': e['hp'],
                                       'max_hp': e['max_hp'], 'pos0': (e['x'], e['y'])})
                r['last'] = t
    last_t = ticks[-1]
    match_end = rows[-1][0]
    own_towers = {e['category']: e['hp'] for e in ents if e['side'] == side and e['kind'] in (12, 13)}
    for g, r in frz.items():
        seen = [t for t in later if any(x['category'] == g for x in frames[t]['ents'])]
        r['last_seen'] = seen[-1] if seen else r['last']
        r['died'] = r['last_seen'] < min(last_t, match_end) - 4
        r['died_by'] = (r['last_seen'] - r['last']) / 20 if r['died'] else None
        r['value'] = VAL.get(r['name'], UNKNOWN)
        r['freeze_s'] = (r['last'] - r['first']) / 20
        r['on_my_half'] = my_half(r['pos0'][1])
        r['hit_tower_after'] = any(frames[t]['att'].get(g) in own_towers for t in later if t > r['last'])
        r['rule_counted'] = g in {e['category'] for e in rule_frozen}
    out['frozen'] = frz
    out['n_frozen'] = len(frz)
    out['frozen_value'] = round(sum(r['value'] for r in frz.values()), 2)
    out['n_rule_frozen'] = len(rule_frozen)
    out['rule_bodies_actually_frozen'] = sum(r['rule_counted'] for r in frz.values())
    out['frozen_died'] = sum(r['died'] for r in frz.values())
    out['frozen_died_value'] = round(sum(r['value'] for r in frz.values() if r['died']), 2)
    out['frozen_hit_tower_after'] = sum(r['hit_tower_after'] for r in frz.values())
    # own tower HP lost from the press to the end of the window
    endf = frames[last_t]
    hp_end = {e['category']: e['hp'] for e in endf['ents'] if e['category'] in own_towers}
    out['own_tower_loss'] = sum(own_towers[g] - hp_end.get(g, 0) for g in own_towers)
    # elixir after the press (frame elixir), decisions flagged no_affordable in the next 6 s
    els = [(t, frames[t]['elixir']) for t in later if t <= P + 120]
    out['elixir_min_6s'] = min((e for _, e in els), default=None)
    dd = [d for d in decs if P < d[0] <= P + 120]
    out['dec_6s'] = len(dd)
    out['noaff_6s'] = sum(d[3] for d in dd)
    # an enemy troop on my half while I had no affordable card (the 'short for the next defence' proxy)
    thr = 0
    for d in dd:
        if not d[3]:
            continue
        ft = max((t for t in ticks if t <= d[0]), default=None)
        if ft and any(e['side'] != side and e['kind'] not in (12, 13) and int(e['card_id']) >= 0
                      and NAMES.get(int(e['card_id']), '') not in BUILDINGS and my_half(e['y'])
                      for e in frames[ft]['ents']):
            thr += 1
    out['noaff_threat_6s'] = thr
    return out


def button_audit(m, rows, presses):
    """Per frame: the button reading vs the truth. Only frames with a valid phase-2 block."""
    c, reads, last = {}, [], None
    for i, (t, ok, iw, cube, bst, blue, grey, el) in enumerate(rows):
        if not ok:
            continue
        sts = [s for s, _ in iw]
        truth = 'no_iw' if not sts else ('ready' if 2 in sts else
                                         {3: 'deploying', 6: 'spent', 7: 'pending', 9: 'no_elixir'}.get(sts[0], 'other'))
        dt = min(10, rows[i + 1][0] - t) if i + 1 < len(rows) else 0     # ticks this frame stands for
        k = (bst, truth)
        c[k] = c.get(k, 0) + dt
        if bst == 'ready' and (blue, grey) != last:                       # one row per new 'ready' reading
            reads.append([t, truth, blue, grey])
        last = (blue, grey) if bst == 'ready' else None
    return {f'{a}|{b}': v for (a, b), v in c.items()}, reads


def main():
    inv = json.loads((HERE / 'inventory.json').read_text())
    press_rows, btn = [], {}
    todo = [m for m in inv if m.get('mark') in MARKS and m['frames'] >= 500]
    for i, m in enumerate(todo):
        presses, frames, decs, rows = scan(m)
        evs = {e['tick']: e for e in m['events'] if e['event'] == 'ability'}
        for P in presses:
            r = analyse_press(m, P, evs[P]['why'], evs[P].get('elixir'), frames, decs, rows)
            press_rows.append(r)
        b, reads = button_audit(m, rows, presses)
        btn[m['log']] = {'mark': m['mark'], 'ticks': b, 'ready_reads': reads,
                         'elixir_frames': [[t, el] for t, ok, iw, cube, bst, bl, gr, el in rows][::10],
                         'iw_ready_ticks': [t for t, ok, iw, cube, bst, bl, gr, el in rows
                                            if ok and any(s == 2 for s, _ in iw)][::10],
                         'noaff': [[d[0], d[3]] for d in decs]}
        if i % 25 == 0:
            print(i, len(todo), m['log'], len(press_rows), file=sys.stderr, flush=True)
    (HERE / 'press_rows.json').write_text(json.dumps(press_rows, default=str))
    (HERE / 'button_rows.json').write_text(json.dumps(btn))
    print('presses', len(press_rows))


if __name__ == '__main__':
    main()
