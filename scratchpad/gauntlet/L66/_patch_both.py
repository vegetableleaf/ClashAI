import re, pathlib
p = pathlib.Path("pipeline/s3_teacher.py"); s = p.read_text(encoding="utf-8")
old_roll = '''    end = start_tick + horizon
    t = start_tick
    if opponent == "replay":
        for row in ctx["plays"]:
            if row["side"] == side or row["ability"] or not (start_tick < row["tick"] <= end):
                continue'''
new_roll = '''    end = start_tick + horizon
    t = start_tick
    if opponent in ("replay", "both"):
        for row in ctx["plays"]:
            # "both" (L66m diagnostic ONLY, never a teacher setting): our own recorded follow-ups are
            # replayed too. That leaks the pro's continuation into the score on purpose -- it asks whether
            # the pro's cell scores well GIVEN the pro's own next plays, which separates "the objective is
            # wrong" from "one placement without its sequence is what is wrong" (§5cs.90 C, third cause).
            if (opponent == "replay" and row["side"] == side) or row["ability"] \
                    or not (start_tick < row["tick"] <= end):
                continue'''
assert old_roll in s; s = s.replace(old_roll, new_roll)
old_arg = '''    ap.add_argument("--opponent", default="replay", choices=("replay", "none"),'''
new_arg = '''    ap.add_argument("--include-pro", action="store_true",
                    help="add the pro's own cell to the candidate set and report its score and rank (diagnostic)")
    ap.add_argument("--opponent", default="replay", choices=("replay", "none", "both"),'''
assert old_arg in s; s = s.replace(old_arg, new_arg)
old_c = '''                cands = legal_cells(env, row["side"], di, a.off, a.max_candidates)
'''
new_c = '''                cands = legal_cells(env, row["side"], di, a.off, a.max_candidates)
                pro_cell = (min(GRID_X - 1, int(row["x"] * GRID_X)), min(GRID_Y - 1, int(row["y"] * GRID_Y)))
                if a.include_pro and pro_cell not in cands:
                    cands = list(cands) + [pro_cell]
                scored: dict[tuple[int, int], float] = {}
'''
assert old_c in s; s = s.replace(old_c, new_c)
old_d = '''                        if dump is not None:
                            dump.write('''
new_d = '''                        scored[(cx, cy)] = sc
                        if dump is not None:
                            dump.write('''
assert old_d in s; s = s.replace(old_d, new_d)
old_w = '''                sc, cx, cy = best
                fh.write(json.dumps({"tag": tag, "tick": row["tick"], "slot": row["slot"],
                                     "px": float(cx) + a.off, "py": float(cy) + a.off,
                                     "score": round(sc, 1), "candidates": n_eval}) + chr(10))'''
new_w = '''                sc, cx, cy = best
                out_row = {"tag": tag, "tick": row["tick"], "slot": row["slot"],
                           "px": float(cx) + a.off, "py": float(cy) + a.off,
                           "score": round(sc, 1), "candidates": n_eval}
                if a.include_pro and pro_cell in scored:
                    ps = scored[pro_cell]
                    out_row.update({"pro_cx": pro_cell[0], "pro_cy": pro_cell[1], "pro_score": round(ps, 1),
                                    "pro_rank": 1 + sum(1 for v in scored.values() if v > ps),
                                    "n_scored": len(scored), "best_score": round(max(scored.values()), 1)})
                fh.write(json.dumps(out_row) + chr(10))'''
assert old_w in s; s = s.replace(old_w, new_w)
p.write_text(s, encoding="utf-8"); print("patched")
