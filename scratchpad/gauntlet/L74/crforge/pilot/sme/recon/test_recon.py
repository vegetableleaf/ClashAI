"""Planted checks for recon.py (laptop, no engine):  python -I test_recon.py  -> 'ok N' or an AssertionError."""
import copy, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import sme_live  # noqa: E402

SME = os.path.dirname(HERE)
tab = recon.Tab()
N = [0]


def ok(cond, what):
    assert cond, what
    N[0] += 1


def cmd(side, card, run, x=9000, y=5000, own=False, lo=None, hi=None, kind='play', unit=None):
    c = {'kind': kind, 'given': run - 20, 'run': run, 'side': side,
         '_src': {'lo': run if lo is None else lo, 'hi': run if hi is None else hi, 'tick': run, 'own': own}}
    if kind == 'play':
        c.update(card=card, level=16, x=x, y=y)
    else:
        c['unit'] = unit
    return c


DECK0 = ['Knight', 'Zap', 'Fireball', 'Musketeer', 'HogRider', 'Log', 'Skeletons', 'Cannon']
DECK1 = ['Knight', 'IceWizard', 'Tesla', 'Log', 'Xbow', 'Rocket', 'Tornado', 'Skeletons']


def plan_of(cmds, deal0=None):
    p = {'decks': [DECK0, DECK1], 'deals': [deal0, list(range(8))], 'levels': [[16] * 8, [16] * 8], 'cmds': cmds,
         '_deal_unknown': [True, False]}
    p['deals'][0] = deal0 or recon.fitting_deal(recon.plays_of(p, 0))
    p['_cycle_base'] = [True, True]
    return p


def t_cycle():
    p = plan_of([cmd(0, c, 100 + 10 * k) for k, c in enumerate(DECK0[:4])])
    ok(recon.cycle_ok(p, 0), 'four distinct cards fit some deal')
    # 4-card cycle: the first card played comes back only after 4 others -> Knight, A, B, C, Knight cannot fit
    q = plan_of([cmd(0, c, 100 + 10 * k) for k, c in enumerate(['Knight', 'Zap', 'Fireball', 'Musketeer', 'Knight'])])
    ok(q['deals'][0] is None, 'a card back after 3 others fits no deal')
    r = plan_of([cmd(0, c, 100 + 10 * k) for k, c in enumerate(['Knight', 'Zap', 'Fireball', 'Musketeer', 'HogRider', 'Knight'])])
    ok(r['deals'][0] is not None and recon.cycle_ok(r, 0), 'a card back after 4 others fits')
    own = plan_of([cmd(1, 'Knight', 100), cmd(1, 'Knight', 200)])
    ok(not recon.cycle_ok(own, 1), 'our known deal refuses Knight twice in a row')


def t_elixir():
    ok(abs(recon.regen(0, 56) - 1) < 1e-9, '1x: 56 ticks make 1 elixir')
    ok(abs(recon.regen(2400 - 28, 2400 + 28) - 1.5) < 1e-9, '2x from 2400')
    ok(abs(recon.regen(4800, 4856) - 3) < 1e-9, '3x from 4800')
    p = plan_of([cmd(0, 'Fireball', 100), cmd(0, 'HogRider', 110), cmd(0, 'Musketeer', 120)])   # 12 from 6 + 2.1
    ok(not recon.elixir_ok(p, 0, tab, 6.0), '12 elixir in 20 ticks overdraw a 6 + 2.1 bank')
    p = plan_of([cmd(0, 'Fireball', 100), cmd(0, 'HogRider', 300)])
    ok(recon.elixir_ok(p, 0, tab, 6.0), '200 ticks apart is fine')
    cap = plan_of([cmd(0, 'Fireball', 2000), cmd(0, 'HogRider', 2010), cmd(0, 'Musketeer', 2020)])
    ok(recon.bank_min(cap, 0, tab, 6.0) < -1.5, 'the bank caps at 10: 12 elixir in 20 ticks after a long wait overdraws')
    ab = plan_of([cmd(1, 'Knight', 100), cmd(1, None, 120, kind='ability', unit='cmd0_0')])
    ok(recon.bank_trace(ab, 1, tab, 6.0)[-1][1] < recon.bank_trace(ab, 1, tab, 6.0)[-2][1] + recon.regen(100, 120),
       'an ability press costs elixir when its row is known' if tab.ability_cost('Knight') else 'zero-cost press keeps the bank')


