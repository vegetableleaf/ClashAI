"""OPP-SIEGE2 PROBE patch for the POD code copy only (/workspace/siege/opp/cb2, never committed to pipeline/):
  SIEGE_CELL_T=x   timing-head seats draw the CELL at temperature x (card keeps cfg T); unset = unchanged.
  SIEGE_TGT=1      hab samples get s[8] = [[uid, team, kind, target_uid], ...] for every engine entity (read only).
python patch_pod.py CB_DIR"""
import sys
from pathlib import Path

cb = Path(sys.argv[1])
p = cb / "pipeline/decision_options.py"
s = p.read_text()
old = "    c = np.asarray(cell_logits_fn(slot), dtype=np.float64) / T\n"
new = ("    import os as _os                          # OPP-SIEGE2 probe (pod copy only)\n"
       "    c = np.asarray(cell_logits_fn(slot), dtype=np.float64) / float(_os.environ.get('SIEGE_CELL_T') or T)\n")
assert s.count(old) == 1
p.write_text(s.replace(old, new))
p = cb / "pipeline/search_s0.py"
s = p.read_text()
old = "            round(float(bs.my_elixir), 3), tw, en, xb]\n"
new = ("            round(float(bs.my_elixir), 3), tw, en, xb] + ([[[int(e.uid), int(e.team), int(e.kind), int(e.target_uid)]\n"
       "            for e in m.env.core.state().entities]] if __import__('os').environ.get('SIEGE_TGT') else [])   # OPP-SIEGE2 probe\n")
assert s.count(old) == 1
p.write_text(s.replace(old, new))
print("patched", cb)
