"""Exactly one ghost-screen and one reactive plain match, then tiny RL inference.

Fresh randomly initialized v3 model with gen_v1's real card vocabulary. No training.
"""
import os
os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ['OMP_NUM_THREADS']='2'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
import importlib.util
import json
import time
from pathlib import Path
from unittest.mock import patch
import numpy as np
import torch
from pipeline import e1_eval as E, search_s0 as S
from pipeline.model_gen import GenModel
from pipeline.tests.gen_v3.test_sim_integration import tiny_rollout

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
V1=ROOT/'icebow/data/pipeline/gen_v1_s0/gen_s0.pt'
PIN=ROOT/'scratchpad/gauntlet/L68/generalist/lat26/screens/train_C.jsonl'


def stats(rows):
    uf=np.concatenate([r['unit_form'][r['mask']] for r in rows])
    op=np.stack([r['opp_past'] for r in rows])
    return dict(rows=len(rows),unit_tokens=len(uf),evolved=int((uf==1).sum()),hero=int((uf==2).sum()),
                rows_with_opponent_plays=int(op[:,:,0].any(axis=1).sum()),
                opponent_forms=sorted(set(op[:,:,1][op[:,:,0]>0].astype(int).tolist())))


def main():
    torch.set_num_threads(2)
    out=HERE/('sim_smoke_'+time.strftime('%Y%m%d_%H%M%S'));out.mkdir()
    old=torch.load(V1,map_location='cpu')
    torch.manual_seed(123)
    model=GenModel(d=16,layers=1,d_c=8,n_cards=len(old['card_vocab']),feature_version=3).eval()
    ck=out/'fresh_v3.pt'
    torch.save(dict(gen=True,args=dict(d=16,layers=1,grid='lattice',feature_version=3),d_c=8,
                    card_vocab=old['card_vocab'],model=model.state_dict(),deck='generalist',epoch=0,
                    n_params=sum(p.numel() for p in model.parameters())),ck)
    rows=[];orig=E.Match.gen_row
    def capture(m,p):
        r=orig(m,p)
        if 'unit_form' in r:rows.append(r)
        return r
    runner=ROOT/'scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py'
    spec=importlib.util.spec_from_file_location('v3_screen',runner)
    screen=importlib.util.module_from_spec(spec);spec.loader.exec_module(screen)
    assert len({json.loads(x)['tag'] for x in PIN.read_text().splitlines() if x.strip()})==299
    with patch.object(E.Match,'gen_row',capture):
        assert screen.main(['--ckpt',str(ck),'--out',str(out/'ghost.jsonl'),'--split','train','--only-tags-from',str(PIN),
                            '--seeds','0','--tau','0.27','--forms-mode','deck','--noise-off','all','--opp-elixir','counter',
                            '--action-delay','26','--extrapolate','26','--device','cpu','--batch','1','--max-matches','1'])==0
        ghost=stats(rows);rows.clear()
        assert S.main(['--gen',str(ck),'--opp-gen',str(V1),'--out',str(out/'reactive'),'--arms','plain','--opps','gen',
                       '--seeds','0','--workers','1','--threads','2','--device','cpu','--forms-mode','deck'])==0
        reactive=stats(rows)
    result,bn,collate,gae=tiny_rollout()
    rl=stats([{k:result['traj'][k][i] for k in ('unit_form','mask','opp_past')}
              for i in range(len(result['traj']['mask']))])
    report=dict(checkpoint=str(ck),ghost=ghost,reactive=reactive,rl=rl,collate=collate,gae=gae)
    (HERE/'sim_smoke_result.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2));print('SIM_SMOKE_OK')


if __name__=='__main__':main()
