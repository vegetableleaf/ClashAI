"""Fixed-recipe expert ablations for body identity, rare contexts and target aim.

No runtime action rules or synthetic expert actions. Checkpoints require gameplay
acceptance. A CPU smoke saves no checkpoint. Only one GPU job may run at a time.
"""
import argparse
import copy
import ctypes
import json
from pathlib import Path
import time

import numpy as np
import torch

from .expert_context import load_contexts, probabilities, MIXTURES
from .eval_gen import GenRows, evaluate
from .model_gen import GenModel
from .rocket_teaching import sha
from .train_rocket_curriculum import load_subset, train_step


def initialize(state, feature_version, dataset_meta):
    source_version = int(state['args'].get('feature_version', 1))
    if (not state.get('gen') or source_version not in (4,5,6) or feature_version not in (4,5,6) or
            source_version > feature_version or state['card_vocab'] != dataset_meta['card_vocab']):
        raise ValueError('Unsupported public checkpoint migration')
    expected_data_version = 5 if feature_version == 6 else feature_version
    if dataset_meta.get('feature_version') != expected_data_version or state['args']['grid'] != dataset_meta['grid']:
        raise ValueError('Checkpoint observation/grid contract mismatch')
    a=state['args']
    model=GenModel(d=int(a['d']),layers=int(a['layers']),d_c=int(state['d_c']),
                   n_cards=len(state['card_vocab']),feature_version=feature_version)
    migrated = feature_version == 6 and source_version < 6
    missing=model.load_state_dict(state['model'],strict=not migrated)
    expected={'projectile_target_in.0.weight','projectile_target_in.0.bias',
              'projectile_target_in.2.weight','projectile_target_in.2.bias','projectile_target_spread.weight'}
    if migrated and (set(missing.missing_keys)!=expected or missing.unexpected_keys):
        raise ValueError('Unexpected checkpoint tensors during spatial migration')
    return model


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data',type=Path,required=True)
    ap.add_argument('--source-data',type=Path,required=True)
    ap.add_argument('--correction-manifest',type=Path)
    ap.add_argument('--contexts',type=Path,required=True)
    ap.add_argument('--init-ckpt',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--arm',choices=tuple(MIXTURES),required=True)
    ap.add_argument('--feature-version',type=int,choices=(4,5,6),required=True)
    ap.add_argument('--device',choices=('cpu','cuda'),default='cpu')
    ap.add_argument('--steps',type=int,default=1000)
    ap.add_argument('--bs',type=int,default=128)
    ap.add_argument('--lr',type=float,default=1e-5)
    ap.add_argument('--target-lr',type=float,default=1e-3)
    ap.add_argument('--seed',type=int,default=20261004)
    ap.add_argument('--smoke-one-batch',action='store_true')
    a=ap.parse_args(argv)
    if a.steps<1 or a.bs<1 or not 0<a.lr<1 or not 0<a.target_lr<1 or a.out.exists():
        raise ValueError('Invalid recipe or existing output')
    if a.smoke_one_batch and a.device!='cpu':
        raise ValueError('Smoke is CPU only')
    torch.set_num_threads(1)
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(),0x4000)
    except AttributeError:
        pass
    cohorts,manifest,meta,binding=load_contexts(a.contexts,a.data,a.source_data,a.correction_manifest)
    with np.load(a.data) as z:
        split,rep=z['split'],z['rep']
    pool=cohorts['pool']
    if set(rep[pool & (split==0)]) & set(rep[pool & (split!=0)]):
        raise ValueError('Held-out replay leakage')
    ids=np.flatnonzero(pool)
    if a.smoke_one_batch:
        ids=np.unique(np.concatenate([np.flatnonzero(cohorts[k] & (split==0))[:8]
                                      for k in MIXTURES[a.arm]]))
    sub,meta=load_subset(a.data,ids)
    torch.manual_seed(a.seed)
    state=torch.load(a.init_ckpt,map_location='cpu')
    model=initialize(state,a.feature_version,meta).to(a.device)
    p=probabilities({k:v[ids] for k,v in cohorts.items()},split[ids],a.arm)
    rows=GenRows(sub,np.arange(len(ids)),a.device)
    new=[v for k,v in model.named_parameters() if k.startswith('projectile_target_')]
    base=[v for k,v in model.named_parameters() if not k.startswith('projectile_target_')]
    groups=[dict(params=base,lr=a.lr)]
    if new:
        groups.append(dict(params=new,lr=a.target_lr))
    opt=torch.optim.AdamW(groups,weight_decay=.01)
    torch.manual_seed(a.seed)  # same base-dropout stream after architecture construction
    rng=np.random.default_rng(a.seed)
    a.out.mkdir(parents=True)
    config=dict(args={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},
        **binding,contexts_manifest_sha256=sha(a.contexts/'manifest.json'),
        init_checkpoint_sha256=sha(a.init_ckpt),trainer_sha256=sha(__file__),
        mixture=MIXTURES[a.arm],selection='fixed final step',runtime_tactical_rules=False,
        targets='unchanged expert gate/card/cell/wait/value',heldout_used_for_sampling=False)
    (a.out/'run.json').write_text(json.dumps(config,indent=2))
    seen={k:0 for k in cohorts}
    start=time.time()
    with (a.out/'train.jsonl').open('w') as log:
        for step in range(1,(1 if a.smoke_one_batch else a.steps)+1):
            chosen=rng.choice(len(ids),size=a.bs,p=p)
            loss,parts=train_step(model,rows.batch(chosen),opt,bool(rng.random()<.5),meta['grid'])
            for key,mask in cohorts.items():
                seen[key]+=int(mask[ids[chosen]].sum())
            record=dict(step=step,loss=loss,parts=parts,seconds=round(time.time()-start,1))
            log.write(json.dumps(record)+'\n')
            if step%100==0 or a.smoke_one_batch:
                log.flush();print(json.dumps(record),flush=True)
    if a.smoke_one_batch:
        (a.out/'smoke.json').write_text(json.dumps(dict(loss=loss,sampled_cohorts=seen,checkpoint_saved=False),indent=2))
        print('EXPERT_CONTEXT_SMOKE_PASS')
        return 0
    checkpoint=dict(state,model=model.state_dict(),expert_context=config,args=dict(state['args'],feature_version=a.feature_version))
    model.eval()
    checkpoint['val']=evaluate(model,rows.view(np.flatnonzero(split[ids]!=0)),grid=meta['grid'])
    torch.save(checkpoint,a.out/'candidate.pt')
    (a.out/'result.json').write_text(json.dumps(dict(val=checkpoint['val'],sampled_cohorts=seen,
        checkpoint_sha256=sha(a.out/'candidate.pt'),deployment_accepted=False),indent=2))
    print('EXPERT_CONTEXT_TRAINING_FINISHED_REQUIRES_ACCEPTANCE')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
