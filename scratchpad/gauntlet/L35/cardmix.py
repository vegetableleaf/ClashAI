r"""CARD MIX / SPELL SHARE -- the continuation instrument's rollout, counting every play.

    PYTHONHASHSEED=0 python cardmix.py --matches 16 --ckpt <a.pt> [<b.pt> ...]

Identical rollout to tools/continuation_report.py (greedy, search-free, Searcher(12.0, 0, 4, 1.0,
0.25, cells=3), the same fixed SEEDS), so its plays are the SAME plays that report's gap/rate
columns are computed from -- only the counting differs. Reports each card's share of all plays,
the SPELL share (the_log + tornado + rocket), and the elixir at which each was played is NOT
available here (the gate probe is the instrument for elixir). Cross-arm only vs other runs of
THIS script (HANDOFF 5ci)."""
import argparse, collections, pathlib, sys
import torch
ROOT = pathlib.Path(__file__).resolve().parents[3] / "icebow"
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "tools"))
from clashrl.config import Config
from clashrl.sim.env import SimMatchEnv
from clashrl.sim import rollout_search as RS
import continuation_report as CR

SPELL = ("the_log", "tornado", "rocket")

def run(ckpt, cfg, matches):
    env = SimMatchEnv(cfg)
    net = RS.load_net(str(ckpt), env, torch.device("cpu"))
    sr = RS.Searcher(env, net, torch.device("cpu"), 12.0, 0, 4, 1.0, 0.25, cells=3)
    cnt = collections.Counter(); n = 0
    for seed in CR.SEEDS[:matches]:
        env.rng.seed(seed); env.reset(); done = False
        while not done:
            act, _ = sr.act(0)
            if act[0] == 1:
                cnt[CR._base(env.deck_keys[act[1]])] += 1; n += 1
            _o, _r, done, _i = env.step(act)
    name = pathlib.Path(str(ckpt)).stem.replace("policy_", "")
    if not n:
        print("%-20s NO PLAYS" % name); return
    sp = sum(cnt[k] for k in SPELL)
    print("%-20s plays=%-5d SPELL %4.1f%% (log %.1f nado %.1f rocket %.1f) | %s"
          % (name, n, 100*sp/n, 100*cnt['the_log']/n, 100*cnt['tornado']/n, 100*cnt['rocket']/n,
             "  ".join("%s %.1f%%" % (k, 100*v/n) for k, v in cnt.most_common())))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=16)
    ap.add_argument("--ckpt", nargs="+", required=True)
    ap.add_argument("--config", default=None)
    a = ap.parse_args()
    cfg = Config.load(a.config) if a.config else Config.load()
    print("card mix | %d matches/ckpt | greedy, search-free | continuation_report's rollout + SEEDS" % a.matches)
    for c in a.ckpt: run(c, cfg, a.matches)

if __name__ == "__main__":
    main()
