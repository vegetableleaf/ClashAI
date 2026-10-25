"""Print wikitext context around a phrase (api.php, read-only).   python wiki_ctx.py PAGE PHRASE [CHARS]"""
import json, sys, urllib.parse, urllib.request
page, phrase = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 900
url = 'https://clashroyale.fandom.com/api.php?' + urllib.parse.urlencode(dict(action='parse', page=page, prop='wikitext', format='json'))
req = urllib.request.Request(url, headers={'User-Agent': 'ClashBot-research/1.0 (read-only parity check)'})
txt = json.load(urllib.request.urlopen(req, timeout=30))['parse']['wikitext']['*']
i = txt.find(phrase)
print(txt[max(0, i - n): i + 300] if i >= 0 else 'not found')
