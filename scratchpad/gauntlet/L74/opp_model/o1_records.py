"""O1 step 1: live ladder logs -> driven-corpus records (replay_<log stem>.json) that pipeline.dataset_gen reads unchanged
(the schema of L74/replay_rec/to_record.py: record_native / record_full frames, log, play_frames, final_decks).
Single process, below-normal priority, local files only.

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/o1_records.py [--limit N] [--holdout 0.25]
      -> out/o1_corpus/{train,holdout}/replay_<stem>.json + out/o1_corpus/index.json  (derived, NOT committed)

Matches: live_table.py rows, icebow main account, trophies before >= 12,000, logs with 2-tick `frame` events (since 10-15 17:26).
Holdout = the newest 25% by start time (never trains; the sealed live block is everything after this build).

PUBLIC INFORMATION ONLY for the opponent's seat (owner rule):
  * frames: the reader's public bodies / towers / projectiles / area effects, kept every >= 8 ticks (the pro corpus records every
    10). `elixir` = [own exact, opponent = the live public counter `opp_elixir_est`] per side, so the opponent seat's own-elixir
    input is the public estimate. dataset_gen itself rebuilds each seat's estimate of the OTHER side from public sightings.
  * opponent plays = recording_observers()'s public detections (the dataset's own detector) on these frames; deck = the cards
    detected, completed from the live census (mix/decks_live_*.json) only when exactly 7 are seen and one 8th card has >= 60%
    of the matching census weight; else no opponent rows.
  * opponent hand before play k (the public cycle rule): the 4 most recently played cards are the queue, so hand = deck - last 4
    plays, next = the oldest of those 4. Defined only from the 5th play on, when the 4 are distinct, in the deck, and play k is
    not among them (a repeat inside 4 plays proves a missed / extra detection). Otherwise the play gets no play frame and its
    hand stays unknown -> dataset_gen drops that play row and the wait rows before it (its own `play_skipped` / `wait_no_hand`).
  * play frame = the last kept frame >= 4 ticks before the first sighting (the reader sees a deploy at once, so the decision was
    just before).
OUR seat (used only for the self-check, never as imitation rows): hand from the logged decisions, next from the card that
enters the hand after each confirmed play, plays = confirmed taps at their decision tick."""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from pathlib import Path

import orjson

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(HERE), str(ROOT)]
import live_table as LT  # noqa: E402  (also sets below-normal priority via opp_behaviour)
from pipeline import vocab  # noqa: E402
from pipeline.obs_contract import catalog_card_form  # noqa: E402
from pipeline.public_observation import recording_observers  # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402

OUT = HERE / 'out' / 'o1_corpus'
LIVE_OFF = LT.LIVE_OFF
FRAME_EVERY = 8
PRE_PLAY = 4
SUFFIX = {0: '', 1: '@evolution', 2: '@hero'}
CENSUS = [ROOT / 'scratchpad/gauntlet/L74/mix/decks_live_train.json', ROOT / 'scratchpad/gauntlet/L74/mix/decks_live_eval.json']


def key_of(name):
    return vocab.base_key(vocab.engine_key(name) or '') if name else None


def cname(cid):
    return catalog_card_form(int(cid))[0] if int(cid) >= 0 else None


_CEN = None


def census():
    """[(set of base keys, {key: form}, weight)] over both live census files."""
    global _CEN
    if _CEN is None:
        _CEN = []
        for p in CENSUS:
            for d in json.loads(p.read_text(encoding='utf-8'))['decks']:
                ks = {key_of(n.split('@')[0]): (1 if n.endswith('@evolution') else 2 if n.endswith('@hero') else 0) for n in d['engine']}
                if len(ks) == 8 and None not in ks:
                    _CEN.append((set(ks), ks, float(d.get('sides') or 1)))
    return _CEN


def towers(ents):
    out = []
    for e in ents:
        if e['card_id'] != -1:
            continue
        x, y = float(e['x']), float(e['y'])
        if abs(x - 9000) < 1500 and min(abs(y - 3000), abs(y - 29000)) < 1500:
            out.append([e['side'], 'king', None, e['x'], e['y'], e['hp'], e['max_hp']])
        elif min(abs(x - 3500), abs(x - 14500)) < 1500 and min(abs(y - 6500), abs(y - 25500)) < 1500:
            out.append([e['side'], 'princess', 'left' if x < 9000 else 'right', e['x'], e['y'], e['hp'], e['max_hp']])
    return out


