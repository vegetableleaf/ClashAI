import sys, torch, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, sys.argv[1])
from pipeline.model_gen import GenModel
from pipeline.dataset import load as load_ds
_, meta = load_ds(sys.argv[2]); nc = len(meta["card_vocab"]); print("n_cards", nc, "fv", meta.get("feature_version"))
for d, L in [(128,4),(160,4),(160,5),(192,4),(224,6),(224,7),(256,5),(256,6),(288,7),(320,6),(320,7),(320,8),(384,10),(384,11)]:
    m = GenModel(d=d, layers=L, d_c=64, n_cards=nc, feature_version=5)
    print(d, L, sum(p.numel() for p in m.parameters()))
