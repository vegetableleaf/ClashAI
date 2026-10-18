"""Read verified backups using live_cmp's existing paired bootstrap; no SIM locally."""
import hashlib,json,math,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
L74=HERE.parent
ROOT=Path('C:/Users/benpe/pod_backup_weekend/codex1018')
sys.path.insert(0,str(L74/'mix'))
import live_cmp
CLIII='edc82ada38e102369f9e99bdd681df16355851185ae44b95027378b404289952'
STD=(741200,742000);FRESH=(743000,744000)
latest={}
for p in sorted(ROOT.glob('*/*/COPY_VERIFIED.json')):
 r=json.loads(p.read_text())
 if r['verified']:
  for remote in r['roots']:latest[(r['port'],remote)]=p.parent/Path(remote).relative_to('/workspace')

def root(port,remote):
 full=latest.get((port,remote))
 if full is not None:return full
 children=[(r,p) for (rp,r),p in latest.items() if rp==port and r.startswith(remote+'/')]
 if not children:return None
 # A local view contains only rows/plans copied from independently SHA-verified,
 # finished seed archives. It never reads an in-flight pod output.
 view=ROOT/'completed_seed_views'/str(port)/Path(remote).relative_to('/workspace')
 for r,p in children:
  for rel in ('D3/matches.jsonl','inputs/plan.json'):
   target=view/Path(r).relative_to(remote)/rel;target.parent.mkdir(parents=True,exist_ok=True)
   shutil.copy2(p/rel,target)
 return view
def resolve(base,*parts):return None if base is None else base.joinpath(*parts)
def rows(directory,name,seeds,baseline=False):
 if directory is None:return None
 out=[]
 for seed in seeds:
  d=directory/f'{name}_{seed}';p=d/'D3/matches.jsonl'
  if not p.is_file():return None
  values=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
  if len(values)!=480:return None
  plan=d/'inputs/plan.json'
  if baseline:
   assert plan.is_file(),'baseline plan missing'
   assert json.loads(plan.read_text())['files'][0]['sha256']==CLIII,'baseline is not CLIII'
  out.extend(values)
 return out

def model_identity(directory,name,seeds):
 hashes={json.loads((directory/f'{name}_{s}'/'inputs/plan.json').read_text())['files'][0]['sha256'] for s in seeds}
 assert len(hashes)==1,'checkpoint changed between seed sets'
 return next(iter(hashes))

def wilson(w,n):
 z=1.959963984540054;p=w/n;den=1+z*z/n
 m=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
 return [100*(m-h),100*(m+h)]

def behaviour(old,new):
 """Existing habit counts and recorded accepted presses; no new play rules."""
 import numpy as np
 a={(r['census'],r['seed']):r for r in old};b={(r['census'],r['seed']):r for r in new}
 assert a.keys()==b.keys()
 keys=sorted(a);metrics={}
 if all('own_presses' in r for r in old+new):metrics['accepted_ability_presses_per_game']=lambda r:len(r['own_presses'])
 for field in ('rocket','tornado'):
  if all(field in r.get('habits',{}) for r in old+new):metrics[field+'_per_game']=lambda r,f=field:r['habits'][f]
 for field in ('presses_froze','frozen_elixir'):
  if all(field in r.get('ability_stats',{}) for r in old+new):metrics[field+'_per_game']=lambda r,f=field:r['ability_stats'][f]
 if not metrics:return {}
 av=np.array([[fn(a[k]) for fn in metrics.values()] for k in keys],dtype=float)
 bv=np.array([[fn(b[k]) for fn in metrics.values()] for k in keys],dtype=float)
 strata={}
 for i,k in enumerate(keys):strata.setdefault((k[0],a[k]['learner_side']),[]).append(i)
 rng=np.random.default_rng(20261018);boot=np.zeros((2000,len(metrics)))
 for ids in strata.values():
  d=(bv-av)[ids];boot+=d[rng.integers(len(ids),size=(2000,len(ids)))].sum(axis=1)
 lo,hi=np.quantile(boot/len(keys),[.025,.975],axis=0)
 return {name:dict(baseline_mean=float(av[:,i].mean()),candidate_mean=float(bv[:,i].mean()),delta=float((bv-av)[:,i].mean()),ci95=[float(lo[i]),float(hi[i])],method='2000 paired bootstrap draws within census and learner side') for i,name in enumerate(metrics)}

