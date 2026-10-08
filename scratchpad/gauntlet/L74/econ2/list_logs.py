"""Print the live log files of one family (anti-leak OFF), from the compact live data.  python list_logs.py towerref"""
import sys
import econ2 as E

print("\n".join(m["file"] for m in E.load("live") if m["fam"] == sys.argv[1] and not m.get("al")))