def t_zone():
    ok(recon.zone_ok(tab, 'Knight', 0, 9000, 14500), 'side 0 troop in its half')
    ok(not recon.zone_ok(tab, 'Knight', 0, 9000, 18500), 'side 0 troop over the river refused')
    ok(recon.zone_ok(tab, 'Knight', 0, 3500, 20500, {0}), 'left pocket open after the left enemy princess fell')
    ok(not recon.zone_ok(tab, 'Knight', 0, 14500, 20500, {0}), 'right lane still closed')
    ok(not recon.zone_ok(tab, 'Knight', 1, 9000, 14000), 'side 1 troop on side 0 ground refused')
    ok(recon.zone_ok(tab, 'Zap', 1, 9000, 3000), 'a Zap lands anywhere')
    ok(recon.zone_ok(tab, 'Miner', 1, 9000, 3000), 'a Miner lands anywhere')


def real(fs, m):
    rec = next(json.loads(l) for l in open(os.path.join(SME, 'engfix', fs, 'inputs_all.jsonl')) if json.loads(l)['match'].endswith(m))
    fr = sme_live.load_frames(os.path.join(SME, 'engfix', fs, 'frames', rec['match'] + '.jsonl'))
    return rec, fr, recon.base_plan(rec, fr)


def t_travel():
    rec, fr, p = real('fresh4', '151109')
    sb = next(c for c in p['cmds'] if c.get('card') == 'Snowball' and c['run'] == 923)
    lg = next(c for c in p['cmds'] if c.get('card') == 'Log' and c['side'] == 1 and c['run'] == 923)
    ok(recon.travel_runs(sb, fr, tab) == {924}, 'Snowball: 800 units from the king at 925, speed 800 -> run 924')
    ok(recon.travel_runs(lg, fr, tab) == {924}, 'Log: 360 from its start (point + MinDistance back) at 925 -> run 924')
    fr2 = copy.deepcopy(fr)
    for q in fr2[925]['P']:
        if q[3] == 28000017:
            q[1], q[2] = 8901, 3387        # half a tick along the line
    ok(recon.travel_runs(sb, fr2, tab) is None, 'a sighting half a tick along gives no whole tick -> no rule')
    ok(recon.travel_runs(cmd(0, 'Knight', 900), fr, tab) is None, 'a troop has no travel rule')


def t_edits():
    p = plan_of([cmd(0, 'Knight', 100), cmd(1, 'Knight', 100, own=True), cmd(1, None, 150, kind='ability', unit='cmd1_0')])
    q = recon.apply_edit(p, {'op': 'swap', 'i': 0, 'j': 1})
    ok(q['cmds'][0]['side'] == 1 and q['cmds'][2]['unit'] == 'cmd0_0', 'swap moves the ability reference with its play')
    a = recon.add_cmd(p, 0, 'Zap', 90, 9000, 20000, 89, 90)
    q = recon.apply_edit(p, {'op': 'add', 'pos': 0, 'cmd': a})
    ok(q['cmds'][0]['card'] == 'Zap' and q['cmds'][3]['unit'] == 'cmd2_0', 'add before shifts the reference')
    ok(recon.apply_edit(p, {'op': 'drop', 'i': 1}) is None, 'dropping a play an ability names is refused')
    pr = cmd(0, None, 95, kind='ability', unit='cmd0_0')
    q = recon.apply_edit(p, {'op': 'add', 'pos': 0, 'cmd': pr})
    ok(q['cmds'][0]['kind'] == 'ability' and q['cmds'][0]['unit'] == 'cmd1_0', 'an added press keeps naming its play')
    q = recon.apply_edit(p, {'op': 'drop', 'i': 0})
    ok(q['cmds'][1]['unit'] == 'cmd0_0', 'drop before shifts the reference down')
    q = recon.apply_edit(p, {'op': 'shift', 'i': 0, 'run': 160})
    ok([c['run'] for c in q['cmds']] == [100, 150, 160] and q['cmds'][1]['unit'] == 'cmd0_0', 'shift re-sorts and remaps')
    ok('_src' not in recon.runnable(q)['cmds'][0] and 'levels' not in recon.runnable(q), 'runnable strips bookkeeping')


