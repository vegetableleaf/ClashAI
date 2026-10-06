"""Explicit manual hand-model entry; canonical live CLI/actions, no auto-start.

Use normal icebow Python, --ckpt <hand candidate> and optionally --check.
It only substitutes the pilot in this new process, leaving owner workers alone.
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
    runpy.run_path(str(ROOT/'scratchpad/gauntlet/L68/live_reader/live_play.py'),run_name='__main__')

if __name__=='__main__':main()
