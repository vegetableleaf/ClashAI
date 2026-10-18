"""Bounded read-only collection of the public SIM source allowlist."""
import concurrent.futures,datetime,hashlib,json,subprocess,sys
from pathlib import Path
import inventory
HERE=Path(__file__).resolve().parent
def get(pair):
 host,port=pair
 out=subprocess.check_output([sys.executable,str(HERE/'remote.py'),host,str(port),str(HERE/'source_identity.py')],text=True)
 return str(port),json.loads(out)
with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
 data=dict(ex.map(get,[(h,p) for h,p in inventory.PODS if p in (14009,10757,19400,34210,30988)]))
if '--verify' in sys.argv:
 initial=HERE/'source_identity_summary.json'
 before=json.loads(initial.read_text())['files']
 changes={port:[n for n,v in paths.items() if before[port].get(n)!=v] for port,paths in data.items()}
 assert all(not names for names in changes.values()),'public evaluation source changed since initial inventory: '+str(changes)
 (HERE/'source_identity_verified.json').write_text(json.dumps(dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_map_sha256=hashlib.sha256(json.dumps(before,sort_keys=True,separators=(',',':')).encode()).hexdigest(),unchanged=True,ports=sorted(map(int,data)),paths_checked_per_pod=21),indent=2)+'\n')
 print('PUBLIC_EVALUATION_SOURCE_UNCHANGED',len(data),'pods, 21 paths each')
 raise SystemExit(0)
comparisons={}
for name,a,b in [('c3',14009,10757),('combo',19400,34210),('cue_c3_source',14009,30988)]:
 diffs=[n for n in data[str(a)] if data[str(a)][n]!=data[str(b)][n]]
 comparisons[name]=dict(ports=[a,b],checked=len(data[str(a)]),differences=diffs)
 print(name,'checked',len(data[str(a)]),'differences',diffs)
(HERE/'source_identity_summary.json').write_text(json.dumps(dict(files=data,comparisons=comparisons),indent=2)+'\n')
