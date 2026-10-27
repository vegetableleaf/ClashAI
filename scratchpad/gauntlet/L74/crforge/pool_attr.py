import csv,sys,collections
rows=list(csv.DictReader(open(sys.argv[1]),delimiter="\t"))
known=set(sys.argv[2].split(","))
inrng=collections.Counter(); inall=collections.Counter(); unexpl=0; unexpl_cards=collections.Counter(); n=0
for r in rows:
    if r["fault"]!="0": continue
    n+=1
    cards=set(r["deck0"].split(","))|set(r["deck1"].split(","))
    rng=int(r["draws"])>0
    for c in cards:
        inall[c]+=1
        if rng: inrng[c]+=1
    if rng and not (cards&known):
        unexpl+=1
        for c in cards: unexpl_cards[c]+=1
    if not rng and (cards&known): pass
print("battles",n,"rng",sum(int(r["draws"])>0 for r in rows if r["fault"]=="0"),"rng w/o known drawer",unexpl)
print("cards in every unexplained rng battle-ish:", unexpl_cards.most_common(12))
pred=sum(1 for r in rows if r["fault"]=="0" and (set(r["deck0"].split(","))|set(r["deck1"].split(",")))&known)
print("predicted rng by known drawers", pred)
print("zero-draw battles containing a known drawer", sum(1 for r in rows if r["fault"]=="0" and int(r["draws"])==0 and (set(r["deck0"].split(","))|set(r["deck1"].split(",")))&known))
