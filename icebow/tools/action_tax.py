"""ACTION TAX: is a PLAY punished more than a WAIT, in the reward's own accounting?

The open question after 5a. Both standing explanations for the low gate are measured false --
offence sums strongly POSITIVE (+3466 vs -737) and the largest single negative is a penalty for
IDLING -- yet the policy plays on ~10% of ticks. The remaining lead is the shape policy-stats
flags: SIX terms fire and can never be positive, and FIVE of those are reachable only BY ACTING.

This attributes reward terms to the DECISION that produced them by snapshotting the env's own
per-term totals either side of one step, then splits the accounting by whether that step was a
play or a wait.

WARNING: PER-DECISION, NOT TOTALS. 3x's "the offence has no positive signal" died because it read
one-fire totals; this is the same question asked the way that mistake cannot recur.

WARNING: The policy's OWN card and cell are used, not a stand-in. gate_probe measured itself for months
by playing `aff[0]` at the centre cell; placement drives xbow_into_push and building_waste
directly, so a stand-in cell would manufacture exactly the tax being tested for.
"""
from __future__ import annotations

from pathlib import Path
import sys

# Allow direct execution via `python tools/gate_probe.py` from the icebow root.
_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import numpy as np
import torch
import torch.nn as nn

from clashrl.config import Config
from clashrl.model import PolicyNet
from clashrl.sim.env import SimMatchEnv
from clashrl.train_rl import _pick_device


