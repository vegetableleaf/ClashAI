"""Replay chosen fights with fights.py's own path and keep every (tick, live bodies, sim bodies) row (diagnosis only).
  capture(match_stem, pred) -> [(fight dict, anchor event, rows)]"""
import os, sys
from collections import defaultdict, Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('PARITY_SIM_PATH', 'C:/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/c11d06f6-d4d0-44d7-aa99-0f9ff1579dd8/scratchpad/rt35')
import importlib
F = importlib.import_module("scratchpad.gauntlet.L74.parity." + os.environ.get("DIAG_FIGHTS", "fights"))
from scratchpad.gauntlet.L74.parity.core import load_catalog, ps

_ENG = None


def engine():
    global _ENG
    if _ENG is None:
        _ENG = F.Engine()
    return _ENG


def setup(stem):
    catalog, by_name = load_catalog()
    m, why = F.read_match(str(ps.LIVE/(stem+'.jsonl')))
    assert m, why
    events, delay = F.deployments(m, catalog)
    fights = F.cut(m, events, 240)
    eng = engine()
    levels, seen = {}, Counter()
    for t, bodies in m['frames']:          # = run_match
        for bd in bodies:
            c = catalog.get(bd['card_id'])
            if bd['tower'] or c is None or (bd['side'], c['display_name']) in levels or F.form_of(bd['card_id'], c) == 1:
                continue
            lv = eng.level(c['display_name'], bd['max_hp'])
            if lv:
                levels[bd['side'], c['display_name']] = lv; seen[bd['side'], lv] += 1
    for s_ in (0, 1):
        mode = [lv for (ss, lv), _ in seen.most_common() if ss == s_]
        levels[s_, '*'] = mode[0] if mode else 15
    if hasattr(F, "spell_levels"):
        levels.update(F.spell_levels(m, events, eng, catalog))
    t0b = m['frames'][0][1]; tw = []
    for s_ in (0, 1):
        k = next((b['max_hp'] for b in t0b if b['tower'] and b['side'] == s_ and b['id'].endswith('K')), None)
        p = next((b['max_hp'] for b in t0b if b['tower'] and b['side'] == s_ and not b['id'].endswith('K')), None)
        tw.append(eng.tower_level(k, p) or levels[s_, '*'])
    return dict(m=m, events=events, fights=fights, catalog=catalog, by_name=by_name, levels=levels, tw=tw, delay=delay)


def capture(stem, pred, ctx=None):
    ctx = ctx or setup(stem)
    eng = engine(); out = []
    keep = {}
    orig = F.measure

    def spy(rows, setup_, flags, catalog, stamp):
        keep['rows'] = rows; keep['setup'] = setup_
        return orig(rows, setup_, flags, catalog, stamp)
    F.measure = spy
    try:
        for f in ctx['fights']:
            a = ctx['events'][f['anchor']]
            if not pred(f, a):
                continue
            keep.clear()
            r = F.run_fight(eng, ctx['m'], ctx['events'], f, ctx['catalog'], ctx['by_name'], ctx['levels'], ctx['tw'], None)
            out.append((f, a, keep.get('rows'), keep.get('setup'), r))
    finally:
        F.measure = orig
    return out, ctx
