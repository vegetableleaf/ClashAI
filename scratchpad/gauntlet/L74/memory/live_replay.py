"""Plan A S1b (E): recorded live matches replayed through the LIVE memory path, offline (no ADB / MuMu / model; live_play.py
is never imported or run).

    research/ext/Royale/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/live_replay.py [LOG ...]

Per log: every 'frame' event -> a reader-shaped frame (entities incl. the cid -1 towers, projectiles, effects; players:
my side's elixir_raw from the logged own elixir, a visible dummy hand) -> the REAL pipeline.live_gen.GenPilot.observe;
'confirmed' / 'late_landing' -> GenPilot.record_play (model-frame intended xy, the decided form, the confirmation tick, as
live_play.py:1318/1345); 'ability_confirmed' -> GenPilot.record_ability(tap tick, as live_play.py:1280); every 'decision'
-> GenPilot.memory_rows on the latest frame (what row() feeds a memory model). Reference: the S1a offline build
(live_dump.read samples + plays, forms filled the same way) at the same ticks. Reports per match the decisions whose six
MEM arrays are identical, and the memory_rows latency."""
from __future__ import annotations

import collections
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path[:0] = [str(REPO), str(HERE)]
import live_dump as D  # noqa: E402
from pipeline import match_memory as MM  # noqa: E402
from pipeline.dataset_gen import card_key  # noqa: E402
from pipeline.live_gen import GenPilot  # noqa: E402
from pipeline.public_observation import _native_ids  # noqa: E402
from pipeline import vocab  # noqa: E402

