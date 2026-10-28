"""SME-HARDEN planted-divergence suite. sme_live.do_match runs it on every match of every run (SME_PLANTS=0 skips) and
writes result['plants']; round_cmp.py prints the totals and fails the run on any miss.

Targets on one match (the final fitted plan's sim run):
- every torn frame (torn_t1 / cmd / step / mixed / cross / snap / late / hidden);
- up to REP non-div frames per representation rule: KIND_T (a card -1 row whose kind is not 12/13, read as a unit),
  placeholder (a recorded body at hp -1), REPR (sim t has a row the reader-representation map drops or remaps);
- up to REP exact frames (the verifier's plants turned exact frames torn_mixed).
Plants on a target frame t (one change each): every body row (towers included) moved x+1 and y+1, hp +1 and -1,
removed, duplicated; every projectile / area effect removed, moved x+1, duplicated; a unit added 3000 units away; our
elixir +-1 raw and +-1 whole (10000); our hand's first two cards swapped. No hp plant on a row at hp -1 (the reader's
placeholder: its hp is not read) and no hp-1 on a row at hp 0 (it would write the placeholder value).
The planted frame is classified by the full comparator (sme_live.analyse + reclassify) on the frames t +- W.
Outcome: caught (div), or -- only with an independent witness that the planted frame is a real state -- legal:
- legal_t / legal_t1: the planted frame equals sim t / t+1 by the plain multiset comparison;
- legal_state: torn_snap (its board equals one crforge in-step state by the plain multiset comparison) or torn_cmd (board
  = sim t by the plain comparison, elixir = sim t+1's before its regen);
- legal_version (move / hp / dup plants): the planted object equals, recomputed here from the raw sim rows, the version of
  one entity named by the new provenance, and that entity's label changed from the base provenance;
- legal_absent (remove plants): the new provenance shows an entity absent (it is absent from one line) that the base
  provenance showed present.
Anything else is MISSED. window_mismatch: the windowed comparator did not reproduce the target's own class (skipped)."""
import collections, copy, json, random
import bp_snap
import sme_live as L
from sme import diff

REP, W = 3, 6


def _memo_snaps(orig):
    cache = {}

    def f(plan, ticks, end, workdir):
        need = sorted(T for T in set(ticks) if T not in cache)
        if need:
            got = orig(plan, need, max(need) + 2, workdir)
            for T in need:
                cache[T] = got.get(T, [])
        return {T: cache[T] for T in ticks}
    return f


def _memo_batch(orig):
    cache = {}

    def f(jobs, workdir):
        keys = [json.dumps(j, sort_keys=True) for j in jobs]
        need = [(k, j) for k, j in zip(keys, jobs) if k not in cache]
        if need:
            for (k, _), r in zip(need, orig([j for _, j in need], workdir)):
                cache[k] = r
        return [cache[k] for k in keys]
    return f


def _obj(e):
    """A recorded body row as the comparator's (k, tuple)."""
    return ('T' if e[3] == -1 and (not L.KIND_T or e[5] in (12, 13)) else 'U', (e[0], e[1], e[2], e[4]))


def plants(f):
    """[(name, planted frame, kind, planted object)]; kind: move / hp / remove / dup / other."""
    out = []
    for i, e in enumerate(f['E']):
        ch = [('x+1', 1, 1), ('y+1', 2, 1)]
        if e[4] != -1:
            ch.append(('hp+1', 4, 1))
            if e[4] != 0:
                ch.append(('hp-1', 4, -1))
        for name, j, dv in ch:
            g = copy.deepcopy(f)
            g['E'][i][j] += dv
            out.append(('body%d_%s' % (i, name), g, 'hp' if j == 4 else 'move', _obj(g['E'][i])))
        g = copy.deepcopy(f)
        g['E'].pop(i)
        out.append(('body%d_remove' % i, g, 'remove', _obj(e)))
        g = copy.deepcopy(f)
        g['E'].append(list(e))
        out.append(('body%d_dup' % i, g, 'dup', _obj(e)))
    for key in ('P', 'A'):
        for i, e in enumerate(f[key]):
            g = copy.deepcopy(f)
            g[key].pop(i)
            out.append(('%s%d_remove' % (key, i), g, 'remove', (key, tuple(e[:3]))))
            g = copy.deepcopy(f)
            g[key][i][1] += 1
            out.append(('%s%d_x+1' % (key, i), g, 'move', (key, tuple(g[key][i][:3]))))
            g = copy.deepcopy(f)
            g[key].append(list(e))
            out.append(('%s%d_dup' % (key, i), g, 'dup', (key, tuple(e[:3]))))
    src = next((e for e in f['E'] if e[3] != -1), f['E'][0] if f['E'] else None)
    if src is not None:
        g = copy.deepcopy(f)
        e = list(src)
        e[1] = e[1] + 3000 if e[1] < 9000 else e[1] - 3000
        e[3] = e[3] if e[3] != -1 else 26000000  # a unit, not a tower
        g['E'].append(e)
        out.append(('add_unit', g, 'other', None))
    for name, dv in (('el+1', 1), ('el-1', -1), ('el+1whole', 10000), ('el-1whole', -10000)):
        g = copy.deepcopy(f)
        g['el'] += dv
        out.append((name, g, 'other', None))
    if f.get('hand') and len(f['hand']) > 1 and f['hand'][0] != f['hand'][1]:
        g = copy.deepcopy(f)
        g['hand'][0], g['hand'][1] = g['hand'][1], g['hand'][0]
        out.append(('hand_swap', g, 'other', None))
    return out


