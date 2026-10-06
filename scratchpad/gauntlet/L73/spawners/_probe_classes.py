import json,glob,collections
files=sorted(glob.glob('scratchpad/gauntlet/ext/corpus_v6/icebow_public_v1/j00*/replay_*.json'))[::15]
FAMN={'Witch','DarkWitch','FirespiritHut','WitchMother','Tombstone','GoblinHut','BarbarianHut','Graveyard'}
C=collections.defaultdict(collections.Counter)
for f in files:
    d=json.load(open(f)); seen={}
    for fr in d['frames']:
        for e in fr['entities']:
            if e[3] in FAMN:
                if e[8] not in seen:
                    seen[e[8]]=[e[3],e[6],e[5],e[4]]
                else:
                    seen[e[8]][2]=max(seen[e[8]][2],e[5])
    for n,c,mh,h in seen.values():
        C[n][(c, (mh//50)*50)]+=1
for n,v in C.items(): print(n,dict(v))
