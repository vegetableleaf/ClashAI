"""Offline RoyaleAPI pages -> sanitized replay JSONL and crawl2 CSVs. No SIM imports.

Reuse phase_stats.ReplayHTML for command/timeline parsing. Extra HTML handling is
an allowlist for card summaries and battle identity, never player text or URLs.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'scratchpad/gauntlet/L74/phase_stats'))
from scratchpad.gauntlet.L74.phase_stats.phase_stats import ReplayHTML

HERE = Path(__file__).resolve().parent
TYPES = ('icebow-like', 'other X-Bow', 'Log Bait', 'other')
ICEBOW = {'x-bow', 'tesla', 'knight', 'ice-wizard', 'skeletons', 'the-log', 'tornado', 'rocket'}


def base(card):
    return re.sub(r'-(ev1|hero)$', '', card)


def deck_type(deck):
    cards = {base(c) for c in deck}
    if len(cards & ICEBOW) >= 5:
        return TYPES[0]
    if 'x-bow' in cards:
        return TYPES[1]
    # Explicit operational definition, independent of owner selection metadata.
    if 'goblin-barrel' in cards and cards & {'princess', 'goblin-gang', 'dart-goblin', 'skeleton-barrel'}:
        return TYPES[2]
    return TYPES[3]


def phase(tick):
    if tick < 0:
        raise ValueError('negative_tick')
    return '1x' if tick < 2400 else '2x' if tick < 4800 else '3x' if tick < 6000 else 'postgame'


def canonical_xy(x, y, seat):
    """Page tiles <-> engine/crawl tiles (involution). Side 0 top; side 1 bottom."""
    if seat not in ('0', '1'):
        raise ValueError('missing_or_invalid_seat')
    if x is None or y is None:
        return None, None
    if not all(math.isfinite(v) for v in (x, y)) or not (0 <= x <= 18 and 0 <= y <= 32):
        raise ValueError('invalid_coordinates')
    return (18-x, 32-y) if seat == '1' else (x, y)


class Page(ReplayHTML):
    def __init__(self):
        super().__init__()
        self.decks = defaultdict(set)
        self.battle_id = None

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        a = dict(attrs)
        if 'battle_replay' in a.get('class', '').split():
            self.battle_id = a.get('data-tag')
        if tag == 'img' and a.get('data-s') in ('blue', 'red') and 'data-card' in a and 'data-t' not in a:
            card = a['data-card']
            if re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', card):
                self.decks['1' if a['data-s'] == 'blue' else '0'].add(card)


def parse_page(document):
    parser = Page()
    parser.feed(document['payload']['html'])
    q = parse_qs(urlparse(document.get('request_url', '')).query)
    battle_id = parser.battle_id or q.get('tag', [None])[0]
    if not battle_id or not re.fullmatch(r'[A-Za-z0-9_-]+', battle_id):
        raise ValueError('missing_or_invalid_battle_id')
    if parser.battle_id and q.get('tag') and parser.battle_id != q['tag'][0]:
        raise ValueError('battle_id_conflict')
    # Timeline entries carry ability flags; placement markers do not. Join with
    # multiplicity, not a set (two events at the same tick must remain distinct).
    timeline = defaultdict(deque)
    for tick, side, card, ability in parser.timeline:
        timeline[tick, side, card].append(ability)
    plays, blocks = [], []
    for index, p in enumerate(parser.plays):
        if p['tick'] < 0:
            raise ValueError('negative_tick')
        side = {'t': 1, 'o': 0}[p['side']]
        key = (p['tick'], 'blue' if side == 1 else 'red', p['card'])
        if not timeline[key]:
            raise ValueError('marker_without_timeline')
        ability = bool(timeline[key].popleft())
        x, y = canonical_xy(p['x'], p['y'], p['index'])
        if not ability and (x is None or y is None):
            blocks.append('unpositioned_play')
        if not ability and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', p['card']):
            blocks.append('invalid_card')
        plays.append(dict(play_index=index, tick=p['tick'], side=side, card=p['card'],
                          x=x, y=y, ability=ability, evolution_visible=p['card'].endswith('-ev1'),
                          hero_visible=p['card'].endswith('-hero'), page_seat=p['index']))
    if any(timeline.values()):
        raise ValueError('timeline_without_marker')
    if not plays:
        raise ValueError('no_plays')
    plays.sort(key=lambda p: (p['tick'], p['play_index']))
    decks = {s: sorted(parser.decks[s]) for s in ('0', '1')}
    # Summary is a census of visible cards, not proof of an unplayed slot/form.
    for side, deck in decks.items():
        if len({base(c) for c in deck}) != 8:
            blocks.append('incomplete_or_ambiguous_deck:' + side)
        if any(not p['ability'] and base(p['card']) not in {base(c) for c in deck}
               for p in plays if p['side'] == int(side)):
            blocks.append('play_outside_deck:' + side)
    crowns = {s: int(q[k][0]) if q.get(k) else None
              for s, k in [('0', 'opponent_crowns'), ('1', 'team_crowns')]}
    if any(c is None for c in crowns.values()):
        blocks.append('result_unavailable')  # dataset._crowns otherwise silently invents zero.
    # captured_at is download time, NEVER battle time.
    battle_time = next((q[k][0] for k in ('battle_time', 'battleTime') if q.get(k)), None)
    return dict(schema='pro2-source-v1', tag=battle_id, battle_time=battle_time,
                decks=decks, deck_types={s: deck_type(d) for s, d in decks.items()}, plays=plays,
                expected={'crowns_by_side': crowns}, end_tick=round(parser.end_seconds*20) if parser.end_seconds else None,
                player_identity='omitted', forms_evidence='visible_suffixes_only; unmarked forms unknown',
                deck_evidence='public_card_summary; unplayed slots cannot be recovered',
                blocks=sorted(set(blocks)))


def identity_keys(record):
    keys = set()
    tag = record.get('tag') or record.get('replay_tag')
    if tag:
        keys.add('id:' + str(tag).upper())
    when = record.get('battle_time') or record.get('battleTime')
    decks = record.get('decks')
    if when and decks and all(len(d) == 8 for d in decks.values()):
        # Seat and deck order independent, retain forms when explicitly known.
        pair = sorted(tuple(sorted(base(c) for c in d)) for d in decks.values())
        keys.add('time-decks:' + json.dumps([when, pair], separators=(',', ':')))
    return keys


class Dedupe:
    def __init__(self, existing=()):
        self.existing = set(existing)
        self.seen = set()

    def add(self, record):
        keys = identity_keys(record)
        reason = 'existing_corpus' if keys & self.existing else 'input_duplicate' if keys & self.seen else None
        self.seen.update(keys)
        return reason


def existing_index(corpora, battle_csvs):
    keys, tags, files = set(), set(), 0
    for corpus in corpora:
        if not corpus.is_dir():
            raise ValueError('missing_existing_corpus:' + str(corpus))
        for p in corpus.rglob('replay_*.json'):
            tag = p.stem.removeprefix('replay_').upper()
            tags.add(tag); keys.add('id:' + tag); files += 1
    time_rows = 0
    for path in battle_csvs:
        with path.open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                if r.get('replay_tag', '').upper() not in tags:
                    continue  # dedupe against corpus membership, not unused source games
                rec = dict(tag=r['replay_tag'], battle_time=r.get('battle_time') or r.get('battleTime'),
                           decks={'0': r.get('opponent_deck', '').split(','), '1': r.get('team_deck', '').split(',')})
                kk = identity_keys(rec); keys.update(kk)
                time_rows += any(k.startswith('time-decks:') for k in kk)
    return keys, dict(recordings=files, unique_battle_ids=len(tags), time_deck_source_rows=time_rows)


def default_corpora():
    meta = json.loads((ROOT/'icebow/data/pipeline/gen_dataset_v32_fv5.json').read_text(encoding='utf-8'))
    return [ROOT/Path(p.replace('\\', '/')) for p in meta['corpora']]


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def convert(inputs, out, corpora, battle_csvs):
    if out.exists() and any(out.iterdir()):
        raise ValueError('output_must_be_empty')
    out.mkdir(parents=True, exist_ok=True)
    keys, coverage = existing_index(corpora, battle_csvs)
    dedupe = Dedupe(keys)
    counts = Counter({k: 0 for k in ('input_files','parse_error','existing_corpus','input_duplicate',
                                   'new_replays','crawl_ready','source_blocked','battle_time_available')})
    decks, phases, blocks, sources = Counter(), Counter(), Counter(), Counter()
    battles, csvplays, audit = [], [], []
    with (out/'replays.jsonl').open('w', encoding='utf-8') as output:
        for source_index, directory in enumerate(inputs):
            files = sorted(directory.rglob('*.json')) if directory.is_dir() else [directory]
            for path in files:
                raw = path.read_bytes(); sha = hashlib.sha256(raw).hexdigest()
                counts['input_files'] += 1; sources[str(source_index)] += 1
                try:
                    rec = parse_page(json.loads(raw))
                except (ValueError, KeyError, TypeError) as e:
                    counts['parse_error'] += 1
                    audit.append(dict(source_sha256=sha, status='parse_error', reason=type(e).__name__))
                    continue
                reason = dedupe.add(rec)
                if reason:
                    counts[reason] += 1
                    audit.append(dict(tag=rec['tag'], source_sha256=sha, status=reason))
                    continue
                rec['source_sha256'] = sha
                counts['new_replays'] += 1
                counts['battle_time_available'] += rec['battle_time'] is not None
                decks.update(rec['deck_types'].values())
                phases.update(phase(p['tick']) for p in rec['plays'] if not p['ability'])
                counts['plays'] += sum(not p['ability'] for p in rec['plays'])
                counts['ability_events'] += sum(p['ability'] for p in rec['plays'])
                counts['visible_evolution_events'] += sum(p['evolution_visible'] for p in rec['plays'])
                counts['visible_hero_events'] += sum(p['hero_visible'] for p in rec['plays'])
                blocks.update(rec['blocks'])
                output.write(json.dumps(rec, separators=(',', ':'))+'\n')
                if rec['blocks']:
                    counts['source_blocked'] += 1
                    continue
                counts['crawl_ready'] += 1
                c = rec['expected']['crowns_by_side']
                battles.append(dict(replay_tag=rec['tag'], battle_time=rec['battle_time'] or '',
                                    team_deck=','.join(rec['decks']['1']), opponent_deck=','.join(rec['decks']['0']),
                                    team_crowns=c['1'], opponent_crowns=c['0'], plays=len(rec['plays']),
                                    result='win' if c['1']>c['0'] else 'loss' if c['1']<c['0'] else 'draw'))
                for p in rec['plays']:
                    csvplays.append(dict(replay_tag=rec['tag'], play_index=p['play_index'], tick=p['tick'],
                                         attr_s='blue' if p['side']==1 else 'red', attr_card=base(p['card']),
                                         attr_ability=int(p['ability']), attr_i='0',
                                         x_units='' if p['x'] is None else round(p['x']*1000),
                                         y_units='' if p['y'] is None else round(p['y']*1000)))
    write_csv(out/'battles.csv', ['replay_tag','battle_time','team_deck','opponent_deck','team_crowns','opponent_crowns','plays','result'], battles)
    write_csv(out/'plays_ext.csv', ['replay_tag','play_index','tick','attr_s','attr_card','attr_ability','attr_i','x_units','y_units'], csvplays)
    (out/'tags.json').write_text(json.dumps([r['replay_tag'] for r in battles]), encoding='utf-8')
    (out/'audit.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')
    summary = dict(status='SOURCE_CONVERTED_SIM_PENDING', counts=dict(counts), input_groups=dict(sources),
                   deck_sides={k: decks[k] for k in TYPES}, source_play_events_by_phase=dict(phases),
                   dataset_rows_by_phase=None, divergence_rows=None, blockers=dict(blocks), existing_index=coverage,
                   limitations=['Pages contain no body snapshots: unit-missing/position fidelity is unavailable.',
                                'Unmarked evolution/hero forms are unknown, not confirmed base.',
                                'Battle-time dedupe unavailable when no battle timestamp is present; capture time is not used.'])
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n', encoding='utf-8')
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--inputs', type=Path, nargs='+', default=[Path('C:/Users/benpe/Downloads/raw2/raw'), Path('C:/Users/benpe/Downloads/bait')])
    ap.add_argument('--out', type=Path, default=HERE/'output')
    ap.add_argument('--corpus', type=Path, nargs='+')
    ap.add_argument('--battle-csv', type=Path, nargs='*')
    a = ap.parse_args()
    csvs = a.battle_csv if a.battle_csv is not None else [p for root in
            [ROOT/'scratchpad/gauntlet/ext', ROOT/'icebow/data/royaleapi', ROOT/'hogeq/data/royaleapi'] for p in root.rglob('battles.csv')]
    print(json.dumps(convert(a.inputs, a.out, a.corpus or default_corpora(), csvs), indent=2))


if __name__ == '__main__':
    main()
