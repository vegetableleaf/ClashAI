p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()
s = s.replace('''    ap.add_argument("--score", default="v2", choices=("v1", "v2"), help="v1 rewarded hiding; see evaluate()")''',
'''    ap.add_argument("--score", default="v2", choices=("v1", "v2"), help="v1 rewarded hiding; see evaluate()")
    # Writes EVERY candidate's score, not just the winner. The bench output records only the argmax, which
    # cannot distinguish "the search found a clear optimum at the back" from "most candidates tied and the
    # first one wins, and the first one is the lowest cy" (§5cs.88 D). Those need opposite fixes.
    ap.add_argument("--dump-scores", type=Path, default=None)''')
old = """                def try_cells(cells):
                    got = None
                    for (cx, cy) in cells:"""
new = """                def try_cells(cells, stage=""):
                    got = None
                    for (cx, cy) in cells:"""
assert s.count(old) == 1
s = s.replace(old, new, 1)
old2 = """                        sc = evaluate(env, row["side"], a.horizon, a.score)
                        if got is None or sc > got[0]:
                            got = (sc, cx, cy)
                    return got"""
new2 = """                        sc = evaluate(env, row["side"], a.horizon, a.score)
                        if dump is not None:
                            dump.write(json.dumps({"tag": tag, "tick": row["tick"], "stage": stage,
                                                   "cx": cx, "cy": cy, "score": round(sc, 2)}) + chr(10))
                        if got is None or sc > got[0]:
                            got = (sc, cx, cy)
                    return got"""
assert s.count(old2) == 1
s = s.replace(old2, new2, 1)
s = s.replace("                best = try_cells(cands)", '                best = try_cells(cands, "coarse")')
s = s.replace("                    fine = try_cells(near)", '                    fine = try_cells(near, "fine")')
s = s.replace("""    env = NativeRoyaleEnv(port=a.port, timeout=180.0)""",
              """    env = NativeRoyaleEnv(port=a.port, timeout=180.0)
    dump = a.dump_scores.open("w", encoding="utf-8") if a.dump_scores else None""")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
