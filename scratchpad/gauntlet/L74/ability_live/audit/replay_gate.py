"""Offline replay of the 10-18 perception fixes (hero_button.press_gate + pick_hero) on the Mark CXXXVIII live logs.
Read-only, no device. OLD = the code before the fix (first-listed hero body, no gate); NEW = press_gate, then the rule on
pick_hero's body. The pro timing gate does not read the hero body, so its logged verdict is reused at the presses.
  A. every logged rule press: what NEW does with it (pressed / withheld by gate reason / rule now holds), with the truth
  B. every frame the live button read 'ready' with an own hero body on the board: gate verdicts by truth; frames where
     the judged body changes and the freeze-geometry verdict that follows; all other frames identical by construction
     (same body, gate passes) -- asserted.
Usage: icebow/.venv/Scripts/python.exe replay_gate.py [mark] > replay_gate.out"""
import json, re, sys
from bisect import bisect_right
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
LIVE = ROOT / 'scratchpad/gauntlet/L68/live_reader'
sys.path[:0] = [str(ROOT), str(LIVE)]
from pipeline.obs_contract import _catalog_names                     # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies      # noqa: E402
import hero_button as hb                                             # noqa: E402

MARK = sys.argv[1] if len(sys.argv) > 1 else 'CXXXVIII'
NAMES = dict(_catalog_names())
HIDS = {hb.ICE_WIZARD}
IDS = HIDS | hb.hero_form_ids(HIDS)
EV = re.compile(rb'^\{"event": "([a-z_]+)"')
TICK = re.compile(rb'"tick": (\d+)')
PRO = re.compile(r'pro_hazard p=[0-9.]+ (>=|<) ')
STATE = {2: 'ready', 3: 'deploying', 6: 'spent', 7: 'pending', 9: 'no_elixir'}


def frame_of(j, hand, side):
    ents = [dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7],
                 category=s[3]) for e, s in zip(j['ents'], j['ents_state'])]
    fake = {-9000 - k: n for k, n in enumerate(hand)}                  # hand names -> ids the rule can look up
    pl = [dict(side=side, deck_card_ids=list(fake), hand_deck_indices=list(range(len(fake))),
               elixir_raw=j['elixir'] * 1e4)]
    return dict(entities=ents, phase2=j.get('phase2'), game_tick=j['tick'], players=pl), fake


def old_pick(f, side):
    return next((e for e in f['entities'] if e['side'] == side and int(e['card_id']) in IDS), None)


def truth(f, side):
    hit = hb._ability_body(f, side, [e for e in f['entities'] if e['side'] == side and int(e['card_id']) in IDS])
    if hit is None:
        return 'no_phase2'
    if hit[1] is None:
        return 'no_own_action'
    st, ch = hit[1].get('state_raw'), int(hit[1].get('charges_raw') or 0)
    return 'spent' if st == 2 and ch < 1 else STATE.get(st, f'state{st}')


def replay(log, side):
    btn, deps, abil, conf, hands = [], [], [], [], []
    for raw in open(LIVE / log, 'rb'):                                  # pass 1: events only
        g = EV.match(raw)
        if not g or g.group(1) == b'frame':
            continue
        e, ev = None, g.group(1)
        if ev in (b'button', b'confirmed', b'ability', b'ability_confirmed', b'decision'):
            e = json.loads(raw)
        if ev == b'button':
            btn.append((e['tick'], e['state'], e['blue']))
        elif ev == b'confirmed' and e.get('name') == 'IceWizard':
            deps.append(e['tick'])
        elif ev == b'ability':
            abil.append((e['tick'], e['why']))
        elif ev == b'ability_confirmed':
            conf.append(e['tick'])
        elif ev == b'decision':
            hands.append((e['tick'], [h['name'] for h in (e.get('public') or {}).get('own_hand') or []]))
    pairs = []                                                          # (press tick, its confirmation tick)
    for t, _ in abil:
        c = next((c for c in conf if c > t), None)
        pairs.append((t, c))
    bt, ht = [b[0] for b in btn], [h[0] for h in hands]
    press_at = {t: w for t, w in abil}

    def spent_n(t):                                                     # ability_head_live.deploy_state, from the log
        d = [x for x in deps if x <= t]
        dep = d[-1] if d else t
        return sum(1 for p, c in pairs if c is not None and c <= t and p >= dep)

    rows_a, rows_b = [], []
    for raw in open(LIVE / log, 'rb'):                                  # pass 2: frames while the button read ready
        if not raw.startswith(b'{"event": "frame"'):
            continue
        t = int(TICK.search(raw).group(1))
        i = bisect_right(bt, t) - 1
        st, blue = (btn[i][1], btn[i][2]) if i >= 0 else ('none', 0.0)
        if st != 'ready' and t not in press_at:          # the press frame = the frame the press was decided on
            continue
        if b'203000023' not in raw and b'26000023' not in raw:
            continue
        j = json.loads(raw)
        k = bisect_right(ht, t) - 1
        f, fake = frame_of(j, hands[k][1] if k >= 0 else [], side)
        f = dedupe_hero_bodies(f)
        names = {**NAMES, **fake}
        o, n = old_pick(f, side), hb.pick_hero(f, side, IDS)
        gate = hb.press_gate(f, side, HIDS, blue, spent_n(t))
        tr = truth(f, side)
        n_own = sum(1 for e in f['entities'] if e['side'] == side and int(e['card_id']) in IDS)
        geo_o = hb.ice_wizard_should_press(f, side, o, names)
        geo_n = geo_o if n is o else hb.ice_wizard_should_press(f, side, n, names)
        row = dict(log=log, tick=t, truth=tr, gate=gate, blue=blue, n_own=n_own, same_body=n is o,
                   geo_old=geo_o[0], geo_new=geo_n[0], why_new=geo_n[1])
        if st == 'ready':
            rows_b.append(row)                          # n_own 0 = the hero id on the OTHER side: kept, reported apart
        if t in press_at:
            pro = PRO.search(press_at[t])
            rows_a.append(dict(row, why=press_at[t], pro_ok=bool(pro and pro.group(1) == '>='), button_logged=st))
    return rows_a, rows_b


