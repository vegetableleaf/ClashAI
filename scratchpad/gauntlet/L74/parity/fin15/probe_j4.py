"""W8 probe: J4's open-loop elixir per frame for ONE log (replay_metrics.j4 with its frame list returned), printing every frame
where |SIM - live| changes by >= 0.01, with the drops around it.  PARITY_SIM_PATH=... python probe_j4.py LOG"""
import inspect, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as R  # noqa: E402

# j4 with its frame list and drops exposed: its own source, the summary return swapped for (out, drops)
src = inspect.getsource(R.j4)
src = src[:src.index('    phase = lambda t:')] + '    return out, drops\n'
ns = dict(vars(R)); exec(src, ns)

if __name__ == '__main__':
    out, drops = ns['j4'](sys.argv[1], F.Engine(), None)
    prev = None
    for t, e, s in out:
        d = round(s - e, 2)
        if prev is None or abs(d - prev) >= .01:
            near = [(x['tick'], x['card'], x['cost'], x['live_drop']) for x in drops if abs(x['tick'] - t) <= 8]
            print('t', t, 'live', e, 'sim', s, 'd', d, near)
            prev = d
