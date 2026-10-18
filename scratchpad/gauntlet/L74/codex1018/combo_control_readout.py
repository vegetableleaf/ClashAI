"""Supplement the CLIII gate with paired reward-versus-control attribution."""
import json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'mix'))
import live_cmp
BACKUP=Path('C:/Users/benpe/pod_backup_weekend/codex1018')
copied={}
for p in sorted(BACKUP.glob('*/*/COPY_VERIFIED.json')):
 r=json.loads(p.read_text())
 if r['verified']:
  for root in r['roots']:copied[r['port'],root]=p.parent/Path(root).relative_to('/workspace')

def read_rows(port,parent,name,seeds):
 out=[]
 for seed in seeds:
  child=parent+'/'+name+'_'+str(seed)
  sources=[(remote,local) for (pod,remote),local in copied.items() if pod==port and (remote==child or child.startswith(remote+'/'))]
  if not sources:return None
  remote,local=max(sources,key=lambda pair:len(pair[0]))
  folder=local/Path(child).relative_to(remote)
  path=folder/'D3/matches.jsonl'
  values=[json.loads(s) for s in path.read_text().splitlines() if s.strip()]
  assert len(values)==480
  out.extend(values)
 return out

records=[]
for mode in ('off','offc'):
 for seeds,numbers in (('std',(741200,742000)),('fresh',(743000,744000))):
  arms=[]
  for name,port in (('combo_ctl_c3',19400),('combo_rew_c3',34210)):
   if seeds=='std':parent='/workspace/combo/runs/'+name+'/eval_'+mode
   else:parent='/workspace/codex1018_combo_'+('eval' if mode=='off' else 'fresh_rules')+'/results'
   arms.append(read_rows(port,parent,name,numbers))
  if any(a is None for a in arms):continue
  s=live_cmp.paired_drift(*arms,expected=960)
  records.append(dict(mode=mode,seeds=seeds,control_wins=sum(r['outcome']=='win' for r in arms[0]),reward_wins=sum(r['outcome']=='win' for r in arms[1]),**s))
lines=['# Combo reward versus its control','',
 'Supplementary paired comparison using the existing `mix/live_cmp.py` / `paired_drift` method on SHA-verified backups. Each row contains 960 paired games; 95% intervals use 10,000 paired bootstrap draws within census and learner side. Standard seeds: 741200 + 742000. Fresh seeds: 743000 + 744000. The standard comparisons were also checked with the unchanged live_cmp CLI and `--base combo_ctl_c3`.', '',
 '| Existing evaluation setting | Seeds | Control wins | Reward wins | Reward minus control, pp [95% CI] |',
 '|---|---|---:|---:|---|']
for s in records:
 lo,hi=s['ci95_pp']
 lines.append(f"| {s['mode']} | {s['seeds']} | {s['control_wins']}/960 | {s['reward_wins']}/960 | {s['delta_pp']:+.2f} [{lo:+.2f}, {hi:+.2f}] |")
lines+=['','These attribution comparisons do not replace the required standard **and** fresh comparisons against CLIII in [CANDIDATE_RESULTS.md](CANDIDATE_RESULTS.md). Intervals are nominal, with no correction for correlated arms. No live conclusion follows from a SIM interval.']
(HERE/'COMBO_CONTROL_RESULTS.md').write_text('\n'.join(lines)+'\n')
(HERE/'combo_control_scores.json').write_text(json.dumps(records,indent=2)+'\n')
print('COMBO_ATTRIBUTION_READOUT',len(records),'completed paired comparisons')