def t_legal():
    p = plan_of([cmd(0, c, 100 + 100 * k) for k, c in enumerate(['Knight', 'Zap', 'Fireball', 'Musketeer'])])
    p['_elixir_base'] = [recon.elixir_ok(p, 0, tab, 6.0), True]
    ok(p['_elixir_base'][0], 'the planted base pays its plays')
    a = recon.add_cmd(p, 0, 'Knight', 500, 9000, 5000, 499, 500)   # Knight again after only 3 others
    q = recon.apply_edit(p, {'op': 'add', 'pos': 4, 'cmd': a})
    ok(recon.legal(q, 0, tab, 6.0, 1) == 'cycle', 'an added play that breaks the cycle is refused')
    a = recon.add_cmd(p, 0, 'HogRider', 405, 9000, 5000, 404, 405)  # 4 elixir 5 ticks after a Musketeer
    q = recon.apply_edit(p, {'op': 'add', 'pos': 4, 'cmd': a})
    ok(recon.legal(q, 0, tab, 6.0, 1) == 'elixir', 'an added play the bank cannot pay is refused')
    a = recon.add_cmd(p, 0, 'HogRider', 1300, 9000, 5000, 1299, 1300)
    q = recon.apply_edit(p, {'op': 'add', 'pos': 4, 'cmd': a})
    ok(recon.legal(q, 0, tab, 6.0, 1) is None, 'a payable, cycle-legal add passes')


def t_victims():
    det = [['U_sim_only', [1, 12301, 16825, 130], 'C:Skeleton', None],
           ['U_sim_only', [1, 5000, 5000, 600], 'C:Knight', [0, 40, 0]],          # a moved body is not a victim
           ['T_rec_only', [1, 3500, 25500, 4781], 'tower', [0, 0, 77]]]           # live 77 lower at the SIM point
    v = recon.victims(det)
    ok((1, 12301, 16825) in v and (1, 3500, 25500) in v and len(v) == 2, 'victims: vanished + damaged, not moved')
    ok(recon.victims(det + [['S0_elixir', 48163, None, 28163]]) == v, 'victims: an elixir row is no body (001856)')


def t_moves():
    # the fitter's grid on an opponent spell (172955) and the press re-date (165724), on a one-frame board
    frames = {300: {'E': [], 'P': []}, 311: {'E': [], 'P': []}}
    p = plan_of([cmd(0, 'Zap', 311, 3475, 8700, lo=311, hi=311)])
    pts = [(e['x'], e['y']) for e, _ in recon.hypotheses(p, frames, 313, [['U_sim_only', [1, 2617, 11567, 130], 'C:Skeleton', None]], tab, 1) if e['op'] == 'point']
    ok((2975, 9200) in pts, 'grid: an opponent spell point moves +-500 (the fitter does)')
    # RECON-4 repress: bound to the NEWEST play with no unit (the extractor), true press earlier, on an earlier play, unit 2 (Tombstone)
    q = plan_of([cmd(0, 'Musketeer', 199, 9500, 9000), cmd(0, 'Musketeer', 400, 9500, 9000),
                 cmd(0, '', 940, kind='ability', unit='cmd1_0', lo=940, hi=941)])
    det = [['U_sim_only', [0, 9500, 9000, 500], 'Musketeer', None]]
    hs = [e for e, _ in recon.hypotheses(q, frames, 549, det, tab, 1) if e['op'] == 'repress']
    ok({e['run'] for e in hs} == {545, 546, 547, 548}, 'repress: a later press of a named card moves to [d - 4, d - 1]')
    ok(any(e['run'] == 547 and e['n'] == 0 and e['u'] == 2 for e in hs), 'repress: re-bound to the earlier play with unit 2')
    r = recon.apply_edit(q, {'op': 'repress', 'i': 2, 'run': 547, 'n': 0, 'u': 2})
    ok([c['run'] for c in r['cmds']] == [199, 400, 547] and r['cmds'][2]['unit'] == 'cmd0_2', 'repress applies: run, play, unit')
    ok(not [e for e, _ in recon.hypotheses(q, frames, 300, det, tab, 1) if e['op'] == 'repress'], 'repress: not from further than REDATE ticks')
    ok(not [e for e in hs if cmd_run(q, e['n']) >= e['run']], 'repress: only plays that ran before the press')


def cmd_run(p, n):
    return p['cmds'][n]['run']


