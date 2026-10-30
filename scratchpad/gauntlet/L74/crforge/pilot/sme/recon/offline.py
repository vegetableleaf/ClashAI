"""RECON offline check (laptop, no engine): on the cases a hand rule fixed, does the general generator propose the
hand rule's fix, after the hard rules, and how many engine runs does the round cost?

    python -I offline.py            # the three cases of RECON.md section 5; exit 1 if a hand fix is not proposed

Inputs are the FROZEN fresh inputs (scored before the fix) and the fresh gate's first-divergence diff
(results/live/freshN/*_results.jsonl 'first_detail' = sme_live.describe_first on the pod)."""
import collections, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402
import sme_live  # noqa: E402

SME = os.path.dirname(HERE)


def find(path, m):
    return next(json.loads(l) for l in open(path) if json.loads(l)['match'].endswith(m))


def by_card(p, side, card, run):
    return [k for k, c in enumerate(p['cmds']) if c['side'] == side and c.get('card') == card and c['run'] == run]


CASES = [
    # (set, gate run, match, hand rule, predicate on the edited plan = the hand rule's fix)
    ('fresh5', 'F5_main', '20261029_021310', 'SME_ZAP_DEAD: opponent Zap (12864, 17261) R 1985, window [1984, 1985]',
     lambda p: any(c['side'] == 0 and c.get('card') == 'Zap' and c['_src'].get('source') == 'recon_add'
                   and 1984 <= c['run'] <= 1985 and math.hypot(c['x'] - 12864, c['y'] - 17261) <= 200 for c in p['cmds'])),
    ('fresh4', 'F4_fe', '20261028_151109', 'SME_SPELL_KING: opponent Snowball and our Log both run 924',
     lambda p: by_card(p, 0, 'Snowball', 924) and by_card(p, 1, 'Log', 924)),
    ('fresh6', 'F6_main', '20261029_031310', 'SME_SAMETICK_GEN: our Knight before the opponent Mega Knight on 3931',
     lambda p: (by_card(p, 1, 'Knight', 3931) or [99])[0] < (by_card(p, 0, 'MegaKnight', 3931) or [-1])[0]),
    ('fresh4', 'F4_fe', '20261028_235834', 'SME_TOWER_ZAP + TZ_REACH: opponent Zap on our 19-hp tower centre, R 4611',
     lambda p: any(c['side'] == 0 and c.get('card') == 'Zap' and c['_src'].get('source') == 'recon_add'
                   and c['run'] == 4611 and math.hypot(c['x'] - 14500, c['y'] - 25500) <= 300 for c in p['cmds'])),
    ('fresh4', 'F4_fe', '20261028_220244', 'SME_OWN_BODYPT: our Knight at its first listed body point (1 tile off the tap)',
     lambda p: any(c['side'] == 0 and c.get('card') == 'Knight' and math.hypot(c['x'] - 2499, c['y'] - 13500) <= 100
                   for c in p['cmds'])),
    ('fresh4', 'F4_fe', '20261028_222707', 'SME_OWN_BODYPT: our Knight at its first listed body point (2 tiles off the tap)',
     lambda p: any(c['side'] == 0 and c.get('card') == 'Knight' and math.hypot(c['x'] - 1499, c['y'] - 10500) <= 100
                   for c in p['cmds'])),
]
# No hand fix exists (untraced in SME.md): print what the generator proposes, for the engine run.
PROPOSE = [('fresh6', 'F6_main', '20261029_024716')]


def main():
    tab = recon.Tab()
    bad = 0
    for fs, run, m, rule, fixed in CASES:
        rec = find(os.path.join(SME, 'engfix', fs, 'inputs_all.jsonl'), m)
        res = find(os.path.join(SME, 'results', 'live', fs, run + '_results.jsonl'), m)
        frames = sme_live.load_frames(os.path.join(SME, 'engfix', fs, 'frames', rec['match'] + '.jsonl'))
        me, d, detail = rec['my_side'], res['first_div'], res['first_detail']
        plan = recon.base_plan(rec, frames)
        e0 = recon.start_elixir(frames, plan, me, tab)
        recon.with_elixir_base(plan, tab, e0)
        why = collections.Counter()
        raw = recon.hypotheses(plan, frames, d, detail, tab, me)
        hs = recon.legal_hypotheses(plan, frames, d, detail, tab, me, e0, why)
        hs.sort(key=lambda h: h[1])
        hits = [(k, e, cost) for k, (e, cost, p) in enumerate(hs) if fixed(p)]
        print('=== %s (%s) first div %d; hand rule %s' % (m, fs, d, rule))
        print('  E0 %.3f  base cycle ok %s  elixir ok %s  opp bank min %.2f' % (
            e0, plan['_cycle_base'], plan['_elixir_base'], recon.bank_min(plan, 1 - me, tab, e0) or 0))
        print('  generated %d, legal %d (refused %s); by op %s' % (
            len(raw), len(hs), dict(why), dict(collections.Counter(e['op'] for e, _, _ in hs))))
        if hits:
            k, e, cost = hits[0]
            same = sum(1 for _, c, _ in hs if c <= cost)
            print('  HAND FIX PROPOSED: #%d of %d legal (%d at cost <= %d): %s' % (k + 1, len(hs), same, cost,
                                                                               recon.describe(plan, e)))
            for k2, e2, c2 in hits[1:4]:
                print('    also #%d: %s' % (k2 + 1, recon.describe(plan, e2)))
        else:
            bad += 1
            print('  HAND FIX NOT PROPOSED')
    for fs, run, m in PROPOSE:
        rec = find(os.path.join(SME, 'engfix', fs, 'inputs_all.jsonl'), m)
        res = find(os.path.join(SME, 'results', 'live', fs, run + '_results.jsonl'), m)
        frames = sme_live.load_frames(os.path.join(SME, 'engfix', fs, 'frames', rec['match'] + '.jsonl'))
        plan = recon.base_plan(rec, frames)
        e0 = recon.start_elixir(frames, plan, rec['my_side'], tab)
        recon.with_elixir_base(plan, tab, e0)
        hs = sorted(recon.legal_hypotheses(plan, frames, res['first_div'], res['first_detail'], tab, rec['my_side'], e0),
                    key=lambda h: h[1])
        print('=== %s (%s) first div %d; no hand fix. %d legal; by op %s; the adds:' % (
            m, fs, res['first_div'], len(hs), dict(collections.Counter(e['op'] for e, _, _ in hs))))
        for e, c, _ in [h for h in hs if h[0]['op'] == 'add'][:6]:
            print('    cost %d: %s' % (c, recon.describe(plan, e)))
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
