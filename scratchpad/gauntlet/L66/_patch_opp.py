p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()

# 1. rollout helper that lets the opponent act
s = s.replace("def evaluate(env, side: int, horizon: int, mode: str = \"v2\") -> float:",
'''def rollout(env, ctx, side: int, start_tick: int, horizon: int, opponent: str) -> None:
    """Advance `horizon` ticks. With opponent="replay", the OTHER side's recorded plays are applied at
    their real ticks during the window instead of the opponent standing still.

    Why this matters (§5cs.90 C): an inert opponent makes every placement look safe, because nothing is
    ever punished. Only the other side's plays are replayed -- replaying our own future plays would leak
    the pro's continuation into a score that is supposed to judge one placement.

    Its limitation, which no amount of care removes: the opponent's recorded plays were a response to the
    PRO's placement, not to our candidate. This is "the opponent does what they actually did", which is a
    better environment than a statue and still not a reactive opponent."""
    end = start_tick + horizon
    t = start_tick
    if opponent == "replay":
        for row in ctx["plays"]:
            if row["side"] == side or row["ability"] or not (start_tick < row["tick"] <= end):
                continue
            if row["tick"] > t:
                step = env.step(row["tick"] - t)
                t = int(step["tick_after"])
                if step["episode"].get("terminated"):
                    return
            di = ctx["index_of"][row["side"]].get(row["attr_card"])
            if di is not None:
                env.act(side=row["side"], deck_index=di, x=row["x"], y=row["y"])
    if end > t:
        env.step(end - t)


def evaluate(env, side: int, horizon: int, mode: str = "v2", advance=None) -> float:''')

s = s.replace("    env.step(horizon)\n    after = env.observe()",
              "    (advance or (lambda: env.step(horizon)))()\n    after = env.observe()")

# 2. thread the branch tick + opponent option through try_cells
s = s.replace("""                base_tick = drive_to(env, ctx, target["play_index"], rd)
                if base_tick is None:
                    continue""",
              """                base_tick = drive_to(env, ctx, target["play_index"], rd)
                if base_tick is None:
                    continue""")
s = s.replace("""                    for (cx, cy) in cells:
                        if drive_to(env, ctx, target["play_index"], rd) is None:
                            continue""",
              """                    for (cx, cy) in cells:
                        bt = drive_to(env, ctx, target["play_index"], rd)
                        if bt is None:
                            continue""")
s = s.replace("                        sc = evaluate(env, row[\"side\"], a.horizon, a.score)",
              "                        sc = evaluate(env, row[\"side\"], a.horizon, a.score,\n"
              "                                      lambda: rollout(env, ctx, row[\"side\"], bt, a.horizon, a.opponent))")
s = s.replace('''    ap.add_argument("--dump-scores", type=Path, default=None)''',
              '''    ap.add_argument("--dump-scores", type=Path, default=None)
    ap.add_argument("--opponent", default="replay", choices=("replay", "none"),
                    help="replay = the other side's recorded plays act during the rollout; none = inert")''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
