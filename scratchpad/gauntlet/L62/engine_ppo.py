"""L62: engine_ppo -- a standalone PPO loop on ONE EngineMatchEnv slot (the REAL CR engine), from the
BC init `bc_bias_native_s0.pt`, with an optional per-board KL-to-init term on the cell head.

NO sim doctrine: no drill gates, spell vetoes, exploration floors, pocket/veto logic, search, hazard head.
Reward = EngineMatchEnv's unshaped reward. TWO optional extra loss terms:
  --kl_coef          per-board KL(pi || pi_init) on the cell head (play rows only).
  --gate_prior_coef  v2, 2026-09-05: the sim trainer's GATE PRIOR (train_sim_ppo.py l.340-385 / l.1758-1772) --
                     a Bernoulli cross-entropy pulling the GATE HEAD ONLY toward the pro
                     P(play | elixir bucket, phase) table in icebow/config/gate_prior.json. It exists because a
                     PPO gate with no when-to-play signal collapses: MEASURED on engA (this file at coef 0), the
                     play gate went 36.2 plays/match at the init -> 0.12 at m=253, max p(play) 0.2326, i.e. 0.0%
                     of decisions above the tau=0.25 deploy threshold. Both coefs default to 0.0 and 0.0 is
                     byte-for-byte off (the table is not even read).

What is copied from icebow/src/clashrl/train_sim_ppo.py (which is one closure and cannot be imported
piecewise): PPONet (policy/gate/value/value_d), the masked_logits semantics (card = in-hand AND affordable,
PLAY gate masked when nothing is playable, cell = deployable set of the sampled card), the joint log-prob
factorisation lp_g[g] + play*(lp_c[c] + lp_cell[cell]), entropy split (gate+card at ent_coef, cell at its own
annealed coef), MSE value loss, batch advantage normalisation, Adam(eps 1e-5), grad clip, the head-norm
sharpness cap (_clamp_heads), value warm-up on a warm start, and save()'s checkpoint LAYOUT.
`compute_gae` is imported from the trainer (it is module-level).

Run (from icebow/, PYTHONPATH=src PYTHONHASHSEED=0):
    ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L62/engine_ppo.py --port 37031 --kl_coef 0 \
        --matches 2000 --seed 41 --out_prefix C:/.../icebow/data/bench/engA_ctrl --log C:/.../engA_ctrl.log
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ROOT = HERE.parents[2]
ICEBOW = ROOT / "icebow"
if str(ICEBOW / "src") not in sys.path:
    sys.path.insert(0, str(ICEBOW / "src"))

from engine_env import EngineMatchEnv, load_pool, POOL_DEFAULT, TICK_S   # noqa: E402
from clashrl.model import PolicyNet, _LOGIT_CAP                     # noqa: E402
from clashrl.train_sim_ppo import compute_gae                       # noqa: E402

INIT_DEFAULT = ICEBOW / "data" / "bc_pro" / "models" / "bc_bias_native_s0.pt"
INIT_SHA256_PREFIX = "a1273d5d"
_NEG = -1e9
# The deploy rule's threshold (sim.ppo_gate_threshold, the same number gate_probe.py reads). MONITORING ONLY:
# nothing in training uses it -- it only defines `frac_gt_tau`, the readout whose absence hid engA's collapse.
GATE_TAU = 0.25


# ------------------------------------------------------------------------------------ net
class PPONet(nn.Module):
    """train_sim_ppo.PPONet without the hazard head (inert there at coef 0; not part of the saved layout)."""

    def __init__(self, in_ch, n_cards, n_cells, threat_dim):
        super().__init__()
        self.policy = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)
        self.gate = nn.Linear(self.policy.embed_dim, 2)     # [wait, play]
        self.value = nn.Linear(self.policy.embed_dim, 1)
        self.value_d = nn.Linear(self.policy.embed_dim, 1)  # unused here; kept so save() matches the layout

    def forward(self, x, hand, nxt, elx, thr):
        """cards (tanh-capped), cells (tanh-capped, B x n_cards x n_cells), raw cells (pre-tanh), gate, value.
        Identical to PolicyNet.forward_parts, with the pre-tanh cell map exposed for the rail metric."""
        fmap = self.policy.features(x)
        z = self.policy._embed(fmap, hand, nxt, elx, thr)
        cards = _LOGIT_CAP * torch.tanh(self.policy.card_head(z) / _LOGIT_CAP)
        raw_cells = self.policy._cell_logits(fmap, z)
        cells = _LOGIT_CAP * torch.tanh(raw_cells / _LOGIT_CAP)
        return cards, cells, raw_cells, self.gate(z), self.value(z).squeeze(-1)


def _cpu_sd(mod):
    return {k: v.detach().cpu() for k, v in mod.state_dict().items()}


def sha256_prefix(path: Path, n=8):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


# ------------------------------------------------------------------------------------ trainer
class Trainer:
    def __init__(self, a):
        self.a = a
        self.t_start = time.time()
        # ---- seeds ------------------------------------------------------------------------------
        random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
        torch.set_num_threads(a.threads)
        self.rng_pool = random.Random(a.seed)         # the pool sampling sequence: identical for both arms
        self.rng_act = torch.Generator().manual_seed(a.seed)
        # ---- output-path guards --------------------------------------------------------------------
        self.out_prefix = str(Path(a.out_prefix))
        pre_norm = self.out_prefix.replace("\\", "/")
        ib = str(ICEBOW).replace("\\", "/")
        if pre_norm.startswith(ib + "/data/"):
            assert (pre_norm.startswith(ib + "/data/bench/engA_")
                    or pre_norm.startswith(ib + "/data/bench/engB_")), \
                f"refusing to write under icebow/data/ except icebow/data/bench/eng[AB]_*: {pre_norm}"
        clash = glob.glob(self.out_prefix + "_*.pt")
        assert not clash, f"refusing to overwrite existing checkpoints: {clash}"
        self.log_path = Path(a.log)
        assert not self.log_path.exists(), f"log exists at launch: {self.log_path}"
        Path(self.out_prefix).parent.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.logf = open(self.log_path, "a", encoding="utf-8", buffering=1)
        # ---- env -----------------------------------------------------------------------------------
        self.pool = load_pool(a.pool)
        self.env = EngineMatchEnv(port=a.port, pool=self.pool, seed=a.seed, decision_ticks=a.decision_ticks)
        env = self.env
        self.n_cards, self.n_cells = env.n_cards, env.n_cells
        self.costs = torch.tensor([float(s.elixir) for s in env.sim.specs], dtype=torch.float32)
        assert self.costs.numel() == self.n_cards
        self.anywhere = set(env.anywhere_ids)
        self.pocket_masks = torch.stack([torch.tensor(env.actions.deployable_mask(False, (bool(c & 2), bool(c & 1))),
                                                      dtype=torch.bool) for c in range(4)])
        self.all_mask = torch.ones(self.n_cells, dtype=torch.bool)
        # ---- policy + frozen reference ---------------------------------------------------------------
        init = Path(a.init)
        sha = sha256_prefix(init)
        assert sha.startswith(INIT_SHA256_PREFIX), f"init sha256 {sha} != {INIT_SHA256_PREFIX}* ({init})"
        ck = torch.load(str(init), map_location="cpu", weights_only=False)
        assert int(ck["n_cards"]) == self.n_cards and int(ck["n_cells"]) == self.n_cells \
            and int(ck["threat_dim"]) == env.threat_dim, (ck["n_cards"], ck["n_cells"], ck["threat_dim"])
        assert list(ck["deck"]) == list(env.deck_keys), (ck["deck"], env.deck_keys)
        self.meta = {k: ck[k] for k in ("in_ch", "n_cards", "n_cells", "threat_dim", "grid", "arena_size")}
        self.net = PPONet(int(ck["in_ch"]), self.n_cards, self.n_cells, int(ck["threat_dim"]))
        # exactly the trainer's --init path: policy via load_compat, gate loaded, VALUE HEAD FRESH
        dropped = PolicyNet.load_compat(self.net.policy, ck["model"])
        assert not dropped, f"init tensors dropped: {dropped}"
        self.net.gate.load_state_dict(ck["gate"])
        self.ref = PPONet(int(ck["in_ch"]), self.n_cards, self.n_cells, int(ck["threat_dim"]))
        self.ref.load_state_dict(self.net.state_dict())
        self.ref.eval()
        for p in self.ref.parameters():
            p.requires_grad_(False)
        self.best_wr = float(ck.get("best_wr", -1.0))
        self.init_sha = sha
        self.opt = torch.optim.Adam(self.net.parameters(), lr=a.lr, eps=1e-5)
        with torch.no_grad():
            self._card_ref = float(self.net.policy.card_head.weight.norm())
            self._cell_ref = float(self.net.policy.cell_conv[-1].weight.norm())
        self.warm_left = int(a.value_warmup)
        # ---- GATE PRIOR (semantics copied from train_sim_ppo.py l.340-385 setup + l.1758-1772 loss) ----
        # Bernoulli cross-entropy of the GATE head ONLY toward the pro table's P(play | elixir bucket, phase):
        #     loss += coef * mean( -(p * log pi(play) + (1-p) * log pi(wait)) )
        # = KL(prior || pi) on the gate up to a constant. Card and cell heads are untouched. Rows whose PLAY
        # logit is masked (nothing affordable) are EXCLUDED, via `gq_m[:, 1] > _NEG * 0.5` exactly as the sim
        # trainer does -- otherwise the term is dominated by states the gate cannot act in.
        # coef 0.0 = OFF byte-for-byte: the table is not read and no tensor in the loss changes.
        # SCHEMA 1 ONLY (the blended table, i.e. the sim's ppo_gate_prior_pressure_s = 0.0). The schema-2
        # "opponent troop within W s" pressure key is deliberately NOT implemented here.
        self.gprior = None
        self.gprior_note = "off (gate_prior_coef 0.0)"
        if float(a.gate_prior_coef) > 0.0:
            gj = json.loads(Path(a.gate_prior_path).read_text(encoding="utf-8"))
            assert int(gj.get("schema", 0)) == 1, \
                f"gate prior: engine_ppo implements schema 1 only, got {gj.get('schema')}"
            gtab = np.asarray([gj["p_play"][ph] for ph in ("single", "double", "triple")], np.float32)
            assert gtab.shape == (3, 11), gtab.shape
            greg, gover = float(gj["regulation_s"]), float(gj["overtime_s"])
            # Phase boundaries, exactly the sim trainer's arithmetic: DOUBLE from regulation-60 s, TRIPLE from
            # regulation + max(0, overtime-60) s  =>  120 s and 240 s for regulation 180 / overtime 120.
            self.gprior = (gtab, greg - 60.0, greg + max(0.0, gover - 60.0))
            self.gprior_note = (
                f"ON coef {float(a.gate_prior_coef):.3f} | {a.gate_prior_path} schema {gj.get('schema')} "
                f"({gj.get('replays')} replays, {gj.get('plays')} plays, dt {gj.get('dt')}) | "
                f"double from {self.gprior[1]:.0f}s, triple from {self.gprior[2]:.0f}s | single P(play) at "
                f"4 / 7 / 9 elixir = {gtab[0][4]:.4f} / {gtab[0][7]:.4f} / {gtab[0][9]:.4f}")
        # ---- counters ------------------------------------------------------------------------------
        self.matches = 0
        self.decisions = 0
        self.updates = 0
        self.wld = [0, 0, 0]
        self.ep_hist = []              # (reward, seconds, outcome, wall) for every finished match
        self.last_save_bucket = 0
        self.match_wall_t0 = None
        self.cur_obs = None
        self.write_header()

    # ---------------------------------------------------------------------------------- io
    def log(self, s):
        print(s, flush=True)
        self.logf.write(s + "\n")

    def write_header(self):
        a = self.a
        cfg = {k: getattr(a, k) for k in vars(a)}
        cfg["init_sha256_prefix"] = self.init_sha
        cfg["pool_size"] = len(self.pool)
        cfg["deck"] = self.env.deck_keys
        cfg["reward_spec"] = self.env.reward_spec()
        cfg["value_head"] = "fresh (seeded); the init's own value head is c2r's sim critic and is discarded, as bcA's --init did"
        cfg["torch"] = torch.__version__
        cfg["pid"] = os.getpid()
        self.log("[engine_ppo] config " + json.dumps(cfg, sort_keys=True, default=str))

    def save(self, tag):
        p = Path(f"{self.out_prefix}_{tag}.pt")
        assert not p.exists(), f"refusing to overwrite {p}"
        gw, gh = self.meta["grid"]
        torch.save({"model": _cpu_sd(self.net.policy), "gate": _cpu_sd(self.net.gate),
                    "value": _cpu_sd(self.net.value), "value_d": _cpu_sd(self.net.value_d), "algo": "ppo",
                    "grid": [gw, gh], "n_cards": self.n_cards, "n_cells": self.n_cells,
                    "threat_dim": int(self.meta["threat_dim"]), "in_ch": int(self.meta["in_ch"]),
                    "deck": list(self.env.deck_keys), "best_wr": self.best_wr, "matches": self.matches,
                    "arena_size": list(self.meta["arena_size"]),
                    "engine_ppo": {"kl_coef": self.a.kl_coef, "gate_prior_coef": self.a.gate_prior_coef,
                                   "seed": self.a.seed, "updates": self.updates,
                                   "decisions": self.decisions, "wld": list(self.wld), "port": self.a.port}}, p)
        latest = Path(f"{self.out_prefix}_latest.pt")
        tmp = Path(f"{self.out_prefix}_latest.tmp")
        torch.save(torch.load(str(p), map_location="cpu", weights_only=False), tmp)
        os.replace(tmp, latest)
        self.log(f"[engine_ppo] saved {p.name} (+ _latest) at matches={self.matches} updates={self.updates}")

    # ---------------------------------------------------------------------------------- tensors
    def obs_t(self, obs):
        return torch.from_numpy(np.asarray(obs)).unsqueeze(0).permute(0, 3, 1, 2).contiguous().float() / 255.0

    def vecs(self):
        e = self.env
        return tuple(torch.from_numpy(np.asarray(getattr(e, k), np.float32)).unsqueeze(0)
                     for k in ("hand_vec", "next_vec", "elixir_vec", "threat_vec"))

    def pocket_code(self):
        pk = self.env.sim.pocket_state(0)
        return (2 if pk[0] else 0) + (1 if pk[1] else 0)

    def cellmask_for(self, card, code):
        return self.all_mask if int(card) in self.anywhere else self.pocket_masks[int(code)]

    def gp_target(self):
        """The pro table's P(play) for the CURRENT decision = table[phase][elixir bucket].

        ELIXIR: the ENGINE's own number, `env.sim.eng.elixir[0]`. frame_to_engine sets it from the engine
        frame's players[our side]["elixir_exact"] (L61/build_bc_v2.py l.155-157), and the observation's
        `elixir_vec[0]` is exactly one tenth of it (sim/env.py l.621, no clamp), so `elixir_vec[0] * 10` is
        the SAME number -- I read the engine value directly. Bucket = clip(floor(elixir + 1e-6), 0, 10),
        which is the sim trainer's expression (l.1326-1327) with elx*10 substituted.

        PHASE: from the engine tick, t_s = env.tick * TICK_S (0.05 s/tick), against the boundaries derived
        in __init__ from gate_prior.json's regulation_s / overtime_s (120 s / 240 s). (b) UNVERIFIED that
        engine tick 0 is the same instant as the sim's t = 0: EngineMatchEnv skips a 4.5 s pre-battle
        countdown (ticks 0-90, engine_env.md l.107), so if the engine's own regulation clock starts AFTER
        that countdown this mapping calls each phase flip up to 4.5 s early. Flagged, not hidden.

        MUST be called BEFORE env.step(), which advances the tick and the elixir.
        """
        if self.gprior is None:
            return 0.0
        gtab, g_dbl, g_tri = self.gprior
        ts = float(self.env.tick) * TICK_S
        ph = 2 if ts >= g_tri else (1 if ts >= g_dbl else 0)
        eb = int(np.clip(np.floor(float(self.env.sim.eng.elixir[0]) + 1e-6), 0, 10))
        return float(gtab[ph, eb])

    # ---------------------------------------------------------------------------------- rollout
    def _new_match(self):
        idx = self.rng_pool.randrange(len(self.pool))
        self.cur_obs = self.env.reset(index=idx)
        self.match_wall_t0 = time.perf_counter()
        self.cur_idx = idx

    @torch.no_grad()
    def rollout(self, n):
        self.net.eval()
        B = {k: [] for k in ("obs", "hand", "nxt", "elx", "thr", "cm", "g", "c", "cell", "lp", "val", "rew",
                             "done", "trunc", "playable", "gp", "pg", "pgm")}
        raws = []
        t0 = time.perf_counter()
        t_pol = 0.0
        finished = []
        if self.cur_obs is None:
            self._new_match()
        for _ in range(n):
            obs = self.cur_obs
            x = self.obs_t(obs)
            hand, nxt, elx, thr = self.vecs()
            code = self.pocket_code()
            gp_row = self.gp_target()      # BEFORE env.step(): it reads the live tick and engine elixir
            ta = time.perf_counter()
            cards, cells, raw, gq, val = self.net(x, hand, nxt, elx, thr)
            elixir = elx * 10.0
            playable = (hand > 0.5) & (self.costs.view(1, -1) <= elixir + 1e-6)     # (1, n_cards)
            cq_m = cards.masked_fill(~playable, _NEG)
            gq_m = gq.clone()
            if not bool(playable.any()):
                gq_m[0, 1] = _NEG
            lp_g = F.log_softmax(gq_m, 1)[0]
            g = int(torch.multinomial(lp_g.exp(), 1, generator=self.rng_act))
            c = cell = 0
            lp = float(lp_g[g])
            if g == 1:
                lp_c = F.log_softmax(cq_m, 1)[0]
                c = int(torch.multinomial(lp_c.exp(), 1, generator=self.rng_act))
                cm = self.cellmask_for(c, code)
                lp_cell = F.log_softmax(cells[0, c].masked_fill(~cm, _NEG), 0)
                cell = int(torch.multinomial(lp_cell.exp(), 1, generator=self.rng_act))
                lp += float(lp_c[c]) + float(lp_cell[cell])
            else:
                # rail metric on wait rows too: the card the policy would most likely pick (if any)
                c_r = int(cq_m.argmax()) if bool(playable.any()) else 0
                cm = self.cellmask_for(c_r, code)
            card_for_rail = c if g == 1 else (int(cq_m.argmax()) if bool(playable.any()) else 0)
            raws.append(raw[0, card_for_rail][cm].abs())
            t_pol += time.perf_counter() - ta
            obs2, r, done, info = self.env.step((g, c, cell))
            B["obs"].append(np.asarray(obs)); B["hand"].append(hand[0].numpy()); B["nxt"].append(nxt[0].numpy())
            B["elx"].append(elx[0].numpy()); B["thr"].append(thr[0].numpy()); B["cm"].append(cm.numpy())
            B["g"].append(g); B["c"].append(c); B["cell"].append(cell); B["lp"].append(lp)
            B["val"].append(float(val[0])); B["rew"].append(float(r)); B["done"].append(bool(done))
            B["trunc"].append(bool(done) and bool(info.get("tail_capped")))
            B["playable"].append(playable[0].numpy())
            B["gp"].append(gp_row)
            # MONITORING (not an experimental variable): the gate's own probability at this decision,
            # sigmoid(g_play - g_wait) on the RAW gate logits -- identical to softmax(gq_m)[1] on rows where
            # PLAY is not masked, and the exact quantity gate_probe.py reports. `pgm` marks those rows.
            B["pg"].append(float(torch.sigmoid(gq[0, 1] - gq[0, 0])))
            B["pgm"].append(bool(playable.any()))
            self.decisions += 1
            if done:
                s = self.env.episode_summary()
                wall = time.perf_counter() - self.match_wall_t0
                o = s["outcome"]
                self.wld[{"win": 0, "loss": 1, "draw": 2}.get(o, 2)] += 1
                self.matches += 1
                finished.append({"reward": float(s["reward"]), "seconds": float(s["seconds"]), "outcome": o,
                                 "wall": wall, "tag": s["tag"], "our_plays": s["our_plays"],
                                 "ghost_undelivered": s["ghost_undelivered"], "ghost_total": s["ghost_total"],
                                 "crowns": s["crowns"], "idx": self.cur_idx})
                self.ep_hist.append(finished[-1])
                self._new_match()
            else:
                self.cur_obs = obs2
        # bootstrap value of the state AFTER the last step (0 if that step ended the match)
        if B["done"][-1]:
            boot = 0.0
        else:
            x = self.obs_t(self.cur_obs)
            boot = float(self.net(x, *self.vecs())[4][0])
        B["boot"] = boot
        B["raw_p99"] = float(torch.quantile(torch.cat(raws), 0.99)) if raws else float("nan")
        B["raw_max"] = float(torch.cat(raws).max()) if raws else float("nan")
        B["wall"] = time.perf_counter() - t0
        B["t_pol"] = t_pol
        B["finished"] = finished
        _pg = np.asarray(B["pg"], np.float32)[np.asarray(B["pgm"], bool)]
        B["pg_rows"] = int(_pg.size)
        B["pg_mean"] = float(_pg.mean()) if _pg.size else float("nan")
        B["pg_p90"] = float(np.percentile(_pg, 90)) if _pg.size else float("nan")
        B["pg_gt_tau"] = float((_pg > GATE_TAU).mean()) if _pg.size else float("nan")
        return B

    # ---------------------------------------------------------------------------------- update
    def cell_ent_now(self):
        a = self.a
        if a.cell_ent_anneal <= 0:
            return a.cell_ent
        f = min(1.0, self.matches / a.cell_ent_anneal)
        return a.cell_ent + (a.cell_ent_floor - a.cell_ent) * f

    def clamp_heads(self):
        with torch.no_grad():
            for mod, ref in ((self.net.policy.card_head, self._card_ref), (self.net.policy.cell_conv[-1], self._cell_ref)):
                n = float(mod.weight.norm())
                cap = self.a.head_norm_mult * ref
                if cap > 0 and n > cap:
                    mod.weight.mul_(cap / n)
                    if mod.bias is not None:
                        mod.bias.mul_(cap / n)

    def update(self, B):
        a = self.a
        N = len(B["rew"])
        rew = [np.array([r], np.float32) for r in B["rew"]]
        val = [np.array([v], np.float32) for v in B["val"]]
        done = [np.array([float(d)], np.float32) for d in B["done"]]
        trunc = [np.array([float(t)], np.float32) for t in B["trunc"]]
        adv, ret = compute_gae(rew, val, done, np.array([B["boot"]], np.float32), a.gamma, a.lam, trunc=trunc)
        adv_f = torch.tensor(adv.reshape(-1))
        ret_f = torch.tensor(ret.reshape(-1))
        adv_f = (adv_f - adv_f.mean()) / (adv_f.std() + 1e-8)
        obs_all = torch.from_numpy(np.stack(B["obs"]))
        hand_all = torch.from_numpy(np.stack(B["hand"])); nxt_all = torch.from_numpy(np.stack(B["nxt"]))
        elx_all = torch.from_numpy(np.stack(B["elx"])); thr_all = torch.from_numpy(np.stack(B["thr"]))
        cm_all = torch.from_numpy(np.stack(B["cm"]))
        g_all = torch.tensor(B["g"]); c_all = torch.tensor(B["c"]); cell_all = torch.tensor(B["cell"])
        oldlp = torch.tensor(B["lp"], dtype=torch.float32)
        playable_all = torch.from_numpy(np.stack(B["playable"]))
        gp_f = torch.tensor(B["gp"], dtype=torch.float32) if self.gprior is not None else None
        gps = {"n": 0, "ce": 0.0, "p": 0.0, "rows": 0, "seen": 0}
        # frozen reference (the per-board pro estimate): SAME boards, SAME sampled card, SAME deployable mask,
        # renormalised over that mask. Computed once per update, batched (a per-decision ref forward at batch 1
        # would cost as much as the policy itself).
        refcell_all = torch.empty(N, self.n_cells); refcard_all = torch.empty(N, self.n_cards)
        with torch.no_grad():
            for s0 in range(0, N, 256):
                sl = slice(s0, min(N, s0 + 256))
                x = obs_all[sl].permute(0, 3, 1, 2).contiguous().float() / 255.0
                rc, rcl, _, _, _ = self.ref(x, hand_all[sl], nxt_all[sl], elx_all[sl], thr_all[sl])
                pa = playable_all[sl]
                refcard_all[sl] = F.log_softmax(rc.masked_fill(~pa, _NEG), 1)
                rsel = rcl.gather(1, c_all[sl].view(-1, 1, 1).expand(-1, 1, self.n_cells)).squeeze(1)
                refcell_all[sl] = F.log_softmax(rsel.masked_fill(~cm_all[sl], _NEG), 1)
        cell_coef = self.cell_ent_now()
        acc = {k: 0.0 for k in ("pl", "vl", "ent", "cell_ent", "kl_cell", "kl_card", "kl_term", "clip", "vpred", "warm")}
        last = {"pl": 0.0, "kl_term": 0.0, "kl_cell": 0.0, "n": 0}     # LAST epoch only (init: epoch 0 has ratio 1, pl ~ 0, KL 0)
        nb = 0
        n_play_tot = 0
        rows_tot = 0
        idx = np.arange(N)
        self.net.train()
        for ep in range(a.epochs):
            np.random.shuffle(idx)
            for s in range(0, N, a.minibatch):
                mb = torch.tensor(idx[s:s + a.minibatch])
                x = obs_all[mb].permute(0, 3, 1, 2).contiguous().float() / 255.0
                hand, nxt, elx, thr = hand_all[mb], nxt_all[mb], elx_all[mb], thr_all[mb]
                cards, cells, _, gq, v = self.net(x, hand, nxt, elx, thr)
                playable = playable_all[mb]
                cq_m = cards.masked_fill(~playable, _NEG)
                gq_m = gq.clone()
                none_play = ~playable.any(1)
                gq_m[:, 1] = torch.where(none_play, torch.full_like(gq_m[:, 1], _NEG), gq_m[:, 1])
                g_b, c_b, cell_b, cm_b = g_all[mb], c_all[mb], cell_all[mb], cm_all[mb]
                sel = cells.gather(1, c_b.view(-1, 1, 1).expand(-1, 1, self.n_cells)).squeeze(1)
                ceq_m = sel.masked_fill(~cm_b, _NEG)
                lp_g = F.log_softmax(gq_m, 1); lp_c = F.log_softmax(cq_m, 1); lp_cell = F.log_softmax(ceq_m, 1)
                play = (g_b == 1).float()
                new_lp = lp_g.gather(1, g_b.view(-1, 1)).squeeze(1) \
                    + play * (lp_c.gather(1, c_b.view(-1, 1)).squeeze(1) + lp_cell.gather(1, cell_b.view(-1, 1)).squeeze(1))
                ent = -(lp_g.exp() * lp_g).sum(1) + play * (-(lp_c.exp() * lp_c).sum(1))
                cell_ent = play * (-(lp_cell.exp() * lp_cell).sum(1))
                a_b, r_b, ol_b = adv_f[mb], ret_f[mb], oldlp[mb]
                ratio = (new_lp - ol_b).exp()
                s1 = ratio * a_b
                s2 = torch.clamp(ratio, 1.0 - a.clip, 1.0 + a.clip) * a_b
                pl = -torch.min(s1, s2).mean()
                vl = F.mse_loss(v, r_b)
                # KL( pi_theta(cell | board, card) || pi_ref(cell | board, card) ) over the card's deployable
                # cells, both renormalised (log_softmax over the mask); play rows only. Card head likewise.
                p_cell = lp_cell.exp()
                kl_cell_row = (cm_b.float() * p_cell * (lp_cell - refcell_all[mb])).sum(1)
                p_card = lp_c.exp()
                kl_card_row = (playable.float() * p_card * (lp_c - refcard_all[mb])).sum(1)
                n_play = float(play.sum())
                kl_cell = (play * kl_cell_row).sum() / max(1.0, n_play)
                kl_card = (play * kl_card_row).sum() / max(1.0, n_play)
                kl_term = a.kl_coef * kl_cell
                if self.warm_left > 0:
                    self.warm_left -= 1
                    # critic-only warm-up (bcA). The critic shares the trunk (no detach), so its gradient MOVES the
                    # policy heads' inputs: MEASURED in the launched pair, kl_cell 0.016 -> 0.088 after ONE critic-only
                    # update. --kl_in_warmup 1 keeps the KL term in the loss during warm-up so the KL arm is restrained
                    # from the first minibatch. THE 2026-09-05 LAUNCH RAN WITHOUT THIS (= --kl_in_warmup 0): both arms
                    # were identical for the 60 warm-up minibatches and the penalty pulls the KL arm back afterwards.
                    loss = a.vf_coef * vl + (kl_term if a.kl_in_warmup else 0.0)
                    acc["warm"] += 1
                else:
                    loss = pl + a.vf_coef * vl - a.ent * ent.mean() - cell_coef * cell_ent.mean() + kl_term
                # GATE PRIOR -- added OUTSIDE the value-warmup branch, exactly as the sim trainer does
                # (its term sits at l.1758-1772, after the warm-up split at l.1617-1627): it is a
                # SUPERVISED pull and does not depend on the critic. Gate head only.
                if gp_f is not None:
                    gpk = (gq_m[:, 1] > _NEG * 0.5)     # rows where PLAY is not masked (something affordable)
                    gps["seen"] += int(gpk.numel())
                    if bool(gpk.any()):
                        gpt = gp_f[mb][gpk]
                        gce = -(gpt * lp_g[gpk, 1] + (1.0 - gpt) * lp_g[gpk, 0])
                        gcem = gce.mean()
                        loss = loss + a.gate_prior_coef * gcem
                        gps["n"] += 1; gps["rows"] += int(gpk.sum())
                        gps["ce"] += float(gcem.detach()); gps["p"] += float(gpt.mean())
                self.opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.net.parameters(), a.max_grad)
                self.opt.step()
                self.clamp_heads()
                with torch.no_grad():
                    acc["pl"] += float(pl); acc["vl"] += float(vl); acc["ent"] += float(ent.mean())
                    acc["cell_ent"] += float((play * cell_ent).sum() / max(1.0, n_play))
                    acc["kl_cell"] += float(kl_cell); acc["kl_card"] += float(kl_card); acc["kl_term"] += float(kl_term)
                    acc["clip"] += float(((ratio - 1.0).abs() > a.clip).float().mean())
                    acc["vpred"] += float(v.mean())
                    if ep == a.epochs - 1:
                        last["pl"] += float(pl); last["kl_term"] += float(kl_term); last["kl_cell"] += float(kl_cell); last["n"] += 1
                    n_play_tot += int(n_play)
                    rows_tot += int(mb.numel())
                nb += 1
        out = {k: v / max(1, nb) for k, v in acc.items()}
        out["warm"] = acc["warm"]
        out["pl_last"] = last["pl"] / max(1, last["n"]); out["kl_term_last"] = last["kl_term"] / max(1, last["n"])
        out["kl_cell_last"] = last["kl_cell"] / max(1, last["n"])
        out["nb"] = nb
        out["play_frac"] = n_play_tot / max(1, rows_tot)
        out["p_play_sampled"] = float(np.mean(B["g"]))
        out["ret_mean"] = float(ret_f.mean()); out["adv_raw_abs"] = float(np.abs(adv).mean())
        for k, v in out.items():
            if isinstance(v, float) and not math.isfinite(v):
                raise RuntimeError(f"non-finite {k}={v} at update {self.updates}")
        for p in self.net.parameters():
            if not torch.isfinite(p).all():
                raise RuntimeError(f"non-finite parameter after update {self.updates}")
        # Appended AFTER the loop above: with the prior OFF these are NaN by design, which that guard
        # would (correctly, for a trained quantity) treat as a crash. The prior's own guard is explicit.
        out["gp_ce"] = gps["ce"] / gps["n"] if gps["n"] else float("nan")
        out["gp_target"] = gps["p"] / gps["n"] if gps["n"] else float("nan")
        out["gp_rows"] = gps["rows"] / max(1, gps["seen"])
        if self.gprior is not None and not math.isfinite(out["gp_ce"]):
            raise RuntimeError(f"non-finite gate-prior CE {out['gp_ce']} at update {self.updates}")
        return out

    # ---------------------------------------------------------------------------------- loop
    def run(self):
        a = self.a
        self.save("m0")
        self.log(f"[engine_ppo] init check: card_head |w| {self._card_ref:.3f}  cell_conv[-1] |w| {self._cell_ref:.3f}  "
                 f"value head fresh |w| {float(self.net.value.weight.norm()):.3f}  ref frozen  kl_coef {a.kl_coef}")
        self.log(f"[engine_ppo] GATE PRIOR {self.gprior_note}")
        t_run = time.perf_counter()
        try:
            while self.matches < a.matches:
                B = self.rollout(a.rollout)
                t_u = time.perf_counter()
                u = self.update(B)
                t_u = time.perf_counter() - t_u
                self.updates += 1
                fin = B["finished"]
                w = sum(1 for f in fin if f["outcome"] == "win"); l = sum(1 for f in fin if f["outcome"] == "loss")
                d = len(fin) - w - l
                mr = float(np.mean([f["reward"] for f in fin])) if fin else float("nan")
                ms = float(np.mean([f["seconds"] for f in fin])) if fin else float("nan")
                spm = float(np.mean([f["wall"] for f in fin])) if fin else float("nan")
                recent = self.ep_hist[-50:]
                mr50 = float(np.mean([f["reward"] for f in recent])) if recent else float("nan")
                el = time.perf_counter() - t_run
                self.log(
                    f"[upd {self.updates:4d}] m={self.matches:5d} dec={self.decisions:7d} | win ep_r {mr:+.3f} (last50 {mr50:+.3f}) "
                    f"WLD {w}/{l}/{d} cum {self.wld[0]}/{self.wld[1]}/{self.wld[2]} len {ms:.0f}s | "
                    f"pl {u['pl']:+.4f} vl {u['vl']:.4f} ent {u['ent']:.3f} cell_ent {u['cell_ent']:.3f} "
                    f"kl_cell {u['kl_cell']:.4f} kl_card {u['kl_card']:.4f} kl_term {u['kl_term']:+.4f} clip {u['clip']:.3f} "
                    f"vpred {u['vpred']:+.3f} ret {u['ret_mean']:+.3f} | last-epoch pl {u['pl_last']:+.4f} kl_cell {u['kl_cell_last']:.4f} kl_term {u['kl_term_last']:+.4f} | raw_p99 {B['raw_p99']:.2f} max {B['raw_max']:.1f} "
                    f"| p_play {u['p_play_sampled']:.3f} | s/match {spm:.2f} roll {B['wall']:.1f}s (pol {B['t_pol']:.1f}s) upd {t_u:.1f}s "
                    f"warm_mb {int(u['warm'])} cell_coef {self.cell_ent_now():.4f} elapsed {el/60:.1f}m"
                    f" | GATE p_gate {B['pg_mean']:.4f} p90 {B['pg_p90']:.4f} frac_gt_tau {B['pg_gt_tau']:.4f} "
                    f"(n {B['pg_rows']}) gp_ce {u['gp_ce']:.4f} gp_target {u['gp_target']:.4f} "
                    f"gp_rows {u['gp_rows']:.3f}")
                bucket = self.matches // a.save_every
                if bucket > self.last_save_bucket:
                    self.last_save_bucket = bucket
                    self.save(f"m{self.matches}")
            self.save(f"m{self.matches}" if not Path(f"{self.out_prefix}_m{self.matches}.pt").exists() else f"final{self.matches}")
            self.log(f"[engine_ppo] DONE matches={self.matches} updates={self.updates} decisions={self.decisions} "
                     f"WLD {self.wld} elapsed {(time.perf_counter()-t_run)/60:.1f} min")
        except BaseException as exc:  # noqa: BLE001
            self.log(f"[engine_ppo] ABORT {type(exc).__name__}: {exc} at matches={self.matches} updates={self.updates}")
            try:
                self.save(f"crash{self.matches}_{int(time.time())}")
            except Exception as e2:  # noqa: BLE001
                self.log(f"[engine_ppo] crash save failed: {e2}")
            raise
        finally:
            try:
                self.env.close()
            except Exception:
                pass
            self.logf.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=37031)
    ap.add_argument("--kl_coef", type=float, default=0.0)
    ap.add_argument("--matches", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=41)
    ap.add_argument("--rollout", type=int, default=1024)
    ap.add_argument("--out_prefix", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--save_every", type=int, default=250)
    ap.add_argument("--init", default=str(INIT_DEFAULT))
    ap.add_argument("--pool", default=str(POOL_DEFAULT))
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--decision_ticks", type=int, default=10)
    # hyper-parameters: the VALUES from icebow/data/bench/bcA_run.yaml
    ap.add_argument("--gamma", type=float, default=0.994)        # train.gamma
    ap.add_argument("--lam", type=float, default=0.95)           # sim.ppo_gae_lambda
    ap.add_argument("--clip", type=float, default=0.2)           # sim.ppo_clip
    ap.add_argument("--lr", type=float, default=0.00025)         # sim.ppo_lr
    ap.add_argument("--ent", type=float, default=0.02)           # sim.ppo_entropy (gate + card)
    ap.add_argument("--cell_ent", type=float, default=0.05)      # sim.ppo_cell_entropy (start)
    ap.add_argument("--cell_ent_floor", type=float, default=0.008)   # sim.ppo_cell_entropy_floor
    ap.add_argument("--cell_ent_anneal", type=float, default=3000)   # sim.ppo_cell_entropy_anneal (episodes)
    ap.add_argument("--epochs", type=int, default=4)             # sim.ppo_epochs
    ap.add_argument("--minibatch", type=int, default=512)        # sim.ppo_minibatch
    ap.add_argument("--vf_coef", type=float, default=0.5)        # sim.ppo_vf_coef
    ap.add_argument("--max_grad", type=float, default=0.5)       # sim.ppo_max_grad_norm
    ap.add_argument("--head_norm_mult", type=float, default=2.0) # sim.ppo_head_norm_mult (0 = off)
    ap.add_argument("--value_warmup", type=int, default=60)      # sim.ppo_value_warmup (minibatches, critic only)
    ap.add_argument("--kl_in_warmup", type=int, default=1)       # keep the KL term active during the critic warm-up
    # GATE PRIOR: sim.ppo_gate_prior_coef (the sim runs it at 2.0) / sim.ppo_gate_prior_path.
    # Default 0.0 so this file's pre-2026-09-05 behaviour is unchanged byte-for-byte.
    ap.add_argument("--gate_prior_coef", type=float, default=0.0)
    ap.add_argument("--gate_prior_path", default=str(ICEBOW / "config" / "gate_prior.json"))
    a = ap.parse_args()
    Trainer(a).run()


if __name__ == "__main__":
    main()