ref_c3=resolve(root(14009,'/workspace/c3/results_clIII_ref'),'eval')
cue=root(30988,'/workspace/codex1018/results')
combo_ref=root(19400,'/workspace/codex1018_combo_eval/results')
contexts={
 'cue_same_code':dict(ref=(cue,'clIII_ref'),candidates={n:{'std':(cue,n),'fresh':(cue,n)} for n in ('cue_ab2_sample','cue_ab2')}),
 'c3_same_code':dict(ref=(ref_c3,'clIII_ref'),candidates={n:{k:(resolve(root(p,'/workspace/c3/results_'+n),'eval'),n) for k in ('std','fresh')} for n,p in (('c3_ab',14009),('c3_ctl',10757))}),
 'combo_off':dict(ref=(combo_ref,'clIII_ref'),candidates={n:{'std':(resolve(root(p,'/workspace/combo/runs/'+n),'eval_off'),n),'fresh':(root(p,'/workspace/codex1018_combo_eval/results'),n)} for n,p in (('combo_ctl_c3',19400),('combo_rew_c3',34210))}),
 'combo_offc':dict(ref=(root(34210,'/workspace/codex1018_combo_eval/results'),'clIII_ref_offc'),ref_fresh=(root(34210,'/workspace/codex1018_combo_fresh_rules/results'),'clIII_ref_offc'),candidates={n:{'std':(resolve(root(p,'/workspace/combo/runs/'+n),'eval_offc'),n),'fresh':(root(p,'/workspace/codex1018_combo_fresh_rules/results'),n)} for n,p in (('combo_ctl_c3',19400),('combo_rew_c3',34210))})}
records=[];baselines=[]
for context,c in contexts.items():
 base={k:rows(*(c.get('ref_fresh',c['ref']) if k=='fresh' else c['ref']),seeds,baseline=True) for k,seeds in (('std',STD),('fresh',FRESH))}
 for k,rs in base.items():
  if rs is not None:
   bw=sum(r['outcome']=='win' for r in rs)
   baselines.append(dict(context=context,seed_set=k,wins=bw,games=len(rs),win_ci95=wilson(bw,len(rs)),checkpoint_sha256=CLIII))
 for name,sources in c['candidates'].items():
  rec=dict(context=context,candidate=name,comparisons={},missing=[])
  candidate={k:rows(*src,STD if k=='std' else FRESH) for k,src in sources.items()}
  for key in sources:
   if base[key] is None or candidate[key] is None:
    rec['missing'].append(key);continue
   rec['comparisons'][key]=live_cmp.paired_drift(base[key],candidate[key],expected=960)
   rec['comparisons'][key]['checkpoint_sha256']=model_identity(*sources[key],STD if key=='std' else FRESH)
   w=sum(r['outcome']=='win' for r in candidate[key])
   bw=sum(r['outcome']=='win' for r in base[key])
   rec['comparisons'][key].update(candidate_wins=w,win_ci95=wilson(w,960),baseline_wins=bw,baseline_win_ci95=wilson(bw,960))
   rec['comparisons'][key]['behaviour']=behaviour(base[key],candidate[key])
  if all(k in rec['comparisons'] for k in ('std','fresh')):
   assert rec['comparisons']['std']['checkpoint_sha256']==rec['comparisons']['fresh']['checkpoint_sha256']
   rec['comparisons']['pooled']=live_cmp.paired_drift(base['std']+base['fresh'],candidate['std']+candidate['fresh'],expected=1920)
   w=sum(r['outcome']=='win' for r in candidate['std']+candidate['fresh'])
   bw=sum(r['outcome']=='win' for r in base['std']+base['fresh'])
   rec['comparisons']['pooled'].update(candidate_wins=w,win_ci95=wilson(w,1920),baseline_wins=bw,baseline_win_ci95=wilson(bw,1920))
   rec['standard_and_fresh_gain']=all(rec['comparisons'][k]['ci95_pp'][0]>0 for k in ('std','fresh'))
  records.append(rec)
 # Exercise the unchanged live_cmp CLI for each completed standard-seed context.
 complete=[r['candidate'] for r in records if r['context']==context and 'std' in r['comparisons']]
 if base['std'] is not None and complete:
  view=ROOT/'comparison_views'/context;view.mkdir(parents=True,exist_ok=True)
  sources={'clIII_ref':c['ref'],**{n:c['candidates'][n]['std'] for n in complete}}
  for alias,(directory,name) in sources.items():
   for seed in STD:
    out=view/f'{alias}_{seed}'/'D3';out.mkdir(parents=True,exist_ok=True)
    shutil.copy2(directory/f'{name}_{seed}'/'D3/matches.jsonl',out/'matches.jsonl')
  result=subprocess.run([sys.executable,str(L74/'mix/live_cmp.py'),str(view),*complete,'--base','clIII_ref'],capture_output=True,text=True)
  if result.returncode:raise RuntimeError('live_cmp CLI failed: '+result.stderr)
  (HERE/(context+'_live_cmp.txt')).write_text(result.stdout)
(HERE/'candidate_scores.json').write_text(json.dumps(records,indent=2)+'\n')
(HERE/'baseline_scores.json').write_text(json.dumps(baselines,indent=2)+'\n')
lines=['# Candidate SIM comparisons','',
       'Reference: ICEBOW Mark CLIII: LEVELS, grafted checkpoint '+CLIII+'. Standard seeds 741200+742000 and fresh seeds 743000+744000; 960 paired games each. The existing live_cmp / validate.paired_drift method uses 10,000 paired bootstrap draws within census and learner side. Draws count as non-wins. No live conclusions or deployment follow from these scores.','',
       '| Evaluation context | Candidate arm | Seed set | Wins / games | Win rate % [Wilson 95% CI] | CLIII wins | Delta vs CLIII, pp [paired 95% CI] |',
       '|---|---|---|---|---|---|---|']
