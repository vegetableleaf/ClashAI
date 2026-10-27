"""A2c-BP5: goal5.py from bp4/goal_census.py: AimRun5 (rpx event after each replan) and per row the rpx variants:
x = {e1..e6, acq: variant goal}, acq_age = t - acquisition tick"""
s = open("/workspace/pilot/bp4/goal_census.py").read()
s = s.replace("/workspace/pilot/bp3/build_aim\x27, \x27AimRun\x27", "/workspace/pilot/bp5/build_aim5\x27, \x27AimRun5\x27")
s = s.replace("\x27/workspace/pilot/bp4/work/goal\x27", "\x27/workspace/pilot/bp5/work/goal5\x27")
a = "            rx, ry, R = v[8], v[9], v[11]\n"
b = a + """            rp = next((x for x in ev[k + 1:k + 2] if x[0] == "rpx" and x[1] == eid and len(x) > 3), None)
            xv = None if rp is None else dict(zip(("e1", "e2", "e3", "e4", "e5", "e6", "acq"), rp[8:15]))
            acq_age = None if rp is None else t - 1 - rp[15]
            chk = None if rp is None else rp[16] == goal
"""
assert s.count(a) == 1; s = s.replace(a, b)
a = "                   \x27ref_id\x27: pos[t][eid][4],"
b = "                   \x27x\x27: xv, \x27acq_age\x27: acq_age, \x27chk\x27: chk, \x27unit\x27: None if rp is None else rp[5:7],\n" + a
assert s.count(a) == 1; s = s.replace(a, b)
assert "AimRun5" in s and "goal5" in s
open("/workspace/pilot/bp5/goal5.py", "w").write(s)
print("ok")
