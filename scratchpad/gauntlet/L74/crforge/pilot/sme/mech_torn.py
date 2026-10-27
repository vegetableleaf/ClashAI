"""A2c-M comparator rule SME_MECH_CROSS: an isolated div frame read inside step t+1 with a body at its t point already
carrying its t+1 hp (or at its t+1 point still at its t hp). torn_mixed accepts an object only as a whole t or t+1
tuple; a read between the game's per-entity updates can show a body hit by an attacker updated earlier in the step
before its own move (192935@382: our Knight at its t point with the Mega Knight's 429 already taken; every other object
at t, the X-Bow bolt removed; the next frames exact). crforge's in-step states (SnapRun) cannot show this: its
component passes move every body before any attack. Exact: each recorded object must equal a sim t / t+1 tuple or the
(position of t, hp of t+1) / (position of t+1, hp of t) cross of ONE sim body present at both lines; our elixir and hand
as torn_mixed. Planted checks: mech_torn_test.py."""
import collections
from sme_live import canon_live, sim_canon, repr_rows


def cross_ok(f, ot, ot1, me):
    r, a, b = canon_live(f, me), sim_canon(ot, me), sim_canon(ot1, me)
    ra = {e[0]: e for e in repr_rows(ot) if e[1] in 'TC'}
    rb = {e[0]: e for e in repr_rows(ot1) if e[1] in 'TC'}
    cross = collections.defaultdict(set)
    for i in ra.keys() & rb.keys():
        k = 'T' if ra[i][1] == 'T' else 'U'
        cross[k].add((ra[i][3], ra[i][4], ra[i][5], rb[i][6]))
        cross[k].add((rb[i][3], rb[i][4], rb[i][5], ra[i][6]))
    used = 0
    for k in 'TUPA':
        for x in r[k]:
            if x in a[k] or x in b[k]:
                continue
            if x in cross[k]:
                used += 1
                continue
            return False
    if not used:
        return False  # a frame torn_mixed would take is not this rule's
    return all(r[k] in (a.get(k), b.get(k)) or r[k][0] in (a.get(k, (None,))[0], b.get(k, (None,))[0])
               for k in r if k.startswith('S'))


def reclass(an, obs, frames, me):
    cls = dict(an['cls'])
    ts = sorted(cls)
    by = {o['t']: o for o in obs}
    for i, t in enumerate(ts):
        if cls[t] != 'div' or t + 1 not in by or t not in by:
            continue
        if any(cls[ts[j]] == 'div' for j in (i - 1, i + 1) if 0 <= j < len(ts)):
            continue
        if cross_ok(frames[t], by[t], by[t + 1], me):
            cls[t] = 'torn_cross'
    first = next((t for t in ts if cls[t] == 'div'), None)
    return dict(an, cls=cls, first=first, counts=dict(collections.Counter(cls.values())))
