"""Polite Clash Royale Fandom wiki access via api.php (1 request/s, cached in wiki_cache.json). Public info only.
  python wiki.py search "Hero Balloon"        -> page titles
  python wiki.py page "Balloon/Hero"          -> raw wikitext saved to wiki/<title>.txt (cached)
"""
import json, os, sys, time, urllib.parse, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__))
API = 'https://clashroyale.fandom.com/api.php'
CACHE = os.path.join(HERE, 'wiki_cache.json')


def call(**p):
    p['format'] = 'json'
    url = API + '?' + urllib.parse.urlencode(p)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    if url not in cache:
        time.sleep(1.0)
        req = urllib.request.Request(url, headers={'User-Agent': 'ClashBot-research/1.0 (1 req/s)'})
        cache[url] = json.loads(urllib.request.urlopen(req, timeout=30).read())
        json.dump(cache, open(CACHE, 'w'))
    return cache[url]


if __name__ == '__main__':
    what, arg = sys.argv[1], sys.argv[2]
    if what == 'search':
        r = call(action='query', list='search', srsearch=arg, srlimit=15)
        for m in r['query']['search']:
            print(m['title'])
    else:
        r = call(action='parse', page=arg, prop='wikitext', redirects=1)
        if 'error' in r:
            print('ERROR', r['error']); sys.exit(1)
        t = r['parse']['wikitext']['*']
        os.makedirs(os.path.join(HERE, 'wiki'), exist_ok=True)
        fn = os.path.join(HERE, 'wiki', arg.replace('/', '__') + '.txt')
        open(fn, 'w', encoding='utf-8').write(t)
        print(fn, len(t))
