"""A2c-M comparator rule SME_MECH_CROSS: an isolated div frame read inside step t+1 with a body at its t point already
carrying its t+1 hp (or at its t+1 point still at its t hp). torn_mixed accepts an object only as a whole t or t+1
tuple; a read between the game's per-entity updates can show a body hit by an attacker updated earlier in the step
before its own move (192935@382: our Knight at its t point with the Mega Knight's 429 already taken; every other object
at t, the X-Bow bolt removed; the next frames exact). crforge's in-step states (SnapRun) cannot show this: its
component passes move every body before any attack.
SME-HARDEN (sound form, sme_live.two_line_read cross=True): a bijection between the recorded objects and the entities of
sim t / t+1 (every class, multiplicity included); each entity shown at its t or t+1 tuple or, for a body present at both
lines, at the (position of t, hp of t+1) / (position of t+1, hp of t) cross, or absent only where it is absent from t or
t+1; our whole player state t's or t+1's. Planted checks: mech_torn_test.py, plant_suite.py."""
import collections
from sme_live import two_line_read


def cross_ok(f, ot, ot1, me):
    """The provenance of a sound crossed read, or None. Called on frames torn_mixed rejected, so a match uses a cross."""
    return two_line_read(f, ot, ot1, me, cross=True)


def reclass(an, obs, frames, me):
    cls, prov = dict(an['cls']), dict(an.get('prov', {}))
    ts = sorted(cls)
    by = {o['t']: o for o in obs}
    for i, t in enumerate(ts):
        if cls[t] != 'div' or t + 1 not in by or t not in by:
            continue
        if any(cls[ts[j]] == 'div' for j in (i - 1, i + 1) if 0 <= j < len(ts)):
            continue
        p = cross_ok(frames[t], by[t], by[t + 1], me)
        if p:
            cls[t], prov[t] = 'torn_cross', p
    first = next((t for t in ts if cls[t] == 'div'), None)
    return dict(an, cls=cls, prov=prov, first=first, counts=dict(collections.Counter(cls.values())))
