"""search_s0 with every lethal_rocket fire logged (search_s0 results carry no per-play 'why').
  cd <repo>; FIRE_DIR=<dir> python <this> <search_s0 args>
Module-level patch: spawn workers re-import this main module first, so the patch is active in every worker before
search_s0 / e1_eval bind the functions. match_kwargs is wrapped only to remember the batch's match tags (logging)."""
import json, os, sys
sys.path.insert(0, os.getcwd())
import pipeline.decision_options as D

_orig, _orig_mk, _tags = D.decide_batch, D.match_kwargs, []


def _mk(matches):
    _tags[:] = [(getattr(m, 'tag', None), int(getattr(m, 'side', -1))) for m in matches]
    return _orig_mk(matches)


def _logged(*a, **k):
    out = _orig(*a, **k)
    rows = [r for r, d in enumerate(out) if d.get('why') in ('lethal_rocket', 'lethal_log')]
    if rows:
        with open(os.path.join(os.environ['FIRE_DIR'], f'fires_{os.getpid()}.jsonl'), 'a') as f:
            for r in rows:
                towers, side, _ = k['lethal'][r]
                f.write(json.dumps(dict(why=out[r]['why'], t_sec=float(k['t_sec'][r]), slot=out[r]['slot'], cell=out[r]['cell'],
                                        tag=_tags[r][0] if r < len(_tags) else None,
                                        behind=D.crowns_behind(towers, side) if hasattr(D, 'crowns_behind') else None,
                                        target=D.lethal_rocket_target(
                                            towers, side, 'Log' if out[r]['why'] == 'lethal_log' else 'Rocket'))) + '\n')
    return out


D.decide_batch, D.match_kwargs = _logged, _mk

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