def read_log(path):
    """One pass: kept public frames (reader dicts), decisions (tick, hand [(name, form, deck_index)], own elixir), our play
    taps and confirmations."""
    frames, dec, taps, conf, side, last = [], [], [], [], None, -10 ** 9
    with open(path, 'rb') as fh:
        for raw in fh:
            if raw.startswith(b'{"event": "frame"'):
                j = LT.loads(raw)
                t = int(j['tick'])
                if t - last < FRAME_EVERY:
                    continue
                last = t
                side = int(j['my_side'])
                st = j.get('ents_state') or []
                ents = []
                for i, e in enumerate(j['ents']):
                    s_, x, y, cid, hp, mx, kind, addr = e
                    ents.append(dict(side=s_, x=x, y=y, card_id=cid, hp=hp, max_hp=mx, kind=kind, address=addr,
                                     category=st[i][3] if i < len(st) else None))
                fr = dedupe_hero_bodies(dict(game_tick=t, entities=ents))
                frames.append(dict(tick=t, ents=fr['entities'], own_el=float(j.get('elixir') or 0.0),
                                   opp_est=j.get('opp_elixir_est'), proj=j.get('proj') or [], fx=j.get('fx') or []))
            elif raw.startswith(b'{"event": "decision"'):
                j = LT.loads(raw)
                p = j.get('public') or {}
                if 'own_hand' in p:
                    dec.append(dict(tick=int(j['tick']), hand=[(h['name'], int(h.get('form') or 0), int(h['deck_index']))
                                                              for h in p['own_hand']],
                                    own_el=float(p['own_elixir_raw']) if p.get('own_elixir_raw') is not None else None,
                                    opp_est=float(p['opponent_elixir_estimate']) if p.get('opponent_elixir_estimate') is not None else None,
                                    raw_bodies=p.get('raw_bodies') or []))
            elif raw.startswith(b'{"event": "play"'):
                j = LT.loads(raw)
                taps.append(dict(tick=int(j['tick']), name=j.get('name'), xy=j.get('xy')))
            elif raw.startswith(b'{"event": "confirmed"'):
                j = LT.loads(raw)
                conf.append(dict(tick=int(j.get('tick') or 0), name=j.get('name')))
    return side, frames, dec, taps, conf


def native_frame(f, ids):
    """ids: this match's {(side, address, category): int} -- the reader's identity is the (address, category) PAIR (category
    alone repeats across bodies; address alone is reused), as public_frame(source='reader') keys it."""
    ents, seen, dup = [], set(), 0
    for e in f['ents']:
        cid = int(e['card_id'])
        eid = None if e.get('category') is None else ids.setdefault((e['side'], e.get('address'), e['category']), len(ids))
        if cid >= 0 and cname(cid) is None:          # an id the card catalog lacks (e.g. 203000042): dataset_gen refuses the whole
            dup += 1                                  # recording, so the body is dropped and counted (stats key below)
            continue
        if cid >= 0 and e['hp'] > 0:
            if eid is None or (e['side'], eid) in seen:
                dup += 1
                continue
            seen.add((e['side'], eid))
        ents.append([e['side'], e['x'], e['y'], '-1' if cid < 0 else (cname(cid) or str(cid)), e['hp'], e['max_hp'], e['kind'],
                     cid, int(eid) if eid is not None else -1])
    return dict(tick=f['tick'], entities=ents, towers=towers(f['ents']),
                projectiles=[dict(side=p[0], x=p[1], y=p[2], card_id=p[3], target_x=p[4], target_y=p[5]) for p in f['proj']
                             if int(p[3]) < 0 or cname(p[3])],
                area_effects=[dict(side=e[0], x=e[1], y=e[2], card_id=e[3], remaining_ms=e[4]) for e in f['fx']
                              if int(e[3]) < 0 or cname(e[3])]), dup


def engine_xy(side, sxy):
    sx, sy = sxy
    return (round((18 - sx * 18) * 1000), round(sy * 32000)) if side == 1 else (round(sx * 18 * 1000), round((32 - sy * 32) * 1000))


def infer_hands(plays, deck):
    """Public cycle rule -> [(hand keys in deck order, next key) or None] per play (hand BEFORE that play)."""
    out = []
    for k, p in enumerate(plays):
        q = [x['key'] for x in plays[k - 4:k]] if k >= 4 else None
        if q is None or len(set(q)) != 4 or not set(q) <= set(deck) or p['key'] in q or p['key'] not in deck:
            out.append(None)
            continue
        out.append(([c for c in deck if c not in q], q[0]))
    return out


