# -*- coding: utf-8 -*-
"""Dump {{#vardefine:...}} pairs from a cached wikitext page (P1 path)."""
import re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
fn = sys.argv[1]
wt = open(fn, encoding='utf-8').read()
for m in re.finditer(r"\{\{#vardefine:\s*([^|}]+?)\s*\|\s*([^}]*?)\s*\}\}", wt):
    print(f"{m.group(1)} = {m.group(2)}")
