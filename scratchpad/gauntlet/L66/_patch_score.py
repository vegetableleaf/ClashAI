p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()
old = s[s.index("def evaluate(env"):s.index("def legal_cells(")]
new = '''def evaluate(env, side: int, horizon: int, mode: str = "v2") -> float:
    """Roll forward `horizon` ticks and score from `side`'s view.

    v1 (kept for comparison) scored (tower damage dealt - taken) + 1/8 * unit_swing, where unit_swing
    counted our units' CURRENT hitpoints. That rewards cowardice and it showed: placing a card adds its
    full hp to "our units", and placing it where nothing can reach it preserves that hp, while placing it
    into a fight spends it. Over a 6 s horizon almost no candidate does tower damage, so the unit term
    decided everything -- 53% of v1's targets landed in the back third of its own half (median py 5.5
    against the pros' 39.0, §5cs.88).

    v2 removes the perverse incentive by never counting our own units' hitpoints as a gain. It scores
    DAMAGE only: enemy tower hp lost, plus enemy unit hp destroyed at 1/8 weight, minus our own tower hp
    lost. A placement earns by hurting the opponent or by preventing damage, never by hiding."""
    before = env.observe()
    ot0, tt0 = tower_hp(before, side)
    ou0, tu0 = unit_hp(before, side)
    env.step(horizon)
    after = env.observe()
    ot1, tt1 = tower_hp(after, side)
    ou1, tu1 = unit_hp(after, side)
    if mode == "v1":
        return float((tt0 - tt1) - (ot0 - ot1)) + 0.125 * float((ou1 - ou0) - (tu1 - tu0))
    enemy_units_destroyed = max(0.0, float(tu0 - tu1))     # their hp that went away; spawns only lower it
    return float((tt0 - tt1) - (ot0 - ot1)) + 0.125 * enemy_units_destroyed


'''
s = s.replace(old, new, 1)
s = s.replace('''    ap.add_argument("--refine", type=int, default=2, help="stage-B radius in cells; 0 disables")''',
              '''    ap.add_argument("--refine", type=int, default=2, help="stage-B radius in cells; 0 disables")
    ap.add_argument("--score", default="v2", choices=("v1", "v2"), help="v1 rewarded hiding; see evaluate()")''')
s = s.replace("                        sc = evaluate(env, row[\"side\"], a.horizon)",
              "                        sc = evaluate(env, row[\"side\"], a.horizon, a.score)")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
