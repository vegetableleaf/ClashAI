"""Fetch Fandom wikitext via api.php (python urllib + UA, the sanctioned route) and print the sentences about King Tower
activation. Read-only.   python wiki_king.py PAGE [PAGE ...]"""
import json, re, sys, urllib.parse, urllib.request
for page in sys.argv[1:]:
    url = 'https://clashroyale.fandom.com/api.php?' + urllib.parse.urlencode(dict(action='parse', page=page, prop='wikitext', format='json'))
    req = urllib.request.Request(url, headers={'User-Agent': 'ClashBot-research/1.0 (read-only parity check)'})
    try:
        txt = json.load(urllib.request.urlopen(req, timeout=30))['parse']['wikitext']['*']
    except Exception as e:
        print(page, 'ERROR', e); continue
    print(f'=== {page} ({len(txt)} chars)')
    for s in re.split(r'(?<=[.!?])\s+|\n', txt):
        if re.search(r'(?i)king.{0,40}(activ|wake|awak)|activat', s):
            print(' -', s.strip()[:400])
