p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()
old = """                        if got is None or sc > got[0]:
                            got = (sc, cx, cy)
                    return got"""
new = """                        # RANDOM tie-break among equal maxima (reservoir), not "first wins".
                        # Measured (§5cs.89): ~40% of candidates tie at the maximum and in the median
                        # state the winner's cy equalled the LOWEST cy offered -- candidates are generated
                        # ascending in cy, so "first wins" silently resolved every plateau to the back of
                        # our own half. That, not the objective, produced the 12.5-tile bias.
                        if got is None or sc > got[0]:
                            got = (sc, cx, cy); n_tied = 1
                        elif sc == got[0]:
                            n_tied += 1
                            if rng.random() < 1.0 / n_tied:
                                got = (sc, cx, cy)
                    return got"""
assert s.count(old) == 1
s = s.replace(old, new, 1)
s = s.replace("""                def try_cells(cells, stage=\"\"):
                    got = None""",
              """                def try_cells(cells, stage=\"\"):
                    got = None; n_tied = 0""")
s = s.replace("import time\n", "import random\nimport time\n", 1)
s = s.replace("""    env = NativeRoyaleEnv(port=a.port, timeout=180.0)""",
              """    rng = random.Random(a.seed)
    env = NativeRoyaleEnv(port=a.port, timeout=180.0)""")
open(p, "w", encoding="utf-8", newline="\n").write(s)
print("ok")
