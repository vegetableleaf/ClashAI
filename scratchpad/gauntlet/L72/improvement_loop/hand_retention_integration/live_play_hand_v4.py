"""Opt-in hand pilot with canonical explicit/default checkpoint selection.

Used only when the live supervisor's HAND_READER switch is enabled. The standard
checkpoint pointer and between-match change detection remain canonical behavior.
"""
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT))

def main():
    from pipeline import live_gen_v2
    from pipeline.live_hand_v2 import HandGenPilot
    live_gen_v2.GenPilot=HandGenPilot
    entry=ROOT/'scratchpad/gauntlet/L68/live_reader/live_play.py'
    sys.path.insert(0,str(entry.parent))
    runpy.run_path(str(entry),run_name='__main__')

if __name__=='__main__':main()
