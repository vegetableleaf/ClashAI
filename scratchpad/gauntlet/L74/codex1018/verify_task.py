"""Bounded artifact checks. Does not train, evaluate games, stage, commit, or send."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
BACKUP=Path('C:/Users/benpe/pod_backup_weekend/codex1018')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def inventory_check():
 rows=read(HERE/'job_snapshot.json')['pods']
 assert {r['port'] for r in rows}=={15617,19899,13396,14009,30988,19834,10757,19400,34210,38758,23363,29286,23408}
 assert all(r['keep'] for r in rows if r['reachable'])
 jobs=read(HERE/'local_jobs.json')['jobs']
 assert {j['recorded_pid'] for j in jobs}=={10448,26708,41080}
 assert all(j['status'] in ('alive','done','failed') and j['evidence'] for j in jobs)
 print('INVENTORY_VERIFIED')
def ticket_check():
 ticket=(HERE.parent/'stepd/EXECUTOR_TICKET.md').read_text()
 assert 'anchored to the PRO-IMITATION policy (IL-cue), VERY loose' in ticket
 assert 'CARD choice only' in ticket and 'no other heads leashed' in ticket
 assert 'supersedes the earlier CLIII-anchor' in ticket
 assert 'Corrected EXECUTOR_TICKET.md decision 6' in (HERE.parent/'stepd/STATUS.md').read_text()
 print('TICKET_VERIFIED')
def backups_check():
 receipts=list(BACKUP.glob('*/*/COPY_VERIFIED.json'));assert receipts
 unique=set();copied=set()
 for p in receipts:
  r=read(p);assert r['verified']
  copied.update((r['port'],root) for root in r['roots'])
  manifests=list(p.parent.glob('*.manifest.json'));assert len(manifests)==1
  m=read(manifests[0]);assert r['files']==len(m['files']) and r['archive_sha256']==m['archive_sha256']
  for root in r['roots']:
   name=Path(root).name
   if re.fullmatch(r's2_all_il_s[AB]',name):
    assert f'cb_tt/icebow/data/bench/rl_royale/{name}/{name}_u0130.pt' in m['files'],'Stage-2 final checkpoint not backed up'
  archive=p.parent/Path(m['archive']).name
  assert archive.is_file() and archive.stat().st_size>0
  for rel,f in m['files'].items():
   local=p.parent/rel
   assert local.is_file() and local.stat().st_size==f['bytes'],str(local)
   unique.add((r['port'],rel))
 # Every completed assigned root seen at the reporting cut must have a full
 # verified receipt. Partial seed receipts do not substitute for checkpoints.
 for pod in read(HERE/'job_snapshot.json')['pods']:
  for result in pod.get('results',[]):
   path=result['path']
   assigned=path.startswith(('/workspace/results/r7','/workspace/results/v7_','/workspace/results/v7c_','/workspace/results/FIN13','/workspace/results/FIN14','/workspace/c3/results_','/workspace/ab2/results_cue_ab2','/workspace/s2/runs/s2_all_il_s','/workspace/codex1018')) or path in ('/workspace/combo/runs/combo_ctl_c3','/workspace/combo/runs/combo_rew_c3')
   if assigned and any(m in result['markers'] for m in ('DONE','ALL_DONE')):
    assert (pod['port'],path) in copied,'finished assigned root lacks a full verified backup: '+str(pod['port'])+' '+path
 print('BACKUP_RECEIPTS_VERIFIED',len(receipts),'archives',len(unique),'unique source files; per-file SHA verified at copy time')
def scores_check():
 rows=read(HERE/'candidate_scores.json')
 assert any(r['comparisons'] for r in rows),'no completed candidate comparison'
 for r in rows:
  for k,s in r['comparisons'].items():
   assert s['pairs']==(1920 if k=='pooled' else 960)
   assert s['ci95_pp'][0]<=s['delta_pp']<=s['ci95_pp'][1]
  if r.get('standard_and_fresh_gain'):
   assert all(r['comparisons'][k]['ci95_pp'][0]>0 for k in ('std','fresh'))
 required=[r for r in rows if r['candidate']!='c3_ab']
 assert len(required)==7 and all(all(k in r['comparisons'] for k in ('std','fresh')) for r in required),'one of the scheduled standard/fresh comparisons is incomplete'
 identities=read(HERE/'source_identity_summary.json')
 assert all(not c['differences'] for c in identities['comparisons'].values())
 verified=read(HERE/'source_identity_verified.json')
 assert verified['unchanged'] and verified['source_map_sha256']==hashlib.sha256(json.dumps(identities['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
 parity=read(HERE/'round7_paired_scores.json');assert len(parity)>=23
 for r in parity:
  for s in r['cohorts'].values():
   assert s['base_n']>0 and s['arm_n']>0
   assert s['delta_ci95_pp'][0]<=s['delta_pp']<=s['delta_ci95_pp'][1]
 print('SCORES_VERIFIED')
def preservation_check():
 data=read(HERE/'preservation.json')
 for rel,digest in data.items():
  if rel in ('initial_head','stale_handoff_initial') or digest is None:continue
  assert hashlib.sha256((REPO/rel).read_bytes()).hexdigest()==digest,rel
 assert data['HANDOFF.md']==data['stale_handoff_initial']
 print('PRESERVATION_VERIFIED')
def report_check():
 report=(HERE/'REPORT.md').read_text()
 assert len(report)>1500 and 'edc82ada' in report
 assert '47.8%' in report and '+4.4' in report
 assert all(str(p) in report for p in (15617,19899,13396,14009,30988,19834,10757,19400,34210,38758,23363,29286,23408))
 assert 'CANDIDATE_RESULTS.md' in report and 'ROUND7_RESULTS.md' in report
 assert not re.search(r'TODO|TBD|PLACEHOLDER|IN PROGRESS|will be refreshed before publication|Publication checks will',report)
 print('REPORT_VERIFIED')
def summary_check():
 text=(HERE/'discord_summary.txt').read_text().strip();assert 0<len(text)<=900
 print('SUMMARY_LENGTH_VERIFIED',len(text))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('gate',choices=['inventory','ticket','backups','scores','preservation','report','summary']);a=ap.parse_args()
 globals()[a.gate+'_check']()