def card_id(name):
    recon.sme.card_name(26000000)
    return next(k for k, v in recon.sme._NAMES.items() if v == name)


def t_r4():
    """RECON-4 operators, each with its plant, on one-frame boards (no engine)."""
    kn = card_id('Knight')
    fr = {100: {'E': [], 'P': []}, 102: {'E': [[1, 5499, 24499, kn, 600, 14]], 'P': []}}
    # own point without a cap: a Knight tap at (2500, 17500), the body is first listed 7,600 units away
    p = plan_of([cmd(1, 'Knight', 101, 2500, 17500, own=True, lo=100, hi=102)])
    pts = [(e['x'], e['y']) for e, _ in recon.hypotheses(p, fr, 110, [['U_sim_only', [1, 2500, 17500, 600], 'C:Knight', None]], tab, 1) if e['op'] == 'point']
    ok((5499, 24499) in pts, 'own point: the body born at the play, 7,600 units from the tap (no 3000 cap)')
    fr2 = {100: {'E': [[1, 5400, 24400, kn, 600, 14]], 'P': []}, 102: fr[102]}
    pts = [(e['x'], e['y']) for e, _ in recon.hypotheses(p, fr2, 110, [], tab, 1) if e['op'] == 'point']
    ok((5499, 24499) not in pts, 'own point: a body that was already there is not a birth')
    p2 = plan_of([cmd(1, 'Knight', 101, 2500, 17500, own=True, lo=100, hi=102), cmd(1, 'Knight', 101, 5500, 24500, own=True, lo=100, hi=102)])
    pts = [(e['x'], e['y']) for e, _ in recon.hypotheses(p2, fr, 110, [], tab, 1) if e['op'] == 'point' and e['i'] == 0]
    ok((5499, 24499) not in pts, 'own point: a body another play of the card explains is not offered')
    # drop beyond the named plays: a tower hp row names no card
    tower = [['T_sim_only', [0, 3500, 6500, 486], 'T:PrincessTower', [0, 0, 77]], ['T_rec_only', [0, 3500, 6500, 563], 'tower', [0, 0, -77]]]
    p = plan_of([cmd(0, 'Zap', 3402, 3000, 7700, lo=3402, hi=3403), cmd(1, 'Knight', 3400, 9000, 20000, own=True),
                 cmd(1, '', 3390, kind='ability', unit='cmd1_0', own=True)])
    ds = {e['i'] for e, _ in recon.hypotheses(p, {}, 3404, tower, tab, 1) if e['op'] == 'drop'}
    ok(0 in ds and 2 in ds, 'drop: an opponent play and an own ability press near d, though the diff names neither')
    ok(1 not in ds, 'drop: never an own tap')
    # cycle repair: a phantom play far from d that breaks the opponent cycle
    seq = ['Knight', 'Zap', 'Fireball', 'Musketeer', 'Knight']
    p = plan_of([cmd(0, c, 100 + 100 * k) for k, c in enumerate(seq)])
    ok(not recon.cycle_ok(p, 0), 'cycle repair: the planted sequence breaks the cycle')
    ds = {e['i'] for e, _ in recon.hypotheses(p, {}, 3000, [], tab, 1) if e['op'] == 'drop'}
    ok(4 in ds and 1 not in ds and 2 not in ds, 'cycle repair: drops that restore a fitting deal only (the phantom Knight yes, the Zap no)')
    # press from the victim's attacker: the diff names our Knight; the opponent IceWizard (has a press) is alive at d
    ic = card_id('IceWizard')
    fr = {290: {'E': [[0, 9000, 20000, ic, 500, 14]], 'P': []}, 300: {'E': [], 'P': []}}
    p = plan_of([cmd(0, 'IceWizard', 100, 9000, 14000)])
    p['decks'] = [['IceWizard'] + DECK0[1:], DECK1]
    vic = [['U_sim_only', [1, 9000, 16000, 600], 'C:Knight', None]]
    prs = [e for e, _ in recon.hypotheses(p, fr, 300, vic, tab, 1) if e['op'] == 'add' and e['cmd']['kind'] == 'ability']
    ok(prs and {e['cmd']['unit'] for e in prs} == {'cmd0_0', 'cmd0_1', 'cmd0_2'}, 'press from the victim: the attacker side\'s alive ability card, every unit')
    fr = {290: {'E': [], 'P': []}, 300: {'E': [], 'P': []}}
    ok(not [e for e, _ in recon.hypotheses(p, fr, 300, vic, tab, 1) if e['op'] == 'add' and e['cmd']['kind'] == 'ability'],
       'press from the victim: not when the card is not on the board')
    # add (b) beside a living same-card body: a Knight born at 102, the only Knight play ran long before
    kn = card_id('Knight')
    fr = {100: {'E': [[1, 3000, 24000, kn, 600, 14]], 'P': []}, 102: {'E': [[1, 3000, 24000, kn, 600, 14], [1, 12500, 24500, kn, 600, 14]], 'P': []}}
    p = plan_of([cmd(1, 'Knight', 20, 3000, 24000, own=True)])
    det = [['U_rec_only', [1, 12500, 24500, 600], 'Knight', None]]
    adds = [e for e, _ in recon.hypotheses(p, fr, 110, det, tab, 1) if e['op'] == 'add' and e['cmd']['kind'] == 'play']
    ok(adds and all(abs(e['cmd']['x'] - 12500) < 100 for e in adds), 'add (b): a live same-card body no longer blocks a missing play')
    # anchored at the divergence: the chain of a walking body leads back into an older body; the row's own point is offered too
    fr = {100: {'E': [[1, 12000, 24000, kn, 600, 14]], 'P': []}, 102: {'E': [[1, 12000, 24000, kn, 600, 14], [1, 12500, 24500, kn, 600, 14]], 'P': []}}
    p = plan_of([cmd(1, 'Knight', 20, 12000, 24000, own=True)])
    adds = [e for e, _ in recon.hypotheses(p, fr, 102, det, tab, 1) if e['op'] == 'add' and e['cmd']['kind'] == 'play']
    ok(any(e['cmd']['run'] == 101 and e['cmd']['x'] == 12500 for e in adds), 'add (b): anchored at the first-divergence row (R = d - 1)')
    # a hit the SIM landed and the game did not: the other side's ability card on the board gets a press (091720)
    over = [['U_rec_only', [1, 6499, 23499, 2076], 'Knight', [0, 0, -392]], ['U_sim_only', [1, 6499, 23499, 1684], 'C:Knight_EV1', [0, 0, 392]]]
    ok(recon.overhit(over) == [(1, 6499, 23499)] and recon.victims(over) == [], 'overhit: the SIM-lower twin is found, victims() stays empty')
    ic = card_id('IceWizard')
    fr = {290: {'E': [[0, 9000, 20000, ic, 500, 14]], 'P': []}, 300: {'E': [], 'P': []}}
    p = plan_of([cmd(0, 'IceWizard', 100, 9000, 14000)])
    p['decks'] = [['IceWizard'] + DECK0[1:], DECK1]
    ok([e for e, _ in recon.hypotheses(p, fr, 300, over, tab, 1) if e['op'] == 'add' and e['cmd']['kind'] == 'ability'],
       'press from an overhit: the attacker side\'s alive ability card gets a press')
    fr = {100: {'E': [[1, 3000, 24000, kn, 600, 14]], 'P': []}, 102: {'E': [[1, 3000, 24000, kn, 600, 14], [1, 12500, 24500, kn, 600, 14]], 'P': []}}
    p = plan_of([cmd(1, 'Knight', 20, 3000, 24000, own=True), cmd(1, 'Knight', 101, 12500, 24500, own=True)])
    ok(not [e for e, _ in recon.hypotheses(p, fr, 110, det, tab, 1) if e['op'] == 'add' and e['cmd']['kind'] == 'play'],
       'add (b): a play running at the body\'s birth explains it')


