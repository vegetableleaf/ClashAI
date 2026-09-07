"""Make native_core/worker.py call the shell scripts on Linux, the .ps1 on Windows. Idempotent.

The sandbox lives under research/ext/, which this project never commits, so the port is kept HERE (in
scratchpad, which is committed) and applied to the working tree by running this file. Re-running is safe;
running it on an already-patched file changes nothing and says so.

Three edits, all of them platform BRANCHES rather than replacements -- the Windows path has to keep
working, because that is the box the corpus drives run on today (11.24 s/match median, L64u).

  1. worker.py:76,:80   adb.exe / emulator.exe  ->  the .exe suffix only on nt
  2. worker.py:286-287  the start launcher      ->  bash scripts/start_direct_service.sh with the same
                        arguments, spelled --serial/--port/--slot instead of -Serial/-Port/-Slot
  3. worker.py:345-349  the stop launcher       ->  same, for stop_direct_service.sh

Nothing else in the package needs touching: the portability survey grepped the whole tree for platform
branches and found hits only in this file (plus cosmetic error text), and pyproject declares no
dependencies at all.

usage: python worker_linux.patch.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
WORKER = REPO / "research" / "ext" / "cr-native-sandbox" / "native_core" / "worker.py"

EDITS = [
    # (must appear exactly once, replacement)
    ('        return self.sdk_root / "platform-tools" / "adb.exe"',
     '        return self.sdk_root / "platform-tools" / ("adb.exe" if os.name == "nt" else "adb")'),
    ('        return self.sdk_root / "emulator" / "emulator.exe"',
     '        return self.sdk_root / "emulator" / ("emulator.exe" if os.name == "nt" else "emulator")'),
    # The start block is replaced WHOLE, both branches, because a patch that opens `if os.name == "nt":`
    # around the existing list and stops there leaves `command` undefined on Linux -- caught by reading
    # the replacement back rather than by trusting that the anchor matched.
    ('''        command = [
            _powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(PROJECT_ROOT / "scripts" / "start_direct_service.ps1"),
            "-Adb", str(self.config.adb), "-Serial", self.config.serial,
            "-Port", str(port), "-Slot", str(slot), "-DataRoot", str(self.config.data_root),
            "-BootstrapReplayJson", str(PROJECT_ROOT / "examples" / "eight-card-bootstrap.json"),
        ]''',
     '''        _bootstrap = str(PROJECT_ROOT / "examples" / "eight-card-bootstrap.json")
        if os.name == "nt":
            command = [
                _powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(PROJECT_ROOT / "scripts" / "start_direct_service.ps1"),
                "-Adb", str(self.config.adb), "-Serial", self.config.serial,
                "-Port", str(port), "-Slot", str(slot), "-DataRoot", str(self.config.data_root),
                "-BootstrapReplayJson", _bootstrap,
            ]
        else:
            # CR_SANDBOX_* come from runtime.env.sh; the .sh takes --adb only via the env var, so the
            # config's adb path is exported rather than passed, keeping one source of truth.
            os.environ.setdefault("CR_SANDBOX_ADB", str(self.config.adb))
            command = [
                "bash", str(PROJECT_ROOT / "scripts" / "start_direct_service.sh"),
                "--serial", self.config.serial, "--port", str(port), "--slot", str(slot),
                "--bootstrap", _bootstrap,
            ]'''),
    ('''                [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(script), "-Adb", str(self.config.adb), "-Serial", self.config.serial,
                 "-Port", str(port), "-Slot", str(slot)],''',
     '''                ([_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                  str(script), "-Adb", str(self.config.adb), "-Serial", self.config.serial,
                  "-Port", str(port), "-Slot", str(slot)] if os.name == "nt" else
                 ["bash", str(script.with_suffix(".sh")), "--serial", self.config.serial,
                  "--port", str(port), "--slot", str(slot)]),'''),
]

NOTE = """
# --- Linux port (scratchpad/gauntlet/L65/port/) -------------------------------------------------------
# The start command above is Windows-only; on Linux the same work is done by scripts/start_direct_service.sh,
# which prints the identical JSON. CR_SANDBOX_ADB and friends come from runtime.env.sh instead of
# runtime.env.ps1 -- the variable NAMES are unchanged, which is why nothing else here moves.
"""


def main() -> int:
    check = "--check" in sys.argv
    if not WORKER.exists():
        print("worker.py not found at", WORKER); return 2
    s = WORKER.read_text(encoding="utf-8")
    done, todo = 0, 0
    for old, new in EDITS:
        if new in s:
            done += 1
        elif s.count(old) == 1:
            todo += 1
            if not check:
                s = s.replace(old, new, 1)
        else:
            print("REFUSING: anchor not found exactly once ->", old.strip().splitlines()[0][:70])
            return 3
    print({"already_applied": done, "would_apply" if check else "applied": todo, "file": str(WORKER)})
    if todo and not check:
        WORKER.write_text(s, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
