"""flags-off vs flags-on input plays of one match: what the 20 hand rules changed (plays only)."""
import json,sys,glob,os
B='C:/Users/benpe/ClashBot/.foreman/scratch/recon2/'
def get(tag,m):
    for f in sorted(glob.glob(B+tag+'/f*.jsonl')):
        for l in open(f):
            r=json.loads(l)
            if r['match'].endswith(m): return r
K=('side','kind','card','run_ticks','x','y','source','unit_index','dated','ghost')
key=lambda p: json.dumps({k:p[k] for k in K if k in p},sort_keys=True)
for m in sys.argv[1:]:
    a,b=get('off',m),get('on',m)
    A=[key(p) for p in a['plays']];Bk=[key(p) for p in b['plays']]
    oo=[x for x in A if x not in Bk]; nn=[x for x in Bk if x not in A]
    print('==',m,'plays off',len(A),'on',len(Bk),'| flags-off-only',len(oo),'flags-on-only',len(nn))
    for x in oo[:8]: print('   OFF-only',x[:230])
    for x in nn[:8]: print('   ON-only ',x[:230])
    for k in ('own_cycle_fail','opp_fitting_deals','opp_deal_fit'):
        if a.get(k)!=b.get(k): print('   ',k,a.get(k),'->',b.get(k))
