"""Fixed held-out diagnostics for expert-context experiments; no policy overrides."""
import argparse
import json
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import torch

from . import vocab
from .body_identity import FAMILIES
from .eval_gen import GenRows
from .expert_context import load_contexts
from .model_gen import load_model
from .opp_elixir_count import card_cost
from .rocket_teaching import sha
from .train_rocket_curriculum import load_subset, take


def count(values, mask):
    n=int(mask.sum());k=int(np.asarray(values)[mask].sum())
    return dict(n=k,denominator=n,rate=k/n if n else None)


def metrics(sub, c, cv, predictions, spawners):
    p=predictions
    play=sub['y_gate']==1;has=p['allowed'].any(1)
    called=(p['gate']>.35) & has
    card_ok=(p['chosen_card']==sub['y_card']) & has
    xy=np.c_[p['expert_cell']%36/36,p['expert_cell']//36/64]
    dist=np.linalg.norm((xy-sub['y_xy'])*[18,32],axis=1)
    agrees=np.where(play,called & card_ok & (dist<=1),~called)
    rocket=cv.index('rocket');tornado=cv.index('tornado');log=cv.index('the-log')
    rp=play & (sub['y_card']==rocket)
    masks=dict(c,**spawners)
    masks['spawners']=np.logical_or.reduce(list(spawners.values()))
    masks['xbow_useful']=c['xbow'] & ~c['xbow_no_lifetime_target']
    masks['pro_rocket']=rp
    result=dict(global_card_agreement=count(card_ok,play),global_action_agreement=count(agrees,np.ones(len(play),bool)),
        contexts={k:dict(rows=int(m.sum()),plays=int((m & play).sum()),
                        card_agreement=count(card_ok,m & play),action_agreement=count(agrees,m),
                        gate_play=count(called,m),rocket_gated=count(called & (p['chosen_card']==rocket),m))
                  for k,m in masks.items()},
        rocket_recall=count(called & card_ok,rp),
        rocket_finish=count(called & card_ok & (dist<=2),rp & c['finish']),
        combo_rocket=count(called & card_ok,c['combo'] & rp),
        combo_tornado=count(called & card_ok,c['combo'] & play & (sub['y_card']==tornado)))
    shots=sub['projectiles'];enemy=(shots[:,:,0]==cv.index('goblin-barrel')) & (shots[:,:,1]==1)
    first=enemy.argmax(1);target=shots[np.arange(len(shots)),first,4:6]
    log_available=((sub['hand_card']==log) & p['allowed']).any(1)
    known=(enemy.sum(1)==1) & (target[:,0]>=0) & (target[:,0]<=1) & (target[:,1]>=.5) & (target[:,1]<=1)
    known &= (target[:,0]<.4) | (target[:,0]>.6)
    pro=known & log_available & play & (sub['y_card']==log) & ((sub['y_xy'][:,0]<.5)==(target[:,0]<.5))
    log_x=p['log_cell']%36/36
    same=(log_x<.5)==(target[:,0]<.5)
    fired=called & (p['chosen_card']==log)
    result['barrel']=dict(pro_same_lane_rows=int(pro.sum()),
        forced_log_same_lane=count(same,pro),gated_correct_lane=count(fired & same,pro),
        gated_wrong_lane=count(fired & ~same,pro),
        known_playable_rows=int((known & log_available).sum()))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--source-data',type=Path,required=True);ap.add_argument('--correction-manifest',type=Path)
    ap.add_argument('--contexts',type=Path,required=True);ap.add_argument('--ckpt',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True);ap.add_argument('--device',choices=('cpu','cuda'),default='cpu')
    a=ap.parse_args();torch.set_num_threads(1)
    if a.out.exists():raise ValueError('Fresh diagnostic output required')
    c,manifest,meta,binding=load_contexts(a.contexts,a.data,a.source_data,a.correction_manifest)
    with np.load(a.data) as z:
        ids=np.flatnonzero(c['pool'] & (z['split']==1))
    sub,meta=load_subset(a.data,ids);cv=meta['card_vocab']
    c={k:v[ids] for k,v in c.items()}
    if len(ids)!=38317:raise ValueError('Validation membership changed')
    # Fixed masks use the original observations, so changing identity cannot change denominators.
    with np.load(a.source_data) as z,ZipFile(a.source_data) as archive:
        off=z['off'];gather=np.concatenate([np.arange(off[i],off[i+1]) for i in ids])
        original=take(archive,'tok',gather)
    spawners={}
    for key in FAMILIES:
        present=original[:,0]==vocab.unit_id(key)
        prefix=np.r_[0,np.cumsum(present)]
        spawners[key]=(prefix[sub['off'][1:]]-prefix[sub['off'][:-1]])>0
    model,state=load_model(a.ckpt,a.device);model.eval()
    if state['card_vocab']!=cv or (5 if model.feature_version==6 else model.feature_version)!=meta['feature_version']:
        raise ValueError('Model and diagnostic data contract mismatch')
    rows=GenRows(sub,np.arange(len(ids)),a.device)
    costs=np.array([card_cost(k.replace('-','_')) or 0 for k in cv])
    allowed=(sub['hand_card']>0) & (costs[sub['hand_card']]<=np.floor(sub['sc'][:,3]*10+1e-3)[:,None])
    p=dict(allowed=allowed,gate=np.empty(len(ids),np.float32),chosen_card=np.empty(len(ids),np.int32),
           expert_cell=np.empty(len(ids),np.int32),log_cell=np.empty(len(ids),np.int32))
    with torch.no_grad():
        for lo in range(0,len(ids),128):
            ix=np.arange(lo,min(lo+128,len(ids)));b=rows.batch(ix)
            enc=model.encode_gen(b);h=model.heads_gen(enc,b)
            p['gate'][ix]=h['gate'].sigmoid().cpu().numpy()
            slot=h['card'].masked_fill(~torch.as_tensor(allowed[ix],device=a.device),-torch.inf).argmax(-1).cpu().numpy()
            p['chosen_card'][ix]=sub['hand_card'][ix,slot]
            p['expert_cell'][ix]=model.cell_logits_gen(enc,b['card'],b['form']).argmax(-1).cpu().numpy()
            card=torch.full_like(b['card'],cv.index('the-log'))
            p['log_cell'][ix]=model.cell_logits_gen(enc,card,torch.zeros_like(card)).argmax(-1).cpu().numpy()
    report=metrics(sub,c,cv,p,spawners)
    a.out.mkdir(parents=True)
    np.savez_compressed(a.out/'predictions.npz',ids=ids,**p)
    report.update(**binding,checkpoint_sha256=sha(a.ckpt),feature_version=model.feature_version,
        predictions_sha256=sha(a.out/'predictions.npz'),evaluator_sha256=sha(__file__),
        contexts_manifest_sha256=sha(a.contexts/'manifest.json'),
        limitations=['Expert-state diagnostic, not gameplay or live win evidence.',
            'Finish coverage is distance to the expert cast, not confirmed tower damage.',
            'Spawner masks are original-input parent identities, including original child mislabels.'])
    (a.out/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({k:report[k] for k in ('global_card_agreement','rocket_recall','rocket_finish','combo_rocket','combo_tornado','barrel')}))
    print('EXPERT_CONTEXT_HELDOUT_COMPLETE')


if __name__=='__main__':main()
