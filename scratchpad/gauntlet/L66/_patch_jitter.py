import pathlib
p = pathlib.Path("pipeline/s3_teacher.py"); s = p.read_text(encoding="utf-8")
old = '''def rollout(env, ctx, side: int, start_tick: int, horizon: int, opponent: str) -> None:'''
new = '''def rollout(env, ctx, side: int, start_tick: int, horizon: int, opponent: str, jit=None) -> None:'''
assert old in s; s = s.replace(old, new)
old = '''    end = start_tick + horizon
    t = start_tick
    if opponent in ("replay", "both"):
        for row in ctx["plays"]:'''
new = '''    end = start_tick + horizon
    t = start_tick
    if opponent in ("replay", "both"):
        plays = ctx["plays"]
        if jit is not None:
            # L66n oracle-future test: the OTHER side's recorded plays are perturbed in time and position by
            # a generator seeded per (state, future k) -- NOT per candidate -- so every candidate in a state
            # faces the same K sampled futures and the ranking compares like with like (§5cs.93 G).
            J, S, seed = jit
            jr = random.Random(seed)
            plays = []
            for row in ctx["plays"]:
                if row["side"] == side or row["ability"]:
                    plays.append(row); continue
                r2 = dict(row)
                r2["tick"] = max(start_tick + 1, row["tick"] + jr.randint(-J, J))
                r2["x"] = min(17999, max(0, row["x"] + jr.gauss(0.0, S * 1000.0)))
                r2["y"] = min(31999, max(0, row["y"] + jr.gauss(0.0, S * 1000.0)))
                plays.append(r2)
            plays.sort(key=lambda r: r["tick"])
        for row in plays:'''
assert old in s; s = s.replace(old, new)
old = '''    ap.add_argument("--include-pro", action="store_true",'''
new = '''    ap.add_argument("--futures", type=int, default=1, help="K sampled opponent futures per candidate (mean score)")
    ap.add_argument("--jitter-ticks", type=int, default=0, help="opponent play tick shift ~ U(-J, J)")
    ap.add_argument("--jitter-tiles", type=float, default=0.0, help="opponent play position noise sd, tiles")
    ap.add_argument("--include-pro", action="store_true",'''
assert old in s; s = s.replace(old, new)
old = '''                    for (cx, cy) in cells:
                        bt = drive_to(env, ctx, target["play_index"], rd)
                        if bt is None:
                            continue
                        ex, ey = cell_to_engine(cx, cy, row["side"], a.off)
                        res = env.act(side=row["side"], deck_index=di, x=ex, y=ey)
                        if not res.get("accepted"):
                            continue
                        sc = evaluate(env, row["side"], a.horizon, a.score,
                                      lambda: rollout(env, ctx, row["side"], bt, a.horizon, a.opponent))'''
new = '''                    for (cx, cy) in cells:
                        ex, ey = cell_to_engine(cx, cy, row["side"], a.off)
                        parts = []
                        for k in range(a.futures):
                            bt = drive_to(env, ctx, target["play_index"], rd)
                            if bt is None:
                                break
                            res = env.act(side=row["side"], deck_index=di, x=ex, y=ey)
                            if not res.get("accepted"):
                                break
                            jit = None
                            if a.jitter_ticks or a.jitter_tiles:
                                jit = (a.jitter_ticks, a.jitter_tiles,
                                       hash((tag, row["tick"], k, a.seed)) & 0xFFFFFFFF)
                            parts.append(evaluate(env, row["side"], a.horizon, a.score,
                                                  lambda: rollout(env, ctx, row["side"], bt, a.horizon,
                                                                  a.opponent, jit)))
                        if len(parts) < a.futures:
                            continue
                        sc = sum(parts) / len(parts)'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); print("patched")
