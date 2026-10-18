"""S2-08 -> the ONE diagnosed Phase C iteration (prepared, NOT launched): s2_hog_il + opponent tower-damage shaping (PLAN
S2-08 'neither passes' branch: the trained opponents reach Hog overtime too often and take towers in regulation too rarely --
SIM regulation-loss 10-18% vs live 24%). ONE change vs cfg/s2_hog_il.yaml: rl_royale ``shaping: tower_score`` with the weights
successor/cfg/succ_tower.yaml pinned (the owner-reviewed A1+A1b potential), nothing else.
    python mkcfg_c_iter.py   -> cfg/s2_hog_il_ts.yaml"""
import os
import yaml
H = os.path.dirname(os.path.abspath(__file__))
base = yaml.safe_load(open(os.path.join(H, "cfg/s2_hog_il.yaml")))
ts = yaml.safe_load(open(os.path.join(H, "../successor/cfg/succ_tower.yaml")))
c = {**base, "shaping": "tower_score", **{k: v for k, v in ts.items() if k.startswith("shaping_ts_")}}
diff = sorted(k for k in set(c) | set(base) if c.get(k) != base.get(k))
assert diff == ["shaping", "shaping_ts_h_power", "shaping_ts_w_foe", "shaping_ts_w_own", "shaping_ts_w_tb"], diff
yaml.safe_dump(c, open(os.path.join(H, "cfg/s2_hog_il_ts.yaml"), "w", newline="\n"), sort_keys=False)
print("cfg/s2_hog_il_ts.yaml vs s2_hog_il:", diff)
