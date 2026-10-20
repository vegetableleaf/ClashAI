"""Self-check of the metric helpers that need no engine: python test_metrics.py  (prints METRICS_SELFTEST_OK)."""
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as R  # noqa: E402
from scratchpad.gauntlet.L74.parity.metrics import static_check as S  # noqa: E402


def main():
    # J6: a side-0 body walking up the left lane crosses at the first sample past the river; a body born past it never does
    assert R.crossing([(10, 3500, 12000), (20, 3500, 16000), (30, 3400, 18000)], 0) == (30, 'L')
    assert R.crossing([(10, 14000, 20000), (20, 14000, 13000)], 1) == (20, 'R')
    assert R.crossing([(10, 3500, 18000), (20, 3500, 19000)], 0) is None
    # bootstrap over matches: a constant metric has a zero-width CI
    v, ci = R.boot([('a', 1), ('a', 1), ('b', 1)], lambda xs: sum(xs) / len(xs), B=50)
    assert v == 1 and ci == (1, 1)
    # static: level 16 = floor(base x ladder[15] / 100); an override that sets the device value resolves the diff
    card = dict(hitpoints=690, level_scaling=dict(multiplier_percent_by_level=list(range(100, 116))))
    assert S.at16(card, 'hitpoints') == 690 * 115 // 100
    ovs = [dict(card='Fireball', column='CrownTowerDamagePercent', value=-77)]
    assert S.resolved('Fireball', {}, 'crown_tower_damage_percent', 23, ovs)
    assert not S.resolved('Zap', {}, 'crown_tower_damage_percent', 23, ovs)
    # J5b: the entering card is the one played 4 plays before (FIFO)
    deck = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    hand, queue, rows, t = deck[:4], deck[4:], [], 0
    for k in range(10):
        rows.append(dict(event='decision', tick=t, public=dict(own_hand=[dict(name=n) for n in hand])))
        card = hand[k % 4]
        rows.append(dict(event='confirmed', tick=t + 1, name=card))
        hand[hand.index(card)] = queue.pop(0); queue.append(card); t += 10
    rows += [dict(event='decision', tick=t + 5 * i, public=dict(own_hand=[dict(name=n) for n in hand])) for i in range(12)]
    with tempfile.NamedTemporaryFile('w', suffix='.jsonl', delete=False) as f:
        f.write('\n'.join(json.dumps(r) for r in rows))
    res = R.j5_cycle(f.name)
    Path(f.name).unlink()
    assert res['fifo_n'] == 6 and res['fifo_ok'] == 6, res
    print('METRICS_SELFTEST_OK')


if __name__ == '__main__':
    main()
