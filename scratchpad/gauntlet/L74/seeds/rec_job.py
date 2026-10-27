"""Battle-log replay recording (replay_rec/recorder.py) -> SeedSearch job with BOTH full deal orders.

    python -I rec_job.py --tables <crforge tables/16.402.22> --rec REC.jsonl --tags '#OURTAG' '#OPPTAG' --out JOB.txt

The first active frame with both hands visible holds each side's deal: hand_deck_indices (slots 0-3) + cycle_deck_indices
(queue, front first); deck_card_ids give the deck in slot order. Side 0/1 are the recording's player sides. The side
holding an X-Bow (27000008) gets our tag's word, the other side the opponent's.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_jobs import id_names, word


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', required=True)
    ap.add_argument('--rec', required=True)
    ap.add_argument('--tags', nargs=2, required=True, metavar=('OURS', 'OPPONENT'))
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    names = id_names(a.tables)
    for line in open(a.rec):
        r = json.loads(line)
        f = r.get('f') or {}
        ps = f.get('players') or []
        if r.get('event') == 'frame' and f.get('battle_active') and len(ps) == 2 \
                and all(min(p['hand_deck_indices']) >= 0 and len(p.get('deck_card_ids') or []) == 8 for p in ps):
            break
    else:
        raise SystemExit('no frame with both hands and decks')
    ours = next(p['side'] for p in ps if 27000008 in p['deck_card_ids'])
    lines = [f'# {a.rec} tick {f["game_tick"]}']
    for p in sorted(ps, key=lambda p: p['side']):
        s = p['side']
        lines += [f'deck{s}=' + ','.join(names[c] for c in p['deck_card_ids']),
                  f'word{s}={word(a.tags[0] if s == ours else a.tags[1])}',
                  f'order{s}=' + ','.join(map(str, p['hand_deck_indices'] + p['cycle_deck_indices']))]
    open(a.out, 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
