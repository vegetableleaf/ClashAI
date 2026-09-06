"""L64 cleanup: classify every file under scratchpad/ into KEEP / DELETE and write cleanup_manifest.csv."""
import csv, os, sys
from pathlib import Path

ROOT = Path(r"C:\Users\benpe\ClashBot")
SP = ROOT / "scratchpad"
OUT = SP / "gauntlet" / "L64" / "cleanup_manifest.csv"

BULK_EXT = {".json", ".jsonl", ".txt", ".log", ".pyc", ".png", ".jpg", ".csv", ".err", ".out",
            ".npz", ".mp4", ".progress", ".wav", ".html", ".bin", ".elf"}
KEEP_EXT = {".md", ".py", ".pt", ".sh", ".ps1", ".yaml", ".yml", ".npy"}
REF_KEEP = {  # files referenced by HANDOFF/GAUNTLET_LOG tails or tracked code
    "gauntlet/L12/stage_timer.json", "gauntlet/L61/crawl_icebow_wave4.log",
    "gauntlet/L59/reward_ref.npy", "gauntlet/ext/usable_replays.json",
    "gauntlet/ext/cr_sandbox_internals.md", "gauntlet/L17/wiki_Hidden_card_stats",
}
KEEP_DIRS = ("gauntlet/ext/corpus_v3/", "gauntlet/ext/batch_v2/", "gauntlet/ext/re/",
             "gauntlet/L62/", "gauntlet/L63/", "gauntlet/L64/")
DELETE_DIRS_ALL = ("__pycache__/", "ceiling/", "gauntlet/ext/batch/")
PT_DIRS = ("ab/", "ab2/", "adv/", "sweep/", "bb/")


def classify(rel: str, ext: str):
    if "/data/" in "/" + rel or rel.startswith("data/"):
        return "KEEP", "guardrail: data/ never touched"
    if ext == ".pt":
        return "KEEP", "checkpoint: never delete weights"
    if rel in REF_KEEP:
        return "KEEP", "referenced by HANDOFF/GAUNTLET_LOG tail or tracked code"
    for d in KEEP_DIRS:
        if rel.startswith(d):
            return "KEEP", f"kept directory {d}"
    for d in DELETE_DIRS_ALL:
        if rel.startswith(d):
            return ("KEEP", "instrument in old dir") if ext in (".py", ".sh", ".md") else ("DELETE", f"old-pipeline dir {d}")
    top = rel.split("/")[0]
    if "/" not in rel:  # scratchpad root
        if rel.startswith("_") and ext in (".sh", ".out", ".txt", ".md"):
            return "DELETE", "loose _* scratch (owner list)"
        if ext in BULK_EXT:
            return "DELETE", "root loop bulk (L1-L61 result/log/corpus)"
        return "KEEP", "root instrument/config/report"
    if top + "/" in PT_DIRS and ext in KEEP_EXT:
        return "KEEP", f"{top}/ config/instrument kept with its .pt"
    if top + "/" in PT_DIRS:
        return "DELETE", f"{top}/ old A/B or sweep bulk (its .pt kept)"
    if rel.startswith("gauntlet/ext/engine_view/"):
        if ext in (".mp4", ".png"):
            return "DELETE", "render output of L62/live_view.py, regenerable"
        return "KEEP", "engine_view result json/py/log cited in 5cs.50"
    if rel.startswith("gauntlet/ext/dump/"):
        if ext in (".py", ".sh", ".md", ".c", ".h"):
            return "KEEP", "dump/ script or source"
        return "DELETE", "libg memory dump, regenerable via dump_libg.sh"
    if rel.startswith("gauntlet/ext/"):
        base = rel.split("/")[-1]
        if base.startswith("replay_") and ext in (".json", ".html"):
            return "DELETE", "v1 recording/view, duplicated in batch_v2 / regenerable"
        if ext in (".log", ".err") or base.startswith("_t_"):
            return "DELETE", "service/probe log"
        return "KEEP", "ext loose script/record"
    if rel.startswith("gauntlet/L"):
        if rel.count("/") == 1:  # loose gauntlet/L2_* files
            return ("DELETE", "loose gauntlet log") if ext in BULK_EXT else ("KEEP", "loose gauntlet script")
        if ext in KEEP_EXT:
            return "KEEP", "L<N> instrument/record (md/py/sh/ps1/yaml/npy)"
        if ext in BULK_EXT:
            return "DELETE", "L1-L61 loop bulk"
        return "KEEP", "unknown extension, unsure -> keep"
    return "KEEP", "unclassified, unsure -> keep"


rows = []
for p in sorted(SP.rglob("*")):
    if not p.is_file():
        continue
    rel = p.relative_to(SP).as_posix()
    if "/data/" in "/" + rel:
        continue  # never list
    cls, why = classify(rel, p.suffix.lower())
    rows.append(("scratchpad/" + rel, p.stat().st_size, cls, "delete" if cls == "DELETE" else "keep", why))

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["path", "bytes", "class", "action", "reason"])
    w.writerows(rows)

d = [r for r in rows if r[2] == "DELETE"]; k = [r for r in rows if r[2] == "KEEP"]
print(f"files={len(rows)} DELETE={len(d)} bytes={sum(r[1] for r in d):,} KEEP={len(k)} bytes={sum(r[1] for r in k):,}")