def main(ckpt="data/policy_sim_ppo.pt", matches=8, envs=4, size="432"):
    cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    cfg = Config.load(cfg_path)
    if size == "432":
        cfg.data.setdefault("action", {})["grid"] = [18, 24]

    pool = [SimMatchEnv(cfg, seed=4242 + i) for i in range(envs)]
    e0 = pool[0]
    for e in pool:
        if getattr(e, "domain_rand", None) is not None:
            e.domain_rand.enabled = False
            e.domain_rand.resample()

    device = _pick_device(cfg)

    ck_path = Path(ckpt)
    if not ck_path.is_absolute():
        ck_path = cfg.path(str(ck_path))
    state = torch.load(ck_path, map_location="cpu", weights_only=True)
    model_sd = state.get("model") or {}
    conv0_w = model_sd.get("features.0.weight")
    ck_in_ch = int(state.get("in_ch", 0) or 0)
    if ck_in_ch <= 0:
        ck_in_ch = int(conv0_w.shape[1]) if conv0_w is not None and hasattr(conv0_w, "shape") else 3
    thr_w = model_sd.get("threat_fc.0.weight")
    ck_threat_dim = int(state.get("threat_dim", 0) or 0)
    if ck_threat_dim <= 0:
        ck_threat_dim = int(thr_w.shape[1]) if thr_w is not None and hasattr(thr_w, "shape") else int(e0.threat_dim)

    class PPONet(nn.Module):
        def __init__(self):
            super().__init__()
            self.policy = PolicyNet(ck_in_ch, e0.n_cards, e0.n_cells, threat_dim=ck_threat_dim)
            self.gate = nn.Linear(self.policy.embed_dim, 2)
            self.value = nn.Linear(self.policy.embed_dim, 1)

        def forward(self, x, hand, nxt=None, elx=None, thr=None):
            # `cell_head` HAS NOT EXISTED since the spatial-cell refactor, and `features_vec`
            # discards the pre-pool feature map that head needs -- PolicyNet.forward_parts says so
            # in its own docstring. This probe kept calling both and raised AttributeError on every
            # invocation, so the gate diagnostic has been dead for as long as that refactor is old.
            z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
            return cards, cells, self.gate(z), self.value(z).squeeze(-1)

    net = PPONet().to(device)
    net.policy.load_state_dict(state["model"])
    if "gate" in state:
        net.gate.load_state_dict(state["gate"])
    net.eval()

    costs = np.asarray([float(s.elixir) for s in e0.specs], np.float32)
    wincon = [i for i, k in enumerate(e0.deck_keys) if k in ("x_bow", "rocket")]

    def obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > ck_in_ch:
            x = x[:, :, :ck_in_ch]
        elif x.shape[2] < ck_in_ch:
            pad = np.zeros((x.shape[0], x.shape[1], ck_in_ch - x.shape[2]), dtype=x.dtype)
            x = np.concatenate([x, pad], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1).to(device) / 255.0

    def vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    def thr_t(v):
        t = np.asarray(v, np.float32)
        if t.shape[0] > ck_threat_dim:
            t = t[:ck_threat_dim]
        elif t.shape[0] < ck_threat_dim:
            t = np.pad(t, (0, ck_threat_dim - t.shape[0]))
        return torch.from_numpy(t).to(device)

    obs = [e.reset() for e in pool]

    def term_snapshot(e):
        st = getattr(e, "rw_stats", None)
        if st is None:
            return {}
        return {k: float(v.total) for k, v in st.run.items()}

    play_r, wait_r = [], []
    play_terms, wait_terms = {}, {}
    steps = done_n = 0

    while done_n < matches:
        with torch.no_grad():
            cq, ceq, gq, _ = net(
                torch.stack([obs_t(o) for o in obs]),
                torch.stack([vec_t(e.hand_vec) for e in pool]),
                torch.stack([vec_t(e.next_vec) for e in pool]),
                torch.stack([vec_t(e.elixir_vec) for e in pool]),
                torch.stack([thr_t(e.threat_vec) for e in pool]),
            )
            pg = torch.sigmoid(gq[:, 1] - gq[:, 0]).cpu().numpy()

        for i, e in enumerate(pool):
            steps += 1
            hand = [c for c in range(e0.n_cards) if e.hand_vec[c] > 0.5]
            aff = [c for c in hand if costs[c] <= e.elixir + 1e-6]
            # THE POLICY'S OWN CHOICE: greedy card over the affordable set, then that card's own
            # best cell -- ceq is (n_cards, n_cells), so the cell must be read from the card's row.
            if aff:
                cvals = cq[i].cpu().numpy()
                pick = int(max(aff, key=lambda c: cvals[c]))
                row = ceq[i][pick].cpu().numpy() if ceq[i].dim() == 2 else ceq[i].cpu().numpy()
                cell = int(np.argmax(row))
            else:
                pick, cell = None, 0
            play = pick is not None and float(np.random.random()) < float(pg[i])
            before = term_snapshot(e)
            act = (1, pick, cell) if play else (0, 0, 0)
            nobs, rew, done, _ = e.step(act)
            after = term_snapshot(e)
            d = {k: after[k] - before.get(k, 0.0) for k in after
                 if abs(after[k] - before.get(k, 0.0)) > 1e-12}
            bucket = (play_r, play_terms) if play else (wait_r, wait_terms)
            bucket[0].append(float(rew))
            for k, v in d.items():
                acc = bucket[1].setdefault(k, [0.0, 0])
                acc[0] += v
                acc[1] += 1
            obs[i] = e.reset() if done else nobs
            done_n += int(done)

    import statistics as st
    np_ = len(play_r); nw = len(wait_r)
    mp = st.mean(play_r) if np_ else 0.0
    mw = st.mean(wait_r) if nw else 0.0
    sp = st.stdev(play_r) if np_ > 1 else 0.0
    sw = st.stdev(wait_r) if nw > 1 else 0.0
    se = ((sp * sp / max(1, np_)) + (sw * sw / max(1, nw))) ** 0.5
    print("")
    print("steps=%d  plays=%d (%.1f%%)  waits=%d" % (steps, np_, 100.0 * np_ / max(1, steps), nw))
    print("")
    print("PER-DECISION REWARD")
    print("  play   mean %+.4f  sd %.4f  n %d" % (mp, sp, np_))
    print("  wait   mean %+.4f  sd %.4f  n %d" % (mw, sw, nw))
    print("  play - wait = %+.4f   (%.2f sigma)" % (mp - mw, (mp - mw) / se if se else 0.0))
    print("")
    print("TERM TOTALS BY DECISION KIND  (total, and per-decision-of-that-kind)")
    print("  %-22s %12s %12s %12s %12s" % ("term", "play tot", "per play", "wait tot", "per wait"))
    allk = sorted(set(play_terms) | set(wait_terms),
                  key=lambda k: (play_terms.get(k, [0, 0])[0] / max(1, np_)))
    for k in allk:
        pt = play_terms.get(k, [0.0, 0])[0]
        wt = wait_terms.get(k, [0.0, 0])[0]
        print("  %-22s %12.1f %12.4f %12.1f %12.4f"
              % (k, pt, pt / max(1, np_), wt, wt / max(1, nw)))


if __name__ == "__main__":
    import sys as _s
    _ck = _s.argv[1] if len(_s.argv) > 1 else "data/policy_sim_ppo.pt"
    _m = int(_s.argv[2]) if len(_s.argv) > 2 else 60
    main(_ck, matches=_m)
