"""V1-LIVEROWS step 1: live logs -> driven-corpus records for the OPPONENT seat's slot rows (plan1026 Pillar 2 step 3).

    python -I live_records.py --logs DIR --select select.json --out OUT [--block train|calibration] [--workers N] [--limit N]
      -> OUT/<block>/c<chunk>/replay_<stem>.json  (dataset_gen corpus layout)  +  OUT/<block>/index.jsonl (one line per log)

Built from opp_model/o1_records.py (its helpers are imported unchanged); what differs, and why:
  * frames: EVERY reader frame (FRAME_EVERY 1; duplicate ticks dropped), gzip logs accepted. The reader's frame parity is NOT
    fixed within a match (measured: 35-83 gaps of 1 / 3 ticks per match), so no single phase shift puts the 10-tick grid on
    frames. Instead each grid tick g (g % 10 == 0, the raw tick = the engine clock: 2x elixir starts at raw 2400-2403) gets a
    frame: the frame AT g, else a copy of the newest frame at g-1 / g-2 relabelled g ('snapped', <= 2 ticks stale), else none
    (a grid hole). Counts per log: grid_exact / grid_snapped / grid_hole.
  * opponent act tick = first public sighting - LAG (20: crforge's command delay; our seat's decision -> sighting is measured in
    selfcheck.py), minus 1 more when that lands ON a grid tick (a play row on a grid tick would hide its slot row: the
    HF rows never have one, rows_to_npz's grid = wait rows).
  * opponent own elixir (frames' elixir[opp]) = the live public counter (opp_elixir_est) minus the cost of every opponent play
    already acted but not yet sighted (act < t < sighting): the counter charges a play at its sighting, the player paid at act.
  * opponent hand: the public cycle rule (o1_records.infer_hands) from the 5th detected play on; plays 1-4 get the FITTED deal
    H0 = {p1..p4} (consistent with every later hand; Q = the other 4 in deck order) and `hand_known_from` = act(5) so their rows
    are hand_inferred (no card label, slot labels kept), as the HF rows' fitted deal.
  * deck: 8 seen -> 'seen8'; else the battle log's deck when this log maps to one (calibration block, 10-26 on) -> 'battlelog';
    else 7 seen -> the HF library completion P(8th | 7 seen) when its top card holds >= 60% of >= 3 matching sides -> 'hf'; else
    no opponent rows. The battle-log deck also CHECKS seen8 / hf completions (deck_check.py).
  * tags in rec['live']: block, band (L / M / R), Mark, our / their tower level (princess max HP 4424 = 15, 4858 = 16), arch.
OUR seat: as o1_records (logged hands, plays at the decision tick of each confirmed tap) -- never imitation rows; they feed the
self-check (selfcheck.py)."""
from __future__ import annotations

import argparse
import bisect
import gzip
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[2]
ROOT = L74.parents[2]
sys.path[:0] = [str(L74 / 'opp_model'), str(L74 / 'opp_model/humanlike'), str(ROOT)]

LAG = 20
GRID = 10
SNAP = 2
SPLIT = json.loads((HERE.parent / 'live_split.json').read_text())
TOWER_LVL = {4424: 15, 4858: 16}


def block_of(stem):
    s = stem[len('live_play_'):]
    return 'train' if s < SPLIT['train_before'] else 'sealed' if s >= SPLIT['sealed_from'] else 'calibration'


def _open(p):
    return gzip.open(p, 'rb') if str(p).endswith('.gz') else open(p, 'rb')


def read_log(path, LT, R):
    """o1_records.read_log with every frame kept (distinct ticks), gzip aware, plus the decision raw ticks."""
    frames, dec, taps, conf, side, last = [], [], [], [], None, -10 ** 9
    with _open(path) as fh:
        for raw in fh:
            if raw.startswith(b'{"event": "frame"'):
                j = LT.loads(raw)
                t = int(j['tick'])
                if t <= last:
                    continue
                last = t
                side = int(j['my_side'])
                st = j.get('ents_state') or []
                ents = []
                for i, e in enumerate(j['ents']):
                    s_, x, y, cid, hp, mx, kind, addr = e
                    ents.append(dict(side=s_, x=x, y=y, card_id=cid, hp=hp, max_hp=mx, kind=kind, address=addr,
                                     category=st[i][3] if i < len(st) else None))
                fr = R.dedupe_hero_bodies(dict(game_tick=t, entities=ents))
                frames.append(dict(tick=t, ents=fr['entities'], own_el=float(j.get('elixir') or 0.0),
                                   opp_est=j.get('opp_elixir_est'), proj=j.get('proj') or [], fx=j.get('fx') or []))
            elif raw.startswith(b'{"event": "decision"'):
                j = LT.loads(raw)
                p = j.get('public') or {}
                if 'own_hand' in p:
                    dec.append(dict(tick=int(j['tick']), hand=[(h['name'], int(h.get('form') or 0), int(h['deck_index']))
                                                              for h in p['own_hand']]))
            elif raw.startswith(b'{"event": "play"'):
                j = LT.loads(raw)
                taps.append(dict(tick=int(j['tick']), name=j.get('name'), xy=j.get('xy')))
            elif raw.startswith(b'{"event": "confirmed"'):
                j = LT.loads(raw)
                conf.append(dict(tick=int(j.get('tick') or 0), name=j.get('name')))
    return side, frames, dec, taps, conf


