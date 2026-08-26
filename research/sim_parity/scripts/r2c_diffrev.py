# -*- coding: utf-8 -*-
"""Unified-diff two revisions of a page (stat-relevant lines only)."""
import json, sys, io, difflib, time, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
HDR = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
def wt(oldid):
    u = BASE + '?' + urllib.parse.urlencode(
        {'action': 'parse', 'oldid': str(oldid), 'prop': 'wikitext', 'format': 'json'})
    with urllib.request.urlopen(urllib.request.Request(u, headers=HDR), timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))['parse']['wikitext']['*']
a, b = sys.argv[1], sys.argv[2]
A = wt(a).split('\n'); time.sleep(0.3); B = wt(b).split('\n')
for line in difflib.unified_diff(A, B, 'rev' + a, 'rev' + b, n=1, lineterm=''):
    if line.startswith(('+', '-', '@')):
        print(line[:300])
