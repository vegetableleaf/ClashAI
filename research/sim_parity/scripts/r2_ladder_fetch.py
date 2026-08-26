# -*- coding: utf-8 -*-
"""CROSS-CHECK 3 fetch: live wikitext + rendered per-level table for the ladder audit."""
import json, os, time, urllib.request, urllib.parse, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
UA   = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
ROOT = r'C:/Users/benpe/ClashBot/research/sim_parity'
CACHE = os.path.join(ROOT, 'webcache')

TITLES = [
 ("Knight","Common"),("Archers","Common"),("Skeletons","Common"),("Bomber","Common"),
 ("Musketeer","Rare"),("Hog Rider","Rare"),("Valkyrie","Rare"),("Wizard","Rare"),
 ("P.E.K.K.A.","Epic"),("Witch","Epic"),("Golem","Epic"),("Baby Dragon","Epic"),
 ("Princess","Legendary"),("Miner","Legendary"),("Sparky","Legendary"),("Electro Wizard","Legendary"),
 ("Mighty Miner","Champion"),("Archer Queen","Champion"),("Golden Knight","Champion"),
 ("Skeleton King","Champion"),
]
# revids recorded by earlier r2 fetch logs for the archived copies (2026-08-25/26)
CACHED_REV = {
 "Knight":437500,"Skeletons":436874,"Musketeer":436481,"Hog Rider":436540,"Valkyrie":437199,
 "Wizard":437068,"P.E.K.K.A.":436708,"Witch":436707,"Golem":436719,"Princess":436737,
 "Miner":437332,"Sparky":436735,"Mighty Miner":437349,"Archer Queen":436755,
 "Golden Knight":437147,"Skeleton King":436753,
}

def api(params):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)

meta = {}
for title, rarity in TITLES:
    fn = title.replace('/', '_').replace(' ', '_') + '.wikitext'
    path = os.path.join(CACHE, fn)
    rec = {'rarity': rarity, 'file': fn, 'fetched': '2026-08-26'}
    try:
        d = api({'action':'parse','page':title,'prop':'wikitext|revid','format':'json'})
        rev_wt = d['parse']['revid']; wt = d['parse']['wikitext']['*']
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        rec['revid_live'] = rev_wt
        rec['revid_cached'] = CACHED_REV.get(title)
        rec['content_identical_to_archive'] = (old == wt) if old is not None else None
        if old is not None and old != wt:
            oldrev = CACHED_REV.get(title)
            keep = os.path.join(CACHE, fn.replace('.wikitext', '.rev%s.wikitext' % (oldrev or 'cached0826')))
            open(keep, 'w', encoding='utf-8').write(old)
            rec['archived_old_as'] = os.path.basename(keep)
        open(path, 'w', encoding='utf-8').write(wt)
        time.sleep(0.25)
        d2 = api({'action':'parse','page':title,'prop':'text|revid','format':'json'})
        rec['revid_rendered'] = d2['parse']['revid']
        rfn = fn.replace('.wikitext', '.rendered.html')
        open(os.path.join(CACHE, rfn), 'w', encoding='utf-8').write(d2['parse']['text']['*'])
        rec['rendered_file'] = rfn
        # edit_war: cached revid known and different -> CHANGED; unknown -> lean on content identity
        cr = rec['revid_cached']
        if cr is None:
            rec['edit_war'] = 'pass' if rec['content_identical_to_archive'] else 'CHANGED'
            rec['edit_war_basis'] = 'content-identity (no cached revid on record)'
        else:
            rec['edit_war'] = 'pass' if cr == rev_wt else 'CHANGED'
            rec['edit_war_basis'] = 'revid'
        print('%-16s live=%s cached=%s same=%s %s' % (title, rev_wt, cr,
              rec['content_identical_to_archive'], rec['edit_war']))
    except Exception as e:
        rec['error'] = repr(e); print(title, 'ERROR', repr(e))
    meta[title] = rec
    time.sleep(0.25)
json.dump(meta, open(os.path.join(ROOT, 'ledger', 'r2_ladder_fetchmeta.json'), 'w'), indent=1)
print('done', len(meta))
