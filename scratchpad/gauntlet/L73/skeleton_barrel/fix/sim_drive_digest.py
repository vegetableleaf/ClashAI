"""Verifier driver: run_screen with per-call digests of extrapolate() output and to_tokens() output."""
import hashlib, json, os, sys
ROOT = os.path.abspath(sys.argv[1]); TAG = sys.argv[2]; rest = sys.argv[3:]
sys.path.insert(0, ROOT)
try:
    import ctypes; assert ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception as e:
    print("nice failed", e)
import numpy as np
import pipeline.extrapolate as X, pipeline.e1_eval as E
H = {"ext": hashlib.sha256(), "tok": hashlib.sha256()}; N = {"ext": 0, "tok": 0, "pred": 0, "pend_max": 0}
_ext, _tt = X.extrapolate, E.to_tokens
def ext(*a, **k):
    out = _ext(*a, **k)
    H["ext"].update(json.dumps(out, sort_keys=True, default=repr).encode()); N["ext"] += 1
    N["pred"] += sum(1 for e in out.get("entities", ()) if str(e.get("entity_id", e.get("address", ""))).startswith("predicted_drop"))
    if k.get("drops"): N["pend_max"] = max(N["pend_max"], len(k["drops"]))
    return out
def tt(*a, **k):
    tok, mask, sc = _tt(*a, **k)
    for t in (tok, mask, sc): H["tok"].update(np.ascontiguousarray(np.asarray(t)).tobytes())
    N["tok"] += 1
    return tok, mask, sc
X.extrapolate, E.to_tokens = ext, tt
sys.argv = ["run_screen.py"] + rest
import importlib.util
spec = importlib.util.spec_from_file_location("rs", os.path.join(ROOT, "scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py"))
rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)
rc = rs.main(rest)
print("DIGEST", TAG, json.dumps({k: v.hexdigest() for k, v in H.items()}), json.dumps(N), flush=True)
