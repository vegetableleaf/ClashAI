"""A2c-BP comparator rule SME_BP_SNAP: a read taken inside a game step. An isolated div frame t (no div neighbour) is
'torn_snap' when its board equals, by the SME comparison, crforge's own state at one in-step event of step t+1
(SnapRun: after the pre-pass, each hit, launch, impact, spawn, removal, the post-hooks pass), and our elixir equals that
state's or an earlier one's (the reader reads our elixir before the board). Exact: no tolerance, crforge's own states
only. Probe: 141505@1808 = the state at a spawn event of step 1809; 171232@961 = the state after a hit in step 962."""
import collections, json, os, subprocess
import sme
from sme import diff
from sme_live import canon_live, sim_canon, fill_placeholder, HP_PH

SNAP_BUILD = os.environ.get('SME_SNAP_BUILD', '/workspace/pilot/bp/build_snap')


def snapshots(plan, ticks, end, workdir):
    """{T: [state, ...]} of crforge's in-step states of the steps that make lines T."""
    os.makedirs(workdir, exist_ok=True)
    pf, of = os.path.join(workdir, 'snap_p.json'), os.path.join(workdir, 'snap_o.jsonl')
    json.dump(plan, open(pf, 'w'))
    jf = os.path.join(workdir, 'snap_jobs.txt')
    open(jf, 'w').write('%s %d %s %d\n' % (pf, end, of, end))
    env = dict(os.environ, SNAP_TICKS=','.join(str(T) for T in sorted(ticks)))
    subprocess.run(['java', '-Xmx8g', '-cp', sme.LIB + '/*:' + SNAP_BUILD, 'SnapRun', sme.TABLES, jf, '1'],
                   capture_output=True, text=True, env=env)
    out = collections.defaultdict(list)
    if os.path.exists(of + '.snap.jsonl'):
        for l in open(of + '.snap.jsonl'):
            s = json.loads(l)
            out[s['T']].append(s)
        os.remove(of + '.snap.jsonl')
    if os.path.exists(of):
        os.remove(of)
    return out


def in_step(f, states, me):
    """True when the frame's board equals one state and our elixir equals that state's or an earlier one's."""
    els = set()
    for s in states:
        els.add(s['S'][me][0])
        sc = sim_canon(s, me)
        rc = canon_live(f, me)
        if HP_PH:
            rc = fill_placeholder(rc, sc)
        if not [x for x in diff(rc, sc) if not x[0].startswith('S')] and f['el'] in els:
            return True
    return False


def reclass(plan, frames, me, an, obs, workdir):
    """Re-class the isolated div frames of an analysis; returns the analysis with counts / first updated."""
    cls = dict(an['cls'])
    ts = sorted(cls)
    cand = [t for k, t in enumerate(ts) if cls[t] == 'div' and
            all(cls[ts[j]] != 'div' for j in (k - 1, k + 1) if 0 <= j < len(ts))]
    if not cand:
        return an
    by = {o['t']: o for o in obs}
    snaps = snapshots(plan, [t + 1 for t in cand], max(cand) + 3, workdir)
    for t in cand:
        if t not in by or t + 1 not in by:
            continue
        states = [by[t]] + snaps.get(t + 1, []) + [by[t + 1]]
        if in_step(frames[t], states, me):
            cls[t] = 'torn_snap'
    first = next((t for t in ts if cls[t] == 'div'), None)
    return dict(an, cls=cls, first=first, counts=dict(collections.Counter(cls.values())))
