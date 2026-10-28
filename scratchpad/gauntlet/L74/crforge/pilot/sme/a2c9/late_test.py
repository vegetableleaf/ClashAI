"""A2c-9T planted checks for torn_late (sme_live.late_reclass): python3 late_test.py PLAN.json FRAMES.jsonl SIDE
(env as run9.sh, SME_LATE9=1, SME_CODE=sme9). Every listed late frame must pass as is and fail with each planted change;
an unlisted frame must never be re-classed."""
import copy, json, os, sys
sys.path.insert(0, os.environ.get('SME_CODE', '/workspace/pilot/sme9'))
import sme_live
plan, frames, me = json.load(open(sys.argv[1])), sme_live.load_frames(sys.argv[2]), int(sys.argv[3])
late = [(i, t) for i, c in enumerate(plan['cmds']) for t in c['_src'].get('late_reads', ())]
assert late, 'no late_reads in the plan'
wd = '/workspace/pilot/a2c9/work_lt%d' % os.getpid()


def cls_of(fr, t, plan=plan):
    an = {'cls': {t: 'div'}, 'counts': {}, 'first': t}
    return sme_live.late_reclass(plan, fr, me, an, wd)['cls'][t]


def planted(t):
    f = frames[t]
    own = next((k for k, e in enumerate(f['E']) if e[0] == me), None)
    knight = next(c for i, c in enumerate(plan['cmds']) if (i, t) in late)
    out = {
        'our elixir +1': dict(f, el=f['el'] + 1),
        'our elixir with the cost taken': dict(f, el=f['el'] - 30000),
        'a recorded body of ours moved 1 unit': dict(f, E=[e if k != own else [e[0], e[1] + 1] + e[2:] for k, e in enumerate(f['E'])]),
        "the play's body added at its point": dict(f, E=f['E'] + [[me, knight['x'], knight['y'], 26000000, 2822, 14]]),
        'an opponent body removed': dict(f, E=[e for e in f['E'] if e is not next(x for x in f['E'] if x[0] != me)]),
        'a projectile added': dict(f, P=f['P'] + [[1 - me, 9000, 16000, 0]]),
    }
    return out


for i, t in late:
    print('late frame', t, 'cmd', i, 'base:', cls_of(frames, t))
    for name, f2 in planted(t).items():
        fr2 = dict(frames)
        fr2[t] = f2
        print('  planted %-40s -> %s' % (name, cls_of(fr2, t)))
    # an unlisted frame is never re-classed, even when it would equal the counterfactual state
    nxt = min(x for x in frames if x > t)
    p2 = copy.deepcopy(plan)
    p2['cmds'][i]['_src']['late_reads'] = []
    print('  same frame, not listed (late_reads emptied) ->', cls_of(frames, t, p2))
    print('  next frame %d, not listed ->' % nxt, cls_of(frames, nxt))
