"""MEM-FULL step 1: how often does match_memory.E_MAX = 128 truncate? Read-only.

    python -I scratchpad/gauntlet/L74/memory/full/count_events.py tables MEMORY_NPZ [DATASET_NPZ]   # pro / any memory_tables file
    python -I scratchpad/gauntlet/L74/memory/full/count_events.py counts COUNTS.json [label]        # per-table lists (live / SIM)

Per table (one match, one side; events = every visible event of the match, MatchMemory.table): the count distribution, the
share over 128, the max; by type and phase; at the match end the events a 128 window has DROPPED (the oldest), by type and
phase; with a dataset (decision rows: tick + row_tab) the share of DECISIONS whose visible events exceed 128."""
import json
import sys

import numpy as np

E = 128
DOUBLE_T, OT_T = 2400, 3600
TYPES = ('play', 'ability', 'tower_damage', 'tower_fall')


def pct(a):
    a = np.asarray(a)
    return {p: int(np.percentile(a, p)) for p in (50, 90, 95, 99)} | {'mean': round(float(a.mean()), 1), 'max': int(a.max())}


def phase(t):
    t = np.asarray(t)
    return np.where(t < DOUBLE_T, 0, np.where(t < OT_T, 1, 2))


def report(label, n, typ=None, ph=None, mine=None, off=None, dropped=None):
    out = dict(label=label, tables=int(len(n)), events=pct(n), over_128=round(float((n > E).mean()), 4),
               over_192=round(float((n > 192).mean()), 4), over_256=round(float((n > 256).mean()), 4))
    if typ is not None:
        out['by_type_mean'] = {k: round(float((typ == i).sum() / len(n)), 1) for i, k in enumerate(TYPES)}
        out['by_phase_mean'] = {k: round(float((ph == i).sum() / len(n)), 1) for i, k in enumerate(('1x', '2x', 'ot'))}
        out['own_share'] = round(float(mine.mean()), 3)
    if dropped is not None:
        out['dropped_at_end'] = dropped
    return out


def tables(path, dataset=None):
    z = np.load(path, allow_pickle=False)
    off = z['tab_off'].astype(np.int64)
    vals, tick, vis = z['tab_vals'], z['tab_tick'].astype(np.int64), z['tab_vis'].astype(np.int64)
    typ = np.argmax(vals[:, :4], 1)
    mine = vals[:, 4] == 1
    del vals
    n = np.diff(off)
    keep = n > 0
    ph = phase(tick)
    # dropped at the end: the oldest n - 128 events of each table (tables are chronological: MatchMemory.events order)
    tab_of = np.repeat(np.arange(len(n)), n)
    pos = np.arange(len(tick)) - off[tab_of]
    dr = pos < (n[tab_of] - E)
    dropped = dict(events=int(dr.sum()), share_of_all=round(float(dr.mean()), 4),
                   by_type={k: int((dr & (typ == i)).sum()) for i, k in enumerate(TYPES)},
                   by_phase={k: int((dr & (ph == i)).sum()) for i, k in enumerate(('1x', '2x', 'ot'))},
                   own=int((dr & mine).sum()), opp=int((dr & ~mine).sum()))
    out = report(str(path).replace('\\', '/').split('/')[-1], n, typ, ph, mine, off, dropped)
    out['empty_tables'] = int((~keep).sum())
    # when does a match pass 128: the tick of its 129th event (seconds), by phase
    t129 = tick[off[:-1][n > E] + E]
    out['tick_of_event_129_s'] = pct(t129 / 20) if len(t129) else None
    out['event_129_phase'] = {k: int((phase(t129) == i).sum()) for i, k in enumerate(('1x', '2x', 'ot'))}
    if dataset:
        d = np.load(dataset, allow_pickle=False)
        rt = z['row_tab'].astype(np.int64)
        rt_ok = rt >= 0
        t = d['tick'].astype(np.int64)[rt_ok]
        rt = rt[rt_ok]
        key = tab_of * (1 << 32) + vis
        order = np.sort(key)
        visible = np.searchsorted(order, rt * (1 << 32) + t, 'right') - np.searchsorted(order, rt * (1 << 32), 'left')
        out['decisions'] = dict(rows=int(len(t)), visible=pct(visible), over_128=round(float((visible > E).mean()), 4),
                                over_128_by_phase={k: round(float((visible[phase(t) == i] > E).mean()), 4)
                                                   for i, k in enumerate(('1x', '2x', 'ot'))},
                                dropped_mean_when_over=round(float((visible[visible > E] - E).mean()), 1)
                                if (visible > E).any() else 0)
    return out


def counts(path, label=None):
    j = json.loads(open(path, encoding='utf-8').read())
    n = np.array([r['n'] for r in j], np.int64)
    out = report(label or path, n)
    for k in ('play', 'ability', 'tower_damage', 'tower_fall', '1x', '2x', 'ot', 'dropped', 'dropped_1x', 'dropped_2x',
              'dropped_ot', 'dropped_own', 'dropped_opp', 'dec', 'dec_over'):
        if j and k in j[0]:
            out[k + ('_sum' if k.startswith('d') else '_mean')] = (int(sum(r[k] for r in j)) if k.startswith('d') else
                                                                  round(float(np.mean([r[k] for r in j])), 1))
    if j and 'dec' in j[0]:
        out['decision_over_128_share'] = round(sum(r['dec_over'] for r in j) / max(1, sum(r['dec'] for r in j)), 4)
    t129 = [r['t129'] for r in j if r.get('t129') is not None]
    out['tick_of_event_129_s'] = pct(np.array(t129) / 20) if t129 else None
    return out


if __name__ == '__main__':
    a = sys.argv[1:]
    print(json.dumps(tables(*a[1:]) if a[0] == 'tables' else counts(*a[1:]), indent=1))
