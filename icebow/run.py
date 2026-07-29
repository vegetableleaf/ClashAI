"""Bootstrap: add src/ to sys.path and dispatch to the CLI."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "src"))

from clashrl.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
