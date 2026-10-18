"""Reduce inventories and verified receipts to reviewable publication evidence."""
import json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=Path('C:/Users/benpe/pod_backup_weekend/codex1018')
source=sorted(HERE.glob('inventory_*.json'))[-1]
pods=json.loads(source.read_text())
out=[]
for pod in pods:
 record={k:pod[k] for k in ('host','port','reachable')}
 if pod['reachable']:
  record.update({k:pod[k] for k in ('utc','keep','free_gib')})
  active=[j for j in pod['jobs'] if j['kinds']]
  record['active_job_parents']=[j for j in active if j['ppid'] not in {k['pid'] for k in active}]
  results=[]
  for r in pod['results']:
   x=dict(path=r['path'],markers=r['markers'],completed_eval_rows=sum(m['rows'] for m in r['matches']))
   train='\n'.join(line for log in r['logs'] if log['name']=='train.log' for line in log['tail'])
   updates=re.findall(r'\[rl\] u(\d+)',train)
   if updates:x['training_update']=int(updates[-1])
   if 'DONE: max_updates' in train:x['training_done']=True
   results.append(x)
  record['results']=results
  record['stepd']=pod.get('stepd',{})
 else:
  record['current_evidence']='SSH connection refused'
  record['prior_record']='HEAD SESSION HANDOVER says stopped before this worker ticket; no lifecycle action by Codex'
 out.append(record)
local=json.loads((HERE/'local_workers_current.json').read_text(encoding='utf-8-sig'))
workers=[dict(kind=w['kind'],root_pid=w['root_pid'],process_count=len(w['processes']),status='alive') for w in local['workers']]
(HERE/'job_snapshot.json').write_text(json.dumps(dict(source_inventory=source.name,local_checked_utc=local['checked_utc'],local_workers=workers,pods=out),indent=2)+'\n')
receipts=[];unique=set()
for p in sorted(ROOT.glob('*/*/COPY_VERIFIED.json')):
 r=json.loads(p.read_text());assert r['verified']
 manifest=json.loads(next(p.parent.glob('*.manifest.json')).read_text())
 unique.update((r['port'],f) for f in manifest['files'])
 receipts.append(r)
(HERE/'backup_index.json').write_text(json.dumps(dict(receipts=receipts,archive_count=len(receipts),unique_source_files=len(unique),method='Remote SHA-256 manifest; archive SHA-256 verification; safe extraction; every extracted file SHA-256 and byte count verified; Linux text and Git-Bash binary hash modes normalized'),indent=2)+'\n')
print('PUBLICATION_EVIDENCE',len(out),'pods;',len(receipts),'verified archives;',len(unique),'unique source files')