_LIB = None


def hf_library():
    """{frozenset of 8 base keys: sides}: the bec5811a HF re-drive's usable sides (P2-SCORE's hf_ref file, 21,717 decks /
    150,458 sides) + the live census o1_records used (mix/decks_live_{train,eval}.json, live opponents up to 10-15)."""
    global _LIB
    if _LIB is None:
        import o1_records as R
        p = Path(os.environ.get('HF_DECKS', HERE / 'hf_decks.json'))
        _LIB = Counter({frozenset(d): n for d, n in json.loads(p.read_text())})
        for ks, _, wt in R.census():
            _LIB[frozenset(ks)] += wt
    return _LIB


def complete_hf(seen):
    w = Counter()
    for ks, n in hf_library().items():
        if seen <= ks and len(ks - seen) == 1:
            w[next(iter(ks - seen))] += n
    if not w:
        return None, 'hf_no_match', 0, 0.0
    k, v = w.most_common(1)[0]
    tot = sum(w.values())
    ok = v >= 0.6 * tot and tot >= 3
    return (k if ok else None), ('hf' if ok else 'hf_ambiguous'), tot, v / tot


def fitted_hands(seq, deck):
    """Plays 1-4: the fitted deal H0 = {p1..p4} -> [(hand keys before play j, next key)] or None when p1..p4 are not 4
    distinct deck cards. Consistent with the cycle rule's hand before play 5 (= deck - {p1..p4})."""
    if len(seq) < 4:
        return None
    p = [e['key'] for e in seq[:4]]
    if len(set(p)) != 4 or not set(p) <= set(deck):
        return None
    q = [c for c in deck if c not in p]
    return [([c for c in deck if c in set(p[j:]) | set(q[:j])], q[j]) for j in range(4)]