def targets(frames, me, an, by):
    cls = an['cls']
    ts = sorted(cls)
    out = collections.OrderedDict((t, cls[t]) for t in ts if cls[t].startswith('torn'))
    ok = [t for t in ts if cls[t] != 'div' and t not in out]
    pick = lambda pred: [t for t in ok if pred(t)][:REP]  # noqa: E731
    for t in pick(lambda t: any(e[3] == -1 and e[5] not in (12, 13) for e in frames[t]['E'])):
        out.setdefault(t, 'KIND_T')
    for t in pick(lambda t: any(e[4] == -1 for e in frames[t]['E'])):
        out.setdefault(t, 'placeholder')
    for t in pick(lambda t: len(L.repr_rows(by[t])) != len(by[t]['E']) or
                  any(r[1] != e[1] for r, e in zip(L.repr_rows(by[t]), by[t]['E']))):
        out.setdefault(t, 'REPR')
    ex = [t for t in ok if cls[t] == 'exact']
    for t in random.Random(7).sample(ex, min(REP, len(ex))):
        out.setdefault(t, 'exact')
    return out


def version(label, eid, ot, ot1):
    """An entity's version under a provenance label, recomputed from the raw sim rows (None: not recomputable here)."""
    a, b = L.ents_of(ot), L.ents_of(ot1) if ot1 is not None else {}
    if label == 't':
        return a.get(eid)
    if label == 't1':
        return b.get(eid)
    if eid not in a:
        return None
    k, va = a[eid]
    if label == 'dead_at_t':
        return k, va[:3] + (0,)
    if label == 'impact':
        e = next((e for e in L.repr_rows(ot) if e[0] == eid), None)
        return (k, (va[0], e[9], e[10])) if e is not None and len(e) > 10 else None
    if label in ('pos_t_hp_t1', 'pos_t1_hp_t') and eid in b:
        vb = b[eid][1]
        return (k, va[:3] + vb[3:]) if label == 'pos_t_hp_t1' else (k, vb[:3] + va[3:])
    return None


def witness(kind, obj, base, now, bprov, nprov, ot, ot1):
    """The legal_* label of a non-div planted outcome, or None (MISSED)."""
    if now in ('torn_snap', 'torn_cmd'):
        return 'legal_state'
    if not nprov or 'objects' not in nprov:
        return None
    bo = (bprov or {}).get('objects', {})
    dflt = {'exact': 't', 'torn_t1': 't1'}.get(base)
    absent = lambda d: {e for e, l in d.items() if l.startswith('absent')}  # noqa: E731
    if kind == 'remove':
        return 'legal_absent' if absent(nprov['objects']) - absent(bo) else None
    if kind in ('move', 'hp', 'dup'):
        for eid, lab in nprov['objects'].items():
            if lab == bo.get(eid, dflt):
                continue
            for l in lab.split('/'):
                v = version(l, eid, ot, ot1)
                if v is not None and (v == obj or (L.HP_PH and obj[0] in ('T', 'U') and obj[1][3] == -1 and
                                                   obj[0] == v[0] and obj[1][:3] == v[1][:3])):
                    return 'legal_version'
    return None


def run(plan, frames, me, an, obs, workdir):
    by = {o['t']: o for o in obs}
    ts = sorted(an['cls'])
    orig_snaps, orig_batch = bp_snap.snapshots, L.run_batch
    bp_snap.snapshots, L.run_batch = _memo_snaps(orig_snaps), _memo_batch(orig_batch)
    res = {'targets': collections.Counter(), 'plants': 0, 'caught': 0, 'legal': collections.Counter(), 'legal_list': [],
           'missed': [], 'window_mismatch': []}
    try:
        def classify(fr, t):
            k = ts.index(t)
            lo, hi = ts[max(0, k - W)], ts[min(len(ts) - 1, k + W)]
            a = L.reclassify(plan, fr, me, L.analyse(obs, fr, me, lo, hi), obs, workdir)
            return a['cls'][t], a['prov'].get(t)
        for t, cat in targets(frames, me, an, by).items():
            base = an['cls'][t]
            if t not in by or classify(frames, t)[0] != base:
                res['window_mismatch'].append([t, base])
                continue
            res['targets'][cat] += 1
            bprov = an['prov'].get(t)
            for name, g, kind, obj in plants(frames[t]):
                fr = dict(frames)
                fr[t] = g
                now, nprov = classify(fr, t)
                res['plants'] += 1
                if now == 'div':
                    res['caught'] += 1
                    continue
                r = L.canon_live(g, me)
                why = None
                for lab, o in (('legal_t', by.get(t)), ('legal_t1', by.get(t + 1))):
                    if o is not None and why is None:
                        s = L.sim_canon(o, me)
                        if not diff(L.fill_placeholder(r, s) if L.HP_PH else r, s):
                            why = lab
                why = why or witness(kind, obj, base, now, bprov, nprov, by[t], by.get(t + 1))
                if why is None:
                    res['missed'].append([t, cat, base, name, now, bprov, nprov])
                else:
                    res['legal'][why] += 1
                    res['legal_list'].append([t, cat, base, name, now, why])
    finally:
        bp_snap.snapshots, L.run_batch = orig_snaps, orig_batch
    res['targets'], res['legal'] = dict(res['targets']), dict(res['legal'])
    return res
