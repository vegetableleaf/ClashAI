"""Q4: OLS trend per 10 updates of the training curves (train_log.jsonl), first-10 vs last-10 update means."""
import json, sys
U = [d for d in (json.loads(l) for l in open(sys.argv[1]) if '"type": "update"' in l)]
def trend(name, f):
    y = [f(d) for d in U]; x = list(range(len(y))); n = len(y); mx = sum(x)/n; my = sum(y)/n
    b = sum((a-mx)*(c-my) for a, c in zip(x, y)) / sum((a-mx)**2 for a in x)
    print(f"{name:28s} first10 {sum(y[:10])/10:8.4f} last10 {sum(y[-10:])/10:8.4f} slope/10upd {10*b:+.4f}")
trend('winrate', lambda d: d['winrate'])
trend('press per decision', lambda d: d['ability']['press_rate'])
trend('accepted presses / match', lambda d: d['ability']['accepted_per_match'])
trend('ability decisions / match', lambda d: d['ability']['decisions'] / d['matches'])
trend('head entropy (ep0)', lambda d: d['ability']['ent_ability_ep0'])
trend('l_ab', lambda d: d['ability']['l_ab'])
trend('plays / match', lambda d: d['plays_per_match'])
