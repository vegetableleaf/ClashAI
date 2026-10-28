import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
old = """                fast = v > GK_STEP
"""
new = """                fast = v > GK_STEP
                if fast and GK8 and dt == 1:
                    # round 8.6: a one-tick pair whose speed does not hold over two ticks is a mislabelled frame
                    # (bp_rules.not_a_dash's test). Taken as a burst it also set lastcast and hid the real dash 8 ticks
                    # later (001141@5389 fake, 5399 real; bp_rules then dropped the fake, leaving no cast).
                    c = min((t for t in ts if t >= a + 2), default=None)
                    pc = [f for f in frames[c]['E'] if f[0] == side and f[3] == GK_ID] if c is not None else []
                    if pc:
                        q2 = min(pc, key=lambda f: abs(f[1] - q[1]) + abs(f[2] - q[2]))
                        fast = (abs(q2[1] - q[1]) + abs(q2[2] - q[2])) / (c - a) > GK_STEP
"""
assert s.count(old) == 1
s = s.replace(old, new)
old2 = "GK_DASH = int(os.environ.get('SME_GK', '0'))"
assert s.count(old2) == 1
s = s.replace(old2, "GK8 = int(os.environ.get('SME_GK8', '0'))  # round 8.6: a mislabelled one-tick pair is no dash burst\n" + old2)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('ok')
