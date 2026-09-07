#!/bin/bash
# L67c: fetch the 52 replay parts of VanguardX101/IL_Replay (825 MB); resumable; verifies sha256 from the manifest.
cd /c/Users/benpe/ClashBot/scratchpad/gauntlet/L67/hf
python - <<'PY'
import json,hashlib,subprocess,os,sys
m=json.load(open('../hf_manifest.json'))
parts=[f for f in m['files'] if f['path'].startswith('replays/')]
ok=bad=0
for f in parts:
    p=f['path']; url='https://huggingface.co/datasets/VanguardX101/IL_Replay/resolve/main/'+p
    if os.path.exists(p) and os.path.getsize(p)==f['bytes']:
        pass
    else:
        subprocess.run(['curl','-sL','--retry','5','-o',p,url],check=True)
    h=hashlib.sha256(open(p,'rb').read()).hexdigest()
    if h==f['sha256']: ok+=1
    else: bad+=1; print('BAD',p,flush=True); os.remove(p)
    print(p,'ok' if h==f['sha256'] else 'bad',flush=True)
print('DONE ok',ok,'bad',bad,flush=True)
PY
