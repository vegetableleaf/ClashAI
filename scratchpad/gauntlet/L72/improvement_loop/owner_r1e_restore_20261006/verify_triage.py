"""Independent raw receipt/decision/outcome reconciliation and omission census."""
import collections,copy,datetime,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(x) for x in p.read_text().splitlines()]
def equal(a,b):assert a==b
def main():
 assert not (HERE/'triage_verified.json').exists()
 r=read(HERE/'triage.json');details=read(HERE/'triage_details.json');assert sha(HERE/'triage_details.json')==r['details_sha256']
 for p,h in r['sources'].items():assert sha(ROOT/p)==h
 allcards={};counts=collections.Counter();omitted=0;entries=0;explicit=0
 for m in r['matches']:
  rows=lines(ROOT/'scratchpad/gauntlet/L68/live_reader'/m['match']);events=collections.Counter(x['event'] for x in rows)
  assert events['play']==m['played'] and events['confirmed']==m['confirmed'] and events['unconfirmed']==m['unconfirmed'] and events['decision']==m['decisions']
  acts=[a for a in details if a['match']==m['match']];assert len(acts)==events['play'];spent=0
  for a in acts:
   x=rows[a['source_index']];assert x['event']=='play' and x['tick']==a['tick'] and x['name']==a['name']
   d=next(d for d in rows if d['event']=='decision' and d['tick']==x['tick']);cost=d['public']['own_hand'][x['hand_pos']]['cost'];assert cost==a['cost']
   after=rows[a['source_index']+1:];nextplay=next((i for i,e in enumerate(after) if e['event']=='play'),len(after))
   receipts=[e for e in after[:nextplay] if e['event'] in ('confirmed','unconfirmed')];assert len(receipts)<=1
   assert a['receipt']==(receipts[0]['event'] if receipts else 'unresolved')
   if receipts:assert receipts[0]['tick']==a['receipt_tick'] and receipts[0]['name']==a['name']
   c=allcards.setdefault(a['name'],dict(attempted=0,confirmed=0,confirmed_cost=0.));c['attempted']+=1
   if a['receipt']=='confirmed':c['confirmed']+=1;c['confirmed_cost']+=cost;spent+=cost
  assert spent==m['confirmed_card_cost']
  for d in [x for x in rows if x['event']=='decision']:
   u=d['public'];hero=[b for b in u['raw_bodies'] if b['card_id']==203000023 and b['hp']>0]
   if hero:
    assert all(b['side']==u['observer_side'] for b in hero)
    omitted+=1;entries+=len(hero);explicit+=int(any(b['cls']==2 and b['form']==2 for b in u['model_bodies']))
  for f in ('decisions','played','confirmed','unconfirmed','unresolved','confirmed_card_cost','ability_confirmed','below_raw_cost','below_raw_cost_confirmed','cpu_starved','forced','review_subset'):counts[f]+=m[f]
 assert dict(counts)==r['totals'] and allcards==r['cards']
 # Independent navigation outcome mapping via filename chronological boundaries.
 files=sorted(m['match'] for m in r['matches']);nav=[e for p in r['sources'] if 'ladder_nav_' in p for e in lines(ROOT/p) if e['event']=='outcome'];mapped=[]
 for i,name in enumerate(files):
  t=datetime.datetime.strptime(name[10:-6],'%Y%m%d_%H%M%S').timestamp()
  end=datetime.datetime.strptime(files[i+1][10:-6],'%Y%m%d_%H%M%S').timestamp() if i+1<len(files) else float('inf')
  hits=[e for e in nav if t<e['t']<end];assert len(hits)<=1
  result=('win' if hits[0]['won'] else 'loss') if hits else 'unknown';assert result==r['matches'][i]['outcome'];mapped.append(result)
 assert dict(collections.Counter(mapped))==r['outcomes']
 sample=dict(played=3,confirmed=1,unconfirmed=1,unresolved=1,cost=2.,checkpoint='expected',outcome='unknown')
 equal(dict(sample),sample);neg=0
 for field in sample:
  bad=copy.deepcopy(sample);bad[field]=bad[field]+1 if isinstance(bad[field],(int,float)) else 'changed'
  try:equal(bad,sample)
  except AssertionError:neg+=1
  else:raise AssertionError(field)
 out=dict(complete=True,matches=len(files),attempts=len(details),controls=dict(positive=1,negative=neg),raw_hero_ice_wizard_decisions=omitted,raw_hero_entries=entries,decisions_with_model_hero=explicit,
  triage_sha256=sha(HERE/'triage.json'),details_sha256=sha(HERE/'triage_details.json'),source_sha256=sha(Path(__file__)),causal_attribution=False)
 (HERE/'triage_verified.json').write_text(json.dumps(out,indent=2));print('OWNER_TOWER_TRIAGE_VERIFIED')
if __name__=='__main__':main()
