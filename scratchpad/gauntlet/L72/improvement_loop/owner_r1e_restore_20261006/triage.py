import collections,datetime,hashlib,json
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];LOG=ROOT/'scratchpad/gauntlet/L68/live_reader'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def readlog(p):return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8')
def towers(pub):
 side=pub['observer_side'];out={}
 for b in pub['raw_bodies']:
  if b['side']==side and b['card_id']==-1 and b['kind']==13:
   out[b['address']]=dict(hp=b['hp'],x=b['x'],y=b['y'])
 return out
def main():
 assert not (HERE/'triage.json').exists()
 files=sorted(LOG.glob('live_play_20261006_14*.jsonl'));assert len(files)==9
 navs=sorted(LOG.glob('ladder_nav_20261006_14*.jsonl'));sources={str(p.relative_to(ROOT)):sha(p) for p in files+navs}
 outcomes=sorted([x for p in navs for x in readlog(p) if x['event']=='outcome'],key=lambda x:x['t'])
 report=[];details=[]
 for k,p in enumerate(files):
  rows=readlog(p);start=rows[0];assert start['event']=='start' and start['ckpt_sha256']=='2feffe4f0990d93721ceb0b6661338f52e7f935e85b80e29535ea713ad6569a0'
  assert start['public_audit'] and not start['anti_leak'] and start['decision_options']['card_choice']==start['decision_options']['spell_aim']=='argmax'
  decisions=[x for x in rows if x['event']=='decision'];bytick={x['tick']:x for x in decisions};assert len(bytick)==len(decisions)
  acts=[];pending=None;confirmed=[]
  for index,row in enumerate(rows):
   if row['event']=='play':
    assert pending is None
    d=bytick[row['tick']];pub=d['public'];slot=row['hand_pos'];hand=pub['own_hand'][slot]
    assert d['decision']['play'] and d['decision']['name']==row['name']==hand['name'] and d['decision']['hand_pos']==slot
    assert row['elixir']==pub['own_elixir_raw'] and not row['forced']
    enemy=[b for b in pub['raw_bodies'] if b['side']!=pub['observer_side'] and b['card_id']>=0 and b['hp']>0]
    friendly=[b for b in pub['raw_bodies'] if b['side']==pub['observer_side'] and b['card_id']>=0 and b['hp']>0]
    a=dict(match=p.name,source_index=index,tick=row['tick'],name=row['name'],cost=hand['cost'],card=hand['card'],gate=d['decision']['p_play'],aim=row['xy'],
     raw_elixir=row['elixir'],model_elixir=pub['model_own_elixir'],receipt='unresolved',receipt_tick=None,
     enemy_bodies=enemy,friendly_bodies=friendly,public=pub,
     prior_confirmed_60ticks=[dict(tick=z['receipt_tick'],name=z['name'],cost=z['cost']) for z in confirmed if row['tick']-60<=z['receipt_tick']<=row['tick']])
    acts.append(a);pending=a
   elif row['event'] in ('confirmed','unconfirmed'):
    assert pending is not None and pending['name']==row['name']
    pending['receipt']=row['event'];pending['receipt_tick']=row['tick'];pending['receipt_details']=row
    if row['event']=='confirmed':confirmed.append(pending)
    pending=None
  for a in acts:
   following=[x for x in decisions if x['tick']>(a['receipt_tick'] or a['tick'])]
   a['next_observed_elixir']=following[0]['public']['own_elixir_raw'] if following else None
   a['next_observation_gap_ticks']=following[0]['tick']-(a['receipt_tick'] or a['tick']) if following else None
   later=[x for x in decisions if a['tick']+200<=x['tick']<=a['tick']+240]
   a['public_after_10s']=later[0] if later else None
   a['return_tick']=None;a['princess_hp_loss_before_return']=None
   if a['receipt']=='confirmed':
    # Card return is counted only after a public snapshot first shows its absence.
    absent=False;base=towers(a['public'])
    for x in following:
     present=any(h['card']==a['card'] for h in x['public']['own_hand'])
     if not present:absent=True
     if absent and present:a['return_tick']=x['tick'];break
     if absent and a['princess_hp_loss_before_return'] is None:
      current=towers(x['public'])
      loss=sum(max(0,v['hp']-current[uid]['hp']) for uid,v in base.items() if uid in current)
      if loss>0:a['princess_hp_loss_before_return']=dict(tick=x['tick'],observed_hp_loss=loss,known_towers=len(set(base)&set(current)))
   a['review_subset']=a['name'] in ('Log','Tornado') and len(a['enemy_bodies'])<=1 and len(a['friendly_bodies'])>=2
  stamp=datetime.datetime.strptime(p.stem.removeprefix('live_play_'),'%Y%m%d_%H%M%S').timestamp()
  stopstamp=datetime.datetime.strptime(files[k+1].stem.removeprefix('live_play_'),'%Y%m%d_%H%M%S').timestamp() if k+1<len(files) else float('inf')
  result=[x for x in outcomes if stamp<x['t']<stopstamp];assert len(result)<=1
  e=next(x for x in rows if x['event']=='end');assert e['played']==len(acts) and e['confirmed']==len(confirmed) and e['fails']==sum(a['receipt']=='unconfirmed' for a in acts)
  card={}
  for name in sorted(set(a['name'] for a in acts)):
   selected=[a for a in acts if a['name']==name];ok=[a for a in selected if a['receipt']=='confirmed']
   card[name]=dict(attempted=len(selected),confirmed=len(ok),confirmed_cost=sum(a['cost'] for a in ok))
  report.append(dict(match=p.name,decisions=len(decisions),played=len(acts),confirmed=len(confirmed),unconfirmed=e['fails'],unresolved=sum(a['receipt']=='unresolved' for a in acts),
   cards=card,confirmed_card_cost=sum(a['cost'] for a in confirmed),ability_confirmed=sum(x['event']=='ability_confirmed' for x in rows),
   below_raw_cost=sum(a['raw_elixir']<a['cost'] for a in acts),below_raw_cost_confirmed=sum(a['raw_elixir']<a['cost'] for a in confirmed),
   latency_ms_median=float(np.median([x['decide_ms'] for x in decisions])),latency_ms_p95=float(np.percentile([x['decide_ms'] for x in decisions],95)),
   max_backlog=max(x['backlog'] for x in decisions),cpu_starved=sum(x['event']=='cpu_starved' for x in rows),forced=sum(x['forced'] for x in decisions),
   review_subset=sum(a['review_subset'] for a in acts),outcome=('win' if result[0]['won'] else 'loss') if result else 'unknown'))
  details.extend(acts)
 write(HERE/'triage_details.json',details)
 allcards={name:{field:sum(x['cards'].get(name,{}).get(field,0) for x in report) for field in ('attempted','confirmed','confirmed_cost')} for name in sorted(set(a['name'] for a in details))}
 totals={field:sum(x[field] for x in report) for field in ('decisions','played','confirmed','unconfirmed','unresolved','confirmed_card_cost','ability_confirmed','below_raw_cost','below_raw_cost_confirmed','cpu_starved','forced','review_subset')}
 write(HERE/'triage.json',dict(complete=True,sources=sources,source_sha256=sha(Path(__file__)),details_sha256=sha(HERE/'triage_details.json'),matches=report,totals=totals,cards=allcards,outcomes=dict(collections.Counter(x['outcome'] for x in report)),trophies='unrecorded',causal_waste_labels=False))
 print('OWNER_TOWER_SESSION_TRIAGED')
if __name__=='__main__':main()
