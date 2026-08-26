# -*- coding: utf-8 -*-
"""troops_c round-2: refetch every group page LIVE, compare revid+content against the
archived timepoint, archive any new revision. Writes r2_troops_c_livefetch2.json."""
import json, os, time, urllib.request, urllib.parse, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
UA = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
ROOT = r'C:/Users/benpe/ClashBot/research/sim_parity'
CACHE = os.path.join(ROOT, 'webcache')
META = os.path.join(ROOT, 'ledger', 'r2_troops_c_fetchmeta.json')

TITLES = ["Night Witch", "P.E.K.K.A.", "Phoenix", "Prince", "Princess", "Ram Rider",
          "Rascals", "Ronin", "Royal Ghost", "Royal Giant", "Royal Hogs", "Royal Recruits",
          "Rune Giant", "Skeleton Army", "Skeleton Army/Evolution", "Skeleton Barrel",
          "Skeleton Dragons", "Skeletons", "Sparky", "Spear Goblins", "Spirit Empress",
          "Suspicious Bush", "Three Musketeers", "Valkyrie", "Wall Breakers", "Witch",
          "Wizard", "Zappies", "Royal Delivery"]

old = json.load(open(META, encoding='utf-8')) if os.path.exists(META) else {}
out = {}
for t in TITLES:
    fn = t.replace('/', '_').replace(' ', '_') + '.wikitext'
    path = os.path.join(CACHE, fn)
    prior_rev = old.get(t, {}).get('revid')
    prior_txt = open(path, encoding='utf-8').read() if os.path.exists(path) else None
    url = BASE + "?" + urllib.parse.urlencode(
        {'action': 'parse', 'page': t, 'prop': 'wikitext|revid', 'format': 'json'})
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25))
        p = r['parse']
        rev = p['revid']; wt = p['wikitext']['*']; title = p['title']
        same_txt = (prior_txt == wt) if prior_txt is not None else None
        if prior_rev is not None and rev != prior_rev:
            # archive the NEW revision separately, then refresh the head file
            open(os.path.join(CACHE, fn.replace('.wikitext', '.rev%d.wikitext' % rev)),
                 'w', encoding='utf-8').write(wt)
        if prior_txt is None or not same_txt:
            open(path, 'w', encoding='utf-8').write(wt)
        out[t] = {'resolved_title': title, 'revid_live': rev, 'revid_archived': prior_rev,
                  'edit_war': 'pass' if (prior_rev is None or rev == prior_rev) else 'CHANGED',
                  'content_identical': same_txt, 'bytes': len(wt),
                  'fetched': '2026-08-26', 'file': fn}
        print('%-26s live=%-7s arch=%-7s same=%s len=%d' % (t, rev, prior_rev, same_txt, len(wt)))
    except Exception as e:
        out[t] = {'error': repr(e)}
        print('%-26s ERROR %r' % (t, e))
    time.sleep(0.25)

json.dump(out, open(os.path.join(ROOT, 'ledger', 'r2_troops_c_livefetch2.json'), 'w',
                    encoding='utf-8'), indent=1)
ch = [t for t, v in out.items() if v.get('edit_war') == 'CHANGED']
print('\nCHANGED:', ch if ch else 'none')
print('ERRORS :', [t for t, v in out.items() if 'error' in v] or 'none')
