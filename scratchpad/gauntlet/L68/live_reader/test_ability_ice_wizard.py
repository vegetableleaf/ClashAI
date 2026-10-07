"""Assert-based check: python test_ability_ice_wizard.py"""
import ability_ice_wizard as A

m = A.load_model()
assert m["feature_names"] == A.FEATURE_NAMES and len(m["coefficients"]) == len(A.FEATURE_NAMES)
assert abs(sum(A.hat(7.3)) - 1.0) < 1e-9                                       # between two knots the weights sum to 1
assert A.hat(0.0) == [0.0] * 10 and A.hat(99.0)[-1] == 1.0

def ctx(age, opp_plays=(), own_plays=(), t=100.0, own_e=5.0, opp_e=5.0):
    return A.build_features(age, t, own_e, opp_e, list(opp_plays), list(own_plays))

quiet = ctx(3.0)
p = A.frosty_fella_press_probability(quiet)
assert 0.0 < p < 1.0
push = ctx(3.0, [{"t": 98.0, "cost": 4, "kind": "troop", "mine": True, "wincon": True, "card": "hog-rider"},
                 {"t": 99.0, "cost": 3, "kind": "troop", "mine": True, "wincon": False, "card": "knight"}])
assert A.frosty_fella_press_probability(push) > p                              # opponent push on my half raises the hazard
assert A.frosty_fella_press_probability(ctx(0.0)) < p                          # nobody presses the instant of the deploy
assert A.frosty_fella_press_probability(ctx(3.0)) > A.frosty_fella_press_probability(ctx(29.0)) * 0.5
try:
    A.frosty_fella_press_probability({**quiet, "own_elixir": float("nan")}); raise SystemExit("nan accepted")
except ValueError:
    pass
# ---- live adapter on a hand-built state (side 1: my half is y > 16000, enemy comes from y < 16000)
from types import SimpleNamespace as NS
assert abs(A.P_STAR - m["policy"]["P_STAR"]) < 1e-12 and A.V_MIN == m["policy"]["V_MIN"]

def pilot_for(side, flip):
    fy = (lambda y: 32000 - y) if flip else (lambda y: y)
    opp = [dict(card="hog_rider", form=0, x=9000, y=fy(14000), tick=1900, side=1 - side, accepted=True),
           dict(card="knight", form=0, x=9500, y=fy(15000), tick=1930, side=1 - side, accepted=True)]
    own = [dict(card="knight", tick=1950, side=side, accepted=True, ability=False),
           dict(card="ice-wizard", tick=1920, side=side, accepted=True, ability=False)]     # hero deploy is not an 'own play'
    return NS(public=NS(plays=opp, own_events=own, estimate_at=lambda t: 3.0, side=side))

frame1 = {"game_tick": 2000, "players": [{"side": 1, "elixir_raw": 45000}, {"side": 0, "elixir_raw": 99999}]}
frame0 = {"game_tick": 2000, "players": [{"side": 0, "elixir_raw": 45000}, {"side": 1, "elixir_raw": 99999}]}
f1 = A.live_features(pilot_for(1, False), frame1, 1, 1920)
f0 = A.live_features(pilot_for(0, True), frame0, 0, 1920)
assert list(f1) == A.FEATURE_NAMES and f1 == f0                                   # side-symmetric: mirrored state, same features
assert f1["own_elixir"] == 4.5 and f1["opp_elixir"] == 3.0 and f1["own_n6"] == 1.0 and abs(f1["age_hat_4"] - 1.0) < 1e-9
assert f1["opp_wincon_mine10"] == 1.0 and f1["opp_mine_cost6"] >= 4.0              # Hog dead-reckoned across the river
ok, why = A.should_press_pro(pilot_for(1, False), frame1, 1, 1920, geometry_ok=True)
assert ok, why
assert not A.should_press_pro(pilot_for(1, False), frame1, 1, 1920, geometry_ok=False)[0]          # geometry gate
quiet = NS(public=NS(plays=[], own_events=[], estimate_at=lambda t: 8.0, side=1))
assert not A.should_press_pro(quiet, {**frame1, "players": [{"side": 1, "elixir_raw": 90000}]}, 1, 1990, True)[0]   # nothing happening
fr_b = {**frame1, "game_tick": 2012}                                               # 0.6 s later, same grid second
assert A.should_press_pro(pilot_for(1, False), frame1, 1, 1920, True)[1].split("age")[0] ==        A.should_press_pro(pilot_for(1, False), fr_b, 1, 1920, True)[1].split("age")[0]
print("live adapter ok:", why)
print("ok p_quiet=%.4f p_push=%.4f" % (p, A.frosty_fella_press_probability(push)))
