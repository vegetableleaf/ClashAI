"""Drill suite -- normalise the pro corpus (corpus_v6/icebow_public_v1 re-drives, frames every 10 ticks) into data/pros.pkl.gz,
in the SAME per-match format as build_live.py (live.pkl.gz), so one selector code path runs on both sources.

  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/drills/build_pros.py [max_files]      (2 processes, below-normal priority)

Unlike the push-Rocket / defence extractions (enemy bodies at own y <= 20, names only), this keeps EVERY enemy body (any y, hp fraction),
my own non-tower bodies (needed for the X-Bow drills) and the opponent's accepted plays.  Per match:
  S  = [(t, el, hand, eb, tw, None, own, [])]   eb = (cls, X, Y, val, entity id, t_first, hpf, air); own = (cls, X, Y, hp, max_hp)
  P  = [(tap, land, card, X, Y, el_before, None)]   tap = engine deploy - 26 ticks (as mistakes.py), land = deploy
  opx = [(deploy, card key, X, Y, cost)]   opponent's accepted plays (referee information only; never a model input)
Enemy classes go through the model's own body resolution (pipeline.body_identity.resolve_board), like build_live.py.
"""
import os, sys, glob, gzip, pickle, json, bisect, collections
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
sys.path.insert(0, HERE)
import build_live as BL               # sets below-normal priority (via review), MAIN on sys.path
from build_live import V, vocab, BI, catalog_card_form, AIR, cval

CORPUS = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j*/replay_*.json"
BASE = {"Xbow", "Skeletons", "Log", "Knight", "Tesla", "Tornado", "IceWizard", "Rocket"}
CARD = {"x-bow": "Xbow", "the-log": "Log", "ice-wizard": "IceWizard", "skeletons": "Skeletons", "knight": "Knight", "tesla": "Tesla",
        "tornado": "Tornado", "rocket": "Rocket"}
TAP_LAG = 26


def one(f):
    if not BL.VAL: BL.load_values()
    d = json.load(open(f)); out = []
    decks = {s: [c.split('@')[0] for c in d['final_decks'][str(s)]] for s in (0, 1)}
    for s in (0, 1):
        if set(decks[s]) != BASE: continue
        o = 1 - s
        mylog = sorted((p['tick'], tuple(h.split('@')[0] for h in p['hand_before'])) for p in d['log'] if p['side'] == s and p.get('hand_before'))
        LT = [t for t, _ in mylog]
        first, twmax, seen_tw, S = {}, {}, set(), []
        for fr in d['frames']:
            t = int(fr['tick']); j = bisect.bisect_left(LT, t)
            hand = mylog[j][1] if j < len(mylog) else None
            tw, pend, own = {}, [], []
            for e in fr['entities']:
                side, x, y, card, hp, mx, kind, cid, eid = e[:9]
                X, Y = V.own(s, x, y)
                if str(card) == '-1':
                    k = ('m' if side == s else 'e') + ('K' if kind == 12 else ('L' if X < 9 else 'R'))
                    if hp > 0: tw[k] = hp; twmax[k] = mx
                    continue
                if hp is not None and hp <= 0: continue
                n, fm = catalog_card_form(int(cid)) if cid not in (None, -1) else (None, None)
                if side == s:
                    own.append((vocab.engine_key(n) if n else str(card), round(X, 2), round(Y, 2), hp, mx)); continue
                pend.append((X, Y, n or str(card), mx, fm, n is None, eid, hp))
            ids = BI.resolve_board([(0, p[2], p[3], p[4], p[5]) for p in pend], {0: 1.0}) if pend else []
            eb = []
            for p, idn in zip(pend, ids):
                if idn.cls is None: continue
                nm = vocab.UNIT_VOCAB[idn.cls]
                if (p[6], idn.cls) not in first: first[(p[6], idn.cls)] = t
                hpf = (p[7] / p[3]) if p[3] and p[3] > 0 and p[7] is not None else None
                eb.append((nm, round(p[0], 2), round(p[1], 2), round(cval(idn.cls), 3), p[6], first[(p[6], idn.cls)], hpf, nm in AIR))
            seen_tw |= set(tw)
            for k in seen_tw: tw.setdefault(k, 0)
            S.append((t, fr['elixir'][s], hand, eb, tw, None, own, []))
        P = [(p['tick'] - TAP_LAG, p['tick'], CARD.get(p['card'], p['card']), *[round(v, 2) for v in V.own(s, p['x'], p['y'])], p.get('elixir_before'), None)
             for p in d['log'] if p['side'] == s and p.get('accepted') and p.get('x') is not None]
        opx = [(p['tick'], (vocab.engine_key(p['card']) or p['card']).replace('-', '_'), *[round(v, 2) for v in V.own(s, p['x'], p['y'])], p.get('cost'))
               for p in d['log'] if p['side'] == o and p.get('accepted') and p.get('x') is not None]
        fin = d['final']
        res = "DRAW" if fin.get('winner') is None else ("WIN" if fin.get('winner') == s else "LOSS")
        out.append(dict(file=os.path.basename(f)[7:19] + f'_s{s}', src="pros", fam="pros", side=s, end=int(fin['tick']), S=S, P=P, opx=opx,
                        twmax=twmax, res=res, opp_deck=decks[o]))
    return out


if __name__ == '__main__':
    from multiprocessing import Pool
    fs = sorted(glob.glob(CORPUS))
    if len(sys.argv) > 1: fs = fs[:int(sys.argv[1])]
    res = []
    with Pool(2) as pool:
        for i, r in enumerate(pool.imap_unordered(one, fs, chunksize=8)):
            res += r
            if i % 300 == 0: print(i, len(fs), len(res), flush=True)
    os.makedirs(HERE + "data", exist_ok=True)
    with gzip.open(HERE + ("data/pros.pkl.gz" if len(sys.argv) == 1 else "data/pros_small.pkl.gz"), "wb") as fh: pickle.dump(res, fh)
    print("sides", len(res), collections.Counter(m["res"] for m in res))