def main():
    inv = json.loads((HERE / 'inventory.json').read_text(encoding='utf-8'))
    logs = [(m['log'], m['side']) for m in inv if m.get('mark') == MARK]
    A, B = [], []
    for log, side in logs:
        a, b = replay(log, side)
        A += a
        B += b
    print(f'===== {MARK}: {len(logs)} logs, {len(A)} logged rule presses')
    print('--- A. logged presses: NEW verdict by truth at the press frame (replay fidelity: the OLD rule geometry '
          f'reproduces {sum(r["geo_old"] for r in A)} / {len(A)} logged presses)')
    c = Counter()
    for r in A:
        if r['gate']:
            v = f'withheld why={r["gate"]}'
        elif not r['same_body'] and not (r['geo_new'] and r['pro_ok']):
            v = 'held: rule on the ability body says no'
        else:
            v = 'pressed (same decision)' if r['same_body'] else 'pressed (judged on the ability body)'
        r['new'] = v
        c[(v, r['truth'], 'n_own=%d' % r['n_own'])] += 1
    for k, n in sorted(c.items(), key=lambda kv: -kv[1]):
        print(f'  {n:4d}  {k[0]:42s} truth={k[1]:14s} {k[2]}')
    print('  changed presses:')
    for r in A:
        if r['new'] != 'pressed (same decision)':
            print(f"    {r['log']} t={r['tick']} truth={r['truth']} n_own={r['n_own']} gate={r['gate']} "
                  f"blue={r['blue']} -> {r['new']} | new rule: {r['why_new'][:70]}")
    print(f'--- B. ready-button frames (button read ready); {sum(r["n_own"] == 0 for r in B)} more frames had no own '
          f'hero (old rule: iw_unseen, no press; gate: state) and are left out below')
    B = [r for r in B if r['n_own'] > 0]
    print('  gate verdict by truth:', dict(Counter((r['gate'], r['truth']) for r in B)))
    diff = [r for r in B if not r['same_body']]
    print(f'  judged body changed: {len(diff)} frames; n_own: {dict(Counter(r["n_own"] for r in diff))}; '
          f'truth on the ability body: {dict(Counter(r["truth"] for r in diff))}')
    print('  geometry old -> new on those frames (gate passing only):',
          dict(Counter((r['geo_old'], r['geo_new']) for r in diff if not r['gate'])))
    same = [r for r in B if r['same_body'] and not r['gate']]
    assert all(r['geo_old'] == r['geo_new'] for r in same)
    print(f'  identical by construction (same body, gate passes): {len(same)} frames, geometry equal on all')
    print('  gate fires on single-body frames:', dict(Counter((r['gate'], r['truth']) for r in B
                                                          if r['gate'] and r['n_own'] == 1)))
    json.dump(dict(A=A, B_changed=[r for r in B if r['gate'] or not r['same_body']]),
              open(HERE / f'replay_gate_{MARK}.json', 'w'), indent=0)


if __name__ == '__main__':
    main()