def build(job):
    """One log -> (record or None, index line). job: (path, select entry, battle-log deck keys or None)."""
    import live_table as LT
    import o1_records as R
    from pipeline.native_recording import tag_native_recording
    from pipeline.opp_elixir_count import card_cost
    from pipeline.public_observation import recording_observers
    path, m, bl_deck = job
    st = Counter()
    me, frames, dec, taps, conf = read_log(path, LT, R)
    info = dict(stem=m['stem'], block=m['block'], band=m['band'], mark=m['mark'], tro=m['tro'], res=m['res'])
    if me is None or len(frames) < 50 or not dec:
        st['skip_no_frames'] += 1
        return None, dict(info, stats=dict(st))
    opp = 1 - me
    # ---- native frames (every reader frame) + grid frames
    nfr, ids = [], {}
    for f in frames:
        nf, d = R.native_frame(f, ids)
        st['bodies_dropped_dup_id_or_unknown_card'] += d
        nf['elixir'] = [0.0, 0.0]
        nf['elixir'][me] = f['own_el']
        nf['elixir'][opp] = float(f['opp_est']) if f['opp_est'] is not None else 0.0
        nfr.append(nf)
    fticks = [f['tick'] for f in nfr]
    have = set(fticks)
    grid_add = []
    for g in range((fticks[0] // GRID + 1) * GRID, fticks[-1] + 1, GRID):
        if g in have:
            st['grid_exact'] += 1
            continue
        i = bisect.bisect_right(fticks, g) - 1
        if i >= 0 and g - fticks[i] <= SNAP:
            grid_add.append(dict(nfr[i], tick=g))
            st['grid_snapped'] += 1
        else:
            st['grid_hole'] += 1
    nfr = sorted(nfr + grid_add, key=lambda f: f['tick'])
    ticks = [f['tick'] for f in nfr]
    # ---- our deck and confirmed plays (o1_records)
    ours = {}
    for d in dec:
        for name, form, di in d['hand']:
            ours.setdefault(di, (name, form))
    if sorted(ours) != list(range(8)):
        st['skip_own_deck_incomplete'] += 1
        return None, dict(info, stats=dict(st))
    own_names = [ours[i][0] for i in range(8)]
    own_final = [ours[i][0] + R.SUFFIX[ours[i][1]] for i in range(8)]
    dticks = [d['tick'] for d in dec]

    def dec_at(t):
        i = bisect.bisect_right(dticks, t) - 1
        return dec[i] if i >= 0 else None
    used, mine = set(), []
    for c in conf:
        cand = [i for i, tp in enumerate(taps) if i not in used and tp['name'] == c['name'] and 0 <= c['tick'] - tp['tick'] <= 80
                and tp['xy']]
        if cand:
            used.add(cand[-1])
            mine.append(dict(taps[cand[-1]], conf=c['tick']))
    mine.sort(key=lambda t: t['tick'])
    # ---- public detections of both seats (the dataset's own detector) on every frame
    prov = dict(tag=path.name.split('.')[0], record_native=True, record_full=True, frames=nfr, log=[])
    obs = recording_observers(tag_native_recording(prov, {}))
    oplays = sorted(obs[me].plays, key=lambda e: e['tick'])          # the opponent's plays, as OUR seat saw them
    our_seen = sorted(obs[opp].plays, key=lambda e: e['tick'])       # OUR plays, as the opponent's seat saw them
    seen_forms = {}
    for e in oplays:
        k = R.key_of(e['card'])
        seen_forms[k] = max(seen_forms.get(k, 0), int(e.get('form') or 0))
    if 'mirror' in seen_forms:
        st['skip_mirror'] += 1
        return None, dict(info, stats=dict(st))
    seen = set(seen_forms)
    st[f'opp_cards_seen:{min(len(seen), 9)}'] += 1
    deck, how, hf_n, hf_p = None, None, 0, None
    if len(seen) == 8:
        deck, how = sorted(seen), 'seen8'
    elif bl_deck is not None and seen <= set(bl_deck):
        deck, how = sorted(bl_deck), 'battlelog'
    elif len(seen) == 7:
        k8, how, hf_n, hf_p = complete_hf(seen)
        if k8:
            deck = sorted(seen | {k8})
    else:
        how = 'seen_lt7' if len(seen) < 7 else 'seen_gt8'
    if deck is not None:
        for k in deck:
            seen_forms.setdefault(k, 0)
    st['opp_deck:' + how] += 1
    log, pframes = [], []

    def frame_at(t, slack=SNAP + 20):
        i = bisect.bisect_right(ticks, t) - 1
        return nfr[i] if i >= 0 and t - ticks[i] <= slack else None
    # ---- our plays (o1_records)
    for p in mine:
        d0 = dec_at(p['tick'])
        if d0 is None:
            continue
        hb = [h[0] for h in d0['hand']]
        after = next((d for d in dec if d['tick'] > p['tick'] + 10 and [h[0] for h in d['hand']] != hb), None)
        nxt = None
        if after is not None:
            new = [h for h in after['hand'] if h[0] not in hb]
            nxt = new[0][2] if len(new) == 1 else None
        x, y = R.engine_xy(me, p['xy'])
        fr = frame_at(p['tick'], 0)
        k = len(log)
        ok = fr is not None and p['name'] in hb
        log.append(dict(play_index=k, tick=p['tick'], side=me, card=R.key_of(p['name']), x=x, y=y, accepted=True,
                        hand_before=hb if ok else [], actual_form=ours[own_names.index(p['name'])][1] if p['name'] in own_names else 0))
        if ok:
            pframes.append(dict(fr, play_index=k, side=me, card=R.key_of(p['name']), x=x, y=y,
                                players=[dict(side=me, elixir=fr['elixir'][me], hand=hb, next=nxt)]))
        st['own_play_rows_offered' if ok else 'own_play_no_frame'] += 1
    # ---- opponent plays
    opp_final, hk_from = None, None
    if deck is not None:
        dnames = [R.cname_of_key(k) for k in deck]
        if None in dnames:
            st['skip_opp_deck_unmapped'] += 1
            deck = None
    if deck is not None:
        opp_final = [n + R.SUFFIX[seen_forms.get(k, 0)] for n, k in zip(dnames, deck)]
        seq = [dict(key=R.key_of(e['card']), sight=int(e['tick']), **e) for e in oplays]
        fr_at = {f['tick']: f for f in frames}
        for e in seq:                                          # O1b: a projectile spell's label = its TARGET
            f = fr_at.get(e['sight'])
            hits = [p for p in (f or {}).get('proj', []) if p[0] == opp and int(p[3]) >= 0 and R.key_of(R.cname(p[3]) or '') == e['key']
                    and p[4] is not None and p[5] is not None and (p[4], p[5]) != (0, 0)]
            if hits:
                e['x'], e['y'] = sum(p[4] for p in hits) / len(hits), sum(p[5] for p in hits) / len(hits)
                st['opp_spell_label_target'] += 1
            a = e['sight'] - LAG
            if a % GRID == 0:
                a -= 1
                st['opp_act_off_grid_shift'] += 1
            e['tick'] = a
        # opponent own elixir: the counter minus plays acted but not yet sighted
        cost = [card_cost(e['key']) or 0.0 for e in seq]
        acts, sights = [e['tick'] for e in seq], [e['sight'] for e in seq]
        for f in nfr:
            t = f['tick']
            lo = bisect.bisect_left(sights, t + 1) - 8          # only plays sighted after t can be pending
            pend = sum(cost[k] for k in range(max(0, lo), len(seq)) if acts[k] < t < sights[k])
            if pend:
                f['elixir'] = list(f['elixir'])
                f['elixir'][opp] = max(0.0, f['elixir'][opp] - pend)
                st['opp_frames_pending_deducted'] += 1
        hands = R.infer_hands(seq, deck)
        fit = fitted_hands(seq, deck)
        if fit is not None and len(seq) > 4 and hands[4] is not None:
            hands[:4] = fit
            hk_from = seq[4]['tick'] - 21                      # rows with tick <= hk_from + 20 = before act(5): inferred
            st['opp_fitted_deal'] += 1
        for e, h in zip(seq, hands):
            k = len(log)
            fr = frame_at(int(e['tick']))
            ok = h is not None and fr is not None
            hb = [dnames[deck.index(c)] for c in h[0]] if ok else []
            log.append(dict(play_index=k, tick=int(e['tick']), side=opp, card=e['key'], x=round(e['x']), y=round(e['y']),
                            accepted=True, hand_before=hb, actual_form=int(e.get('form') or 0), sight=e['sight']))
            if ok:
                pframes.append(dict(fr, play_index=k, side=opp, card=e['key'], x=round(e['x']), y=round(e['y']),
                                    players=[dict(side=opp, elixir=fr['elixir'][opp], hand=hb, next=deck.index(h[1]))]))
            st['opp_play_hand_known' if ok else ('opp_play_hand_unknown' if h is None else 'opp_play_no_frame')] += 1
    # ---- tags
    def tower_lvl(side):
        hp = [t[6] for f in nfr[:5] for t in f['towers'] if t[0] == side and t[1] == 'princess']
        return TOWER_LVL.get(max(hp)) if hp else None
    import card as CD
    names = sorted({R.cname_of_key(R.key_of(e['card'])) or e['card'] for e in oplays})
    live = dict(block=m['block'], band=m['band'], mark=m['mark'], sha=m['sha'], tro=m['tro'], res=m['res'],
                my_side=me, opp_side=opp, own_tower_lvl=tower_lvl(me), opp_tower_lvl=tower_lvl(opp),
                opp_deck=opp_final, opp_deck_how=how, hf_n=hf_n, hf_p=hf_p, seen=sorted(seen), bl_deck=bl_deck,
                arch=CD.arch2(names), hand_known_from={str(me): None, str(opp): hk_from},
                our_taps=[(p['tick'], p['conf'], R.key_of(p['name'])) for p in mine],
                our_sightings=[(int(e['tick']), R.key_of(e['card'])) for e in our_seen],
                opp_sightings=[(int(e['tick']), R.key_of(e['card'])) for e in oplays])
    if deck is None:
        return None, dict(info, stats=dict(st), live=live)
    rec = dict(tag=prov['tag'], source='live_reader_v1', recording=path.name, record_native=True, record_full=True,
               record_every=GRID, final_decks={str(me): own_final, str(opp): opp_final}, expected=dict(crowns_by_side={}),
               log=sorted(log, key=lambda e: (e['tick'], e['play_index'])), play_frames=pframes, frames=nfr, live=live)
    return rec, dict(info, stats=dict(st), live=live)


def _run(job, out_dir):
    try:
        rec, line = build(job)
    except Exception as ex:                                    # noqa: BLE001 -- a broken log is counted and named
        return dict(stem=job[1]['stem'], error=repr(ex)[:400])
    if rec is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"replay_{rec['tag']}.json").write_text(json.dumps(rec))
        line['chunk'] = out_dir.name
    return line


def battlelog_decks(path, stems):
    """{stem: [base keys]} -- each Ranked battle of the poller's log -> the newest log that started 0-12 min before it."""
    import bisect as B
    from datetime import datetime, timedelta
    sys.path.insert(0, str(L74 / 'opp_model/humanlike'))
    import predict_live as PL
    st = sorted(stems)
    t_of = [datetime.strptime(s[10:25], '%Y%m%d_%H%M%S') for s in st]
    out = {}
    for line in open(path, encoding='utf-8'):
        b = json.loads(line)['battle']
        if b.get('type') != 'pathOfLegend' or len(b.get('opponent') or []) != 1:
            continue
        t = datetime.strptime(b['battleTime'][:15], '%Y%m%dT%H%M%S') + timedelta(hours=-4)
        i = B.bisect_right(t_of, t) - 1
        if i < 0 or t - t_of[i] > timedelta(minutes=12):
            continue
        names, _, _, _, bad = PL.deck_of(b['opponent'][0])
        if bad or len(names) != 8:
            continue
        import o1_records as R
        out[st[i]] = sorted({R.key_of(n.split('@')[0]) for n in names})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--logs', type=Path, required=True)
    ap.add_argument('--select', type=Path, default=HERE / 'select.json')
    ap.add_argument('--battlelog', type=Path, default=L74 / 'crapi/data/own_battlelog.jsonl')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--block', choices=('train', 'calibration'), required=True)
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--chunk', type=int, default=50)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--bl-decks', type=Path, default=HERE / 'bl_decks.json', help='{stem: deck keys} from --write-bl')
    ap.add_argument('--write-bl', type=Path, default=None, help='laptop: map the battle log to logs, write, exit')
    a = ap.parse_args()
    sel = [m for m in json.loads(a.select.read_text())['logs'] if m['block'] == a.block]
    jobs = []
    for m in sel:
        if block_of(m['stem']) != a.block:                     # the name test first: the sealed block is never opened
            raise SystemExit(f"refusing {m['stem']}: block {block_of(m['stem'])}")
        p = a.logs / (m['stem'] + '.jsonl.gz')
        p = p if p.exists() else a.logs / (m['stem'] + '.jsonl')
        if p.exists():
            jobs.append((p, m))
    jobs.sort(key=lambda j: j[1]['stem'])
    if a.limit:
        jobs = jobs[:a.limit]
    if a.bl_decks and a.bl_decks.exists():                     # precomputed on the laptop (the API-name mapping needs
        bl = json.loads(a.bl_decks.read_text())                 # mix/live_pool + newsim data files the pod copy lacks)
    else:
        bl = battlelog_decks(a.battlelog, [m['stem'] for _, m in jobs]) if a.battlelog.exists() else {}
    if a.write_bl:
        a.write_bl.write_text(json.dumps(bl, indent=0))
        print('battle-log decks', len(bl), '->', a.write_bl)
        return
    root = a.out / a.block
    root.mkdir(parents=True, exist_ok=True)
    idx_path = root / 'index.jsonl'
    done = set()
    if idx_path.exists():
        done = {json.loads(x)['stem'] for x in open(idx_path)}
    todo = [(p, m, bl.get(m['stem'])) for p, m in jobs if m['stem'] not in done]
    print(f'{a.block}: {len(jobs)} logs on disk of {len(sel)} selected; {len(done)} done; {len(todo)} to build; '
          f'battle-log decks mapped {len(bl)}', flush=True)
    t0 = time.time()
    with open(idx_path, 'a') as idx, ProcessPoolExecutor(a.workers) as ex:
        futs = [ex.submit(_run, j, root / f'c{len(done):05d}_{i // a.chunk:04d}') for i, j in enumerate(todo)]   # unique per run: a re-run never adds to a finished chunk
        for i, fu in enumerate(futs):
            line = fu.result()
            idx.write(json.dumps(line) + '\n')
            idx.flush()
            if i % 100 == 0:
                print(i, len(futs), line.get('stem'), round(time.time() - t0), 's', flush=True)
    print('done', round(time.time() - t0), 's')


if __name__ == '__main__':
    main()
