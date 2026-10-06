"""Rebuild the whole live-match review (read-only on logs): python run_review.py   (use icebow/.venv/Scripts/python.exe, repo root not required)
load.py -> cache.pkl (decision/frame state per log) ; run_all.py -> per_match.pkl (core.py + analyze.py) ; report.py -> results.json ; conceded.py -> conceded_first.json"""
import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
for s in ("load.py", "run_all.py", "report.py", "conceded.py"):
    r = subprocess.run([sys.executable, s], cwd=here, capture_output=True, text=True)
    print("==", s, r.returncode); print(r.stdout[-1500:]); 
    if r.returncode: print(r.stderr[-1500:]); sys.exit(1)
