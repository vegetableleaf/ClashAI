"""Bootstrap entry point.

Adds ``src`` to the import path so you can run the bot without installing it:

    python run.py run                 # start the bot
    python run.py calibrate           # live overlay to tune config coordinates
    python run.py capture-template X  # save a template image for state detection
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from clashbot.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
