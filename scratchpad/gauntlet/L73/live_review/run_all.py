"""Compute per-match features for every in-scope live match -> per_match.pkl (consumed by report.py)."""
import pickle
from core import *
from analyze import analyze
xs = load_all()
rows = []
for m, d in xs:
    o = analyze(m, d)
    m2 = dict(m); m2["tower_hp"] = None  # drop bulky timelines
    m2["an"] = o
    rows.append(m2)
pickle.dump(rows, open(HERE + "per_match.pkl", "wb"))
print(len(rows))
