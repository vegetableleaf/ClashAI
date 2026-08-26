# -*- coding: utf-8 -*-
"""P1 re-extraction with a PERMISSIVE vardefine-name pattern (names may contain spaces,
e.g. '{{#vardefine:melee dmg_11|...}}'). The earlier [A-Za-z0-9_]+ pattern dropped those."""
import re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
CACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache/"
for fn in sorted(sys.argv[1:]):
    wt = open(CACHE + fn, encoding="utf-8").read()
    vs = re.findall(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}|]*?)\s*\}\}", wt)
    print("=== %-32s %s" % (fn.replace('.wikitext', ''),
          "  ".join("%s=%s" % (k, v) for k, v in vs)))
