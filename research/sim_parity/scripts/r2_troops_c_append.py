# -*- coding: utf-8 -*-
"""Append JSONL discrepancy lines + per-key tally for r2 troops_c.
Usage: feed a python literal dict list via stdin exec (called from heredocs)."""
import json, io, sys
LEDGER="C:/Users/benpe/ClashBot/research/sim_parity/ledger/"
def append_lines(lines):
    with open(LEDGER+"r2_troops_c.jsonl","a",encoding="utf-8") as f:
        for l in lines:
            f.write(json.dumps(l,ensure_ascii=False)+"\n")
def tally(key, checked, matched, notes=""):
    try:
        t=json.load(open(LEDGER+"r2_troops_c_tally.json",encoding="utf-8"))
    except Exception:
        t={}
    t[key]={"fields_checked":checked,"matches":matched,"notes":notes}
    json.dump(t,open(LEDGER+"r2_troops_c_tally.json","w",encoding="utf-8"),indent=1)
