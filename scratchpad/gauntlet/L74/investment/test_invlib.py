"""Self-checks for the W5 context rules (no data needed):  python test_invlib.py"""
import invlib as I


def test_cycle_and_placement():
    m = dict(opp=[dict(tick=t, card=c, x=0, y=0) for t, c in
                  ((10, 'earthquake'), (20, 'hog_rider'), (30, 'skeletons'), (40, 'ice_spirit'), (50, 'the_log'))])
    cyc = I.opp_cycle(m, 45)                        # plays before tick 45: EQ, Hog, Skeletons, Ice Spirit
    assert cyc == {'earthquake': 3, 'hog_rider': 2, 'skeletons': 1, 'ice_spirit': 0}, cyc
    assert I.opp_cycle(m, 60)['earthquake'] == 4    # 4 plays since -> back in hand
    assert [I.xtype(y) for y in (12.5, 19.5, 20.5, 21.5)] == ['pocket', 'bridge', 'bridge', 'defensive']


if __name__ == '__main__':
    test_cycle_and_placement()
    print('test_invlib OK')
