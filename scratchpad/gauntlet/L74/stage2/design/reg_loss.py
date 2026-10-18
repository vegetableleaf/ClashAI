"""Regulation-loss rate (lost before overtime) per Mark x band, LIVE, from stage2/gate/live_targets.json (gate_fit rules:
ladder-graded only, OT = live clock >= 186 s). SIM side: pass matches.jsonl globs as NAME=glob (OT = end_tick > 3600).
  icebow/.venv/Scripts/python.exe reg_loss.py [NAME=glob ...]"""
import glob, json, math, sys
sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stage2/gate")
from gate_fit import live, wilson
def show(name, rows):   # rows = (win, cls, ot)
    n = len(rows); rl = sum(not w and not ot for w, _, ot in rows); lo, hi = wilson(rl, n)
    print(f"{name:22s} n {n:4d}  regulation losses {rl:4d} = {rl/n:5.1%} [{lo:.1%}, {hi:.1%}]")
for mk, band in (("CXXIV", "12k"), ("CXXXVIII", "12k"), ("CXXXVIII", "13k")):
    show(f"live {mk} {band}", live(mk, band))
for a in sys.argv[1:]:
    from gate_fit import sim
    k, g = a.split("=", 1); show("SIM " + k, sim(g))
