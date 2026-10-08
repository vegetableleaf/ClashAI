"""Loss review with and without the body-value fix, side by side, WITHOUT touching the loss review's own ledger / rows / report:
reparses every live log into econ2/out/review_fix<0|1>/ (laptop, single process, below-normal priority via review.py).
  icebow/.venv/Scripts/python.exe review_ab.py 1     (then 0)"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/") + "/"
fix = sys.argv[1]
os.environ["REVIEW_BODY_FIX"] = fix
sys.path.insert(0, HERE + "../loss_review")
import review as V
out = HERE + f"out/review_fix{fix}/"
os.makedirs(out, exist_ok=True)
V.LEDGER, V.ROWS, V.REPORT = out + "analyzed.txt", out + "matches.jsonl", out + "report.md"
V.run(None, False, True)
