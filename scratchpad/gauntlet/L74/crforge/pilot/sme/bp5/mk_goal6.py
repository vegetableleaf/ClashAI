"""goal6.py from goal5.py: more per-row features: ref_before (the reference displaced earlier in the tick), ref_rp (the
reference ran a replan earlier in the tick), ref_since (ticks since the reference changed its own target), u_c / r_c (C rows
of unit and reference at t-1: state, z, timers), u_idx/r_idx (holder order)"""
s = open("/workspace/pilot/bp5/goal5.py").read()
s = s.replace("\x27/workspace/pilot/bp5/work/goal5\x27", "\x27/workspace/pilot/bp5/work/goal6\x27")
a = "        pos[o[\x27t\x27]] = {c[0]: (c[2], c[3], c[4], c[1], c[6]) for c in o[\x27C\x27]}\n"
b = a + "        crow[o[\x27t\x27]] = {c[0]: c[7:] + [k] for k, c in enumerate(o[\x27C\x27])}\n"
assert s.count(a) == 1; s = s.replace(a, b)
s = s.replace("    pos = {}\n    evs = []\n", "    pos = {}\n    crow = {}\n    evs = []\n")
a = "                   \x27x\x27: xv,"
b = """                   \x27ref_before\x27: any(y[0] == \x27disp\x27 and y[1] == pos[t][eid][4] for y in ev[:k]),
                   \x27ref_rp\x27: any(y[0] == \x27replan\x27 and y[1] == pos[t][eid][4] for y in ev[:k]),
                   \x27ref_since\x27: t - ref_since.get(pos[t][eid][4], t),
                   \x27u_c\x27: crow.get(t - 1, {}).get(eid), \x27r_c\x27: crow.get(t - 1, {}).get(pos[t][eid][4]),
""" + a
assert s.count(a) == 1; s = s.replace(a, b)
open("/workspace/pilot/bp5/goal6.py", "w").write(s)
print("ok")
