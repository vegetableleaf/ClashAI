"""Apply the SME_BP_SNAP hook to a copy of sme_live.py (exact-string replace)."""
import sys
p = sys.argv[1]
s = open(p).read()
old = """        else:
            o, an = final
"""
new = """        else:
            o, an = final
            if SNAP:  # A2c-BP: isolated div frames that are crforge's own in-step states (bp_snap.py)
                import bp_snap
                an = bp_snap.reclass(runnable(plan), frames, me, an, o, os.path.join(mo, 'work'))
"""
assert s.count(old) == 1, 'text moved'
s = s.replace(old, new)
old2 = "MIX_PH = int(os.environ.get('SME_BP_MIXPH', '0'))"
assert s.count(old2) == 1
s = s.replace(old2, "SNAP = int(os.environ.get('SME_BP_SNAP', '0'))  # A2c-BP: in-step reads by crforge's own in-step states\n" + old2)
open(p, 'w').write(s)
print('patched', p)
