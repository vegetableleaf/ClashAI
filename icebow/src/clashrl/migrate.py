r"""`run.py import-from OLD` -- take an older installation's work along.

Moving to a new checkout otherwise means hand-copying checkpoints, recordings, screen
templates and the two config files, and it is easy to miss one and then wonder why
nothing recognises anything. This walks an old folder, works out what each file is, and
copies the useful ones across.

Nothing is deleted and nothing existing is overwritten unless `--overwrite` says so; a
file that is already there byte for byte is skipped either way. `--dry-run` lists what
would happen without touching the disk.

    .\\.venv\\Scripts\\python.exe run.py import-from "D:\\old\\ClashAI-main" --dry-run
    .\\.venv\\Scripts\\python.exe run.py import-from "D:\\old\\ClashAI-main"
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

# what to look for, where it goes, and how it is described in the report
GROUPS = [
    ("checkpoints", "data", "*.pt", "trained policies"),
    ("benchmarks", "data", "sim_bench.json", "throughput measurements"),
    ("metrics", "data", "metrics.jsonl", "training history"),
    ("card templates", "templates/cards", "*.png", "hand card templates"),
    ("next templates", "templates/next", "*.png", "next-card templates"),
    ("screen templates", "templates", "*.png", "screen state templates"),
    ("card art", "templates/cardart", "*.png", "card reference pictures"),
]
CONFIGS = [("config/cards.yaml", "deck and card database"),
           ("config/config.yaml", "settings")]


def _digest(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def find_root(start: Path) -> Optional[Path]:
    """Accept either the repo root or the icebow folder, and find the one that has data/."""
    start = Path(start).expanduser()
    if not start.exists():
        return None
    for cand in (start, start / "icebow", start.parent):
        if (cand / "config" / "config.yaml").exists() or (cand / "data").exists():
            return cand
    hits = list(start.glob("*/config/config.yaml"))
    return hits[0].parent.parent if hits else None


def scan(old_root: Path, new_root: Path) -> Dict[str, Any]:
    """What is over there, and what would each file mean here."""
    plan: List[Dict[str, Any]] = []
    for label, rel, pattern, desc in GROUPS:
        src_dir = old_root / rel
        if not src_dir.is_dir():
            continue
        for src in sorted(src_dir.glob(pattern)):
            if not src.is_file():
                continue
            dst = new_root / rel / src.name
            same = dst.exists() and dst.stat().st_size == src.stat().st_size and \
                _digest(dst) == _digest(src)
            plan.append({"group": label, "desc": desc, "src": src, "dst": dst,
                         "bytes": src.stat().st_size,
                         "state": "identical" if same else ("exists" if dst.exists() else "new")})
    for rel, desc in CONFIGS:
        src = old_root / rel
        if src.is_file():
            dst = new_root / rel
            same = dst.exists() and _digest(dst) == _digest(src)
            plan.append({"group": "config", "desc": desc, "src": src, "dst": dst,
                         "bytes": src.stat().st_size,
                         "state": "identical" if same else ("exists" if dst.exists() else "new")})

    sessions = []
    src_sessions = old_root / "data" / "sessions"
    if src_sessions.is_dir():
        for s in sorted(p for p in src_sessions.iterdir() if p.is_dir()):
            size = sum(f.stat().st_size for f in s.rglob("*") if f.is_file())
            dst = new_root / "data" / "sessions" / s.name
            sessions.append({"name": s.name, "src": s, "dst": dst, "bytes": size,
                             "state": "exists" if dst.exists() else "new"})
    return {"plan": plan, "sessions": sessions}


def _human(n: int) -> str:
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if n >= div:
            return f"{n / div:.1f} {unit}"
    return f"{n} B"


def import_from(cfg, old: str, dry_run: bool = False, overwrite: bool = False,
                with_sessions: bool = True, with_config: bool = False) -> None:
    new_root = Path(cfg.root)
    old_root = find_root(Path(old))
    if old_root is None:
        print(f"[import-from] no installation found at {old}.")
        print("[import-from] point it at the old folder, either the repository root or the "
              "icebow folder inside it.")
        return
    if old_root.resolve() == new_root.resolve():
        print("[import-from] that is this installation.")
        return
    print(f"[import-from] reading {old_root}")

    found = scan(old_root, new_root)
    plan, sessions = found["plan"], found["sessions"]
    if not plan and not sessions:
        print("[import-from] nothing usable found over there.")
        return

    # The two config files decide how everything else is interpreted, so they are only
    # taken when explicitly asked for -- silently replacing them would change the deck
    # and the screen calibration of THIS installation.
    if not with_config:
        plan = [p for p in plan if p["group"] != "config"]

    by_group: Dict[str, List[Dict[str, Any]]] = {}
    for item in plan:
        by_group.setdefault(item["group"], []).append(item)

    print("[import-from] found:")
    for group, items in by_group.items():
        new = sum(1 for i in items if i["state"] == "new")
        same = sum(1 for i in items if i["state"] == "identical")
        exists = sum(1 for i in items if i["state"] == "exists")
        total = _human(sum(i["bytes"] for i in items))
        print(f"[import-from]   {group:<18} {len(items):>4} files, {total:>9}  "
              f"({new} new, {exists} already here, {same} identical)")
    if sessions:
        n_new = sum(1 for s in sessions if s["state"] == "new")
        print(f"[import-from]   {'recordings':<18} {len(sessions):>4} folders, "
              f"{_human(sum(s['bytes'] for s in sessions)):>9}  ({n_new} new)")
    if not with_config:
        cfgs = [c for c in CONFIGS if (old_root / c[0]).is_file()]
        if cfgs:
            print("[import-from]   config files are NOT taken by default "
                  "(--with-config takes cards.yaml and config.yaml too)")

    copied = skipped = 0
    for item in plan:
        if item["state"] == "identical":
            skipped += 1
            continue
        if item["state"] == "exists" and not overwrite:
            skipped += 1
            continue
        if not dry_run:
            item["dst"].parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item["src"], item["dst"])
        copied += 1

    sess_copied = 0
    if with_sessions:
        for s in sessions:
            if s["state"] == "exists" and not overwrite:
                continue
            if not dry_run:
                shutil.copytree(s["src"], s["dst"], dirs_exist_ok=True)
            sess_copied += 1

    if dry_run:
        print(f"[import-from] --dry-run: {copied} files and {sess_copied} recordings WOULD be "
              f"copied, {skipped} skipped.")
        print("[import-from] run it again without --dry-run to actually copy.")
        return
    print(f"[import-from] copied {copied} files and {sess_copied} recordings, skipped {skipped} "
          "(already present or identical).")
    if any(i["group"] == "checkpoints" and i["state"] != "identical" for i in plan):
        print("[import-from] the imported policies show up under Checkpoints in the panel. "
              "A checkpoint only fits the deck it was trained for; the panel says so per file.")
    if not with_config:
        print("[import-from] cards.yaml and config.yaml were left as they are. If the old deck "
              "is the one you want, copy those two over as well (--with-config).")
