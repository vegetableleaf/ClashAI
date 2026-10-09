"""Local-only configuration of the live memory reader.

The reader's launch values (root address, context offset, on-device binary paths and their extra arguments) are NOT
kept in the repository. They live in ``icebow/data/reader_config.json``, which is git-ignored and exists only on the
machine that runs the live bot. Shape::

    {"root_rva": "<hex string>", "root_ctx": "<hex string>",
     "readers": {"<name>": {"binary": "<path on the device>", "args": "<all remaining command-line text, leading space>"}}}

``load()`` raises ``ReaderConfigError`` (a ``SystemExit``, so a CLI exits with the message) when the file is missing
or malformed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Tuple

CONFIG_PATH = Path(__file__).resolve().parents[1] / "icebow" / "data" / "reader_config.json"
ENV_VAR = "CLASHBOT_READER_CONFIG"   # optional override (tests, a second checkout)


def config_path() -> Path:
    return Path(os.environ[ENV_VAR]) if os.environ.get(ENV_VAR) else CONFIG_PATH


class ReaderConfigError(SystemExit):
    """Missing / malformed local reader config. A SystemExit so live_play.py exits with a readable message."""


def load(path: Path | None = None) -> Dict:
    """Return the validated config dict; clear error when absent or invalid."""
    path = Path(path) if path else config_path()
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ReaderConfigError(
            f"reader config missing: {path}\n"
            "The live reader's launch values are kept out of the repository. Create this local, git-ignored JSON "
            "file ({root_rva, root_ctx, readers: {name: {binary, args}}}) on the machine that runs live.") from None
    except (OSError, ValueError) as e:
        raise ReaderConfigError(f"reader config unreadable ({path}): {e}") from None
    try:
        if not isinstance(cfg["root_rva"], str) or not isinstance(cfg["root_ctx"], str):
            raise TypeError("root_rva / root_ctx must be strings")
        for name, r in cfg["readers"].items():
            if not isinstance(r["binary"], str) or not isinstance(r["args"], str):
                raise TypeError(f"reader {name!r}: binary / args must be strings")
    except (KeyError, TypeError, AttributeError) as e:
        raise ReaderConfigError(f"reader config invalid ({path}): {e!r}") from None
    return cfg


def readers(cfg: Dict) -> Dict[str, Tuple[str, str]]:
    """{name: (binary, args)} -- the shape live_play.READERS has always had."""
    return {k: (v["binary"], v["args"]) for k, v in cfg["readers"].items()}


def reader(name: str, path: Path | None = None) -> Tuple[str, str]:
    """One reader's (binary, args); clear error when the config lacks that name."""
    r = readers(load(path))
    if name not in r:
        raise ReaderConfigError(f"reader {name!r} not defined in {path or config_path()}")
    return r[name]