def complete_deck(seen):
    """7 seen cards -> the 8th from the census when one card holds >= 60% of the matching weight; else None."""
    w = Counter()
    for ks, forms, wt in census():
        if seen <= ks and len(ks - seen) == 1:
            w[next(iter(ks - seen))] += wt
    if not w:
        return None, 'no_census_match'
    k, v = w.most_common(1)[0]
    return (k, 'census') if v >= 0.6 * sum(w.values()) else (None, 'census_ambiguous')


def build(row, path):
    """-> (record dict or None, per-match stats)."""
    st = Counter()
    me, frames, dec, taps, conf = read_log(path)
    if me is None or len(frames) < 50 or not dec:
        st['skip_no_frames'] += 1
        return None, st
    opp = 1 - me
    nfr, ids = [], {}
    for f in frames:
        nf, d = native_frame(f, ids)
        st['bodies_dropped_dup_id_or_unknown_card'] += d
        nf['elixir'] = [0.0, 0.0]
        nf['elixir'][me] = f['own_el']
        nf['elixir'][opp] = float(f['opp_est']) if f['opp_est'] is not None else 0.0
        nfr.append(nf)
    ticks = [f['tick'] for f in nfr]
    # ---- our deck (deck_index order) and our confirmed plays
    ours = {}
    for d in dec:
        for name, form, di in d['hand']:
            ours.setdefault(di, (name, form))
    if sorted(ours) != list(range(8)):
        st['skip_own_deck_incomplete'] += 1
        return None, st
    own_names = [ours[i][0] for i in range(8)]
    own_final = [ours[i][0] + SUFFIX[ours[i][1]] for i in range(8)]
    dticks = [d['tick'] for d in dec]
    import bisect

    def dec_at(t):
        i = bisect.bisect_right(dticks, t) - 1
        return dec[i] if i >= 0 else None
    used, mine = set(), []
    for c in conf:                      # each confirmation -> the latest earlier tap of that card within 80 ticks
        cand = [i for i, tp in enumerate(taps) if i not in used and tp['name'] == c['name'] and 0 <= c['tick'] - tp['tick'] <= 80
                and tp['xy']]
        if cand:
            used.add(cand[-1])
            mine.append(taps[cand[-1]])
    mine.sort(key=lambda t: t['tick'])
    # ---- provisional record -> the dataset's own public detections for both seats
    prov = dict(tag=path.stem, record_native=True, record_full=True, frames=nfr, log=[])
    from pipeline.native_recording import tag_native_recording
    obs = recording_observers(tag_native_recording(prov, {}))
    oplays = sorted(obs[me].plays, key=lambda e: e['tick'])       # what OUR seat publicly saw the opponent play
    seen_forms = {}
    for e in oplays:
        k = key_of(e['card'])
        seen_forms[k] = max(seen_forms.get(k, 0), int(e.get('form') or 0))
    if 'mirror' in seen_forms:
        st['skip_mirror'] += 1
        return None, st
    seen = set(seen_forms)
    st[f'opp_cards_seen:{min(len(seen), 9)}'] += 1
    deck = None
    if len(seen) == 8:
        deck, how = sorted(seen), 'seen8'
    elif len(seen) == 7:
        k8, how = complete_deck(seen)
        if k8:
            deck = sorted(seen | {k8})
            seen_forms.setdefault(k8, 0)
    else:
        how = 'seen_lt7' if len(seen) < 7 else 'seen_gt8'
    st['opp_deck:' + how] += 1
    log, pframes = [], []

    def frame_before(t, gap):
        i = bisect.bisect_right(ticks, t - gap) - 1
        return nfr[i] if i >= 0 and t - ticks[i] <= gap + 20 else None
    # our plays: hand from the decision at the tap, next = the card that enters our hand after the play
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
        x, y = engine_xy(me, p['xy'])
        fr = frame_before(p['tick'], 0)
        k = len(log)
        ok = fr is not None and p['name'] in hb
        log.append(dict(play_index=k, tick=p['tick'], side=me, card=key_of(p['name']), x=x, y=y, accepted=True,
                        hand_before=hb if ok else [], actual_form=ours[own_names.index(p['name'])][1] if p['name'] in own_names else 0))
        if ok:
            pframes.append(dict(fr, play_index=k, side=me, card=key_of(p['name']), x=x, y=y,
                                players=[dict(side=me, elixir=fr['elixir'][me], hand=hb, next=nxt)]))
        st['own_play_rows_offered' if ok else 'own_play_no_frame'] += 1
    # opponent plays
    opp_final = None
    if deck is not None:
        dnames = [cname_of_key(k) for k in deck]
        if None in dnames:
            st['skip_opp_deck_unmapped'] += 1
            deck = None
    if deck is not None:
        opp_final = [n + SUFFIX[seen_forms.get(k, 0)] for n, k in zip(dnames, deck)]
        seq = [dict(key=key_of(e['card']), **e) for e in oplays]
        hands = infer_hands(seq, deck)
        for e, h in zip(seq, hands):
            k = len(log)
            fr = frame_before(int(e['tick']), PRE_PLAY)
            ok = h is not None and fr is not None
            hb = [dnames[deck.index(c)] for c in h[0]] if ok else []
            log.append(dict(play_index=k, tick=int(e['tick']), side=opp, card=e['key'], x=round(e['x']), y=round(e['y']),
                            accepted=True, hand_before=hb, actual_form=int(e.get('form') or 0)))
            if ok:
                pframes.append(dict(fr, play_index=k, side=opp, card=e['key'], x=round(e['x']), y=round(e['y']),
                                    players=[dict(side=opp, elixir=fr['elixir'][opp], hand=hb, next=deck.index(h[1]))]))
            st['opp_play_hand_known' if ok else ('opp_play_hand_unknown' if h is None else 'opp_play_no_frame')] += 1
    rec_crowns = LT_crowns(row)
    rec = dict(tag=path.stem, source='live_ladder_reader', recording=path.name, record_native=True, record_full=True,
               record_every=FRAME_EVERY, final_decks={str(me): own_final, **({str(opp): opp_final} if opp_final else {})},
               expected=dict(crowns_by_side={str(me): rec_crowns[0], str(opp): rec_crowns[1]}),
               log=sorted(log, key=lambda e: (e['tick'], e['play_index'])), play_frames=pframes, frames=nfr,
               o1=dict(my_side=me, opp_side=opp, opp_deck=opp_final, opp_deck_how=how, ts=row['ts'], mark=row['mark'],
                       trophies=row['tro'], arch=row['arch']))
    return rec, st


