# -*- coding: utf-8 -*-
"""Trace ONE page's vardefines + primary attribute row across several dated cutoffs, to
locate exactly when a value moved (and therefore whether History or the table is stale)."""
import json, time, sys, re, io, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
HDR = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
VD = r'\{\{#vardefine:\s*([\w ]+?)\s*\|\s*([^}|]*?)\s*\}\}'

def get(p):
    with urllib.request.urlopen(urllib.request.Request(
            BASE + '?' + urllib.parse.urlencode(p), headers=HDR), timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))

def at(title, cutoff):
    q = get({'action': 'query', 'prop': 'revisions', 'titles': title, 'rvlimit': '1',
             'rvprop': 'ids|timestamp', 'rvstart': cutoff, 'rvdir': 'older', 'format': 'json'})
    pg = list(q['query']['pages'].values())[0]
    rv = pg.get('revisions', [None])[0]
    if not rv:
        return None, {}, None
    time.sleep(0.3)
    wt = get({'action': 'parse', 'oldid': str(rv['revid']), 'prop': 'wikitext',
              'format': 'json'})['parse']['wikitext']['*']
    m = re.search(r'id="unit-attributes-table"(.*?)\n\|\}', wt, re.S)
    row = None
    if m:
        row = " | ".join(l[1:].strip() for l in m.group(1).split('\n')
                         if l.startswith('|') and not l.startswith(('|-', '|}')))
    return rv, dict(re.findall(VD, wt)), row

title = sys.argv[1]
for cutoff in sys.argv[2:]:
    rv, vd, row = at(title, cutoff)
    print("-- %s  -> rev %s (%s)" % (cutoff[:10], rv and rv['revid'], rv and rv['timestamp']))
    if vd:
        print("   VD :", "  ".join("%s=%s" % kv for kv in vd.items()))
    print("   ROW:", (row or "")[:230])
    time.sleep(0.35)
