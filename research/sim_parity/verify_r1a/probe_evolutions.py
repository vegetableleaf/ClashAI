# -*- coding: utf-8 -*-
"""Independent re-derivation of the live Card Evolution set.

Path A: existence-batch probes of '<Display>/Evolution' for ALL base card keys
        in ledger/current_db_snapshot.json.
Path B: wiki search API (list=search), both srsearch='intitle:Evolution' and
        plain 'Evolution', paginated; keep ns-0 titles ending in '/Evolution'.
Then fetch wikitext+revid for every existing candidate page, archive to
webcache/, and classify live vs stub.
"""
import json, time, os, re, sys, urllib.request, urllib.parse

BASE = 'https://clashroyale.fandom.com/api.php'
HDRS = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
WEBCACHE = 'C:/Users/benpe/ClashBot/research/sim_parity/webcache'
OUT = 'C:/Users/benpe/ClashBot/research/sim_parity/verify_r1a'
failures = []

def get(params):
    p = dict(params); p['format'] = 'json'
    url = BASE + '?' + urllib.parse.urlencode(p)
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
            time.sleep(0.2)
            return data
        except Exception as e:
            last = repr(e)
            time.sleep(1.0 + attempt)
    failures.append({'url': url, 'error': last})
    return None

# ---- base card list ----
snap = json.load(open('C:/Users/benpe/ClashBot/research/sim_parity/ledger/current_db_snapshot.json', encoding='utf-8'))
cards = snap['cards']
base = {k: cards[k].get('display', k) for k in cards if not k.endswith('_evo')}

# candidate wiki titles per key (display name, plus variants where ambiguous)
def titles_for(key, disp):
    t = [disp]
    if key == 'mini_pekka':
        t = ['Mini P.E.K.K.A.', 'Mini P.E.K.K.A']
    if key == 'pekka':
        t = ['P.E.K.K.A.', 'P.E.K.K.A']
    return t

probe_titles = {}   # full '<T>/Evolution' -> key
for k, disp in sorted(base.items()):
    for t in titles_for(k, disp):
        probe_titles[t + '/Evolution'] = k

# ---- Path A: existence batches (50 per query) ----
all_titles = sorted(probe_titles)
existing = {}   # normalized existing title -> pageid
missing = set()
for i in range(0, len(all_titles), 50):
    chunk = all_titles[i:i+50]
    data = get({'action': 'query', 'titles': '|'.join(chunk)})
    if data is None:
        print('BATCH FAILED', i, file=sys.stderr); continue
    q = data.get('query', {})
    norm = {n['from']: n['to'] for n in q.get('normalized', [])}
    # map back: response pages use normalized titles
    for pid, page in q.get('pages', {}).items():
        title = page['title']
        if 'missing' in page or int(pid) < 0:
            missing.add(title)
        else:
            existing[title] = int(pid)

# ---- Path B: search API ----
def search_all(query, cap=3000):
    hits, offset = [], 0
    while offset < cap:
        data = get({'action': 'query', 'list': 'search', 'srsearch': query,
                    'srlimit': 50, 'sroffset': offset})
        if data is None:
            break
        sr = data.get('query', {}).get('search', [])
        hits.extend(h['title'] for h in sr)
        cont = data.get('continue', {}).get('sroffset')
        if cont is None:
            break
        offset = cont
    return hits

search_titles = set()
for q in ('intitle:Evolution', 'Evolution'):
    got = search_all(q)
    print(f'search {q!r}: {len(got)} hits')
    for t in got:
        if t.endswith('/Evolution'):
            search_titles.add(t)

# ---- union of candidates that exist ----
candidates = set(existing) | search_titles
# search-derived titles need existence confirmation too (search index can lag)
unconfirmed = sorted(candidates - set(existing))
for i in range(0, len(unconfirmed), 50):
    chunk = unconfirmed[i:i+50]
    data = get({'action': 'query', 'titles': '|'.join(chunk)})
    if data is None: continue
    for pid, page in data.get('query', {}).get('pages', {}).items():
        if 'missing' not in page and int(pid) > 0:
            existing[page['title']] = int(pid)

# ---- fetch wikitext+revid for every existing evo page, archive ----
pages = {}
for title in sorted(existing):
    data = get({'action': 'parse', 'page': title, 'prop': 'wikitext|revid'})
    if data is None or 'parse' not in data:
        failures.append({'title': title, 'error': 'parse failed'})
        continue
    wt = data['parse']['wikitext']['*']
    revid = data['parse']['revid']
    fn = title.replace('/', '_').replace(' ', '_') + '.wikitext'
    with open(os.path.join(WEBCACHE, fn), 'w', encoding='utf-8') as f:
        f.write(wt)
    stub = len(wt) < 200 or bool(re.search(r'coming soon', wt, re.I))
    pages[title] = {'revid': revid, 'bytes': len(wt), 'stub': stub}

# ---- master Card Evolution page ----
data = get({'action': 'parse', 'page': 'Card Evolution', 'prop': 'wikitext|revid'})
master = None
if data and 'parse' in data:
    wt = data['parse']['wikitext']['*']
    master = {'revid': data['parse']['revid'], 'bytes': len(wt)}
    with open(os.path.join(WEBCACHE, 'Card_Evolution.wikitext'), 'w', encoding='utf-8') as f:
        f.write(wt)

result = {
    'n_base_keys_probed': len(base),
    'n_probe_titles': len(all_titles),
    'existing_evo_pages': pages,
    'search_derived_evo_titles': sorted(search_titles),
    'probe_missing_count': len(missing),
    'master_card_evolution': master,
    'failures': failures,
}
with open(os.path.join(OUT, 'probe_result.json'), 'w', encoding='utf-8') as f:
    json.dump(result, f, indent=1)
print(json.dumps({k: (v if not isinstance(v, dict) or k=='master_card_evolution' else len(v)) for k, v in result.items()}, indent=1))
print('EXISTING PAGES:')
for t in sorted(pages):
    print(' ', t, pages[t])
