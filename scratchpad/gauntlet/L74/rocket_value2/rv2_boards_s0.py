"""search_s0 as BASE with EVERY decision's public board logged (logging only; outcomes are BASE's).
  cd <repo>; FIRE_DIR=<dir> python <this> <search_s0 args>
Per worker <FIRE_DIR>/boards_<pid>.jsonl, one line per decision:
  {"tag", "n" (decision index in the match), "tick", "el" (my elixir), "pl" (BASE plays a card here), "card" (its name, or null),
   "why", "ra" (a Rocket slot is affordable), "pe" (a card is pending), "b" [[vocab class id, x tiles, y tiles, hp fraction], ...] for
   every body not mine, "tw" [[hp fraction, alive] x 6: my K, L, R, then the opponent's]}, plus, once per match, a {"tag", "names": [...], "grid"} line.
Everything the rocket_value rule reads (rocket_value_choice: names, allowed, the board's bodies / elixir / time, pending, the gate
decision) is in it, so any variant's FIRST TRIGGER can be found offline by replaying the rule (replay_triggers.py): an arm that fires
nothing plays the match identically to BASE and its first fire is that trigger (BASE and the arm are identical until then)."""
import json, os, sys
sys.path.insert(0, os.getcwd())
import numpy as np
import pipeline.decision_options as D

_orig, _orig_mk, _ctx, _seen, _n = D.decide_batch, D.match_kwargs, {}, set(), {}
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
        _out = open(os.path.join(os.environ['FIRE_DIR'], f'boards_{os.getpid()}.jsonl'), 'a', buffering=1)
    _out.write(json.dumps(rec, separators=(',', ':')) + '\n')


def _logged(*a, **k):
    out = _orig(*a, **k)
    allowed, card_names = a[4], k['card_names']
    for r, d in enumerate(out):
        bs, tag = _ctx['boards'][r], _ctx['tags'][r]
        if tag not in _seen:
            _seen.add(tag)
            _write(dict(tag=tag, names=[None if n is None else str(n) for n in card_names[r]], grid=_ctx['grid']))
        _n[tag] = _n.get(tag, 0) + 1
        name = card_names[r][d['slot']] if d['slot'] >= 0 else None
        ra = any(n is not None and str(n).lower() == 'rocket' and allowed[r][i] for i, n in enumerate(card_names[r]))
        _write(dict(tag=tag, n=_n[tag], tick=int(round(float(bs.t_sec) / 0.05)), el=round(float(bs.my_elixir), 3), pl=bool(d['play']),
                    card=None if name is None else str(name), why=d.get('why'), ra=bool(ra), pe=bool(_ctx['pending'][r]),
                    b=[[int(u.cls), round(float(u.x) * 18, 3), round(float(u.y) * 32, 3), None if u.hp_frac is None else round(float(u.hp_frac), 4)]
                       for u in bs.units if int(u.side) != 0],
                    tw=[[None if t.hp_frac is None else round(float(t.hp_frac), 4), bool(t.alive)] for t in bs.towers]))   # my K, L, R, opp K, L, R
    return out


D.decide_batch, D.match_kwargs = _logged, _mk

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
