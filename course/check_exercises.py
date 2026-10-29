"""Check every exercise: its solution must PASS and its starter must FAIL (unless "starter_passes": true).
Run with the course venv:  course/.venv/Scripts/python.exe course/check_exercises.py [LESSON_ID ...]"""
import json, sys
from pathlib import Path

import server

bad = 0
files = sorted((server.HERE / "exercises").glob("*.json"))
want = set(sys.argv[1:])
for f in files:
    if want and f.stem not in want:
        continue
    for ex in json.loads(f.read_text(encoding="utf-8")):
        tag = f"{f.stem}/{ex.get('id')}"
        missing = [k for k in ("id", "title", "prompt", "starter", "solution") if not ex.get(k)]
        if missing or not (ex.get("tests") or ex.get("expect")):
            print(f"FORMAT {tag}: missing {missing or 'tests/expect'}"); bad += 1; continue
        ok, out = server.run_code(ex, ex["solution"])
        if not ok:
            print(f"SOLUTION FAILS {tag}:\n{out[-1500:]}"); bad += 1
        s_ok, _ = server.run_code(ex, ex["starter"])
        if s_ok and not ex.get("starter_passes"):
            print(f"STARTER PASSES {tag} (the check does not test anything the learner must write)"); bad += 1
lessons = {p.stem for p in (server.HERE / "lessons").glob("*.md")}
print(f"{'OK' if not bad else 'PROBLEMS: ' + str(bad)} -- {len(files)} exercise files, {len(lessons)} lesson files")
sys.exit(1 if bad else 0)
