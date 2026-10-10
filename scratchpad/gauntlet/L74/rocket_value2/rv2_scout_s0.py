"""search_s0 as BASE (the rule is off) + a SHADOW TRIGGER log for many rocket_value variants at once (logging only; outcomes are BASE's).
  cd <repo>; FIRE_DIR=<dir> SCOUT_VARIANTS=<json name -> DecisionOptions kwargs> python <this> <search_s0 args>

An arm that fires nothing in a match plays that match IDENTICALLY to BASE (same seeds, the rule draws no RNG), and an arm's first fire is
the first decision at which the rule's trigger holds on BASE's own board (the two are identical until then). So one BASE run with every
variant's trigger evaluated at every decision says in which matches each variant can differ at all; the arm then only has to be simulated
on those seeds (mk_subsets.py). Per worker <FIRE_DIR>/scout_<pid>.jsonl, one line per (tag, variant) at its FIRST trigger:
  tag, v, t (board seconds), value (the rule's blast value), el (my elixir), play (BASE plays a card at that decision), card, n_dec (decisions so far).
The trigger = rocket_value_choice on the decision board with a per-(match, variant) lead-history holder, the decision's `allowed` slots,
the match's pending flag and BASE's gate decision as `playing` (the idle variants)."""
import json, os, sys
from types import SimpleNamespace
sys.path.insert(0, os.getcwd())
import pipeline.decision_options as D

_orig, _orig_mk, _ctx = D.decide_batch, D.match_kwargs, {}
_variants = {k: D.DecisionOptions(**v) for k, v in json.load(open(os.environ['SCOUT_VARIANTS'])).items()}
_holders, _first, _ndec = {}, set(), {}
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
        _out = open(os.path.join(os.environ['FIRE_DIR'], f'scout_{os.getpid()}.jsonl'), 'a')
    _out.write(json.dumps(rec) + '\n')
    _out.flush()


def _logged(*a, **k):
    out = _orig(*a, **k)
    allowed, card_names, grid = a[4], k['card_names'], _ctx['grid']
    for r, d in enumerate(out):
        bs, tag = _ctx['boards'][r], _ctx['tags'][r]
        _ndec[tag] = _ndec.get(tag, 0) + 1
        name = card_names[r][d['slot']] if d['slot'] >= 0 else None
        for v, opt in _variants.items():
            holder = _holders.setdefault((tag, v), SimpleNamespace())
            hit = D.rocket_value_choice(opt, card_names[r], allowed[r], bs, grid, pending=_ctx['pending'][r], holder=holder,
                                        playing=bool(d['play']))
            if hit is not None and (tag, v) not in _first:
                _first.add((tag, v))
                _write(dict(tag=tag, v=v, t=round(float(bs.t_sec), 2), value=round(hit[2], 3), el=round(float(bs.my_elixir), 2),
                            play=bool(d['play']), card=None if name is None else str(name), why=d.get('why'), n_dec=_ndec[tag]))
    return out


D.decide_batch, D.match_kwargs = _logged, _mk

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
