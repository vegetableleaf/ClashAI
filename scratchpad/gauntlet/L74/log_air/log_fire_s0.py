"""search_s0 with every Log play logged (all arms, incl. the base arm): the Log's corridor content on the decision board.
  cd <repo>; FIRE_DIR=<dir> python <this> <search_s0 args>
Module-level patch (spawn workers re-import this main module first, as air_answer/air_fire_s0.py). Logging only: decisions
are returned untouched. One line per decision where the Log was played OR log_air touched the row:
  kind = hits (ground unit / building / enemy tower in the roll corridor) | only_air | empty (nothing at all)
  why = 'log_air' when log_air re-aimed (retarget) or blocked (block) it;  play = False for a blocked Log (WAIT)
  cell_kind (retarget rows) = ground (the new corridor holds enemy ground elixir) | chip (princess cast cell)"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.getcwd())
import pipeline.decision_options as D

_orig, _orig_mk, _state = D.decide_batch, D.match_kwargs, {}
COR = None


def _mk(matches):
    _state['tags'] = [getattr(m, 'tag', None) for m in matches]
    _state['boards'] = [D.log_air_board(m._cur[1]) for m in matches]       # the decision board of every row (any arm)
    return _orig_mk(matches)


def _kind(board, cell, grid):
    global COR
    COR = COR or D.rolling_corridor('Log')
    ground, air, towers = board
    x, y = D.cell_centres_tiles(grid)
    cx, cy = x[cell:cell + 1], y[cell:cell + 1]
    pad = D.LOG_AIR_UNIT_RADIUS
    gv = float((D._covers(cx, cy, [g[:2] for g in ground], COR, pad) @ np.array([g[2] for g in ground]))[0]) if ground else 0.0
    tw = any(D._covers(cx, cy, [t[:2]], COR, t[2]).any() for t in towers)
    air_n = int(D._covers(cx, cy, air, COR, pad).sum()) if air else 0
    return ('hits' if (gv > 0 or tw or any(D._covers(cx, cy, [g[:2]], COR, pad).any() for g in ground)) else
            'only_air' if air_n else 'empty'), gv, tw, air_n


def _logged(*a, **k):
    out = _orig(*a, **k)
    names, grid = k['card_names'], k.get('grid')
    for r, d in enumerate(out):
        nm = names[r][d['slot']] if d['slot'] >= 0 else None
        if nm is None or not D.is_log(nm) or not (d['play'] or d.get('why') == 'log_air'):
            continue
        try:
            board = _state['boards'][r]
            cell = d['cell'] if d['cell'] >= 0 else None
            row = dict(tag=_state['tags'][r], t_sec=float(k['t_sec'][r]) if k.get('t_sec') is not None else None,
                       play=bool(d['play']), why=d.get('why'), cell=d['cell'])
            if cell is not None:
                kind, gv, tw, air_n = _kind(board, cell, grid)
                row.update(kind=kind, ground_value=round(gv, 2), tower=bool(tw), air_n=air_n)
                if d.get('why') == 'log_air':
                    row['cell_kind'] = 'ground' if gv > 0 else 'chip'
            else:
                row['kind'] = 'blocked'
            with open(os.path.join(os.environ['FIRE_DIR'], f'fires_{os.getpid()}.jsonl'), 'a') as f:
                f.write(json.dumps(row) + '\n')
        except Exception as e:                      # logging must never change a decision
            with open(os.path.join(os.environ['FIRE_DIR'], f'err_{os.getpid()}.txt'), 'a') as f:
                f.write(repr(e) + '\n')
    return out


D.decide_batch, D.match_kwargs = _logged, _mk

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
