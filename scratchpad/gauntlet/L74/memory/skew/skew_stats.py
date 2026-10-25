"""Plan A S2 (memory parity), the missing gate: per-field memory distributions SIM vs pro (vs live), and the SIM perspective
check (lead 10-25). Read-only.

    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/memory/skew/skew_stats.py DUMP_DIR [DUMP_DIR ...] > skew_stats.out

DUMP_DIR = skew_worker.py pickles (one per SIM match: the learner's MatchMemory, its table, env.public_plays = truth).
Pro = icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz (the S3 training tables), a seeded sample of tables + rows.
Live = scratchpad/gauntlet/L74/memory/s1c/live_tables.npz when present (same table format)."""
from __future__ import annotations

import json
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(REPO))
from pipeline import match_memory as MM  # noqa: E402
from pipeline.dataset_gen import FORM_PAD, card_key, checkpoint_gid  # noqa: E402

PRO = REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz'
DATA = REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5.npz'
LIVE = REPO / 'scratchpad/gauntlet/L74/memory/s1c/live_tables.npz'
C = MM._COL
ICE = ('x-bow', 'tesla', 'ice-wizard', 'tornado', 'rocket', 'knight', 'the-log', 'skeletons')


def col(v, k):
    return v[:, C[k]]


def table_stats(tab, gid, end=None):
    """Per-match event stats of one table (TABLE_KEYS). end = match length in ticks (default: last event tick)."""
    v, tick, card = tab['vals'], tab['tick'].astype(np.int64), tab['card'].astype(np.int64)
    if not len(tick):
        return None
    mins = max((end if end is not None else int(tick.max())) * MM.TICK_S / 60, 0.5)
    play, ab, td, tf, mine = (col(v, 'is_play') == 1), col(v, 'is_ability') == 1, col(v, 'is_tower_damage') == 1, \
        col(v, 'is_tower_fall') == 1, col(v, 'mine') == 1
    own, opp = play & mine, play & ~mine
    xb, rk = own & (card == gid['x-bow']), own & (card == gid['rocket'])
    oxb = opp & (card == gid['x-bow'])
    f = tab['form'].astype(np.int64)
    s = dict(mins=mins, own_pm=own.sum() / mins, opp_pm=opp.sum() / mins, abil_pm=ab.sum() / mins,
             own_ab_pm=(ab & mine).sum() / mins, opp_ab_pm=(ab & ~mine).sum() / mins,
             tdmg_mine_pm=(td & mine).sum() / mins, tdmg_opp_pm=(td & ~mine).sum() / mins,
             tfall_mine=(tf & mine).sum(), tfall_opp=(tf & ~mine).sum(),
             mine_share=own.sum() / max(play.sum(), 1),
             own_xy=col(v, 'xy_known')[own].mean() if own.any() else np.nan,
             opp_xy=col(v, 'xy_known')[opp].mean() if opp.any() else np.nan,
             own_y_ownhalf=(col(v, 'y')[own & (col(v, 'xy_known') == 1)] > .5).mean() if own.any() else np.nan,
             opp_y_theirhalf=(col(v, 'y')[opp & (col(v, 'xy_known') == 1)] < .5).mean() if opp.any() else np.nan,
             own_y_mean=col(v, 'y')[own].mean() if own.any() else np.nan,
             opp_y_mean=col(v, 'y')[opp].mean() if opp.any() else np.nan,
             own_el_known=col(v, 'elixir_known')[own].mean() if own.any() else np.nan,
             own_el=col(v, 'elixir_10')[own].mean() * 10 if own.any() else np.nan,
             margin_known=col(v, 'margin_known')[play].mean() if play.any() else np.nan,
             own_form_evo=(f[own] == 1).mean() if own.any() else np.nan, own_form_hero=(f[own] == 2).mean() if own.any() else np.nan,
             own_form_pad=(f[own] == FORM_PAD).mean() if own.any() else np.nan,
             opp_form_evo=(f[opp] == 1).mean() if opp.any() else np.nan, opp_form_hero=(f[opp] == 2).mean() if opp.any() else np.nan,
             opp_card0=(card[opp] == 0).mean() if opp.any() else np.nan, own_card0=(card[own] == 0).mean() if own.any() else np.nan,
             out_tower_known=col(v, 'out_tower_known')[play].mean() if play.any() else np.nan,
             out_value_known=col(v, 'out_value_known')[play].mean() if play.any() else np.nan,
             own_value=col(v, 'out_value_10')[own].mean() * 10 if own.any() else np.nan,
             opp_value=col(v, 'out_value_10')[opp].mean() * 10 if opp.any() else np.nan,
             own_enemy_lost=col(v, 'out_enemy_lost')[own].mean() if own.any() else np.nan,
             own_own_lost=col(v, 'out_own_lost')[own].mean() if own.any() else np.nan,
             tdmg_lost=col(v, 'tower_lost')[td].mean() if td.any() else np.nan,
             xb_pm=xb.sum() / mins, xb_reach=col(v, 'xb_reach')[xb].mean() if xb.any() else np.nan,
             xb_locked=col(v, 'xb_locked')[xb & (col(v, 'xb_done') == 1)].mean() if (xb & (col(v, 'xb_done') == 1)).any() else np.nan,
             xb_answered=col(v, 'xb_answered')[xb & (col(v, 'xb_answer_done') == 1)].mean()
             if (xb & (col(v, 'xb_answer_done') == 1)).any() else np.nan,
             is_answer_pm=(col(v, 'is_xb_answer') == 1).sum() / mins, opp_xb_pm=oxb.sum() / mins,
             rk_pm=rk.sum() / mins, rk_tower=col(v, 'rk_tower')[rk].mean() if rk.any() else np.nan,
             rk_combo=col(v, 'rk_combo')[rk].mean() if rk.any() else np.nan,
             n_events=len(tick), last_t=int(tick.max()), late=float((tab['vis'] > tab['tick'] + 1).mean()))
    return s


