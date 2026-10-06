"""Explicit hand-model live CLI with the canonical sibling import directory.

Preserves the failed v2 entry point. No checkpoint, action or model change.
"""
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))

def main():
    if '--ckpt' not in sys.argv:raise SystemExit('Explicit --ckpt required for hand-model companion')
    from pipeline import live_gen_v2
    from pipeline.live_hand_v2 import HandGenPilot
    live_gen_v2.GenPilot=HandGenPilot
    entry=ROOT/'scratchpad/gauntlet/L68/live_reader/live_play.py'
    # run_path on a script file does not add its parent as direct Python execution does.
    sys.path.insert(0,str(entry.parent))
    runpy.run_path(str(entry),run_name='__main__')

if __name__=='__main__':main()
