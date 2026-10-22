"""python -m pytest scratchpad/gauntlet/L74/ape/test_ape_score.py -q  (synthetic boards for ape_score.score)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ape_score as A  # noqa: E402


def board(t, vh=(0, 0), vl=None, el=5.0, tw=10000.0, on=None):
    return dict(t=t, vh=list(vh), vl=list(vl or vh), cov=[0, 0], el=el, mc=1, tw=tw, on=on or {})


def threat(frames_lane1, start=100):
    """a 6 s, 7-elixir threat in lane 1 (own-frame x >= 9) from tick `start`."""
    return [board(start + 10 * i, vh=(0, 7), on={'a': 7.0}) for i in range(frames_lane1)]


def test_answered_wrong_idle():
    S = threat(12) + [board(220)]
    r = A.score(S, [dict(t=120, name='Knight', x=13, y=.7, el=5)])
    assert r['thr'] == 1 and r['thr_ans'] == 1 and not r['thr_ign']
    r = A.score(S, [dict(t=120, name='Xbow', x=3, y=.61, el=8)])              # other lane first
    assert r['thr_wrong'] == 1 and r['thr_ign'] == 1 and r['xb_other'] == 1
    r = A.score(S, [])                                                            # nothing for 4 s with elixir
    assert r['thr_idle'] == 1 and r['thr_ign'] == 1


def test_short_threat_not_counted():
    r = A.score([board(100, vh=(0, 7)), board(140), board(200)], [])
    assert r['thr'] == 0 and r['thr_short'] == 1


def test_ape_tesla_and_low_reserve_xbow():
    S = threat(12) + [board(220)]
    r = A.score(S, [dict(t=110, name='Tesla', x=13, y=.5625, el=6), dict(t=150, name='Xbow', x=13, y=.61, el=8)])
    assert r['te_ape'] == 1 and r['te_off'] == 1 and r['xb_ape'] == 0 and r['xb_lowres'] == 1


def test_push_hp_and_trade():
    S = [board(100, tw=10000)] + [board(110 + 10 * i, vh=(0, 7), on={'a': 7.0}, tw=9000) for i in range(12)] + \
        [board(240, tw=9000), board(400, tw=9000)]
    r = A.score(S, [dict(t=120, name='Knight', x=13, y=.7, el=5)])
    assert r['push'] == 1 and r['push_lost'] == 1000 and r['push_val'] == 7 and r['push_spend'] == 3
