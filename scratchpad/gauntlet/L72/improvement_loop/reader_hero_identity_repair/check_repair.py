"""Public identity reconstruction, table/privacy controls, and offline startup."""
import copy,hashlib,json,os,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4];sys.path.insert(0,str(ROOT))
from pipeline import obs_contract as O, vocab
from pipeline.live_mem import to_observe
from pipeline.reader_identity_aliases import extend_names,extend_forms
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 assert not (HERE/'verified.json').exists()
 catalog=ROOT/'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json';catalogsha=sha(catalog)
 cards=json.loads(catalog.read_text())['cards'];oldnames={};oldforms={}
 for c in cards:
  for field,form in [('card_id',0),('evolution_form_id',1),('hero_form_id',2)]:
   if c.get(field) is not None:oldnames[int(c[field])]=c['display_name'];oldforms[int(c[field])]=(c['display_name'],form)
 assert 203000023 not in oldnames and 203000023 not in oldforms
 assert extend_names(oldnames)==O._catalog_names()
 for cid,name in oldnames.items():assert O._catalog_names()[cid]==name and O.catalog_card_form(cid)==oldforms[cid]
 assert O._catalog_names()[203000023]=='IceWizard' and O.catalog_card_form(203000023)==('IceWizard',2)
 assert len(O._catalog_names())==len(oldnames)+1 and len(O.catalog_card_form.table)==len(oldforms)+1
 assert O.catalog_card_form(203999999)==(None,0)
 negative=0
 for fn,base,key,bad in [(extend_names,oldnames,203000023,'Knight'),(extend_forms,oldforms,203000023,('IceWizard',0)),
  (extend_names,oldnames,26000023,'Wrong'),(extend_forms,oldforms,26000023,('Knight',0))]:
  changed=dict(base);changed[key]=bad
  try:fn(changed)
  except ValueError:negative+=1
  else:raise AssertionError('conflicting identity accepted')
 assert negative==4
 names=['Tornado','Tesla','IceWizard','Xbow','Rocket','Knight','Log','Skeletons']
 keys=tuple(vocab.engine_key(n) for n in names)
 deck=O.Deck(name='public-body-fixture',cards=keys,card_ids=tuple(vocab.unit_id(k) for k in keys),config=ROOT,src_dir=ROOT,crawl_dir=ROOT,data_dir=ROOT)
 def frame(pub,side):
  return dict(game_tick=pub['raw_tick'],entities=copy.deepcopy(pub['raw_bodies']),players=[
   dict(side=side,elixir_raw=50000,hand_deck_indices=[0,1,2,3],next_deck_index=4),
   dict(side=1-side,elixir_raw=99999,hand_deck_indices=[7,6,5,4],next_deck_index=3,deck_card_ids=[999]*8)])
 def board(f,side,feature):return O.from_engine(to_observe(f,side,names),side,deck,engine_deck=names,unmapped=set(),feature_version=feature)
 files=sorted((ROOT/'scratchpad/gauntlet/L68/live_reader').glob('live_play_20261006_14*.jsonl'));assert len(files)==9
 census=[];totalrows=totalentries=conversions=0;first=None
 for p in files:
  seen=entries=0
  for line in p.read_text().splitlines():
   row=json.loads(line)
   if row['event']!='decision':continue
   pub=row['public'];heroes=[e for e in pub['raw_bodies'] if e['card_id']==203000023 and e['hp']>0]
   if not heroes:continue
   seen+=1;entries+=len(heroes);first=first or pub
   assert not any(u['cls']==vocab.unit_id('ice_wizard') and u['form']==2 for u in pub['model_bodies'])
   for side in (0,1):
    f=frame(pub,side)
    for feature in (4,7):
     b=board(f,side,feature);actual=[u for u in b.units if u.cls==vocab.unit_id('ice_wizard') and u.form==2]
     assert len(actual)==len(heroes)
     for u,e in zip(actual,heroes):
      x=(18000-e['x'])/18000 if side else e['x']/18000
      y=e['y']/32000 if side else 1-e['y']/32000
      assert u.side==int(e['side']!=side) and abs(u.x-x)<1e-15 and abs(u.y-y)<1e-15 and u.hp_frac==e['hp']/e['max_hp']
     # Explicit base name + publicly witnessed form is the independent identity reference.
     observed=to_observe(f,side,names)
     for e in observed['entities']:
      if e['card_id']==203000023:e['card_id']=26000023;e['name']='IceWizard';e['status_flags']=16
     reference=O.from_engine(observed,side,deck,engine_deck=names,unmapped=set(),feature_version=feature)
     assert b==reference;conversions+=1
  census.append(dict(file=p.name,sha256=sha(p),decisions=seen,hero_body_entries=entries));totalrows+=seen;totalentries+=entries
 assert (totalrows,totalentries,conversions)==(1169,2435,4676)
 # Opponent player block has no influence on this public body conversion.
 f=frame(first,first['observer_side']);before=to_observe(f,first['observer_side'],names)
 f['players'][1]=dict(side=1-first['observer_side'],hand_deck_indices=[99]*4,elixir_raw=-999999,next_deck_index=99,deck_card_ids=[42]*8)
 assert to_observe(f,first['observer_side'],names)==before
 dead=copy.deepcopy(f)
 for e in dead['entities']:
  if e['card_id']==203000023:e['hp']=0
 assert not any(u.cls==2 and u.form==2 for u in board(dead,first['observer_side'],7).units)
 unknown=copy.deepcopy(f)
 for e in unknown['entities']:
  if e['card_id']==203000023:e['card_id']=203999999
 assert not any(u.cls==2 and u.form==2 for u in board(unknown,first['observer_side'],7).units)
 assert sha(catalog)==catalogsha
 live=ROOT/'scratchpad/gauntlet/L70/live';stop=live/'STOP';st=(stop.stat().st_mtime_ns,stop.read_bytes())
 command=['C:/Program Files/Git/bin/bash.exe','scratchpad/gauntlet/L70/live/start_live.sh','--check']
 env={k:v for k,v in os.environ.items() if k.upper() not in ('CKPT','HAND_READER')}
 run=subprocess.run(command,cwd=ROOT,env=env,text=True,capture_output=True,timeout=180)
 (HERE/'startup.out').write_text(run.stdout+run.stderr);assert run.returncode==0
 settings=[json.loads(s) for s in run.stdout.splitlines() if s.startswith('{"check":')];assert len(settings)==1
 s=settings[0];assert s['check']=='LIVE_CHECK_PASS' and s['sha256']=='76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd'
 assert s['device']=='cpu' and s['public_audit'] and s['tau']==.35 and not s['anti_leak'] and 'hand-reader model input: 0' in run.stdout
 assert st==(stop.stat().st_mtime_ns,stop.read_bytes())
 sourcefiles=[Path(__file__),HERE/'PLAN.md',HERE/'original/obs_contract.py',ROOT/'pipeline/obs_contract.py',ROOT/'pipeline/reader_identity_aliases.py',ROOT/'pipeline/live_mem.py',ROOT/'pipeline/public_observation.py',ROOT/'scratchpad/gauntlet/L68/live_reader/hero_button.py',catalog]
 result=dict(complete=True,rows=totalrows,raw_body_entries=totalentries,conversion_checks=conversions,census=census,
  existing_mappings_unchanged=len(oldnames),alias_count=1,conflict_negative_controls=negative,private_invariance=True,dead_and_unknown_controls=True,
  sources={str(p.relative_to(ROOT)):sha(p) for p in sourcefiles},settings=s,startup_command=command,stop_unchanged=True,live_started=False,checkpoint_changed=False,gameplay_improvement_unmeasured=True)
 (HERE/'verified.json').write_text(json.dumps(result,indent=2));print('READER_HERO_IDENTITY_REPAIRED')
if __name__=='__main__':main()
