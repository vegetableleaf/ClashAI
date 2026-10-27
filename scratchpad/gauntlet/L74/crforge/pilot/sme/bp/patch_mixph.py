"""Apply the SME_BP_MIXPH change to a copy of sme_live.py (exact-string replace; fails loudly if the text moved)."""
import sys
p = sys.argv[1]
s = open(p).read()
old_flag = "STEP_CLOCK = int(os.environ.get('SME_STEP_CLOCK', '0'))  # round 6.1: our elixir as the step clock\n"
new_flag = old_flag + ("MIX_PH = int(os.environ.get('SME_BP_MIXPH', '0'))  # A2c-BP: torn_mixed reads the hp -1 placeholder "
                       "as the main comparison does (round 2.4)\n")
old = """        r, a, b = canon_live(frames[t], me), sim_canon(by[t], me), sim_canon(by[t + 1], me)
        if all(x in a[k] or x in b[k] for k in 'TUPA' for x in r[k]) and \\"""
new = """        r, a, b = canon_live(frames[t], me), sim_canon(by[t], me), sim_canon(by[t + 1], me)
        # A2c-BP (SME_BP_MIXPH): a recorded body at hp -1 is the reader's placeholder (round 2.4), held by a sim body at
        # its very (side, x, y) at t or t+1, whatever that body's hp; the main comparison already fills it the same way
        pos = {k: {y[:3] for y in a[k] + b[k]} for k in 'TU'} if MIX_PH else {}
        if all(x in a[k] or x in b[k] or (k in pos and x[3] == -1 and x[:3] in pos[k]) for k in 'TUPA' for x in r[k]) and \\"""
assert s.count(old_flag) == 1 and s.count(old) == 1, 'text moved'
s = s.replace(old_flag, new_flag).replace(old, new)
open(p, 'w').write(s)
print('patched', p)
