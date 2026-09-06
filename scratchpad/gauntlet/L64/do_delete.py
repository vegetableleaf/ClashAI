"""L64 cleanup step 4: delete exactly the manifest's DELETE set (tracked -> git rm --cached first)."""
import csv, os, subprocess, zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\benpe\ClashBot")
L64 = ROOT / "scratchpad/gauntlet/L64"
ZIP = Path(r"C:\Users\benpe\ClashBot_archive\scratch_2026-09-06.zip")

rows = [r for r in csv.DictReader(open(L64 / "cleanup_manifest.csv", encoding="utf-8")) if r["class"] == "DELETE"]
paths = [r["path"] for r in rows]
assert all("/data/" not in "/" + p and p.startswith("scratchpad/") for p in paths)
with zipfile.ZipFile(ZIP) as z:  # refuse to delete anything not in the verified backup
    names = set(z.namelist())
missing = [p for p in paths if p not in names]
assert not missing, f"{len(missing)} paths not in backup zip"

tracked = set(subprocess.run(["git", "ls-files", "-z", "scratchpad"], cwd=ROOT, capture_output=True).stdout.decode().split("\0"))
tr = [p for p in paths if p in tracked]
spec = L64 / "_rm_pathspec.txt"
spec.write_text("\n".join(tr) + "\n", encoding="utf-8")
r = subprocess.run(["git", "rm", "-q", "--cached", "--pathspec-from-file=" + str(spec)], cwd=ROOT, capture_output=True, text=True)
print("git rm --cached rc", r.returncode, (r.stderr or "")[:300])

deleted = 0; errs = []
for p in paths:
    try:
        os.remove(ROOT / p); deleted += 1
    except OSError as e:
        errs.append(f"{p}: {e}")
# prune now-empty directories under scratchpad (never the kept ones -- an empty dir has nothing to keep)
pruned = 0
for d in sorted(ROOT.glob("scratchpad/**/"), key=lambda x: -len(str(x))):
    if d.name in ("L64",) or "data" in d.parts:
        continue
    try:
        if d.is_dir() and not any(d.iterdir()):
            d.rmdir(); pruned += 1
    except OSError:
        pass
print(f"tracked_git_rm={len(tr)} deleted={deleted} errors={len(errs)} pruned_dirs={pruned}")
for e in errs[:5]:
    print("ERR", e)
