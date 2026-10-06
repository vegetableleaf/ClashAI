"""How long the live bot holds Rocket in hand and how likely the policy is to play it (decision events). Read-only."""
import json, glob, os, collections, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
fs = sorted(glob.glob(os.path.join(ROOT, 'scratchpad/gauntlet/L68/live_reader/live_play_2026100[456]_*.jsonl')))
tot = collections.Counter(); ps = collections.defaultdict(list); hold = []
files_with = 0
for f in fs:
    n = 0; rk_in = 0; first = None; last_in = None; plays = 0
    for l in open(f):
        if l.startswith('{"event": "play"'):
            plays += 1 if json.loads(l).get('name') == 'Rocket' else 0
        if not l.startswith('{"event": "decision"'):
            continue
        r = json.loads(l); pub = r.get('public') or {}
        hand = [h['name'] for h in pub.get('own_hand', [])]
        d = r['decision']; el = pub.get('own_elixir_raw') or 0
        n += 1
        tot['decisions'] += 1
        if 'Rocket' in hand:
            tot['rocket_in_hand'] += 1
            rk_in += 1
            if el >= 6:
                tot['rocket_in_hand_afford'] += 1
        if d.get('name'):
            ps[d['name']].append(d.get('p_play') or 0)
    if n:
        files_with += 1
        tot['rocket_plays_in_decision_files'] += plays
        hold.append(rk_in / n)
res = dict(files_with_decisions=files_with, decisions=tot['decisions'], rocket_in_hand_pct=round(100 * tot['rocket_in_hand'] / tot['decisions'], 1),
           rocket_in_hand_and_elixir_ge6_pct=round(100 * tot['rocket_in_hand_afford'] / tot['decisions'], 1),
           rocket_plays_total=tot['rocket_plays_in_decision_files'], rocket_plays_per_game=round(tot['rocket_plays_in_decision_files'] / files_with, 2),
           per_file_rocket_in_hand_median_pct=round(100 * statistics.median(hold), 1),
           p_play_mean_by_candidate={k: round(statistics.mean(v), 3) for k, v in ps.items()},
           p_play_p90_by_candidate={k: round(sorted(v)[int(.9 * len(v))], 3) for k, v in ps.items()})
json.dump(res, open(os.path.join(HERE, 'rocket_hold.json'), 'w'), indent=1)
print(json.dumps(res, indent=1))
