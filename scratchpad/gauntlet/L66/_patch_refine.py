p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()

s = s.replace('''    ap.add_argument("--horizon", type=int, default=120)''',
'''    ap.add_argument("--horizon", type=int, default=120)
    # Coarse candidates alone CANNOT reach the pre-registered exact-cell criterion (<= 0.3 tiles): a
    # 4x6 lattice is nearly state-independent (the first full run used 23 distinct cells across 497
    # states) so 0% agreement was guaranteed by the design, not measured. Stage B re-searches the full
    # lattice within +/-R cells of the best coarse cell, which makes the criterion reachable.
    ap.add_argument("--refine", type=int, default=2, help="stage-B radius in cells; 0 disables")''')

old = """                cands = legal_cells(env, row["side"], di, a.off, a.max_candidates)
                best = None
                for (cx, cy) in cands:
                    if drive_to(env, ctx, target["play_index"], rd) is None:
                        continue
                    ex, ey = cell_to_engine(cx, cy, row["side"], a.off)
                    res = env.act(side=row["side"], deck_index=di, x=ex, y=ey)
                    if not res.get("accepted"):
                        continue
                    sc = evaluate(env, row["side"], a.horizon)
                    if best is None or sc > best[0]:
                        best = (sc, cx, cy)
                if best is None:
                    continue"""
new = """                cands = legal_cells(env, row["side"], di, a.off, a.max_candidates)

                def try_cells(cells):
                    got = None
                    for (cx, cy) in cells:
                        if drive_to(env, ctx, target["play_index"], rd) is None:
                            continue
                        ex, ey = cell_to_engine(cx, cy, row["side"], a.off)
                        res = env.act(side=row["side"], deck_index=di, x=ex, y=ey)
                        if not res.get("accepted"):
                            continue
                        sc = evaluate(env, row["side"], a.horizon)
                        if got is None or sc > got[0]:
                            got = (sc, cx, cy)
                    return got

                best = try_cells(cands)
                n_eval = len(cands)
                if best is not None and a.refine > 0:
                    _, bx, by = best
                    near = [(cx, cy)
                            for cy in range(max(0, by - a.refine), min(GRID_Y, by + a.refine + 1))
                            for cx in range(max(0, bx - a.refine), min(GRID_X, bx + a.refine + 1))
                            if (cx, cy) != (bx, by)]
                    n_eval += len(near)
                    fine = try_cells(near)
                    if fine is not None and fine[0] > best[0]:
                        best = fine
                if best is None:
                    continue"""
assert s.count(old) == 1
s = s.replace(old, new, 1)
s = s.replace('''"score": round(sc, 1), "candidates": len(cands)}) + chr(10))''',
              '''"score": round(sc, 1), "candidates": n_eval}) + chr(10))''')
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
