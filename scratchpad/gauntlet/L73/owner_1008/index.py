import json,glob,os,collections
rows=[]
for f in sorted(glob.glob('../../L68/live_reader/live_play_*.jsonl')):
    st=None; n=collections.Counter(); maxtick=0; ab=0
    with open(f) as fh:
        for l in fh:
            if '"event": "start"' in l[:30] and st is None:
                st=json.loads(l)
            e=l[11:40].split('"')[0]
            n[e]+=1
    if st is None: continue
    do=st.get('decision_options') or {}
    rows.append(dict(f=os.path.basename(f),sha=(st.get('ckpt_sha256') or '')[:8],al=st.get('anti_leak'),aim=do.get('spell_aim'),
        dry=st.get('dry_run'),dec=n['decision'],play=n['play'],ab=n['ability'],abc=n['ability_confirmed'],stop=n['stop'],fv=st.get('feature_version')))
json.dump(rows,open('index.json','w'))
c=collections.Counter((r['sha'],r['al'],r['aim'],r['dry']) for r in rows if r['dec']>50)
for k,v in sorted(c.items(),key=lambda x:-x[1]): print(k,v)
