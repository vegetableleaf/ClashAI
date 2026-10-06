"""For every (card_id, max_hp) opponent body seen live, what the fv4 (legacy) and fv5 (body_identity) conversions produce."""
import json, sys
ROOT = r'C:\Users\benpe\ClashBot'; sys.path.insert(0, ROOT)
from pipeline import vocab
from pipeline.obs_contract import _catalog_names, catalog_card_form
from pipeline.body_identity import resolve
ids = {'Witch':26000007,'Witch@evo':13000007,'NightWitch':26000048,'Furnace':27000010,'Furnace@evo':13000106,'MotherWitch':26000083,
 'Tombstone':27000009,'GoblinHut':27000001,'BarbarianHut':27000005,'Graveyard':28000010,'GoblinDrill':27000013,'GoblinDrill@evo':13000108,
 'SkeletonBarrel':26000056,'SkeletonBarrel@evo':13000056,'GoblinCage':27000012,'GoblinCage@evo':13000107,'Phoenix':26000087,'Goblinstein':26000099,
 'SkeletonKing':26000069,'Golem':26000009,'LavaHound':26000029,'ElixirGolem':26000067,'GoblinBarrel':28000004,'GoblinGiant':26000060,
 'GoblinGiant@evo':13000060,'BarbLog':28000015,'GoblinDemolisher':26000095,'SuspiciousBush':26000097}
sv = json.load(open('survey_live.json'))
inv = {v: k for k, v in vocab._ID.items()} if hasattr(vocab, '_ID') else {}
def nm(i): return None if i is None else inv.get(i, i)
rows = []
for card, hist in sv['by_card'].items():
    cid = ids[card]; name = _catalog_names().get(cid); base, form = catalog_card_form(cid)
    for mhp, n in hist.items():
        leg = nm(vocab.engine_unit_id(name, float(mhp)))
        r = resolve(name, float(mhp), form)
        rows.append(dict(card=card, card_id=cid, name=name, max_hp=int(mhp), bodies=n, fv4=leg, fv4_form=form, fv5=nm(r.cls), fv5_form=r.form, fv5_reason=r.reason))
        print(f'{card:18s} {mhp:>5} n={n:<4} fv4={leg}/f{form}  fv5={nm(r.cls)}/f{r.form} ({r.reason})')
json.dump(rows, open('map_live.json', 'w'), indent=1)
