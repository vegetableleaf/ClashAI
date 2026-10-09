"""search_s0 as the benchmark plays it + a per-decision STATE DUMP of the learner side (logging only; the match is unchanged).
  cd <repo>; DUMP_DIR=<dir> python scratchpad/gauntlet/L74/drills/sim_dump.py <search_s0 args>

Module-level patch (spawned workers re-import this module first, as rv2_scout_s0.py): match_kwargs maps each learner match's
decision RNG to the match; decide_batch, after deciding, writes one line per learner decision to <DUMP_DIR>/dump_<pid>.jsonl:
  tag, side, tick, el, hand (vocab names), pending, play, card, xy (board frame, cell centre), units [(name, side, x, y, hp_frac,
  age_s)], towers [hp_frac x6: my K L R, opp K L R].
Public board only (the decision's BoardState); the opponent's side is never dumped. drills.py load('sim') turns the dump into
the same per-match format as live / pros, so the SAME selectors give the SIM moments (seed = the tag's last field, tick).
A decided play may still be refused at landing (afford / placement): SIM plays here are DECISIONS, not accepted plays."""
import json, os, sys
sys.path.insert(0, os.getcwd())
import pipeline.decision_options as D
from pipeline import vocab
from pipeline.model_v3 import cell_xy

_orig, _orig_mk, _byrng, _out = D.decide_batch, D.match_kwargs, {}, [None]


def _mk(matches):
    kw = _orig_mk(matches)
    for m, r in zip(matches, kw.get('rngs') or ()):
        _byrng[id(r)] = m
    return kw


def _name(i):
    return vocab.UNIT_VOCAB[i] if 0 <= int(i) < len(vocab.UNIT_VOCAB) else None


def _logged(*a, **k):
    out = _orig(*a, **k)
    rngs, names = k.get('rngs'), k.get('card_names')
    if not rngs:
        return out
    if _out[0] is None:
        _out[0] = open(os.path.join(os.environ['DUMP_DIR'], f'dump_{os.getpid()}.jsonl'), 'a')
    for r, d in enumerate(out):
        m = _byrng.get(id(rngs[r]))
        if m is None:
            continue
        tick, bs = m._cur[0], m._cur[1]
        card = names[r][d['slot']] if d.get('play') and d.get('slot', -1) >= 0 else None
        xy = [round(v, 4) for v in cell_xy(d['cell'], m.cfg['grid'])] if card is not None and d.get('cell', -1) >= 0 else None
        _out[0].write(json.dumps(dict(
            tag=m.tag, side=getattr(m, 'side', None), tick=int(tick), el=round(float(bs.my_elixir), 3),
            hand=[_name(h) for h in bs.my_hand], pending=getattr(m, 'pending', None) is not None, play=bool(d.get('play')),
            card=None if card is None else str(card), xy=xy, why=d.get('why'),
            units=[(_name(u.cls), int(u.side), round(u.x, 4), round(u.y, 4), None if u.hp_frac is None else round(u.hp_frac, 3),
                    None if u.age_sec is None else round(u.age_sec, 2)) for u in bs.units],
            towers=[None if t.hp_frac is None else (round(t.hp_frac, 4) if t.alive else 0.0) for t in bs.towers])) + '\n')
    _out[0].flush()
    return out


D.decide_batch, D.match_kwargs = _logged, _mk

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