def summarise(rows, label):
    keys = rows[0].keys()
    out = {}
    for k in keys:
        x = np.array([r[k] for r in rows], float)
        x = x[np.isfinite(x)]
        out[k] = (float(x.mean()) if len(x) else np.nan, float(np.median(x)) if len(x) else np.nan, len(x))
    return out


def pro_tables(n, rng, only_icebow=False):
    z = np.load(PRO, allow_pickle=False)
    meta = json.loads(str(z['meta']))
    packed = {k[4:]: z[k] for k in z.files if k.startswith('tab_')}
    gid = checkpoint_gid(meta['card_vocab'])
    ntab = len(packed['off']) - 1
    pick = rng.choice(ntab, size=min(n, ntab), replace=False)
    tabs = [MM.unpack(packed, int(j)) for j in pick]
    if only_icebow:
        ice = {gid[k] for k in ICE}
        tabs = [t for t in tabs if ice <= set(t['card'][(t['vals'][:, C['mine']] == 1) & (t['vals'][:, C['is_play']] == 1)].tolist())]
    return tabs, gid, packed, z['row_tab'], meta


def sim_dumps(dirs):
    recs = []
    for d in dirs:
        for p in sorted(Path(d).glob('*.pkl')):
            with open(p, 'rb') as fh:
                recs.append(pickle.load(fh))
    return recs


