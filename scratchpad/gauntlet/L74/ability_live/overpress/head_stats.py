"""Per arm with a learned head: head decisions / match, head presses / match, mean p, engine-accepted presses / match,
deploy -> press delay (s) median and IQR."""
import glob, json, sys, statistics as st
for name, pat in (('cue_ab promo greedy', sys.argv[1] + '/eval/cue_ab_74*/D3/*/matches.jsonl'),
                  *((n, sys.argv[2] + f'/{n}_74*/D3/*/matches.jsonl') for n in ('ws_greedy', 'ws_sample', 'ab_sample', 'ws_live', 'ws_live_sample'))):
    rows = [json.loads(l) for f in glob.glob(pat) if 'failed' not in f for l in open(f) if l.strip()]
    ah = [r['ability_head'] for r in rows if r.get('ability_head')]
    if not rows:
        continue
    dl = []
    for r in rows:
        dep = [p[1] for p in r['own_plays'] if p[2] == 'ice_wizard' and p[3]]
        for t, c in r['own_presses']:
            prev = [d for d in dep if d <= t]
            if prev: dl.append((t - max(prev)) / 20)
    acc = sum(sum(r['ability_presses'].get(str(r['learner_side']), {}).values()) for r in rows) / len(rows)
    q = st.quantiles(dl, n=4) if len(dl) > 3 else [0, 0, 0]
    print(f"{name:20s} n {len(rows):4d} head dec/m {sum(a['decisions'] for a in ah)/max(1,len(ah)):6.2f} head press/m "
          f"{sum(a['presses'] for a in ah)/max(1,len(ah)):5.2f} p_mean {st.mean(a['p_mean'] for a in ah) if ah else 0:.4f} "
          f"accepted/m {acc:5.2f} delay med {st.median(dl) if dl else 0:.1f}s IQR [{q[0]:.1f}, {q[2]:.1f}]")
