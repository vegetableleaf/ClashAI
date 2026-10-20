import re, sys
def load(p):
    out = {}
    for line in open(p):
        m = re.match(r'^(\S[\w ]*?)\s{2,}(\d+)\s+(\d)\s+(\d+)\s+([\d.]+)', line)
        if m:
            out[(m.group(1).strip(), m.group(3))] = (int(m.group(4)), float(m.group(5)))
    return out
a, b = load(sys.argv[1]), load(sys.argv[2])
rows = sorted(a, key=lambda k: -a[k][0])
print(f"{'card':24s} fly   n   A     B    delta")
for k in rows:
    if k in b:
        print(f"{k[0]:24s} {k[1]:>3} {a[k][0]:4d} {a[k][1]:.2f}  {b[k][1]:.2f}  {b[k][1]-a[k][1]:+.2f}")
