"""Live opponent-elixir counter vs the opponent's TRUE elixir, on the live logs that still carry 'opp_elixir_true_EVAL_ONLY'
(logged for grading until the owner's 10-16 change; read here for grading only, never fed anywhere).
Per frame: est = opp_elixir_est (= the model's counter, rebuilt exactly by livelog.py), truth = the EVAL_ONLY field.
    python counter_truth.py   -> stdout + counter_truth.json"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOGS = HERE.parents[1] / 'L68/live_reader'
idx = json.load(open(HERE / 'index.json'))
RX = re.compile(rb'"tick": (\d+).*?"opp_elixir_true_EVAL_ONLY": ([-\d.eE]+|null), "opp_elixir_est": ([-\d.eE]+|null)')
by_mark = defaultdict(list)
per_phase = defaultdict(list)
n_logs = defaultdict(int)
for name, v in sorted(idx.items()):
    p = LOGS / name
    found = False
    with open(p, 'rb') as f:
        for raw in f:
            if not raw.startswith(b'{"event": "frame"'):
                continue
            m = RX.search(raw, 0, 400)
            if not m:
                break
            if m[2] == b'null' or m[3] == b'null':
                continue
            found = True
            t, tr, es = int(m[1]), float(m[2]), float(m[3])
            by_mark[v['mark']].append(es - tr)
            per_phase[(v['mark'], 'single' if t < 2400 else 'double' if t < 4800 else 'triple')].append(es - tr)
    n_logs[v['mark']] += found
out = {}
for mk, d in sorted(by_mark.items(), key=lambda kv: -len(kv[1])):
    a = [abs(x) for x in d]
    out[mk] = dict(logs=n_logs[mk], frames=len(d), mae=round(statistics.fmean(a), 3), bias=round(statistics.fmean(d), 3),
                   within1=round(sum(x <= 1 for x in a) / len(a), 3), within2=round(sum(x <= 2 for x in a) / len(a), 3),
                   p90_abs=round(sorted(a)[int(.9 * len(a))], 2),
                   phases={ph: dict(n=len(x), mae=round(statistics.fmean(map(abs, x)), 3), bias=round(statistics.fmean(x), 3))
                           for (m_, ph), x in per_phase.items() if m_ == mk})
    print(mk, out[mk])
json.dump(out, open(HERE / 'counter_truth.json', 'w'), indent=1)