def cname_of_key(k):
    n = vocab.display_name(k) if hasattr(vocab, 'display_name') else None
    return n or _key2name().get(k)


_K2N = None


def _key2name():
    """base key -> catalog display name (the names to_record writes), from the live card catalog."""
    global _K2N
    if _K2N is None:
        cards = json.loads((ROOT / 'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json').read_text(encoding='utf-8'))['cards']
        _K2N = {}
        for c in cards:
            k = key_of(c['display_name'])
            if k and k not in _K2N:
                _K2N[k] = catalog_card_form(int(c['card_id']))[0] or c['display_name']
    return _K2N


def LT_crowns(row):
    import crowns as C
    r = C.live_rec(row)
    return r['c_all'], r['oc_all']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--holdout', type=float, default=0.25)
    a = ap.parse_args()
    rows = [orjson.loads(l) for l in gzip.open(HERE / 'out/live_matches.jsonl.gz')]
    rows = sorted([r for r in rows if r['deck'] == 'icebow' and (r['tro'] or 0) >= 12000 and r['ts'] >= '20261015_172600'],
                  key=lambda r: r['ts'])
    if a.limit:
        rows = rows[-a.limit:]
    cut = int(round(len(rows) * (1 - a.holdout)))
    for d in ('train', 'holdout'):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    index, tot, t0 = [], Counter(), time.time()
    for i, r in enumerate(rows):
        split = 'train' if i < cut else 'holdout'
        dst = OUT / split / f'replay_{Path(r["log"]).stem}.json'
        try:
            rec, st = build(r, LT.LOGS / r['log'])
        except Exception as ex:                       # noqa: BLE001 -- a broken log is counted and named, never fatal
            tot['error'] += 1
            print('ERROR', r['log'], repr(ex)[:300], flush=True)
            continue
        tot.update(st)
        if rec is None:
            continue
        dst.write_text(json.dumps(rec), encoding='utf-8')
        index.append(dict(tag=rec['tag'], split=split, **rec['o1'], stats=dict(st)))
        if i % 50 == 0:
            print(i, len(rows), r['log'], round(time.time() - t0), 's', flush=True)
    (OUT / 'index.json').write_text(json.dumps(dict(n=len(index), cut_ts=rows[cut]['ts'] if cut < len(rows) else None,
                                                    totals=dict(tot), matches=index), indent=0), encoding='utf-8')
    print(json.dumps(dict(records=len(index), seconds=round(time.time() - t0), totals=dict(tot))))


if __name__ == '__main__':
    main()
