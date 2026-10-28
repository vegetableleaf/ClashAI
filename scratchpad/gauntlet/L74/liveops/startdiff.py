"""Key-by-key diff of two live logs' start events (flat, nested keys joined by '.')."""
import json, sys
def flat(d, p=""):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, p + k + "."))
        else:
            out[p + k] = v
    return out
a, b = (flat(json.loads(open(f, "rb").readline())) for f in sys.argv[1:3])
for k in sorted(set(a) | set(b)):
    if a.get(k) != b.get(k):
        print(k, "|", str(a.get(k))[:90], "|", str(b.get(k))[:90])
