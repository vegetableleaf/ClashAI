"""search_s0 with every lethal_rocket fire logged (search_s0 results carry no per-play 'why').
  cd <repo>; FIRE_DIR=<dir> python <this> <search_s0 args>
Module-level patch: spawn workers re-import this main module, so the patch is active in every worker."""
import json, os, sys
sys.path.insert(0, os.getcwd())
import pipeline.decision_options as D

_orig = D.decide_batch


def _logged(*a, **k):
    out = _orig(*a, **k)
    rows = [r for r, d in enumerate(out) if d.get('why') == 'lethal_rocket']
    if rows:
        with open(os.path.join(os.environ['FIRE_DIR'], f'fires_{os.getpid()}.jsonl'), 'a') as f:
            for r in rows:
                towers, side, _ = k['lethal'][r]
                f.write(json.dumps(dict(t_sec=float(k['t_sec'][r]), slot=out[r]['slot'], cell=out[r]['cell'],
                                        target=D.lethal_rocket_target(towers, side))) + '\n')
    return out


D.decide_batch = _logged

if __name__ == '__main__':
    from pipeline import search_s0
    sys.exit(search_s0.main(sys.argv[1:]))
