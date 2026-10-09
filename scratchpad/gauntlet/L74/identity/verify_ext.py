"""Offline check of body_identity.extension() on every recorded live decision state (decision.public.raw_bodies).

Each state goes through the live model-input path twice -- dedupe_hero_bodies -> live_mem.to_observe ->
obs_contract.from_engine(feature_version 6, unmapped=set()) -> public_observation.body_only_board -> to_tokens /
to_unit_forms (MAX_U 64) -- once plain, once inside extension(). Token rows are compared as multisets: every
removed / added row must be a targeted body whose non-class columns are unchanged (a remap = the same row with a new
class / form; a previously dropped body = an added row). Anything else is a FAILURE.
Not covered: the look-ahead (extrapolate) and own-hand fields (identical inputs in both passes; identity is applied
after them in GenPilot.row). Single process, below normal.  python verify_ext.py -> verify_ext.json + stdout
"""
import collections, glob, json, os, sys, time
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, '../../../..')))
from pipeline import vocab, body_identity as BI
from pipeline.obs_contract import Deck, REPO, from_engine, to_tokens, to_unit_forms
from pipeline.live_mem import to_observe
from pipeline.public_observation import body_only_board
from pipeline.reader_identity_aliases import dedupe_hero_bodies
from pipeline.train_s1 import MAX_U

LOG = 'C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/'
KEYS = ('x_bow', 'tesla', 'knight', 'skeletons', 'ice_wizard', 'the_log', 'tornado', 'rocket')
DECK = Deck(name='live', cards=KEYS, card_ids=tuple(vocab.unit_id(k) for k in KEYS), config=REPO, src_dir=REPO,
            crawl_dir=REPO, data_dir=REPO)


def model_input(frame, side):
    bs = body_only_board(from_engine(to_observe(frame, side, []), side, DECK, unmapped=set(), feature_version=6))
    tok, mask, _ = to_tokens(bs, MAX_U)
    return tok[mask.astype(bool)], to_unit_forms(bs, MAX_U)[mask.astype(bool)]


def rows(tok, forms):
    return collections.Counter(tuple(np.round(t, 6).tolist()) + (int(f),) for t, f in zip(tok, forms))


def main():
    files = sorted(glob.glob(LOG + 'live_play_2026*.jsonl'))
    stats = collections.Counter(); change = collections.Counter(); fail = []; examples = {}
    t0 = time.time()
    for n, f in enumerate(files):
        b = os.path.basename(f)
        if time.time() - os.path.getmtime(f) < 120:
            continue
        for l in open(f, encoding='utf8', errors='replace'):
            if not (l.startswith('{"event": "decision"') and '"raw_bodies"' in l):
                continue
            try:
                p = json.loads(l)['public']
            except ValueError:
                continue
            if 'observer_side' not in p:
                continue
            side = int(p['observer_side'])
            frame = dedupe_hero_bodies({'game_tick': p['raw_tick'], 'entities': p['raw_bodies'],
                                        'players': [{'side': side, 'elixir_raw': 0, 'hand_deck_indices': [-1] * 4,
                                                     'next_deck_index': -1}]})
            a = model_input(frame, side)
            with BI.extension():
                e = model_input(frame, side)
            stats['states'] += 1
            ra, re_ = rows(*a), rows(*e)
            if ra == re_:
                continue
            stats['states_changed'] += 1
            gone, new = ra - re_, re_ - ra
            # pair each removed row with an added row identical except class (col 0) and form (last)
            new_l = list(new.elements())
            for g in gone.elements():
                j = next((i for i, x in enumerate(new_l) if x[1:-1] == g[1:-1]), None)
                if j is None:
                    fail.append((b, p['raw_tick'], 'removed row with no remapped twin', g)); continue
                x = new_l.pop(j)
                k = (vocab.UNIT_VOCAB[int(g[0])], g[-1], vocab.UNIT_VOCAB[int(x[0])], x[-1])
                change[k] += 1
                examples.setdefault(k, dict(log=b, raw_tick=p['raw_tick'], before=list(g), after=list(x)))
            for x in new_l:                                   # bodies the plain path dropped
                k = (None, None, vocab.UNIT_VOCAB[int(x[0])], x[-1])
                change[k] += 1
                examples.setdefault(k, dict(log=b, raw_tick=p['raw_tick'], before=None, after=list(x)))
            if len(e[0]) >= MAX_U:
                stats['states_at_max_u_with_ext'] += 1
        if n % 100 == 0:
            print(f'[{n}/{len(files)}] {time.time() - t0:.0f}s {dict(stats)}', flush=True)
    out = dict(stats=dict(stats), failures=fail[:50], n_failures=len(fail),
               changes=[dict(before_cls=k[0], before_form=k[1], after_cls=k[2], after_form=k[3], rows=v)
                        for k, v in change.most_common()],
               examples=[dict(change=list(k), **v) for k, v in examples.items()])
    json.dump(out, open(os.path.join(HERE, 'verify_ext.json'), 'w'), indent=1)
    print('stats', dict(stats), 'failures', len(fail))
    for k, v in change.most_common():
        print(f'  {str(k[0]):>18} f{k[1]} -> {k[2]:<14} f{k[3]}  token rows {v}')


if __name__ == '__main__':
    main()
