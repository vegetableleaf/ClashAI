"""Copy newly finished Round-7/FIN13 directories; never starts or stops jobs."""
import concurrent.futures,json
import backup,inventory
copied=set()
for p in backup.DEST.glob('*/*/COPY_VERIFIED.json'):
 d=json.loads(p.read_text())
 if d.get('verified'):copied.update((d['port'],r) for r in d['roots'])
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
 pods=list(ex.map(inventory.probe,[(h,p) for h,p in inventory.PODS if p in (15617,19899)]))
for pod in pods:
 if not pod['reachable']:print(pod['port'],'unreachable');continue
 roots=[r['path'] for r in pod['results'] if r['path'].startswith(('/workspace/results/r7','/workspace/results/v7_','/workspace/results/v7c_','/workspace/results/FIN13','/workspace/results/FIN14'))
        and 'DONE' in r['markers'] and (pod['port'],r['path']) not in copied]
 if roots:backup.copy(pod['host'],pod['port'],roots)
 else:print(pod['port'],'no newly finished parity result')