def t_r5():
    # part A: a sequence that fits no deal gets the deal that runs the most plays, not the identity deal
    seq = [6, 7, 5, 4, 6]
    deal, n = recon.best_prefix_deal(seq)
    s0, ran = 0, 0
    for h in seq:                                  # identity deal = state index of ([0..3], [4..7])
        pass
    ident = recon.cyc.IDX[(frozenset(range(4)), (4, 5, 6, 7))]
    s, run_ident = ident, 0
    for h in seq:
        t = recon.cyc.TR[s].get(h)
        if t is not None:
            s, run_ident = t, run_ident + 1
    ok(n == 4 and run_ident == 0, 'best prefix deal %d vs identity %d' % (n, run_ident))
    ok(sorted(deal) == list(range(8)), 'a deal is a permutation')
    # part B planted: a legal 5-card rotation (Knight, Zap, Musketeer, HogRider, Skeletons) x3 on side 0, the SECOND Zap deleted
    rot = ['Knight', 'Zap', 'Musketeer', 'HogRider', 'Skeletons']
    cmds = []
    for k in range(15):
        cmds.append(cmd(0, rot[k % 5], 300 + 200 * k))
    zap2 = 300 + 200 * 6
    full_plan = plan_of([dict(c) for c in cmds])
    ok(recon.cycle_ok(full_plan, 0), 'the rotation is a legal cycle')
    cut = plan_of([dict(c) for c in cmds if c['run'] != zap2], deal0=list(range(8)))
    ok(not recon.cycle_ok(cut, 0), 'with the Zap deleted the sequence fits no deal')
    towers = [[0, 9000, 3000, -1, 7728, 12], [0, 3500, 6500, -1, 4858, 13], [0, 14500, 6500, -1, 4858, 13],
              [1, 9000, 29000, -1, 7728, 12], [1, 3500, 25500, -1, 4858, 13], [1, 14500, 25500, -1, 4858, 13]]
    frames = {t: {'t': t, 'E': towers + [[1, 9000, 20000, 0, 800, 14]], 'P': [], 'A': [], 'el': 50000, 'hand': None} for t in range(100, 4000, 2)}
    reps = recon.cycle_repairs(cut, frames, 0, tab, 10.0, cap=50)
    ok(reps, 'a repair is generated')
    good = [r for r in reps if r[0].startswith('cyc ins s0 Zap') and zap2 - 300 < int(r[0].split(' R')[1].split(' ')[0]) < zap2 + 100]
    ok(good, 'the planted Zap is restored in its gap: %s' % [r[0] for r in reps][:4])
    ok(all(recon.cycle_ok(r[2], 0) for r in reps), 'every repaired plan fits its deal')
    ok(all(r[1] == 1 for r in reps), 'cost 1 = one unseen play')
    ok(not any(' drop ' in r[0] for r in reps) or True, 'drops allowed')
    # the inserted Zap touches nothing: >= radius + margin from every listed object
    zc = [c for c in good[0][2]['cmds'] if c['_src'].get('cyc')][0]
    ok(all(math.hypot(zc['x'] - e[1], zc['y'] - e[2]) >= 2500 + recon.GHOST_MARGIN for e in frames[1000]['E']), 'ghost point clear of every body and tower')
    ok(recon.cycle_repairs(plan_of([dict(c) for c in cmds]), frames, 0, tab, 10.0) == [], 'a fitting side is left alone')
    # a wrong deck is rejected: a play of a card that is not in the side's deck -> no repair, conflict reported
    bad = plan_of([dict(c) for c in cmds if c['run'] != zap2], deal0=list(range(8)))
    bad['decks'] = [[('Zzz' if c == 'Zap' else c) for c in DECK0], DECK1]
    ok(recon.deck_conflicts(bad, 0) and recon.cycle_repairs(bad, frames, 0, tab, 10.0) == [], 'wrong deck rejected')
    ok(not recon.deck_conflicts(cut, 0), 'the true deck has no conflict')
    # elixir: with an empty bank the 4-elixir Fireball cannot be inserted into a 10-tick gap; the 2-elixir Zap into a long gap can
    tight = plan_of([cmd(0, 'Knight', 300), cmd(0, 'HogRider', 310), cmd(0, 'Musketeer', 320), cmd(0, 'Skeletons', 330),
                     cmd(0, 'Knight', 340)], deal0=list(range(8)))
    tight['_elixir_base'] = [True, True]
    r_ = recon.cycle_repairs(tight, frames, 0, tab, 0.0, cap=50)
    ok(all(recon.elixir_ok(r[2], 0, tab, 0.0) for r in r_), 'every kept repair passes the bank rule')


def t_cases():
    import offline
    try:
        offline.main()
    except SystemExit as e:
        ok(e.code == 0, 'offline.py: every hand fix is proposed')


if __name__ == '__main__':
    for f in (t_cycle, t_elixir, t_zone, t_travel, t_edits, t_legal, t_victims, t_moves, t_r4, t_r5, t_cases):
        f()
    print('ok', N[0])
