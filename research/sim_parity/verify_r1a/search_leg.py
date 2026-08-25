# -*- coding: utf-8 -*-
"""Search-API leg: paginate srsearch='Evolution' fully, retrying transient
empty responses, and collect every ns-0 title ending in '/Evolution'."""
import json, time, urllib.request, urllib.parse

BASE = 'https://clashroyale.fandom.com/api.php'
HDRS = {'User-Agent': 'icebow-monitor/1.0 (+local)'}

def get(params):
    p = dict(params); p['format'] = 'json'
    url = BASE + '?' + urllib.parse.urlencode(p)
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
            time.sleep(0.2)
            return data
        except Exception as e:
            last = repr(e); time.sleep(1.5 + attempt)
    print('FAILED', url, last)
    return None

evo_titles = set()
offset, total_hits, calls = 0, 0, 0
while True:
    data = None
    for retry in range(4):
        data = get({'action': 'query', 'list': 'search', 'srsearch': 'Evolution',
                    'srlimit': 50, 'sroffset': offset})
        if data and data.get('query', {}).get('search'):
            break
        time.sleep(2.0)   # transient empty search result -- retry
    if not data:
        print('giving up at offset', offset); break
    sr = data.get('query', {}).get('search', [])
    if not sr:
        print('empty page at offset', offset, '(after retries) -- treating as end')
        break
    total_hits += len(sr); calls += 1
    for h in sr:
        if h['ns'] == 0 and h['title'].endswith('/Evolution'):
            evo_titles.add(h['title'])
    cont = data.get('continue', {}).get('sroffset')
    if cont is None:
        print('pagination complete at offset', offset)
        break
    offset = cont
    if offset > 5000:
        print('cap reached'); break

print('total search hits walked:', total_hits, 'in', calls, 'calls')
print('distinct /Evolution titles from search:', len(evo_titles))
for t in sorted(evo_titles):
    print(' ', t)
with open('C:/Users/benpe/ClashBot/research/sim_parity/verify_r1a/search_leg_result.json', 'w', encoding='utf-8') as f:
    json.dump(sorted(evo_titles), f, indent=1)
