"""Download the FirstLight IL_Replay parquet parts listed in a manifest -- pure standard library, runs on Windows
PowerShell (no Git Bash, no curl).

Port of the old scratchpad/gauntlet/L67/_hf_dl.sh. For every manifest file whose path starts with --prefix it:
  * skips the file when the local copy already has the manifest's size AND sha256 (so a re-run resumes),
  * otherwise downloads to <file>.part, checks size + sha256, and only then renames it into place,
  * retries a failed or corrupt download (--retries), and deletes a file that still fails.
It ends with `DONE ok N bad M` and exits non-zero when any file is bad.

Files land at <dest>/<manifest path>, e.g. data/hf/replays/part-000000.parquet. The default --dest (data/hf at the
repo root) is gitignored by the `data/` rule in .gitignore, so ~825 MB never gets committed.

usage (from the repo root):
  icebow\\.venv\\Scripts\\python.exe tools\\hf_download.py --dry-run     # list what would be fetched, no network
  icebow\\.venv\\Scripts\\python.exe tools\\hf_download.py               # fetch (or resume) all 52 replay parts
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import sys
import time
import urllib.request
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DEFAULT_MANIFEST = HERE / "hf_manifest.json"
DEFAULT_DEST = REPO / "data" / "hf"
DEFAULT_BASE_URL = "https://huggingface.co/datasets/VanguardX101/IL_Replay/resolve/main/"
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def local_ok(path: Path, size: int, sha: str) -> bool:
    """True when the file exists with exactly the manifest's size and sha256."""
    return path.is_file() and path.stat().st_size == size and sha256_of(path) == sha


def safe_rel(p: str) -> PurePosixPath:
    """A manifest path as a relative path that cannot escape --dest."""
    rel = PurePosixPath(p)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise SystemExit(f"manifest path {p!r} is not a plain relative path")
    return rel


def fetch(url: str, part: Path, timeout: float) -> tuple[int, str]:
    """Stream url into part; return (bytes written, sha256)."""
    h = hashlib.sha256()
    n = 0
    req = urllib.request.Request(url, headers={"User-Agent": "ClashBot-tools/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp, part.open("wb") as out:
        for block in iter(lambda: resp.read(CHUNK), b""):
            out.write(block)
            h.update(block)
            n += len(block)
    return n, h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download + sha256-verify the HF replay parquet parts (resumable).")
    ap.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="manifest json (default: tools/hf_manifest.json)")
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST, help="download folder (default: <repo>/data/hf, gitignored)")
    ap.add_argument("--prefix", default="replays/", help="only manifest paths starting with this (default: replays/)")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="URL each manifest path is appended to")
    ap.add_argument("--retries", type=int, default=5, help="download attempts per file (default: 5)")
    ap.add_argument("--timeout", type=float, default=60.0, help="network timeout in seconds (default: 60)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched; no network, writes nothing")
    a = ap.parse_args(argv)

    manifest = json.loads(a.manifest.read_text(encoding="utf-8"))
    files = [f for f in manifest["files"] if f["path"].startswith(a.prefix)]
    if not files:
        print(f"no manifest files start with {a.prefix!r} in {a.manifest}", flush=True)
        return 2
    total_mb = sum(int(f["bytes"]) for f in files) / 1e6
    print(f"{len(files)} files, {total_mb:.1f} MB, from {a.base_url} into {a.dest}"
          + ("  [dry run]" if a.dry_run else ""), flush=True)

    ok = bad = todo = 0
    for i, f in enumerate(files, 1):
        rel, size, sha = safe_rel(f["path"]), int(f["bytes"]), str(f["sha256"])
        target = a.dest.joinpath(*rel.parts)
        tag = f"[{i}/{len(files)}] {f['path']}"
        if local_ok(target, size, sha):
            ok += 1
            print(f"{tag} have (size+sha256 match, skipped)", flush=True)
            continue
        if a.dry_run:
            todo += 1
            state = "size/sha mismatch" if target.exists() else "missing"
            print(f"{tag} would fetch {size / 1e6:.1f} MB (local: {state})", flush=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        part = target.with_name(target.name + ".part")
        url = a.base_url + str(rel)
        for attempt in range(1, max(1, a.retries) + 1):
            t0 = time.time()
            try:
                n, got = fetch(url, part, a.timeout)
            except (OSError, http.client.HTTPException, ValueError) as e:
                why = f"{type(e).__name__}: {e}"
            else:
                if n == size and got == sha:
                    part.replace(target)
                    ok += 1
                    dt = max(time.time() - t0, 1e-6)
                    print(f"{tag} ok {n / 1e6:.1f} MB in {dt:.1f} s ({n / 1e6 / dt:.1f} MB/s)", flush=True)
                    break
                why = f"got {n} bytes (want {size}), sha256 {'match' if got == sha else 'MISMATCH'}"
            part.unlink(missing_ok=True)
            if attempt < a.retries:
                wait = min(2 ** attempt, 30)
                print(f"{tag} attempt {attempt}/{a.retries} failed ({why}); retry in {wait} s", flush=True)
                time.sleep(wait)
            else:
                bad += 1
                target.unlink(missing_ok=True)          # never leave a wrong-sha file behind (as _hf_dl.sh did)
                print(f"BAD {tag} after {attempt} attempt(s): {why}", flush=True)
    if a.dry_run:
        print(f"DONE (dry run) have {ok} would-fetch {todo}", flush=True)
        return 0
    print(f"DONE ok {ok} bad {bad}", flush=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
