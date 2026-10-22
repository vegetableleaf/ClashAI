"""Clash Royale Fandom via api.php (memory: page fetches are blocked, api.php works). Prints wikitext lines matching patterns.
  python wiki.py PAGE [regex ...]"""
import json, re, sys, urllib.parse, urllib.request
page = sys.argv[1]
url = 'https://clashroyale.fandom.com/api.php?' + urllib.parse.urlencode(dict(action='parse', page=page, prop='wikitext', format='json'))
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research script)'})
d = json.loads(urllib.request.urlopen(req, timeout=30).read())
if 'error' in d:
    print('ERROR', d['error']); sys.exit()
txt = d['parse']['wikitext']['*']
pats = [re.compile(p, re.I) for p in sys.argv[2:]]
lines = txt.split('\n')
print(page, 'lines', len(lines))
for i, l in enumerate(lines):
    if not pats or any(p.search(l) for p in pats):
        print(i, l[:300])
