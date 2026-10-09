"""Offline check of body_identity.extension() on every recorded live decision state (decision.public.raw_bodies).

Each state goes through the live model-input path twice -- dedupe_hero_bodies -> live_mem.to_observe ->
obs_contract.from_engine(feature_version 6, unmapped=set()) -> public_observation.body_only_board -> to_tokens /
to_unit_forms (MAX_U 64) -- once plain, once inside extension(). Token rows are compared as multisets: every
removed / added row must be a targeted body whose non-class columns are unchanged (a remap = the same row with a new
class / form; a previously dropped body = an added row; a body the extension DROPS = a removed row of an allowed
class / form, DROP_OK). Anything else is a FAILURE. off_sha256 = hash of every plain-pass input (compare across code
roots: --root <checkout> --off-only).
Not covered: the look-ahead (extrapolate) and own-hand fields (identical inputs in both passes; identity is applied
after them in GenPilot.row). Single process, below normal.
  python verify_ext.py [--root DIR] [--off-only] [--out NAME]  -> NAME.json (default verify_ext) + stdout
"""
import collections, glob, hashlib, json, os, sys, time
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ARGS = sys.argv[1:]
ROOT = ARGS[ARGS.index('--root') + 1] if '--root' in ARGS else os.path.abspath(os.path.join(HERE, '../../../..'))
OFF_ONLY = '--off-only' in ARGS
OUT = ARGS[ARGS.index('--out') + 1] if '--out' in ARGS else 'verify_ext'
CUT = ARGS[ARGS.index('--cut') + 1] if '--cut' in ARGS else 'live_play_20261009_005738'   # logs before this name
sys.path.insert(0, ROOT)
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
DROP_OK = {('goblins', 2), ('magic_archer', 2)}        # body_identity.EXT_BODIES entries with class None


def model_input(frame, side):
    bs = body_only_board(from_engine(to_observe(frame, side, []), side, DECK, unmapped=set(), feature_version=6))
    tok, mask, _ = to_tokens(bs, MAX_U)
    return tok[mask.astype(bool)], to_unit_forms(bs, MAX_U)[mask.astype(bool)]


def rows(tok, forms):
    return collections.Counter(tuple(np.round(t, 6).tolist()) + (int(f),) for t, f in zip(tok, forms))


def main():
    files = sorted(glob.glob(LOG + 'live_play_2026*.jsonl'))
    stats = collections.Counter(); change = collections.Counter(); fail = []; examples = {}
    states_by, logs_by = collections.defaultdict(int), collections.defaultdict(set)
    h = hashlib.sha256()
    t0 = time.time()
    for n, f in enumerate(files):
        b = os.path.basename(f)
        if b >= CUT:                              # fixed cut so runs over different code roots see the same logs
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
            h.update(a[0].tobytes()); h.update(a[1].tobytes())
            stats['states'] += 1
            if OFF_ONLY:
                continue
            with BI.extension():
                e = model_input(frame, side)
            ra, re_ = rows(*a), rows(*e)
            if ra == re_:
                continue
            stats['states_changed'] += 1
            gone, new = ra - re_, re_ - ra
            new_l, ks = list(new.elements()), set()
            for g in gone.elements():                     # pair with a row identical except class (col 0) / form (last)
                j = next((i for i, x in enumerate(new_l) if x[1:-1] == g[1:-1]), None)
                before = (vocab.UNIT_VOCAB[int(g[0])], g[-1])
                if j is None:
                    if before not in DROP_OK:
                        fail.append((b, p['raw_tick'], 'removed row of a non-dropped class', g)); continue
                    k, x = before + (None, None), None
                else:
                    x = new_l.pop(j)
                    k = before + (vocab.UNIT_VOCAB[int(x[0])], x[-1])
                change[k] += 1; ks.add(k)
                examples.setdefault(k, dict(log=b, raw_tick=p['raw_tick'], before=list(g), after=x and list(x)))
            for x in new_l:                               # bodies the plain path dropped
                k = (None, None, vocab.UNIT_VOCAB[int(x[0])], x[-1])
                change[k] += 1; ks.add(k)
                examples.setdefault(k, dict(log=b, raw_tick=p['raw_tick'], before=None, after=list(x)))
            for k in ks:
                states_by[k] += 1; logs_by[k].add(b)
            if len(e[0]) >= MAX_U:
                stats['states_at_max_u_with_ext'] += 1
        if n % 200 == 0:
            print(f'[{n}/{len(files)}] {time.time() - t0:.0f}s {dict(stats)}', flush=True)
    out = dict(root=ROOT, stats=dict(stats), off_sha256=h.hexdigest(), failures=fail[:50], n_failures=len(fail),
               changes=[dict(before_cls=k[0], before_form=k[1], after_cls=k[2], after_form=k[3], rows=v,
                             states=states_by[k], logs=len(logs_by[k]),
                             logs_since_1008=sum(x >= 'live_play_20261008' for x in logs_by[k]))
                        for k, v in change.most_common()],
               examples=[dict(change=list(k), **v) for k, v in examples.items()])
    json.dump(out, open(os.path.join(HERE, OUT + '.json'), 'w'), indent=1)
    print('root', ROOT, 'stats', dict(stats), 'off_sha256', h.hexdigest(), 'failures', len(fail))
    for c in out['changes']:
        print(f"  {str(c['before_cls']):>18} f{c['before_form']} -> {str(c['after_cls']):<14} f{c['after_form']}  rows "
              f"{c['rows']:5d} states {c['states']:5d} logs {c['logs']:3d} (since 10-08: {c['logs_since_1008']})")


if __name__ == '__main__':
    main()
