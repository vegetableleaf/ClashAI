"""Byte-identity proof: hash from_engine -> to_tokens/to_unit_forms (and the BoardState repr) on 200 native frames
(list path, via tag_native_recording) and 200 live reader frames (raw path, via live_mem.to_observe), for fv1..fv5.
Usage: python fv_hash.py OUT.json   (run before and after the change; compare)."""
import sys, json, hashlib, random, glob
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
from pipeline.obs_contract import from_engine, load_deck, to_tokens, to_unit_forms
from pipeline.native_recording import tag_native_recording
from pipeline.live_mem import to_observe, deck_of
import numpy as np

PICK = {  # one replay per family incl. hogs (WitchMother), Evo Witch unreadable, hero Tombstone, Evo Drill, SK
    'WitchMother', 'Witch@evolution', 'Tombstone@hero', 'GoblinDrill@evolution', 'SkeletonBalloon@evolution',
    'GoblinGiant@evolution', 'FirespiritHut@evolution', 'GoblinCage@evolution', 'Phoenix', 'DarkWitch',
    'GoblinHut', 'Graveyard', 'ElixirGolem', 'Tombstone', 'Witch', 'GoblinDrill', 'GoblinCage', 'FirespiritHut',
    'SkeletonBalloon', 'BarbarianHut'}

def native_frames():
    pre = json.load(open('../spawners/prefilter.json'))
    rnd = random.Random(7); got = []
    byf = {}
    for p, v in sorted(pre.items()):
        for f in v:
            byf.setdefault(f, []).append(p)
    sk = [p for p, v in json.load(open('prefilter_extra.json')).items() if 'SkeletonKing' in v]
    paths = [rnd.choice(byf[f]) for f in sorted(PICK)][:19] + [sorted(sk)[3]]
    deck = load_deck('icebow')
    for p in paths:
        rec = tag_native_recording(json.load(open(p, encoding='utf-8')), {})
        fr = rec['frames']; idx = np.linspace(len(fr) // 3, len(fr) - 1, 10).astype(int)
        for i in idx:
            got.append((p, int(i), dict(fr[i], players=[]), deck))
    return got

def live_frames():
    logs = sorted(glob.glob(r'C:\Users\benpe\ClashBot\scratchpad\gauntlet\L68\live_reader\live_play_2026100[456]_*.jsonl'))
    out = []
    for p in logs:
        fr = []
        with open(p, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if line.startswith('{"event": "frame"'):
                    fr.append(json.loads(line))
        if len(fr) < 200: continue
        for d in fr[len(fr) // 2::max(1, len(fr) // 40)][:20]:
            out.append((p, d['tick'], d))
        if len(out) >= 200: break
    return out[:200]

def reader_frame(d):
    """Log frame -> the reader frame shape live_mem.to_observe takes (my player only; deck unknown -> icebow)."""
    ents = [dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7]) for e in d['ents']]
    return dict(game_tick=d['tick'], entities=ents)

def digest(bs):
    t, m, s = to_tokens(bs, 64)
    h = hashlib.sha256()
    for a in (t, m, s, to_unit_forms(bs, 64)):
        h.update(np.ascontiguousarray(a).tobytes())
    h.update(repr(bs).encode())
    return h.hexdigest()

if __name__ == '__main__':
    out = {}
    nat = native_frames(); live = live_frames()
    deck = load_deck('icebow')
    for fv in (1, 2, 3, 4, 5):
        H = hashlib.sha256(); n = 0
        for p, i, obs, dk in nat:
            for side in (0, 1):
                H.update(digest(from_engine(obs, side, dk, unmapped=set(), feature_version=fv)).encode()); n += 1
        out[f'native_fv{fv}'] = [H.hexdigest(), n, len(nat)]
        H = hashlib.sha256(); n = 0
        for p, t, d in live:
            ms = d['my_side']
            obs = to_observe(dict(reader_frame(d), players=[dict(side=ms, elixir_raw=0, hand_deck_indices=[-1]*4, next_deck_index=-1)]), ms, list(deck.cards))
            H.update(digest(from_engine(obs, ms, deck, unmapped=set(), feature_version=fv, history={})).encode()); n += 1
        out[f'live_fv{fv}'] = [H.hexdigest(), n, len(live)]
        print(fv, out[f'native_fv{fv}'], out[f'live_fv{fv}'], flush=True)
    json.dump(out, open(sys.argv[1], 'w'), indent=1)
