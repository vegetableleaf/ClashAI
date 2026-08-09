"""Source for ClashAI.exe -- the OPTIONAL pretty double-click entry point.

Nothing needs this file or the .exe: ClashAI.bat in the repo root does exactly the same.
It exists so a desktop shortcut can carry an icon.

This is the source for the .exe; it does exactly what ClashAI.bat does, so the .exe is
purely a nicer double-click entry point with its own icon -- it still needs the same
.venv this project has always needed, and starts the same `run.py ui` the CLI has always
had. Nothing here reimplements anything the launcher UI itself does.

Build it into ClashAI.exe by double-clicking tools/build_exe.bat (installs
PyInstaller into the venv once, as a build tool only -- not a runtime dependency). The
result, ClashAI.exe, lands next to this file; move or shortcut it wherever is convenient,
it finds the repo by its own location, the same way ClashAI.bat finds it via %~dp0. Not
tracked in git (see .gitignore) -- rebuild after changing this file.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _pause() -> None:
    try:
        input("Press Enter to close ...")
    except EOFError:                # no interactive console attached (piped/background run)
        pass


def _repo_root() -> Path:
    # PyInstaller's --onefile unpacks to a temp dir at runtime; sys.executable there is
    # the temp copy, not a useful anchor. The FROZEN exe's own path is the right one --
    # same role %~dp0 plays in ClashAI.bat.
    here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    return here.parent


def main() -> int:
    root = _repo_root()
    icebow = root / "icebow"
    venv_py = icebow / ".venv" / "Scripts" / "python.exe"

    if not venv_py.exists():
        print(f"[ClashAI] No virtual environment found: {icebow / '.venv'}")
        print("[ClashAI] Create it with:")
        print(f"[ClashAI]   py -3.11 -m venv .venv && .venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        _pause()
        return 1

    has_flask = subprocess.run([str(venv_py), "-c", "import flask"], cwd=str(icebow)).returncode == 0
    if not has_flask:
        print("[ClashAI] Flask is missing -- installing it once into the venv ...")
        if subprocess.run([str(venv_py), "-m", "pip", "install", "Flask>=3.0"], cwd=str(icebow)).returncode != 0:
            print("[ClashAI] Install failed. Manually:  .venv\\Scripts\\python.exe -m pip install Flask")
            _pause()
            return 1

    print("[ClashAI] Starting the launcher ... (keep this window open; Ctrl+C stops it)")
    rc = subprocess.run([str(venv_py), "run.py", "ui", *sys.argv[1:]], cwd=str(icebow)).returncode
    print()
    print("[ClashAI] Launcher stopped.")
    _pause()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
