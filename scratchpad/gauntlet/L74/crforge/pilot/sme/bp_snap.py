"""A2c-BP comparator rule SME_BP_SNAP: a read taken inside a game step. An isolated div frame t (no div neighbour) is
'torn_snap' when its board equals, by the SME comparison, crforge's own state at one in-step event of step t+1
(SnapRun: after the pre-pass, each hit, launch, impact, spawn, removal, the post-hooks pass; SnapRun2 on the clashbot-bp
engine also after the command pass, each cleanup and every entity visit / action / post-hook), and our elixir equals that
state's or an earlier one's (the reader reads our elixir before the board). SME-HARDEN: the whole frame, player state
included (elixir and, when read, hand), equals that one state; a frame whose player state is an earlier state's is left
to the step read (sme_live.step_read, given these states). Exact: no tolerance, crforge's own states only. Probe:
141505@1808 = the state at a spawn event of step 1809; 171232@961 = the state after a hit in step 962."""
import collections, json, os, subprocess
import sme
from sme import diff
from sme_live import canon_live, sim_canon, fill_placeholder, HP_PH, TORN_STEP, step_read

SNAP_BUILD = os.environ.get('SME_SNAP_BUILD', '/workspace/pilot/bp/build_snap')
SNAP_CLASS = os.environ.get('SME_SNAP_CLASS', 'SnapRun')  # SnapRun2 (clashbot-bp TickProbe): every point inside the step


def snapshots(plan, ticks, end, workdir):
    """{T: [state, ...]} of crforge's in-step states of the steps that make lines T."""
    os.makedirs(workdir, exist_ok=True)
    pf, of = os.path.join(workdir, 'snap_p.json'), os.path.join(workdir, 'snap_o.jsonl')
    json.dump(plan, open(pf, 'w'))
    jf = os.path.join(workdir, 'snap_jobs.txt')
    open(jf, 'w').write('%s %d %s %d\n' % (pf, end, of, end))
    env = dict(os.environ, SNAP_TICKS=','.join(str(T) for T in sorted(ticks)))
    subprocess.run(['java', '-Xmx8g', '-cp', sme.LIB + '/*:' + SNAP_BUILD, SNAP_CLASS, sme.TABLES, jf, '1'],
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
    """SME-HARDEN: the frame equals one state as a whole by the full SME comparison (multiset of every object class, and
    our whole player state: elixir and, when read, hand). Returns {'rule': 'snap', 'board': k, 'ev': event} or None."""
    rc0 = canon_live(f, me)
    for k, s in enumerate(states):
        sc = sim_canon(s, me)
        if not diff(fill_placeholder(rc0, sc) if HP_PH else rc0, sc):
            return {'rule': 'snap', 'board': k, 'ev': s.get('ev')}
    return None


def reclass(plan, frames, me, an, obs, workdir):
    """Re-class the isolated div frames of an analysis; returns the analysis with counts / first updated. SME-HARDEN: a
    frame no single state holds is retried as a step read (sme_live.step_read) whose bodies killed after their move are
    read at their points in these in-step states (an isolated step read: no div / torn_step neighbour)."""
    cls, prov = dict(an['cls']), dict(an.get('prov', {}))
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
        p = in_step(frames[t], states, me)
        if p:
            cls[t], prov[t] = 'torn_snap', p
            continue
        k = ts.index(t)
        if TORN_STEP and all(cls[ts[j]] not in ('div', 'torn_step') for j in (k - 1, k + 1) if 0 <= j < len(ts)):
            p = step_read(frames[t], by[t], by[t + 1], me, snaps=snaps.get(t + 1, []))
            if p:
                cls[t], prov[t] = 'torn_step', p
    first = next((t for t in ts if cls[t] == 'div'), None)
    return dict(an, cls=cls, prov=prov, first=first, counts=dict(collections.Counter(cls.values())))