for rec in records:
 for key,s in rec['comparisons'].items():
  lo,hi=s['ci95_pp'];wins=round(s['new_win_rate']*s['pairs'])
  wl,wh=s['win_ci95']
  lines.append(f"| {rec['context']} | {rec['candidate']} | {key} | {wins}/{s['pairs']} | {100*s['new_win_rate']:.2f} [{wl:.2f}, {wh:.2f}] | {s['baseline_wins']}/{s['pairs']} | {s['delta_pp']:+.2f} [{lo:+.2f}, {hi:+.2f}] |")
 for key in rec['missing']:lines.append(f"| {rec['context']} | {rec['candidate']} | {key} | pending | unavailable | unavailable | no complete paired result |")
lines+=['','The cue rerun uses the frozen C3 source and pinned fork36 SIM with both models evaluated in the same isolated environment. That pod has PyTorch 2.8.0; the original training/evaluation pods use 2.11.0, so original and rerun rows are kept separate. The original cue_ab2 archive used different evaluation code and is excluded from the promotion comparisons. C3 control/reference and combo control/reward public evaluation identities agree at all 21 checked paths, including matching absent optional files. The combo offc rows include the existing combo-rule setting; off rows are the historical promotion protocol. The added fresh offc follow-up uses the same frozen combo tree and settings as the original standard offc runs.', '', 'Each confidence interval is nominal. Arms are correlated, and no multiple-comparison correction has been applied. Pooled results are descriptive; they do not replace the requirement for a positive lower paired CI on both standard and fresh sets. A SIM pass is a candidate finding, with no demonstrated transfer to live.']
lines+=['','## CLIII reference results','','| Context | Seed set | Wins / games | Win rate % [Wilson 95% CI] |','|---|---|---|---|']
for b in baselines:
 lo,hi=b['win_ci95']
 lines.append(f"| {b['context']} | {b['seed_set']} | {b['wins']}/{b['games']} | {100*b['wins']/b['games']:.2f} [{lo:.2f}, {hi:.2f}] |")
lines+=['','## Recorded behavior','','Counts use the existing habit log and accepted-press records. Deltas resample matched games within census and learner side (2,000 draws). More presses or spells are not automatically better; these are behavior checks, not causal quality scores. Where available, presses_froze counts presses followed by at least one frozen enemy within the existing two-second observation; frozen_elixir is the catalogue elixir value of frozen enemies, not a causal economic reward.','','| Context / candidate | Seeds | Metric | CLIII / candidate mean | Delta [paired 95% CI] |','|---|---|---|---|---|']
for r in records:
 for seeds,s in r['comparisons'].items():
  for metric,m in s.get('behaviour',{}).items():
   lo,hi=m['ci95']
   lines.append(f"| {r['context']} / {r['candidate']} | {seeds} | {metric} | {m['baseline_mean']:.3f} / {m['candidate_mean']:.3f} | {m['delta']:+.3f} [{lo:+.3f}, {hi:+.3f}] |")
lines+=['','## Original archived results','',
        'These completed runs are retained with their own win-rate intervals. Cue and C3 used different evaluation code, so their totals are not a valid paired comparison against each other.', '',
        '| Archive | Seed set | Wins / games | Win rate % [Wilson 95% CI] |',
        '|---|---|---|---|']
archived=[]
archive_specs=[('cue_ab2',resolve(root(14009,'/workspace/ab2/results_cue_ab2'),'eval'),STD,'original cue'),
               ('cue_ab2_sample',resolve(root(14009,'/workspace/ab2/results_cue_ab2'),'eval'),STD,'original cue'),
               ('clIII_ref',ref_c3,STD,'C3 reference'),('clIII_ref',ref_c3,FRESH,'C3 reference')]
for name,port in (('combo_ctl_c3',19400),('combo_rew_c3',34210)):
 for mode in ('off','offc'):
  archive_specs.append((name,resolve(root(port,'/workspace/combo/runs/'+name),'eval_'+mode),STD,'combo '+mode))
for name,directory,seeds,archive_context in archive_specs:
 r=rows(directory,name,seeds,baseline=name=='clIII_ref')
 if r is None:continue
 w=sum(x['outcome']=='win' for x in r);lo,hi=wilson(w,len(r));seedset='standard' if seeds==STD else 'fresh'
 archived.append(dict(candidate=name,context=archive_context,seed_set=seedset,wins=w,games=len(r),win_ci95=[lo,hi],paired_comparison=False))
 lines.append(f'| {archive_context} / {name} | {seedset} | {w}/{len(r)} | {100*w/len(r):.2f} [{lo:.2f}, {hi:.2f}] |')
(HERE/'archived_scores.json').write_text(json.dumps(archived,indent=2)+'\n')
(HERE/'CANDIDATE_RESULTS.md').write_text('\n'.join(lines)+'\n')
print('CANDIDATE_READOUT',sum(len(r['comparisons']) for r in records),'complete comparisons;',sum(len(r['missing']) for r in records),'pending seed sets')
for r in records:
 if r['comparisons']:print(r['context'],r['candidate'],{k:(v['delta_pp'],v['ci95_pp']) for k,v in r['comparisons'].items()})