def perspective(rec):
    """SIM: memory plays vs env.public_plays (truth) for one match."""
    side, gid = rec['side'], rec['gid']
    truth = [dict(p, slug=card_key(str(p['card']))) for p in rec['truth']]
    mem = [e for e in rec['plays'] if e['type'] == 'play']
    own_t = [p for p in truth if int(p['side']) == side]
    opp_t = [p for p in truth if int(p['side']) != side]
    own_m = [e for e in mem if e['mine']]
    opp_m = [e for e in mem if not e['mine']]
    deck = set(rec['deck'].tolist()) if rec.get('deck') is not None else set()
    r = dict(own_truth=len(own_t), own_mem=len(own_m), opp_truth=len(opp_t), opp_mem=len(opp_m),
             own_not_deck=sum(gid.get(e['card'], 0) not in deck for e in own_m),
             own_exact=0, opp_found=0, opp_lag=[], opp_xy_err=[], opp_card_miss=Counter(), opp_extra=Counter())
    from pipeline.obs_contract import _engine_xy
    keys = Counter((e['tick'], e['card'], e['xy']) for e in own_m)
    for p in own_t:
        k = (int(p['tick']), p['slug'], _engine_xy(float(p['x']), float(p['y']), side == 1))
        if keys[k] > 0:
            keys[k] -= 1
            r['own_exact'] += 1
    used = set()
    for p in opp_t:
        tp = int(p['tick'])
        cands = [(e['tick'] - tp, i) for i, e in enumerate(opp_m) if i not in used and e['card'] == p['slug'] and 0 <= e['tick'] - tp <= 60]
        if cands:
            lag, i = min(cands)
            used.add(i)
            r['opp_found'] += 1
            r['opp_lag'].append(lag)
            if opp_m[i]['xy'] is not None:
                txy = _engine_xy(float(p['x']), float(p['y']), side == 1)
                r['opp_xy_err'].append(MM._tiles(txy, opp_m[i]['xy']))
        else:
            r['opp_card_miss'][p['slug']] += 1
    for i, e in enumerate(opp_m):
        if i not in used:
            r['opp_extra'][e['card']] += 1
    row = rec['row']
    r['crowns_for'], r['crowns_against'] = row['crowns_for'], row['crowns_against']
    tf = [e for e in rec['tower_ev'] if e['type'] == 'tower_fall']
    r['falls_opp'] = sum(not e['mine'] for e in tf)
    r['falls_mine'] = sum(e['mine'] for e in tf)
    r['king_opp_fell'] = any(not e['mine'] and e['tower'] == 3 for e in tf)
    r['king_mine_fell'] = any(e['mine'] and e['tower'] == 0 for e in tf)
    hp0 = rec['hp'][0] if rec['hp'] else None
    r['hp_first'] = hp0
    r['hp_last'] = rec['hp'][-1] if rec['hp'] else None
    r['abil_mem'] = sum(e['type'] == 'ability' for e in rec['plays'])
    r['abil_truth'] = sum(int(e['side']) == side for e in rec['abil'])
    r['first_tick'] = rec['t'][0] if rec['t'] else None
    r['dec_gap'] = float(np.median(np.diff(rec['t']))) if len(rec['t']) > 1 else None
    return r


def fmt(d):
    return f'{d[0]:8.3f} (med {d[1]:7.3f}, n {d[2]})'


