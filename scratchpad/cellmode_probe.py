"""Why does the GREEDY policy's spell dump rate not reproduce section 4r's 66%?

Section 4r's mechanism was a near-uniform CELL HEAD. The argmax of a near-uniform distribution is
still one specific cell, so a GREEDY (eval) policy can look far better aimed than a SAMPLING
(training) one drawing from the same head. This measures both, on the same states, same checkpoint.
"""
import collections
import math
import sys

sys.path.insert(0, r"C:\Users\benpe\ClashBot\icebow\src")
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad")
import torch  # noqa: E402
from rollout_search import Searcher, load_net, _NEG  # noqa: E402
from clashrl.config import Config  # noqa: E402
from clashrl.sim.env import SimMatchEnv  # noqa: E402

torch.set_num_threads(1)
torch.manual_seed(0)
cfg = Config.load()
env = SimMatchEnv(cfg, seed=12345)
env.domain_rand.enabled = False
env.domain_rand.resample()
env.opponent_provider = None
net = load_net(r"C:\Users\benpe\ClashBot\scratchpad\_rs_policy.pt", env, torch.device("cpu"))
S = Searcher(env, net, torch.device("cpu"), 1e-6, 0, 4, 1.0,
             float(cfg.get("sim", "ppo_gate_threshold", default=0.25)))

matches = int(sys.argv[1]) if len(sys.argv) > 1 else 30
g = torch.Generator().manual_seed(7)
cells = collections.defaultdict(collections.Counter)
dist = collections.defaultdict(lambda: {"greedy": [], "sampled": []})
for m in range(matches):
    env.rng.seed(5_000_000 + m)
    env.reset()
    for _ in range(600):
        act, _ = S.act(0)
        cq_m, ceq, gq_m, playable = S._forward()
        for ci in range(env.n_cards):
            if not bool(playable[ci]) or env.specs[ci].kind != "spell":
                continue
            base = env.specs[ci].base
            mask = S.allcells if ci in S.anywhere else S.yourhalf
            row = ceq[ci].masked_fill(~mask, _NEG)
            gcell = int(row.argmax())
            scell = int(torch.multinomial(torch.softmax(row, 0), 1, generator=g))
            cells[base][gcell] += 1
            for tag, cell in (("greedy", gcell), ("sampled", scell)):
                c = env.actions.deploy_clamp(ci in env.anywhere_ids, cell)
                nx, ny = env.actions.cell_center(c % env.gw, c // env.gw)
                best = min((math.hypot((nx - u.x) * 18.0, (ny - u.y) * 32.0)
                            for u in env.eng.units if u.team == 1 and u.hp > 0), default=None)
                if best is not None:
                    rad = float(env.specs[ci].spell_radius or 2.0)
                    dist[base][tag].append((best, best <= rad))
        _o, _r, done, _i = env.step(act)
        if done:
            break

print(f"matches={matches}   (measured on EVERY step where the spell was playable, "
      f"not only where it was cast)")
for base in sorted(cells):
    c = cells[base]
    tot = sum(c.values())
    top = c.most_common(3)
    print(f"\n{base}: greedy cell argmax over {tot} states -- {len(c)} distinct cells, "
          f"top-1 share {100.0*top[0][1]/tot:.1f}%, top-3 {100.0*sum(v for _, v in top)/tot:.1f}%")
    for tag in ("greedy", "sampled"):
        d = dist[base][tag]
        if not d:
            continue
        ds = sorted(x for x, _ in d)
        hit = 100.0 * sum(h for _, h in d) / len(d)
        print(f"    {tag:8s} median dist {ds[len(ds)//2]:.2f}t   in-radius {hit:.1f}%   "
              f"DUMPED {100.0-hit:.1f}%")
