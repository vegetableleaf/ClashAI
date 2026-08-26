# -*- coding: utf-8 -*-
"""P3 verification: for each (title, balance-date) pair, pull the vardefines from the last
revision BEFORE the balance change and compare against the CURRENT ones, so we can tell
whether today's vardefine already contains the change the History section describes."""
import json, time, sys, re, io, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
HDR = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
VD = r'\{\{#vardefine:\s*([\w ]+?)\s*\|\s*([^}|]*?)\s*\}\}'

def get(params):
    url = BASE + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))

def snap(title, cutoff):
    q = get({'action': 'query', 'prop': 'revisions', 'titles': title, 'rvlimit': '1',
             'rvprop': 'ids|timestamp|comment', 'rvstart': cutoff, 'rvdir': 'older',
             'format': 'json'})
    page = list(q['query']['pages'].values())[0]
    rv = page.get('revisions', [{}])[0]
    if not rv:
        return None, {}, None
    time.sleep(0.3)
    p = get({'action': 'parse', 'oldid': str(rv['revid']), 'prop': 'wikitext', 'format': 'json'})
    wt = p['parse']['wikitext']['*']
    # also grab the primary attribute row so table lag is visible
    m = re.search(r'id="unit-attributes-table"(.*?)\n\|\}', wt, re.S)
    row = None
    if m:
        cells = [l[1:].strip() for l in m.group(1).split('\n')
                 if l.startswith('|') and not l.startswith('|-') and not l.startswith('|}')]
        row = " | ".join(cells[:6])
    return rv, dict(re.findall(VD, wt)), row

PAIRS = [
    ("Ram Rider",        "2026-01-11T00:00:00Z", "before 12/1/2026 atk-speed 1.8->1.7"),
    ("Ram Rider",        "2026-03-01T00:00:00Z", "after  12/1/2026 atk-speed change"),
    ("Ram Rider",        "2026-07-05T00:00:00Z", "before 6/7/2026 hp +4%"),
    ("Rune Giant",       "2026-05-31T00:00:00Z", "before 1/6/2026 dmg +28%"),
    ("Rune Giant",       "2026-08-03T00:00:00Z", "before 4/8/2026 hp +6%"),
    ("Rascals",          "2026-05-31T00:00:00Z", "before 1/6/2026 boy hp -6%"),
    ("Wall Breakers",    "2026-08-03T00:00:00Z", "before 4/8/2026 dmg -20%"),
    ("Skeleton Dragons", "2026-05-03T00:00:00Z", "before 4/5/2026 dmg -6%"),
    ("Royal Giant",      "2026-03-01T00:00:00Z", "before 2/3/2026 'hp'->1.7s"),
    ("Three Musketeers", "2026-02-01T00:00:00Z", "before 2/2/2026 atk 1.3->1.2"),
    ("Phoenix",          "2026-03-01T00:00:00Z", "before 2/3/2026 egg hp+32% lifetime 4.3"),
    ("Suspicious Bush",  "2026-04-05T00:00:00Z", "before 6/4/2026 bush range 0.5->1.6"),
    ("Spirit Empress",   "2026-05-03T00:00:00Z", "before 4/5/2026 hp/hit-speed change"),
]
for title, cutoff, why in PAIRS:
    try:
        rv, vd, row = snap(title, cutoff)
        print("== %-18s %-24s [%s]" % (title, cutoff[:10], why))
        print("   rev %s  ts %s" % (rv.get('revid'), rv.get('timestamp')))
        print("   VD :", "  ".join("%s=%s" % kv for kv in vd.items()))
        print("   ROW:", row)
    except Exception as e:
        print("== %-18s ERROR %r" % (title, e))
    time.sleep(0.35)