def main():
    dirs = sys.argv[1:]
    rng = np.random.default_rng(0)
    recs = sim_dumps(dirs)
    print(f'SIM dumps: {len(recs)} matches from {dirs}')
    tabs, gid, packed, row_tab, meta = pro_tables(4000, rng)
    tabs_ice, *_ = pro_tables(29322, np.random.default_rng(1), only_icebow=True)
    print(f'pro: {len(tabs)} random tables; {len(tabs_ice)} icebow-deck sides (own plays cover the 8 icebow cards)')
    if recs and any(r['gid'] != gid for r in recs):
        print('!! SIM gid != pro gid (card ids would not line up)')
    groups = {'pro_all': [table_stats(t, gid) for t in tabs], 'pro_icebow': [table_stats(t, gid) for t in tabs_ice]}
    if LIVE.is_file():
        lz = np.load(LIVE, allow_pickle=False)
        print('live tables file keys:', lz.files[:12])
        lp = {k[4:]: lz[k] for k in lz.files if k.startswith('tab_')}
        if 'off' in lp:
            groups['live'] = [table_stats(MM.unpack(lp, j), gid) for j in range(len(lp['off']) - 1)]
    for mode in sorted({r['mode'] for r in recs}):
        groups[f'sim_{mode}'] = [table_stats(r['table'], gid, end=r['t'][-1]) for r in recs if r['mode'] == mode]
    groups = {k: [s for s in v if s] for k, v in groups.items()}
    S = {k: summarise(v, k) for k, v in groups.items() if v}
    names = list(S)
    print('\n== per-match event stats: mean (median, n matches) ==')
    print(f'{"field":18s}' + ''.join(f'{n:>34s}' for n in names))
    for k in S[names[0]]:
        print(f'{k:18s}' + ''.join(f'{fmt(S[n][k]):>34s}' for n in names))

    # row-level summary features at decision ticks
    print('\n== decision-row mem_summary: mean / share nonzero ==')
    z = np.load(DATA, allow_pickle=False, mmap_mode=None)
    tick_all, deck_all = z['tick'], z['deck_card']
    ice = np.sort([gid[k] for k in ICE])
    rows = rng.choice(np.flatnonzero(row_tab >= 0), size=20000, replace=False)
    pro_s = MM.rows_features(packed, row_tab, tick_all, deck_all, rows)['mem_summary']
    is_ice = np.all(np.sort(deck_all[rows].astype(np.int64), 1) == ice, 1)
    sims = {}
    for mode in sorted({r['mode'] for r in recs}):
        ss = [MM.features_at(r['table'], r['t'], r['deck'])['mem_summary'] for r in recs if r['mode'] == mode]
        sims[mode] = np.concatenate(ss) if ss else np.zeros((0, MM.S))
    sf = list(MM.SUMMARY_FIELDS) + [f'c{i}_{k}' for i in range(MM.DECK_N) for k in MM.CARD_FIELDS]
    cols = [('pro', pro_s), ('pro_ice', pro_s[is_ice])] + [(f'sim_{m}', v) for m, v in sims.items()]
    print(f'{"field":24s}' + ''.join(f'{n:>22s}' for n, _ in cols))
    for i, k in enumerate(sf):
        print(f'{k:24s}' + ''.join(f'{v[:, i].mean():10.3f} / {(v[:, i] != 0).mean():5.2f}   ' if len(v) else f'{"-":>22s}' for _, v in cols))
    print(f'rows: pro {len(pro_s)}, pro icebow {int(is_ice.sum())}, ' + ', '.join(f'sim_{m} {len(v)}' for m, v in sims.items()))
    # mem_ev: number of visible events per row
    pro_n = MM.rows_features(packed, row_tab, tick_all, deck_all, rows[:5000])['mem_mask'].sum(1)
    print(f'visible events / row: pro mean {pro_n.mean():.1f} (row tick mean {tick_all[rows[:5000]].mean():.0f}); ' + ', '.join(
        f'sim_{m} mean {np.mean([MM.features_at(r["table"], r["t"], r["deck"])["mem_mask"].sum(1).mean() for r in recs if r["mode"] == m]):.1f}'
        for m in sims))
    print(f'row tick: pro mean {tick_all[rows].mean():.0f} median {np.median(tick_all[rows]):.0f} max {tick_all[rows].max()}; ' + ', '.join(
        f'sim_{m} mean {np.mean(np.concatenate([r["t"] for r in recs if r["mode"] == m])):.0f}' for m in sims))

    print('\n== SIM perspective check (memory vs env.public_plays) ==')
    P = [perspective(r) for r in recs]
    if P:
        tot = Counter()
        for p in P:
            for k in ('own_truth', 'own_mem', 'own_exact', 'own_not_deck', 'opp_truth', 'opp_mem', 'opp_found', 'abil_mem', 'abil_truth'):
                tot[k] += p[k]
        print(dict(tot))
        lag = np.concatenate([p['opp_lag'] for p in P]) if P else []
        xe = np.concatenate([p['opp_xy_err'] for p in P]) if P else []
        print(f'opp detection lag (ticks): mean {np.mean(lag):.1f} median {np.median(lag):.0f} p90 {np.percentile(lag, 90):.0f}; '
              f'opp xy error (tiles): median {np.median(xe):.2f} p90 {np.percentile(xe, 90):.2f}')
        miss, extra = Counter(), Counter()
        for p in P:
            miss.update(p['opp_card_miss'])
            extra.update(p['opp_extra'])
        print('opp truth plays never detected (card: n):', miss.most_common(15))
        print('opp memory plays with no truth play (card: n):', extra.most_common(15))
        print('crowns_for vs memory opp tower falls:', Counter((p['crowns_for'], p['falls_opp'], p['king_opp_fell']) for p in P).most_common(8))
        print('crowns_against vs memory own tower falls:', Counter((p['crowns_against'], p['falls_mine'], p['king_mine_fell']) for p in P).most_common(8))
        print('first decision tick:', Counter(p['first_tick'] for p in P).most_common(5), 'median decision gap:', Counter(p['dec_gap'] for p in P).most_common(5))
        print('first sample HP:', Counter(tuple(round(h, 2) if h is not None else None for h in p['hp_first']) for p in P).most_common(3))


if __name__ == '__main__':
    main()
