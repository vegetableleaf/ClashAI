"""L64 cleanup step 3: zip every DELETE-class path from the manifest to ClashBot_archive, then verify."""
import csv, os, random, zipfile
from pathlib import Path

ROOT = Path(r"C:\Users\benpe\ClashBot")
MAN = ROOT / "scratchpad/gauntlet/L64/cleanup_manifest.csv"
ARCH = Path(r"C:\Users\benpe\ClashBot_archive")
ARCH.mkdir(exist_ok=True)
ZIP = ARCH / "scratch_2026-09-06.zip"

rows = [r for r in csv.DictReader(open(MAN, encoding="utf-8")) if r["class"] == "DELETE"]
assert all("/data/" not in "/" + r["path"] for r in rows), "data/ path in DELETE set -- abort"
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for r in rows:
        z.write(ROOT / r["path"], arcname=r["path"])

with zipfile.ZipFile(ZIP) as z:
    infos = {i.filename: i for i in z.infolist()}
    bad = z.testzip()
n_ok = sum(1 for r in rows if r["path"] in infos and infos[r["path"]].file_size == int(r["bytes"]))
print(f"zip={ZIP} bytes={ZIP.stat().st_size:,} entries={len(infos)} manifest_delete={len(rows)} size_match={n_ok} testzip_bad={bad}")
random.seed(64)
for r in random.sample(rows, 3):
    i = infos[r["path"]]
    print(f"spot {r['path']}: manifest {r['bytes']} zip {i.file_size} disk {(ROOT / r['path']).stat().st_size}")
