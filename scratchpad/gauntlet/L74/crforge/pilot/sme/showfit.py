"""Print a fit log compactly: python3 showfit.py fitA.log [first_event]"""
import json, sys
lo = int(sys.argv[2]) if len(sys.argv) > 2 else 0
for l in open(sys.argv[1]):
    try:
        d = json.loads(l)
    except ValueError:
        print(l[:300].rstrip()); continue
    if d.get('event', 0) < lo: continue
    print(d.get('event'), d.get('side'), d.get('card'), d.get('t'), d.get('anchor'), d.get('R'), d.get('pt'), d.get('unit'),
          d.get('window_mismatch'), d.get('ties'), d.get('error', '')[:200])
