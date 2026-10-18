"""Pod-only aggregate readout, using existing strict-fight/card-agreement definitions.

Whole-match paired bootstrap, 2000 draws, seed 0. Arms splice their finished
match files over FIN12, exactly as diag_night/r5c/cmp.py does. Never lands patches.
"""
import collections,datetime,json,pathlib,random,sys
P=pathlib.Path
cb=next(p for p in (P('/workspace/cb12'),P('/workspace/w_r7d/cb'),P('/workspace/w_r7b/cb')) if p.is_dir())
sys.path.insert(0,str(cb))
from scratchpad.gauntlet.L74.parity import fights as F
base_dir=P('/workspace/results/FIN12')
assert (base_dir/'DONE').exists()
cache={}
def load(path,stamped):
 key=(str(path),stamped)
 if key in cache:return cache[key]
 m=json.loads(path.read_text())
 out={}
 if not m['summary'].get('skipped') and (not stamped or m['summary'].get('phase3b_births')):
  for r in m.get('fights',[]):
   if 'error' in r or not F.is_clean(r,'strict'):continue
   s=F.card_scores(r)
   if s is None:continue
   a=r['anchor'];ident=(r['t0'],r['own'],a['name'],a['form'])
   out[ident]=s['aK']
 cache[key]=out
 return out
def score(paths,stamp):
 return {name:load(p,stamp) for name,p in paths.items()}
def ci(a,b):
 keys=sorted(k for k in set(a)|set(b) if a.get(k) or b.get(k));rng=random.Random(0)
 av=[(sum(a.get(k,{}).values()),len(a.get(k,{}))) for k in keys]
 bv=[(sum(b.get(k,{}).values()),len(b.get(k,{}))) for k in keys]
 avn=sum(n for _,n in av);bvn=sum(n for _,n in bv)
 if not avn or not bvn:return None
 raw_a=sum(s for s,_ in av)/avn;raw_b=sum(s for s,_ in bv)/bvn
 ba=[];bb=[];dd=[]
 for _ in range(2000):
  idx=rng.choices(range(len(keys)),k=len(keys))
  na=sum(av[i][1] for i in idx);nb=sum(bv[i][1] for i in idx)
  if not na or not nb:continue
  ma=sum(av[i][0] for i in idx)/na;mb=sum(bv[i][0] for i in idx)/nb
  ba.append(ma);bb.append(mb);dd.append(100*(mb-ma))
 def pct(x):
  x.sort();return [x[int(.025*len(x))],x[max(0,int(.975*len(x))-1)]]
 up=down=0
 for k in keys:
  for f in set(a.get(k,{}))&set(b.get(k,{})):
   up+=b[k][f]>a[k][f];down+=b[k][f]<a[k][f]
 return dict(base_n=avn,arm_n=bvn,base_raw=raw_a,base_ci95=pct(ba),arm_raw=raw_b,arm_ci95=pct(bb),delta_pp=100*(raw_b-raw_a),delta_ci95_pp=pct(dd),up=up,down=down)
groups={
 'H-SNAP-BACK':['r7a_S2_st','r7a_S2_oth'],
 'H-PREROLL':['r7a_P2_st','r7a_P2_oth'],
 'H-PREROLL + H-SNAP-BACK (upgraded arm only)':['r7a_J_st'],
 'H-IW-PRESS-DATE v4':['r7b_pd'],
 'H-IW-PRESS-DATE v5':['r7b_pd5'],
 'S-HOLD-REACH':['r7b_hr'],
 'S-EK-HITTICK':['r7c_ht'],
 'S-PULSE-TWICE':['r7c_pulse'],
 'H-FIXED-AIM v1':['r7c_fixaim'],
 'H-FIXED-AIM v2':['r7c_fixaim2'],
 'r7c joint':['r7c_joint'],
 'H-VOLLEY':['r7d_vol'],
 'H-TPL-ANYBODY':['r7d_tpl'],
 'H-CUBE-DATE v1':[f'r7d_cube_{s}{i}' for s in ('st','un') for i in range(3)],
 'H-CUBE-DATE v2 (available shards)':['r7d_cube2_st0','r7d_cube2_st1','r7d_cube2_st20','r7d_cube2_st21','r7d_cube2_st22'],
 'H-VOLLEY + H-CUBE-DATE v2':[f'r7d_joint_{s}{i}' for s in ('st','un') for i in range(3)],
 'H-NEGHP':[f'r7d_ng{i}' for i in range(3)],
 'S-EVOWITCH-CLOCK':['r7d_ewc'],
 'verifier H-VOLLEY':['v7_r7d_vol'],
 'verifier H-FIXED-AIM v2':['v7_r7c_fixaim'],
 'verifier S-PULSE-TWICE':['v7_r7c_pulse','v7_r7c_pulse_rest'],
 'verifier S-EK-HITTICK':['v7_r7c_ht'],
 'verifier S-HOLD-REACH':['v7_r7b_hr'],
 'verifier joint':['v7_r7d_joint'],
 'verifier H-CUBE-DATE':['v7_r7d_cube_arm'],
 'verifier null':['v7_r7b_null'],
 'closer H-SNAP-BACK':['v7c_snap'],
 'closer S-HOLD-REACH':['v7c_hr'],
}
base={p.name:p for p in (base_dir/'matches').glob('*.json')}
baselines={s:score(base,s) for s in (False,True)}
results=[]
for label,names in groups.items():
 dirs=[P('/workspace/results')/n for n in names]
 if not all((d/'DONE').exists() for d in dirs):continue
 arm=dict(base);replaced={}
 for d in dirs:replaced.update({p.name:p for p in (d/'matches').glob('*.json')})
 arm.update(replaced)
 row=dict(label=label,dirs=names,arm_logs=len(replaced),spliced_over='FIN12',cohorts={})
 for stamped in (False,True):
  if 'upgraded arm only' in label and not stamped:continue
  row['cohorts']['upgraded' if stamped else 'full']=ci(baselines[stamped],score(arm,stamped))
 results.append(row)
 print(label,'scored',flush=True)
out=P('/workspace/codex1018_parity');out.mkdir(exist_ok=True)
(out/'paired_scores.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),method='2000 paired whole-match bootstrap draws, seed 0, percentile CI; existing fights.is_clean/card_scores; affected match files spliced over FIN12',results=results),indent=2)+'\n')
(out/'DONE').touch()
print('PARITY_READOUT_DONE',len(results),flush=True)
