"""search_s0 with FULL-BOARD windows around Rocket decisions (logging only; outcomes are unaffected).
  cd <repo>; FIRE_DIR=<dir> [WIN_TIMES=<json tag -> [t_sec, ...]>] python <this> <search_s0 args>
Per worker process <FIRE_DIR>/bw_<pid>.jsonl, one 'b' line per decision inside a window:
  window opens at every decision that plays a Rocket (any why) and runs 15 s after it; with WIN_TIMES (the base arm, replaying the
  moments another arm fired) it covers [t - 1 s, t + 15 s] for each listed t.
  b: tag, t, el (my elixir), hand (names), play/card/cell(x,y tiles)/why of the decision, pending, enemy [[name, x, y, hp_frac]]
     (tiles, board frame: my king tower at y 28.65, my half y >= 16), mine (same), towers [[side, kind, lane, hp_frac, alive]].
Module-level patch: spawn workers re-import this main module first, so it is active in every worker."""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
import pipeline.decision_options as D
from pipeline import vocab

_orig, _orig_mk, _ctx, _until = D.decide_batch, D.match_kwargs, {}, {}
_times = json.load(open(os.environ['WIN_TIMES'])) if os.environ.get('WIN_TIMES') else {}
_out = None


def _mk(matches):
    _ctx['tags'] = [getattr(m, 'tag', None) for m in matches]
    _ctx['boards'] = [m._cur[1] for m in matches]
    _ctx['pending'] = [getattr(m, 'pending', None) is not None for m in matches]
    _ctx['grid'] = matches[0].cfg['grid']
    return _orig_mk(matches)


def _write(rec):
    global _out
    if _out is None:
        _out = open(os.path.join(os.environ['FIRE_DIR'], f'bw_{os.getpid()}.jsonl'), 'a')
    _out.write(json.dumps(rec) + '\n')
    _out.flush()


def _u(u):
    return [vocab.UNIT_VOCAB[int(u.cls)], round(float(u.x) * 18, 2), round(float(u.y) * 32, 2),
            None if u.hp_frac is None else round(float(u.hp_frac), 3)]


def _logged(*a, **k):
    out = _orig(*a, **k)
    card_names = k['card_names']
    grid = _ctx['grid']
    xs, ys = D.cell_centres_tiles(grid)
    if os.environ.get('PLACEBO'):       # control: the Rocket is spent exactly when the rule fires, on my own back corner (hits nothing)
        safe = int(np.argmin(np.hypot(xs - 1.0, ys - 31.0)))
        for d in out:
            if d.get('why') == 'rocket_value':
                d['cell'] = safe
    for r, d in enumerate(out):
        bs, tag = _ctx['boards'][r], _ctx['tags'][r]
        t = float(bs.t_sec)
        name = card_names[r][d['slot']] if d['slot'] >= 0 else None
        is_rocket = bool(d['play']) and name is not None and str(name).lower() == 'rocket'
        if is_rocket:
            _until[tag] = max(_until.get(tag, -1), t + 15.0)
        inwin = t <= _until.get(tag, -1) or any(tt - 1.0 <= t <= tt + 15.0 for tt in _times.get(tag, ()))
        if not inwin:
            continue
        cell = d.get('cell', -1)
        _write(dict(kind='b', tag=tag, t=round(t, 2), el=round(float(bs.my_elixir), 2),
                    hand=[vocab.UNIT_VOCAB[i] if i >= 0 else None for i in bs.my_hand], pending=bool(_ctx['pending'][r]),
                    play=bool(d['play']), card=None if name is None else str(name), why=d.get('why'),
                    cell=None if cell is None or cell < 0 else [round(float(xs[cell]), 2), round(float(ys[cell]), 2)],
                    enemy=[_u(u) for u in bs.units if int(u.side) != 0], mine=[_u(u) for u in bs.units if int(u.side) == 0],
                    towers=[[tw.side, tw.kind, tw.lane, None if tw.hp_frac is None else round(float(tw.hp_frac), 3), bool(tw.alive)]
                            for tw in bs.towers]))
    return out


D.decide_batch, D.match_kwargs = _logged, _mk

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
