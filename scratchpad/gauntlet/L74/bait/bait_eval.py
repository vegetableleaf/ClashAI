"""Bait eval = gap.py with every chunk run through bait_s0.py (learner deck = the friend's bait deck in every game).
Decision stack = the bait live run's (L70/live/bait/LIVE_OPTIONS + run_live.sh): greedy, tau .35, own_effects, no rules.
In gap.py terms that is arm D3 with EVERY livecal.LIVE key dropped (D3's tail with nothing left but --own-effects);
D1 would drop --own-effects too. Paired plan, opponents (E4 T .1, CAL evo + lad censuses), Hero IW env = gap.py's.
    python bait_eval.py --ckpt CK --out DIR --seed-start 741200 [--workers N]      (other gap.py flags pass through)"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'gap'))
import gap  # noqa: E402

_cmd = gap.livecal.command


def command(*a, **k):
    cmd = _cmd(*a, **k)
    if not cmd[1].endswith('livecal.py') or cmd[2] != '--worker':
        raise ValueError('livecal.command layout changed; refusing to guess')
    return [cmd[0], str(HERE/'bait_s0.py'), *cmd[2:]]


gap.livecal.command = command
if __name__ == '__main__':
    if '--arms' in sys.argv or '--drop' in sys.argv:
        raise SystemExit('bait_eval.py fixes --arms D3 --drop <all live keys>')
    sys.argv += ['--arms', 'D3', '--drop', ','.join(gap.livecal.LIVE)]
    gap.main()
