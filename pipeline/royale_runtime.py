"""Select the reviewed Royale runtime before importing either engine package.

The old installation stays intact for already frozen experiments. There is no
fallback: a missing, changed or previously imported older runtime aborts a new run.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "scratchpad/gauntlet/L71/royale_update_20261005/build_manifest.json"
RUNTIME = REPO / "research/ext/Royale-20261005/runtime"
# Opt-in upgrade: ROYALE_RUNTIME=20261006 selects the newer pinned build. Unset = the pin above, unchanged
# (its stamp carries no runtime_id, so existing checkpoints' recorded stamps still compare equal).
RUNTIME_ID = None
_selected = os.environ.get("ROYALE_RUNTIME", "").strip()
if _selected:
    if _selected not in ("20261006", "20261006-linux", "unpinned-linux"):
        raise RuntimeError(f"Unknown ROYALE_RUNTIME={_selected!r}; known opt-in runtimes: '20261006', '20261006-linux', 'unpinned-linux'")
    RUNTIME_ID = _selected
    MANIFEST = REPO / "scratchpad/gauntlet/L73/royale_update_20261006/build_manifest.json"
    RUNTIME = REPO / "research/ext/Royale-20261006/runtime"
    if _selected in ("20261006-linux", "unpinned-linux"):   # PyPI royalesim 0.1.17 / royalegym 0.1.18 in this venv (Linux VM, benchmark)
        import sysconfig
        RUNTIME = Path(sysconfig.get_paths()["purelib"])
_STAMP = None


def _verify_files(runtime: Path, manifest: dict) -> None:
    if RUNTIME_ID == "unpinned-linux":   # L74 weekend S7 ONLY: an unreviewed newer wheel (royalesim 0.1.25) in a separate venv; no byte check
        return
    runtime = runtime.resolve()
    for name, expected in manifest["files"].items():
        name = name.replace("\\", "/")
        if RUNTIME_ID == "20261006-linux" and (".dist-info/" in name or name.endswith(".pyd")):
            continue   # platform-specific (Windows binary, wheel metadata); provenance is checked in activate()
        path = (runtime / name).resolve()
        if not path.is_relative_to(runtime) or not path.is_file():
            raise RuntimeError(f"Pinned Royale runtime file missing or outside runtime: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Pinned Royale runtime file changed: {name}")


def _check_imports(runtime: Path) -> None:
    for name, module in tuple(sys.modules.items()):
        if name.split(".", 1)[0] in ("royalesim", "royalegym"):
            filename = getattr(module, "__file__", None)
            if filename is None or not Path(filename).resolve().is_relative_to(runtime):
                raise RuntimeError(f"An unpinned Royale module was already imported: {name}. "
                                   "Start a fresh process and activate pipeline.royale_runtime first.")


def activate() -> dict:
    """Verify installed bytes and compiled provenance once per process; return a JSON stamp."""
    global _STAMP
    runtime = RUNTIME.resolve()
    override = os.environ.get("ROYALESIM_DATA_DIR")
    if override and Path(override).resolve() != runtime / "royalesim/data":
        raise RuntimeError("ROYALESIM_DATA_DIR would override the pinned runtime's data")
    _check_imports(runtime)
    if _STAMP is None:
        if not MANIFEST.is_file():
            raise RuntimeError(f"Pinned Royale build manifest missing: {MANIFEST}")
        contents = MANIFEST.read_bytes()
        manifest = json.loads(contents)
        _verify_files(runtime, manifest)
        sys.path.insert(0, str(runtime))
        importlib.invalidate_caches()
        sim = importlib.import_module("royalesim")
        importlib.import_module("royalegym")
        _check_imports(runtime)
        if RUNTIME_ID != "unpinned-linux" and tuple(sim.Battle.provenance()) != (manifest["pins"]["RoyaleSim"], "clean"):
            raise RuntimeError("RoyaleSim compiled provenance differs from the reviewed source")
        if RUNTIME_ID != "unpinned-linux" and sim.card_table_source() != "embedded":
            raise RuntimeError("Pinned RoyaleSim must use its compiled-in card table")
        from royalegym.rust_engine import RustEngine
        from royalegym.protocol import data_dir
        if data_dir().resolve() != runtime / "royalesim/data":
            raise RuntimeError("RoyaleGym data path differs from the pinned runtime")
        _STAMP = dict(schema=1, pins=manifest["pins"], wheels=manifest["wheels"],
                      manifest_sha256=hashlib.sha256(contents).hexdigest(),
                      card_table=RustEngine().card_table_stamp())
        if RUNTIME_ID:
            _STAMP["runtime_id"] = RUNTIME_ID
    return json.loads(json.dumps(_STAMP))


def _same_engine(stamp: dict | None):
    """20261006 (Windows, hand-assembled wheel) and 20261006-linux (PyPI abi3 wheel) are ONE engine: the same manifest,
    compiled provenance d088f53 clean and embedded card table (verified L73 VM bring-up 2026-10-07: identical init pro
    agreement, init screen and u0000 rollouts). Only the platform binary differs, so a run may resume across them."""
    if not stamp:
        return stamp
    s = dict(stamp)
    if s.get("runtime_id") in ("20261006", "20261006-linux"):
        s["runtime_id"] = "20261006"
    return s


def require_same(expected: dict | None) -> dict:
    """Actors and exact resumes must match the learner's recorded runtime."""
    actual = activate()
    if _same_engine(actual) != _same_engine(expected):
        raise RuntimeError("Royale runtime differs from the learner/checkpoint (or was not recorded). "
                           "Use the checkpoint as init for a new run, rather than resuming across engines.")
    return actual
