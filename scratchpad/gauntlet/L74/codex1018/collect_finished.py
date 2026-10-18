"""One bounded copy pass for assigned jobs that have finished; never stops pods."""
import concurrent.futures,json
from pathlib import Path
import backup,inventory

COPIED=set()
for receipt in backup.DEST.glob('*/*/COPY_VERIFIED.json'):
    r=json.loads(receipt.read_text())
    if r.get('verified'):
        COPIED.update((r['port'],p) for p in r['roots'])

targets={13396:['/workspace/s2/runs/s2_all_il_sA','/workspace/s2/runs/s2_all_il_sA_smoke','/workspace/s2/runs/s2_all_il_sA_prep_smoke'],19834:['/workspace/s2/runs/s2_all_il_sB','/workspace/s2/runs/s2_all_il_sB_smoke'],
         14009:['/workspace/c3/results_c3_ab'],10757:['/workspace/c3/results_c3_ctl'],
         19400:['/workspace/combo/runs/combo_ctl_c3','/workspace/codex1018_combo_eval/results','/workspace/codex1018_combo_fresh_rules/results'],
         34210:['/workspace/combo/runs/combo_rew_c3','/workspace/codex1018_combo_eval/results','/workspace/codex1018_combo_fresh_rules/results'],
         30988:['/workspace/codex1018/results']}
with concurrent.futures.ThreadPoolExecutor(max_workers=7) as pool:
    statuses=list(pool.map(inventory.probe,[(h,p) for h,p in inventory.PODS if p in targets]))
for pod in statuses:
    if not pod['reachable']:print(pod['port'],'unreachable');continue
    todo=[]
    for r in pod['results']:
        if r['path'] not in targets[pod['port']]:continue
        if (pod['port'],r['path']) in COPIED:continue
        if not any(m in r['markers'] for m in ('ALL_DONE','DONE')):
            if any(tag in r['path'] for tag in ('/codex1018','/c3/','/combo/runs/')):
                for half in r['matches']:
                    child=r['path']+'/'+half['path'].removesuffix('/D3/matches.jsonl')
                    if half['rows']==480 and (pod['port'],child) not in COPIED:todo.append(child)
            continue
        # backup.copy also verifies and includes the final Stage-2 gate checkpoints.
        todo.append(r['path'])
    if todo:backup.copy(pod['host'],pod['port'],todo)
    else:print(pod['port'],'no newly finished assigned result')
