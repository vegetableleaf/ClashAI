"""First-divergence diagnostics for every failing match of a run (ticket A2c round 6.0).
    SME_HP_PLACEHOLDER=1 SME_TORN_CMD=1 SME_TORN_STEP=1 SME_REPR=... SME_LIB=... SME_BUILD=... \
    python3 diag6.py RUNDIR LIST INPUTS OUT.jsonl
LIST: "<match> <onset>" lines. One sim per match (output t0-150 .. t0+8). Per onset:
- the onset frame's diff size against sim t0-2 .. t0+2 (a read of another tick shows as a smaller diff there);
- why step_read (round 4.1) rejects it, the number of sim bodies moving in step t0+1, and whether it passes with the
  two-mover requirement dropped (hypothesis (ii));
- our elixir: recorded frames t0-6 .. t0+6 against the sim, and our commands in [t0-30, t0+3] (hypothesis (i));
- every command in [t0-130, t0]: card, side, run tick, extracted window, source."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sme_live  # noqa: E402
from sme import run_batch, diff  # noqa: E402
from sme_live import load_frames, runnable, canon_live, sim_canon, fill_placeholder, step_read  # noqa: E402

FRAMES = '/workspace/pilot/sme_live/frames2'


def d_at(fr, by, me, t, s):
    if s not in by:
        return None
    r, sc = canon_live(fr[t], me), sim_canon(by[s], me)
    if sme_live.HP_PH:
        r = fill_placeholder(r, sc)
    return diff(r, sc)


def card_of(plan, c):
    if c.get('card'):
        return c['card']
    u = c.get('unit', '')
    try:
        return 'abil:' + plan['cmds'][int(u[3:].split('_')[0])]['card']
    except (ValueError, IndexError, KeyError):
        return 'abil:?'


def main():
    run, lst, inputs, outp = sys.argv[1:5]
    me_of = {json.loads(l)['match']: json.loads(l)['my_side'] for l in open(inputs)}
    todo = [l.split()[:2] for l in open(lst) if l.strip()]
    plans, frs, jobs = {}, {}, []
    for m, t0 in todo:
        t0 = int(t0)
        plans[m] = json.load(open(os.path.join(run, m, 'plan.json')))
        frs[m] = load_frames(os.path.join(FRAMES, m + '.jsonl'))
        jobs.append((runnable(plans[m]), t0 + 8, max(0, t0 - 150)))
    outs = run_batch(jobs, os.path.join(run, 'diag6_work'))
    with open(outp, 'w') as w:
        for (m, t0), o in zip(todo, outs):
            t0 = int(t0)
            me, fr, plan = me_of[m], frs[m], plans[m]
            if o is None:
                w.write(json.dumps({'match': m, 't0': t0, 'error': 'sim refused'}) + '\n')
                continue
            by = {s['t']: s for s in o}
            kd = {k: (lambda d: None if d is None else len(d))(d_at(fr, by, me, t0, t0 + k)) for k in (-2, -1, 0, 1, 2)}
            why = []
            sr = step_read(fr[t0], by[t0], by[t0 + 1], me, why) if t0 + 1 in by else None
            ba = {e[0]: e for e in sme_live.repr_rows(by[t0]) if e[1] in 'TC'}
            bb = {e[0]: e for e in sme_live.repr_rows(by[t0 + 1]) if e[1] in 'TC'} if t0 + 1 in by else {}
            movers = sum(1 for i in ba if i in bb and ba[i][4:6] != bb[i][4:6])
            sr1 = None
            if sr is False and movers < 2:  # the same test with the two-mover requirement dropped (diagnostic only)
                w1 = []
                sr1 = True if step_read(fr[t0], by[t0], by[t0 + 1], me, w1, min_movers=1) else [list(map(str, x)) for x in w1]
            clock = t0 + 1 in by and fr[t0]['el'] == by[t0 + 1]['S'][me][0] != by[t0]['S'][me][0]
            src = None
            if clock and sr is False:  # our elixir already shows step t0+1's regen: the same test without the mover count
                w1 = []
                src = True if step_read(fr[t0], by[t0], by[t0 + 1], me, w1, min_movers=0) else [list(map(str, x)) for x in w1]
            ts = sorted(fr)
            el = [(t, fr[t]['el'], by[t]['S'][me][0] if t in by else None) for t in ts if t0 - 6 <= t <= t0 + 6]
            sim_el = [(t, by[t]['S'][me][0]) for t in range(t0 - 6, t0 + 7) if t in by]
            cm = [{'k': i, 'card': card_of(plan, c), 'side': c['side'], 'run': c['run'], 'lo': c['_src']['lo'],
                   'hi': c['_src']['hi'], 'src': c['_src'].get('source')}
                  for i, c in enumerate(plan['cmds']) if c['kind'] != 'skip' and t0 - 130 <= c['run'] <= t0 + 3]
            nxt = [t for t in ts if t > t0][:4]
            nxt_cls = {t: (lambda d: None if d is None else len(d))(d_at(fr, by, me, t, t)) for t in nxt}
            w.write(json.dumps({'match': m, 't0': t0, 'me': me, 'gap_prev': t0 - max([t for t in ts if t < t0] or [0]),
                                'k_diff': kd, 'd0': d_at(fr, by, me, t0, t0), 'd1': d_at(fr, by, me, t0, t0 + 1),
                                'dm1': d_at(fr, by, me, t0, t0 - 1),'step_read': sr, 'why': [list(map(str, x)) for x in why],
                                'movers': movers, 'step_read_1mover': sr1, 'el_clock_t1': clock,
                                'step_read_clock': src,'elixir_rec_sim': el, 'sim_el': sim_el,
                                'next_frames_diff': nxt_cls, 'cmds': cm}) + '\n')
    import shutil
    shutil.rmtree(os.path.join(run, 'diag6_work'), ignore_errors=True)


if __name__ == '__main__':
    main()
