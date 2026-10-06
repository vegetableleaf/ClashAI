"""Small live-row fixture qualification before the corrected full model probe."""
import copy,json,sys,tempfile
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[5];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from pipeline.model_hand_belief import initialize
from pipeline.live_hand import HandGenPilot
from pipeline.tests.test_live_gen_afford import frame
def main():
    torch.set_num_threads(1)
    parent=ROOT/'icebow/data/bench/development_iteration_1_20261005/ordinary_v5/candidate_portable.pt'
    model,state=initialize(parent,enabled=True,seed=2026100613)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'initial.pt';torch.save(dict(state,model=model.state_dict()),path)
        p=HandGenPilot(path,device='cpu',extrapolate_ticks=26,public_audit=True)
        f=frame(10);p.observe(f)
        p.public.plays=[dict(tick=f['game_tick']-5,side=1-p.public.side,card='rocket',accepted=True,x=4.5,y=6.,form=0)]
        b,_=p.row(f);audit=copy.deepcopy(p._public_audit_snapshot)
        private=copy.deepcopy(f)
        for player in private['players']:
            if int(player['side'])!=p.public.side:player.update(elixir_raw=999999,deck_card_ids=[999999]*8,
                next_deck_index=99,hidden_hand=['rocket']*4,private_secret='NEVER_INPUT')
        changed,_=p.row(private)
        assert all(torch.equal(b[k],changed[k]) for k in b)
        assert audit==p._public_audit_snapshot and 'NEVER_INPUT' not in json.dumps(audit)
        malformed=copy.deepcopy(private)
        for player in malformed['players']:
            if int(player['side'])!=p.public.side:player['hand_deck_indices']=[99]*4
        try:p.row(malformed)
        except ValueError as e:assert 'exactly one side' in str(e)
        else:raise AssertionError('Ambiguous reader ownership accepted')
        p.public.plays.append(dict(tick=f['game_tick']+1,side=1-p.public.side,card='the-log',x=4.5,y=6.,form=0))
        future,_=p.row(f)
        assert all(torch.equal(b[k],future[k]) for k in ('opp_hand','opp_hand_quality'))
        p.reset_match();empty,_=p.row(f);assert not empty['opp_hand'].any()
    print('LIVE_HAND_FIXTURE_VERIFIED')
if __name__=='__main__':main()
