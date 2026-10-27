"""Reader hp -1 bodies (round 2.4): per body card id, how many recorded body rows read hp -1, and of the bodies seen
with -1 (tracked by the live address in the raw live log), how many ever read a real hp and what max_hp they carry.
    python -I hp_placeholder.py LIVE_DIR INPUTS.jsonl     (laptop: raw live logs)"""
import collections, json, os, sys

live, inputs = sys.argv[1], sys.argv[2]
rows, neg = collections.Counter(), collections.Counter()
addr_hp = collections.defaultdict(lambda: collections.defaultdict(set))
mx = collections.defaultdict(collections.Counter)
for l in open(inputs):
    m = json.loads(l)['match']
    for raw in open(os.path.join(live, m + '.jsonl'), 'rb'):
        if b'"frame"' not in raw[:40]:
            continue
        d = json.loads(raw)
        for e in d['ents']:
            side, x, y, cid, hp, mhp, kind, addr = e[:8]
            if cid == -1:
                continue
            rows[cid] += 1
            addr_hp[cid][(m, addr)].add(hp == -1)
            if hp == -1:
                neg[cid] += 1
                mx[cid][mhp] += 1
print('card id: rows with hp -1 / all rows; bodies always -1 / bodies ever -1; max_hp of the -1 rows')
for cid, n in neg.most_common():
    b = addr_hp[cid]
    ever = [k for k, s in b.items() if True in s]
    always = [k for k in ever if b[k] == {True}]
    print(cid, '%d / %d rows' % (n, rows[cid]), '| bodies always -1 %d of %d ever -1' % (len(always), len(ever)),
          '| max_hp', dict(mx[cid].most_common(3)))
