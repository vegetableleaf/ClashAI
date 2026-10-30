"""Planted checks for recon.py (laptop, no engine):  python -I test_recon.py  -> 'ok N' or an AssertionError."""
import copy, json, os, sys

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


def t_cases():
    import offline
    try:
        offline.main()
    except SystemExit as e:
        ok(e.code == 0, 'offline.py: every hand fix is proposed')


if __name__ == '__main__':
    for f in (t_cycle, t_elixir, t_zone, t_travel, t_edits, t_legal, t_victims, t_cases):
        f()
    print('ok', N[0])
