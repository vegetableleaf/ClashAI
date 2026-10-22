"""progress.py LOG [UPTO] -- tonight 10-21 (lead): one training run's progress from its train_log.jsonl (runs on the pod).
Windows: updates 1-10 and the last 15 (or the 15 up to UPTO, so a finished control run can be cut at the same update).
Per window: overall train win (own opponent mix -- NOT comparable across arms), win vs the init policy (pooled; same opponent
for every arm, so comparable), win vs the exploiter league, Log / Rocket / X-Bow share of plays, plays per min, last screen
delta (pp). Prints one JSON line."""
import json, sys

log, upto = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None
rows = [r for r in map(json.loads, open(log)) if r.get('type') == 'update']
if upto:
    rows = [r for r in rows if r['update'] <= upto]


def win(rs, key=None):
    w = n = 0
    for r in rs:
        c = r if key is None else (((r.get('league') or {}).get('by_opp') or {}).get(key) or {})
        w += c.get('W', 0); n += c.get('n', c.get('matches', 0))
    return round(w / n, 3) if n else None, n


def summ(rs):
    if not rs:
        return None
    cm = lambda k: round(sum((r.get('card_mix') or {}).get(k, 0) for r in rs) / len(rs), 4)   # noqa: E731
    return {'u': [rs[0]['update'], rs[-1]['update']], 'win': win(rs)[0], 'win_init': win(rs, 'init'),
            'win_expl': win(rs, 'exploiter_league'), 'log': cm('the_log'), 'rocket': cm('rocket'), 'xbow': cm('x_bow'),
            'tornado': cm('tornado'), 'ppm': round(sum(r.get('plays_per_min', 0) for r in rs) / len(rs), 2),
            'screen_pp': (rs[-1].get('guards') or {}).get('latest_screen_delta_pp')}


print(json.dumps({'last': rows[-1]['update'] if rows else None, 'early': summ(rows[:10]), 'late': summ(rows[-15:])}))
