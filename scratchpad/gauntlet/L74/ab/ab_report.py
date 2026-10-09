"""Hero IW ability A/B (owner 2026-10-08): arm OFF (--hero-ability-spec off) vs arm ON (supplement), 20 completed
matches each from ab_state.json. Ladder result from overnight.out; economy from the decision events."""
import json, statistics as st, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'L73/live_review'))
from core import read_results          # noqa: E402

LOGS = Path(__file__).resolve().parents[2] / 'L68/live_reader'
S = json.loads(Path(__file__).with_name('ab_state.json').read_text())
RES = read_results()


def arm(files):
    if not files:
        return 'not finished'
    w = l = 0
    el_play, low, abil, plays, secs = [], 0, 0, 0, 0.0
    for f in files[:20]:
        r = RES.get(f)
        w += r == 'WIN'; l += r == 'LOSS'
        last_el = None
        for line in open(LOGS / f, encoding='utf-8', errors='replace'):
            if line.startswith('{"event": "decision"'):
                last_el = json.loads(line)['public']['own_elixir_raw']
            elif line.startswith('{"event": "play"') and last_el is not None:
                plays += 1; el_play.append(last_el); low += last_el < 4
            elif line.startswith('{"event": "ability_confirmed"'):
                abil += 1
            elif line.startswith('{"event": "end"'):
                secs += json.loads(line)['seconds']
    n = min(len(files), 20)
    return {'matches': n, 'W': w, 'L': l, 'unknown': n - w - l, 'win_rate': round(w / max(w + l, 1), 3),
            'plays_per_min': round(plays / secs * 60, 2), 'elixir_before_play_mean': round(st.mean(el_play), 2),
            'share_plays_below_4_elixir': round(low / plays, 3), 'iw_abilities_per_match': round(abil / n, 2)}


if __name__ == '__main__':
    print('OFF', arm(S['off_matches']))
    from ab_watch import matches
    print('ON ', arm(S.get('on_matches') or matches('supplement', S['on_since'])))
