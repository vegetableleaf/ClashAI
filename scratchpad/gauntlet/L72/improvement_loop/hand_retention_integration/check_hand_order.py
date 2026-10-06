import sys
from pathlib import Path
import torch
ROOT=Path(__file__).resolve().parents[5];sys.path.insert(0,str(ROOT))
from pipeline.model_hand_belief_v2 import canonical_hand
def main():
    torch.set_num_threads(1);torch.manual_seed(19)
    tokens=torch.randint(0,5,(64,8,6)).float()/4
    # Duplicate identities with different other public fields are included.
    tokens[...,0]=torch.randint(0,4,(64,8)).float()
    expected=canonical_hand(tokens);count=0
    for _ in range(50):
        perm=torch.stack([torch.randperm(8) for _ in range(64)])
        actual=canonical_hand(tokens.gather(1,perm.unsqueeze(-1).expand_as(tokens)))
        assert torch.equal(expected,actual);count+=64
    for column in range(6):
        changed=tokens.clone();changed[0,0,column]+=1
        assert not torch.equal(expected,canonical_hand(changed))
    print(dict(permutations=count,changed_field_controls=6));print('HAND_CANONICAL_ORDER_VERIFIED')
if __name__=='__main__':main()
