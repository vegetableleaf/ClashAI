"""Download a Roboflow Universe dataset export.  `python tools/roboflow_fetch.py ws proj ver [fmt]`

The key lives in data/roboflow_key.txt (git-ignored, like the CR token and the Discord webhook)
or the ROBOFLOW_API_KEY environment variable. It is never printed, never logged, and never put
into an error message -- Roboflow puts the key in the QUERY STRING, so any naive exception print
leaks it into the terminal and the shell history.

Downloads land outside the repo by default so a 12k-image export cannot accidentally be staged.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]


def api_key() -> str:
    p = _ROOT / "data" / "roboflow_key.txt"
    if p.exists():
        k = p.read_text(encoding="utf-8").strip()
        if k:
            return k
    k = os.environ.get("ROBOFLOW_API_KEY", "").strip()
    if k:
        return k
    raise SystemExit("no Roboflow key: create data/roboflow_key.txt or set ROBOFLOW_API_KEY")


def _get_json(url: str, key: str) -> dict:
    try:
        with urllib.request.urlopen(url + ("&" if "?" in url else "?") + "api_key=" + key,
                                    timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:                      # never echo the URL: it holds the key
        raise SystemExit("roboflow API error %s %s" % (e.code, e.reason))


def project_info(ws: str, proj: str, key: str) -> dict:
    return _get_json("https://api.roboflow.com/%s/%s" % (ws, proj), key)


def fetch(ws: str, proj: str, version: str, fmt: str, out_dir: Path, key: str) -> Path:
    """Download + extract one export. Returns the extracted directory."""
    dest = out_dir / ("%s__%s__v%s" % (ws, proj, version))
    if (dest / ".complete").exists():
        print("[rf] %s already downloaded" % dest.name)
        return dest
    meta = _get_json("https://api.roboflow.com/%s/%s/%s/%s" % (ws, proj, version, fmt), key)
    link = (meta.get("export") or {}).get("link")
    if not link:
        raise SystemExit("no export link for %s/%s v%s (%s)" % (ws, proj, version, fmt))
    size = (meta.get("export") or {}).get("size")
    print("[rf] %s/%s v%s (%s): %.1f MB" % (ws, proj, version, fmt, float(size or 0)))
    dest.mkdir(parents=True, exist_ok=True)
    zp = dest.with_suffix(".zip")
    with urllib.request.urlopen(link, timeout=1800) as r, open(zp, "wb") as fh:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)
    with zipfile.ZipFile(zp) as z:
        z.extractall(dest)
    zp.unlink(missing_ok=True)
    (dest / ".complete").write_text("ok", encoding="utf-8")
    n = sum(1 for _ in dest.rglob("*.jpg")) + sum(1 for _ in dest.rglob("*.png"))
    print("[rf]   -> %s  (%d images)" % (dest, n))
    return dest


def main(argv) -> int:
    if len(argv) < 3:
        print(__doc__)
        return 2
    ws, proj, ver = argv[0], argv[1], argv[2]
    fmt = argv[3] if len(argv) > 3 else "coco"
    out = Path(argv[4]) if len(argv) > 4 else Path(os.environ.get("TEMP", ".")) / "rf_datasets"
    out.mkdir(parents=True, exist_ok=True)
    fetch(ws, proj, ver, fmt, out, api_key())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
