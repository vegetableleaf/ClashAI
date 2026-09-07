p = "pipeline/s3_teacher.py"
s = open(p, encoding="utf-8").read()
old = """    if len(ok) > max_candidates:                          # even subsample, not the first N
        stride = len(ok) / max_candidates
        ok = [ok[int(i * stride)] for i in range(max_candidates)]
    return ok"""
new = """    if len(ok) > max_candidates:
        # 2-D STRATIFIED, not a 1-D stride. Striding this row-major list collapses the candidate set
        # onto a single column whenever the stride is near a multiple of GRID_X (=36): the first run at
        # max_candidates=4 proposed px=0.5 for all six states, i.e. cx=0 every time. A teacher that can
        # only offer the left edge cannot agree with a pro, and the gate would then be measuring the
        # sampler rather than the search. Cover the legal region's bounding box instead.
        xs = [c[0] for c in ok]; ys = [c[1] for c in ok]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        aspect = max(1e-6, (x1 - x0 + 1) / max(1, (y1 - y0 + 1)))
        nx = max(1, int(round((max_candidates * aspect) ** 0.5)))
        ny = max(1, int(round(max_candidates / nx)))
        legal = set(ok)
        picked: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for iy in range(ny):
            for ix in range(nx):
                tx = x0 + (x1 - x0) * (ix + 0.5) / nx
                ty = y0 + (y1 - y0) * (iy + 0.5) / ny
                best, bd = None, None
                for c in ok:                              # nearest LEGAL cell to this lattice point
                    d = (c[0] - tx) ** 2 + (c[1] - ty) ** 2
                    if bd is None or d < bd:
                        best, bd = c, d
                if best is not None and best not in seen:
                    seen.add(best); picked.append(best)
        ok = picked or ok[:max_candidates]
    return ok"""
assert s.count(old) == 1
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new, 1))
print("ok")
