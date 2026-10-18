"""Read-only, bounded job inventory. Never emits process arguments or environment."""
import base64
import concurrent.futures
import datetime
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
PODS = [('216.81.151.5',15617),('64.247.206.76',19899),('64.247.206.76',13396),('64.247.206.76',14009),('64.247.206.80',30988),('64.247.206.120',19834),('64.247.206.79',10757),('64.247.206.79',19400),('216.81.245.71',34210),('216.81.245.71',38758),('81.27.69.177',23363),('216.81.245.71',29286),('81.27.69.177',23408)]
REMOTE = r'''
import datetime,json,pathlib,re,subprocess,shutil
P=pathlib.Path
jobs=[]
for p in P('/proc').iterdir():
 if not p.name.isdigit(): continue
 try:
  args=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  comm=(p/'comm').read_text().strip()
  if comm not in ('python','python3','python3.11','python3.12','bash','flock','cargo','rustc'): continue
  if args.startswith('python3 -c import base64'): continue
  labels=[s for s in ('rl_royale','gap.py','search_s0','fights.py','s2chain','chain_c3','c3_chain','chain_ab2','run14009_c3','train_gen','cue_drive','cue_sidecar','cargo','rustc','codex1018/run_eval.sh','codex1018_combo_eval/run.sh','codex1018_combo_fresh_rules/run.sh','d1_waiter.sh','d1_data_pod.sh','d2a_nocue_pod.sh','d2b_cue_pod.sh','_train_every_epoch.py','arm_waiter.sh','ref_waiter.sh','stepd_smoke.sh','stepd_chain.sh') if s in args]
  runs=sorted(set(re.findall(r'(?:s2_all_il_s[AB]|combo_(?:ctl|rew)_c3|cue_ab2(?:_sample)?|c3_(?:ab|ctl)|clIII_ref|clIII_fin13|stepd_(?:ctrl_nos2|ctrl|rebc3|reb)|FIN1[34][a-zA-Z0-9_]*|r7[a-d][a-zA-Z0-9_]*|v7_[a-zA-Z0-9_]+)',args)))
  stat=(p/'stat').read_text().split()
  jobs.append(dict(pid=int(p.name),ppid=int(stat[3]),state=stat[2],comm=comm,kinds=labels,runs=runs))
 except (OSError,ValueError): pass
roots=[]
for pat in ('s2/runs/s2_all_il_s*','combo/runs/*','ab2/results_*','c3/results_*','results/r7*','results/v7_*','results/v7c_*','results/FIN13*','results/FIN14*','codex1018/results','codex1018_combo_eval/results','codex1018_combo_fresh_rules/results'):
 roots += list(P('/workspace').glob(pat))
results=[]
for root in roots:
 if not root.is_dir():continue
 markers=[p.name for p in root.iterdir() if p.is_file() and p.name in ('DONE','ALL_DONE','FAILED','COPIED','COPY_OK','SMOKE_PASS')]
 matches=[]
 for p in root.glob('**/D3/matches.jsonl'):
  n=sum(1 for line in p.open() if line.strip())
  matches.append(dict(path=str(p.relative_to(root)),rows=n))
 logs=[]
 for p in root.glob('*.log'):
  lines=p.read_text(errors='replace').splitlines()[-4:]
  safe=[]
  for line in lines:
   if re.search(r'reader|offset|sampler|api.key|anthropic|authorization|sk-|webhook|https?://',line,re.I):continue
   safe.append(line[:280])
  logs.append(dict(name=p.name,mtime=p.stat().st_mtime,tail=safe))
 results.append(dict(path=str(root),markers=markers,matches=matches,logs=logs))
bundles=[]
for pat in ('s2/out/*.tgz.sha','combo/out/*.tgz.sha'):
 for p in P('/workspace').glob(pat):bundles.append(dict(path=str(p),mtime=p.stat().st_mtime))
stepd={}
for rel in ('d2/D2A_DONE','d2/D2B_DONE','d1/DONE'):
 stepd[rel]=P('/workspace/stepd',rel).is_file()
stepd['logs']=[]
for rel in ('d2/d2.log','d1_waiter.log','arm_waiter.log','ref_waiter.log'):
 p=P('/workspace/stepd',rel)
 if not p.is_file():continue
 lines=[line[:280] for line in p.read_text(errors='replace').splitlines()[-3:] if not re.search(r'reader|offset|sampler|api.key|anthropic|authorization|sk-|webhook|https?://',line,re.I)]
 stepd['logs'].append(dict(name=rel,mtime=p.stat().st_mtime,tail=lines))
print(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),keep=P('/workspace/KEEP').exists(),free_gib=round(shutil.disk_usage('/workspace').free/2**30,2),jobs=jobs,results=results,bundles=bundles,stepd=stepd)))
'''

def probe(pair):
    host, port = pair
    encoded = base64.b64encode(REMOTE.encode()).decode()
    command = 'python3 -c "import base64;exec(base64.b64decode(\'' + encoded + '\'))"'
    argv = ['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=1','-i',str(Path.home()/'.ssh/runpod_clashbot'),'-p',str(port),'root@'+host,command]
    try:
        r = subprocess.run(argv,capture_output=True,text=True,timeout=45)
        if r.returncode: return dict(host=host,port=port,reachable=False,error=r.stderr.strip()[:200])
        return dict(host=host,port=port,reachable=True,**json.loads(r.stdout))
    except Exception as exc:
        return dict(host=host,port=port,reachable=False,error=type(exc).__name__)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        rows = list(pool.map(probe,PODS))
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out=HERE/('inventory_'+stamp+'.json')
    out.write_text(json.dumps(rows,indent=2)+'\n')
    print(out)
    for r in rows:
        if not r['reachable']:print(r['port'],'UNREACHABLE',r['error']);continue
        active=[j for j in r['jobs'] if j['kinds']]
        parents=[j for j in active if j['ppid'] not in {k['pid'] for k in active}]
        print(r['port'],'ALIVE',r['free_gib'],'GiB free','job parents:',parents[:8])
        for x in r['results']:
            if '/workspace/results/' in x['path']:continue
            print(' ',x['path'],x['markers'],'eval rows',sum(m['rows'] for m in x['matches']))
            for log in x['logs']:
                if log['name']=='train.log' and log['tail']:print('  ',log['tail'][-1][:55])
