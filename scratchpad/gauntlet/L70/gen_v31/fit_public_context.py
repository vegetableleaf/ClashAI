"""Six recording-derived targets, fixed maximum loss weight 2.0, no sweep.

Run only after the lead's reviewed defensive X-Bow labels have been attached.
Outcome labels may use future frames; classifier features never do.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import torch
import torch.nn.functional as F
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
import importlib.util
spec=importlib.util.spec_from_file_location('prior_context',Path(__file__).with_name('fit_context.py'))
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
TARGETS=['tower_rocket','xbow_lane','defensive_rocket','rocket_then_tornado','tornado_then_rocket','defensive_xbow_rocket_cycle']
C.TARGETS=TARGETS

def labels(a,tags,meta,events):
    y=np.zeros((len(a['y_gate']),6),np.float32);known=np.ones_like(y)
    ids={n:i for i,n in enumerate(meta['card_vocab'])}
    index={}
    for i in np.flatnonzero((a['y_gate']==1)&np.isin(a['y_card'],[ids.get('rocket'),ids.get('x-bow')])):
        key=(str(tags[a['rep'][i]]),int(a['side'][i]),int(a['tick'][i]),int(a['y_card'][i]))
        if key in index:raise ValueError('Duplicate row join')
        index[key]=int(i)
    matched=set()
    for row in events:
        card=row['card'];i=index.get((row['tag'],row['side'],row['tick'],ids[card]))
        if i is None:continue
        if i in matched:raise ValueError('Duplicate label join')
        matched.add(i)
        if card=='rocket':
            for j,key in ((0,'tower_rocket'),(2,'defensive_rocket'),(3,'rocket_then_tornado'),(4,'tornado_then_rocket')):
                if row[key] is None:known[i,j]=0
                else:y[i,j]=row[key]
        else:
            if row.get('defensive_xbow') is None:raise ValueError('Defensive X-Bow label awaits LEAD_RULINGS')
            y[i,5]=row['defensive_xbow']
            y[i,1]=row['offensive_xbow']
            known[i,1]=row['lane_state']!='unknown'
    if set(index.values())!=matched:raise ValueError('Dataset events lack labels')
    return y,known

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True);ap.add_argument('--labels',type=Path,required=True)
    ap.add_argument('--rulings',type=Path,required=True);ap.add_argument('--xbow-validation',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    if not a.rulings.is_file():raise ValueError('Missing LEAD_RULINGS.md')
    validation=json.loads(a.xbow_validation.read_text())
    from pipeline.public_geometry import load_calibration
    load_calibration(a.xbow_validation)
    manifest=json.loads(a.labels.with_name('manifest.json').read_text())
    if manifest.get('xbow_calibration_sha256')!=C.sha(a.xbow_validation):raise ValueError('Labels do not bind this R1-REVISED calibration')
    torch.set_num_threads(1);torch.manual_seed(20261004)
    with np.load(a.data,allow_pickle=False) as z:
        meta=json.loads(str(z['meta']));tags=z['tags'];arrays={k:z[k] for k in ('sc','hand_card','rep','split','tick','side','y_gate','y_card')}
    if meta.get('feature_version') not in (4,5):raise ValueError('Requires public v4 or v5 (fv5 changes only body identity; these features are sc+hand)')
    if any('_public_v1' not in p and 'public_preflight_remaining' not in p for p in meta['corpora']):raise ValueError('Cancelled proxy corpus')
    events=[json.loads(s) for s in a.labels.open()];y,k=labels(arrays,tags,meta,events)
    x=C.public_features(arrays,meta)
    buckets=np.array([int(hashlib.sha256(('context-v1:'+str(t)).encode()).hexdigest()[:8],16)%10 for t in tags])
    masks={name:(arrays['split']==0)&pred[buckets[arrays['rep']]] for name,pred in
           [('fit',np.arange(10)<8),('tune',np.arange(10)==8),('test',np.arange(10)==9)]}
    if any(not m.any() for m in masks.values()):raise ValueError('Need nonempty replay-disjoint fit/tune/test groups')
    ix=np.flatnonzero(masks['fit']);mean=x[ix].mean(0);std=x[ix].std(0).clip(.01)
    x-=mean;x/=std;np.clip(x,-20,20,out=x)
    base=((y[ix]*k[ix]).sum(0)/k[ix].sum(0)).clip(1e-5,1-1e-5)
    if not (y[ix].sum(0)>0).all():raise ValueError('No positive fit examples for one of six targets; no complete artifact claim')
    model=torch.nn.Linear(x.shape[1],6)
    with torch.no_grad():model.weight.zero_();model.bias.copy_(torch.from_numpy(np.log(base/(1-base))))
    opt=torch.optim.Adam(model.parameters(),lr=.01);xt,yt,kt=map(torch.from_numpy,(x,y,k));rng=np.random.default_rng(20261004)
    print(json.dumps(dict(rows=len(x),fit_rows=len(ix),fit_positives=y[ix].sum(0).tolist())),flush=True)
    for epoch in range(8):
        rng.shuffle(ix)
        for start in range(0,len(ix),8192):
            ids=ix[start:start+8192];loss=(F.binary_cross_entropy_with_logits(model(xt[ids]),yt[ids],reduction='none')*kt[ids]).sum()/kt[ids].sum()
            opt.zero_grad();loss.backward();opt.step()
        print(json.dumps(dict(epoch=epoch+1,last_batch_loss=float(loss.detach()))),flush=True)
    p=np.empty_like(y)
    with torch.no_grad():
        for start in range(0,len(x),32768):p[start:start+32768]=model(xt[start:start+32768]).sigmoid().numpy()
    a.out.mkdir(parents=True,exist_ok=False);np.save(a.out/'probability.npy',p.max(1))
    torch.save(dict(state=model.state_dict(),mean=mean.tolist(),std=std.tolist(),targets=TARGETS),a.out/'classifier.pt')
    report=dict(targets=TARGETS,fixed_weight=2.0,weight_selection='owner_fixed_no_sweep',joint_score='maximum_of_six_probabilities',
                target_note='defensive_xbow_rocket_cycle is the retained API key for defensive-X-Bow placement; no follow-on Rocket is required by current C2/R1-FINAL.',
                positives=y.sum(0).tolist(),unknown=(1-k).sum(0).tolist(),
                heldout={name:C.evaluate(p[m],y[m],k[m],arrays['rep'][m],base) for name,m in masks.items() if name!='fit'})
    (a.out/'heldout_report.json').write_text(json.dumps(report,indent=2))
    evidence=dict(public_only=True,context_targets=TARGETS,selected_weight=2.0,weight_selection='owner_fixed_no_sweep',
        **{n+'_sha256':C.sha(path) for n,path in [('dataset',a.data),('classifier',a.out/'classifier.pt'),
             ('heldout_report',a.out/'heldout_report.json'),('probability',a.out/'probability.npy'),('labels',a.labels),('lead_rulings',a.rulings),
             ('xbow_calibration',a.xbow_validation),('label_manifest',a.labels.with_name('manifest.json'))]},
        **{name+'_tags':sorted(str(t) for t in tags[np.unique(arrays['rep'][m])]) for name,m in masks.items()})
    (a.out/'artifact.json').write_text(json.dumps(evidence,indent=2));print('PUBLIC_SIX_TARGET_ARTIFACT_PASS')
if __name__=='__main__':main()
