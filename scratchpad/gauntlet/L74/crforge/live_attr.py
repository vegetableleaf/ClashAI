import csv,sys,collections
rows=list(csv.DictReader(open(sys.argv[1]),delimiter="\t"))
known=set(sys.argv[2].split(","))
by=collections.defaultdict(list); exc=collections.Counter()
for r in rows:
    if r["fault"]!="0": exc[r["fault"][:90]]+=1; continue
    by[r["id"]].append(int(r["draws"]))
print("rows",len(rows),"faults",sum(exc.values()), exc.most_common(5))
ids=sorted(by)
anyrng=sum(1 for i in ids if max(by[i])>0); allfree=sum(1 for i in ids if max(by[i])==0)
print("matches",len(ids),"rng-free in all reps",allfree,"draws in >=1 rep",anyrng)
deck={r["id"]:(set(r["deck0"].split(",")),set(r["deck1"].split(","))) for r in rows}
pred=[i for i in deck if (deck[i][0]|deck[i][1])&known]
print("deck has a known drawer",len(pred),"of",len(deck))
ownk=sum(1 for i in deck if deck[i][0]&known); print("own deck has drawer",ownk)
c=collections.Counter(x for i in pred for x in (deck[i][1]&known)); print("drawer cards in opp decks",c)
mis=[i for i in ids if max(by[i])>0 and i not in pred]; print("rng with no known drawer",len(mis))
free_with=[i for i in ids if max(by[i])==0 and i in pred]; print("zero-draw (all reps) but has drawer",len(free_with))