VOCAB = json.loads(str(np.load(REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5.npz')['meta']))['card_vocab']
FA = []                                                          # per match: (features_at rows identical, rows)


# MEM-FULL (memory/MEM_FULL.md): env MEMFULL=E_MAX,SNAP (e.g. 256,1) = the same identity with the full-memory options
FULL = (dict(zip(('e_max', 'snap'), (int(v) for v in __import__('os').environ['MEMFULL'].split(','))))
        if __import__('os').environ.get('MEMFULL') else {})
if FULL:
    FULL['snap'] = bool(FULL['snap'])


def pilot():
    p = GenPilot.__new__(GenPilot)                               # the memory path only: no checkpoint, no device
    p.feature_version, p.public, p.public_battle, p.opp, p.own_fx, p.past = 6, None, None, None, None, []
    p.frames = collections.deque(maxlen=30)
    from pipeline.dataset_gen import checkpoint_gid
    p.gid = checkpoint_gid(VOCAB)
    if FULL:                                                     # MEM-FULL: a model whose encoder reads e_max / snap
        import types
        p.model = types.SimpleNamespace(mem=types.SimpleNamespace(version='v1', **FULL))
    return p


def replay(path):
    side, frame, forms, unconf = None, None, {}, {}
    ids = [_native_ids()[(vocab.engine_key(n), 0)] for n in D.DECK]
    gp = pilot()
    deck = np.array(sorted(gp.gid[card_key(n)] for n in D.DECK))
    got, taps, ms = {}, [], []
    for raw in open(path, 'rb'):
        head = raw[:40]
        if b'"frame"' in head:
            j = json.loads(raw)
            side = j['my_side'] if side is None else side
            st = j.get('ents_state') or []
            ents = [dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7],
                         **({'category': st[i][3]} if i < len(st) else {})) for i, e in enumerate(j['ents'])]
            me = dict(side=side, hand_deck_indices=[0, 1, 2, 3], next_deck_index=4, deck_card_ids=ids,
                      elixir_raw=round(float(j['elixir']) * 1e4))
            frame = dict(game_tick=j['tick'], entities=ents,
                         projectiles=[dict(side=p[0], x=p[1], y=p[2], card_id=p[3], target_x=p[4], target_y=p[5])
                                      for p in j.get('proj') or []],
                         effects=[dict(side=e[0], x=e[1], y=e[2], card_id=e[3], remaining_ms=e[4]) for e in j.get('fx') or []],
                         players=[me, dict(side=1 - side, hand_deck_indices=[-1] * 4, next_deck_index=-1, elixir_raw=0,
                                           deck_card_ids=[-1] * 8)])
            from pipeline.reader_identity_aliases import dedupe_hero_bodies
            frame = dedupe_hero_bodies(frame)
            gp.observe(frame)
        elif b'"decision"' in head:
            j = json.loads(raw)
            d = j.get('decision') or {}
            if d.get('play'):
                forms[d.get('name')] = int(d.get('form', 3))           # the form the next confirmation of it carries
            if frame is not None and j['tick'] not in got and gp.public is not None:
                t0 = time.perf_counter()
                got[j['tick']] = gp.memory_rows(frame, side, deck)
                ms.append((time.perf_counter() - t0) * 1e3)
        elif b'"unconfirmed"' in head:
            j = json.loads(raw)
            unconf[j['name']] = j.get('intended')
        elif b'"confirmed"' in head or b'"late_landing"' in head:
            j = json.loads(raw)
            xy = j.get('intended') if j['event'] == 'confirmed' else unconf.get(j['name'])
            if xy is not None and gp.public is not None:
                gp.record_play(gp.gid[card_key(j['name'])], forms.get(j['name'], 3), tuple(xy), j['tick'] * 0.05)
        elif head.startswith(b'{"event": "ability"'):
            taps.append(json.loads(raw)['tick'])
        elif b'"ability_confirmed"' in head and gp.public is not None:
            gp.record_ability('IceWizard', taps[-1])
    return side, deck, got, ms, forms, gp


def main():
    paths = [Path(a) for a in sys.argv[1:]]
    if not paths:
        for p in sorted(D.LOGS.glob('live_play_2026102*.jsonl'), reverse=True):
            if p.stat().st_size > 2e6 and b'{"event": "end"' in p.read_bytes():
                paths.append(p)
            if len(paths) == 6:
                break
    tot = same_n = 0
    for p in paths:
        side, deck, got, ms, _, gp = replay(p)
        ref_in = D.read(p)                                         # the S1a offline parser (samples + plays)
        own = [e for e in gp.public.own_events]                    # forms as the pilot recorded them
        plays = list(ref_in['plays'])
        fmap = {(int(e['tick']), card_key(e['card'])): e.get('form') for e in own if not e.get('ability')}
        for q in plays:
            if int(q['side']) == side and not q.get('ability'):
                q['form'] = fmap.get((int(q['tick']), card_key(q['card'])))
        ref = MM.build(side, ref_in['samples'], plays, **FULL)
        bad = []
        for t, f in got.items():
            r = ref.features(t, gp.gid, deck)
            if not all(np.array_equal(f[k], r[k]) for k in MM.MEM_KEYS):
                bad.append(t)
        tot += len(got)
        same_n += len(got) - len(bad)
        ticks = sorted(got)                                        # storage path: the end-of-match table + features_at
        t0 = time.perf_counter()
        fa = MM.features_at(gp.mem.table(gp.gid), ticks, deck, e_max=FULL.get('e_max', MM.E_MAX))
        fa_ms = (time.perf_counter() - t0) * 1e3
        fa_bad = sum(not all(np.array_equal(fa[k][i], got[t][k]) for k in MM.MEM_KEYS) for i, t in enumerate(ticks))
        FA.append((len(ticks) - fa_bad, len(ticks)))
        ev = ref.events(10 ** 7)
        print(f'{p.name}: side {side}, decisions {len(got)}: identical {len(got) - len(bad)}/{len(got)}'
              f'{"  first mismatch tick " + str(bad[0]) if bad else ""}; events {len(ev)} (own plays '
              f'{sum(e["type"] == "play" and e["mine"] for e in ev)}, forms known '
              f'{sum(e["type"] == "play" and e["mine"] and e["form"] != 3 for e in ev)}, presses '
              f'{sum(e["type"] == "ability" for e in ev)}); late {gp.mem.late}; memory_rows median '
              f'{np.median(ms):.2f} ms, p90 {np.percentile(ms, 90):.2f} ms, max {max(ms):.1f} ms; table + features_at '
              f'identical {FA[-1][0]}/{FA[-1][1]} ({fa_ms:.0f} ms for all rows)')
    print(f'ALL: {same_n}/{tot} decisions identical (live path vs S1a offline build); features_at(table) vs the live '
          f'MatchMemory: {sum(a for a, _ in FA)}/{sum(b for _, b in FA)}')


if __name__ == '__main__':
    main()
