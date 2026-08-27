"""EVAL-ONLY FLAT ROLLOUT SEARCH -- a MEASUREMENT harness, not shipped code.

HANDOFF section 4x. At every Nth decision, clone `env.eng` (+ the opponent, sharing one RNG),
play each candidate action out for H seconds under a cheap default policy for BOTH sides, score
the resulting board on ACTUAL OUTCOME, and take the argmax. FLAT rollout search: no tree, no
reuse across iterations, no backup. This is NOT MCTS and must not be reported as MCTS.

Nothing here is imported by the repo's source. Run it, read the JSON, throw it away.

SCORING (section 4x, owner-refined). One currency: PRINCESS-TOWER FRACTIONS.

    score =  enemy tower fraction destroyed over the rollout
           - our tower fraction lost over the rollout
           - elixir we spent          * threat_value.ELIXIR_TO_TOWER   (0.061, measured / 113 cards)
           + (our surviving board value - theirs) at the horizon, as a DELTA from the start
           + CROWN_W * (crowns taken - crowns lost)

Never the shaped reward: search optimises whatever objective it is given, and this project spent a
week finding that objective to be wrong in three separate places (section 4x).

TWO IMPLEMENTATION DECISIONS the design note does not settle, both recorded because they change
the number:

  1. `threat_value.bodies_ignore_frac` returns `inf` for a siege building, for anything that
     outranges the crown tower, and for unknown cards -- MEASURED on our own deck that is x_bow,
     and on the enemy side every siege/spawner-ish body. An `inf` in a score is not a score, so a
     body with no finite ignore cost is priced at what it COST, `elixir * ELIXIR_TO_TOWER`, using
     the same measured constant the elixir term already uses. That makes deploying such a card
     instantaneously NEUTRAL (spend 0.366, gain 0.366 for a 6-elixir X-Bow) so only the
     CONSEQUENCE scores -- exactly the property `SimMatchEnv._position`'s docstring demands.
  2. Each side's pooled board value is capped at BOARD_CAP tower fractions. Same argument as
     `threat_value._SPAWNER_CAP`: past a full tower the exact number changes no decision.

DEFAULT ROLLOUT POLICY: our side IDLES for the whole horizon; the opponent keeps playing its
scripted line. That is precisely what the shipped counterfactual fork already does
(`SimMatchEnv._roll_fork`, "the AGENT DOING NOTHING"). It biases every candidate the same way but
NOT by the same amount -- see the WAIT analysis in the ledger.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import pathlib
import random
import sys
import time

os.environ.setdefault("PYTHONHASHSEED", "0")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

ICEBOW = pathlib.Path(r"C:\Users\benpe\ClashBot\icebow")
sys.path.insert(0, str(ICEBOW / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402

from clashrl.config import Config  # noqa: E402
from clashrl.model import PolicyNet  # noqa: E402
from clashrl.sim.env import SimMatchEnv  # noqa: E402
from clashrl import threat_value as TV  # noqa: E402

_NEG = -1e9
BOARD_CAP = 1.0          # tower fractions; see module docstring, decision 2
TILES_X, TILES_Y = 18.0, 32.0


# ---------------------------------------------------------------------------- net

class PPONet(nn.Module):
    """Same shape as train_sim_ppo's actor-critic, so the checkpoint loads verbatim."""

    def __init__(self, in_ch, n_cards, n_cells, threat_dim):
        super().__init__()
        self.policy = PolicyNet(in_ch, n_cards, n_cells, threat_dim=threat_dim)
        self.gate = nn.Linear(self.policy.embed_dim, 2)
        self.value = nn.Linear(self.policy.embed_dim, 1)
        self.value_d = nn.Linear(self.policy.embed_dim, 1)

    def forward(self, x, hand, nxt, elx, thr):
        z, cards, cells = self.policy.forward_parts(x, hand, nxt, elx, thr)
        return cards, cells, self.gate(z), self.value(z).squeeze(-1), self.value_d(z).squeeze(-1)


def load_net(ckpt_path, env, device):
    net = PPONet(int(env.obs_shape[2]), env.n_cards, env.n_cells, env.threat_dim).to(device)
    ck = torch.load(ckpt_path, map_location="cpu")
    dropped = PolicyNet.load_compat(net.policy, ck["model"])
    if dropped:
        raise SystemExit(f"checkpoint tensors did not carry over: {dropped[:8]}")
    net.gate.load_state_dict(ck["gate"])
    if "value" in ck:
        net.value.load_state_dict(ck["value"])
    net.eval()
    return net


# ---------------------------------------------------------------------------- scoring

class Scorer:
    """Everything in PRINCESS-TOWER FRACTIONS."""

    def __init__(self, env, crown_w: float):
        self.db = env.db
        self.tower_level = int(getattr(env, "_tower_level_for_triage", 15))
        self.crown_w = float(crown_w)
        self._finite = {}       # base -> bool, is ignore_cost_frac finite
        self.crown_fires = 0    # how often the crown term was ever non-zero in a rollout

    def _has_finite_ignore(self, base: str) -> bool:
        v = self._finite.get(base)
        if v is None:
            try:
                v = math.isfinite(TV.ignore_cost_frac(self.db, base, tower_level=self.tower_level))
            except Exception:       # noqa: BLE001 -- an unknown card is never ignorable
                v = False
            self._finite[base] = v
        return v

    def board_value(self, eng, team: int) -> float:
        finite, extra = [], 0.0
        for u in eng.units:
            if u.team != team or u.hp <= 0 or u.spec.kind not in ("troop", "building"):
                continue
            b = u.spec.base
            if self._has_finite_ignore(b):
                finite.append(b)
            else:
                per = max(1, u.spec.squad_count or u.spec.count)
                extra += (float(u.spec.elixir) / per) * TV.ELIXIR_TO_TOWER
        v = 0.0
        if finite:
            v = float(TV.bodies_ignore_frac(self.db, finite, tower_level=self.tower_level))
            if not math.isfinite(v):
                v = BOARD_CAP
        return min(BOARD_CAP, v + extra)

    @staticmethod
    def tower_frac(eng, team: int) -> float:
        """Total standing tower HP for `team`, in units of ONE OF ITS OWN PRINCESS TOWERS.

        Same normalisation `SimMatchEnv._position` uses, so the king is worth more than a princess
        by exactly its HP ratio rather than by a chosen number.
        """
        ref = max(1.0, float(eng.towers[team][0].max_hp))
        return sum(max(0.0, float(t.hp)) for t in eng.towers[team]) / ref

    def snapshot(self, eng):
        return {
            "t": float(eng.t),
            "ours": self.tower_frac(eng, 0),
            "theirs": self.tower_frac(eng, 1),
            "bv0": self.board_value(eng, 0),
            "bv1": self.board_value(eng, 1),
            "cr0": eng.crowns(0),
            "cr1": eng.crowns(1),
        }

    def score(self, s0, eng, spent: float):
        s1 = self.snapshot(eng)
        enemy_destroyed = s0["theirs"] - s1["theirs"]
        ours_lost = s0["ours"] - s1["ours"]
        board = (s1["bv0"] - s1["bv1"]) - (s0["bv0"] - s0["bv1"])
        d_crowns = (s1["cr0"] - s0["cr0"]) - (s1["cr1"] - s0["cr1"])
        if d_crowns:
            self.crown_fires += 1
        return (enemy_destroyed
                - ours_lost
                - spent * TV.ELIXIR_TO_TOWER
                + board
                + self.crown_w * d_crowns)


# ---------------------------------------------------------------------------- search

class Searcher:
    def __init__(self, env, net, device, horizon, interval, topk, crown_w, gate_tau,
                 force_policy=False):
        self.env, self.net, self.device = env, net, device
        self.horizon, self.interval, self.topk = float(horizon), int(interval), int(topk)
        self.gate_tau = float(gate_tau)
        # LEAK PROBE: run every rollout, then throw the answer away and play the policy's action.
        # If the match record still equals the baseline's, the search provably writes nothing back
        # into the live match (RNG included). That is the check section 4x's determinism note asks for.
        self.force_policy = bool(force_policy)
        self.scorer = Scorer(env, crown_w)
        self.yourhalf = torch.tensor(env.actions.deployable_mask(False), dtype=torch.bool, device=device)
        self.allcells = torch.ones(env.n_cells, dtype=torch.bool, device=device)
        self.costs = torch.tensor([float(s.elixir) for s in env.specs], dtype=torch.float32, device=device)
        self.anywhere = set(env.anywhere_ids)
        self.rollout_steps = max(1, int(round(self.horizon / env.agent_dt)))
        self.subs = max(1, int(round(env.agent_dt / env.sub_dt)))
        # counters
        self.searched = self.disagree = 0
        self.policy_wait = self.search_wait = 0
        self.wait_over_play = self.play_over_wait = 0      # search chose WAIT / chose a PLAY instead
        self.cands = 0
        self.rollout_s = 0.0
        self.margins = []

    # -- policy ------------------------------------------------------------
    def _forward(self):
        e = self.env
        obs = torch.from_numpy(e._last_obs).float().permute(2, 0, 1).unsqueeze(0).to(self.device) / 255.0
        def v(a):
            return torch.from_numpy(np.asarray(a, np.float32)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            cq, ceq, gq, _, _ = self.net(obs, v(e.hand_vec), v(e.next_vec), v(e.elixir_vec), v(e.threat_vec))
        elixir = v(e.elixir_vec) * 10.0
        playable = (v(e.hand_vec) > 0.5) & (self.costs.view(1, -1) <= elixir + 1e-6)
        cq_m = cq.masked_fill(~playable, _NEG)
        gq_m = gq.clone()
        if not bool(playable.any()):
            gq_m[:, 1] = _NEG
        return cq_m[0], ceq[0], gq_m[0], playable[0]

    def _cell_for(self, ceq, ci):
        m = self.allcells if ci in self.anywhere else self.yourhalf
        return int(ceq[ci].masked_fill(~m, _NEG).argmax())

    def greedy_action(self):
        """Byte-identical to train_sim_ppo.choose_greedy for one env."""
        cq_m, ceq, gq_m, playable = self._forward()
        if not bool(playable.any()) or float(torch.sigmoid(gq_m[1] - gq_m[0])) <= self.gate_tau:
            return (0, 0, 0), (cq_m, ceq, gq_m, playable)
        ci = int(cq_m.argmax())
        return (1, ci, self._cell_for(ceq, ci)), (cq_m, ceq, gq_m, playable)

    # -- rollout -----------------------------------------------------------
    def _rollout(self, action):
        """Fork, apply `action`, then idle our side / run theirs for the horizon. Returns score."""
        e = self.env
        # ONE deepcopy of the PAIR: `eng.rng` and `opponent.rng` are the SAME object in the live
        # match (SimMatchEnv hands env.rng to both), and two separate deepcopy calls -- which is
        # what the shipped `_fork` does -- would split them into two independent streams. Copying
        # the tuple preserves the aliasing, so the branch is a faithful continuation.
        eng, opp = copy.deepcopy((e.eng, e.opponent))
        s0 = self.scorer.snapshot(eng)
        spent = 0.0
        play, card_id, cell = action
        if play:
            spec = e.specs[card_id]
            cell = e.actions.deploy_clamp(card_id in e.anywhere_ids, cell)
            nx, ny = e.actions.cell_center(cell % e.gw, cell // e.gw)
            if eng.deploy(0, spec, nx, ny, delay_s=e.action_latency):
                spent = float(spec.elixir)
        for _ in range(self.rollout_steps):
            if eng.done:
                break
            opp.act(eng)
            for _ in range(self.subs):
                eng.advance(e.sub_dt)
                if eng.done:
                    break
        return self.scorer.score(s0, eng, spent)

    def candidates(self, cq_m, ceq, playable):
        """The policy's top-K PLAYABLE cards at their own argmax cell, plus WAIT -- always."""
        out = [(0, 0, 0)]
        if bool(playable.any()):
            order = torch.argsort(cq_m, descending=True)
            for t in order[: self.topk]:
                ci = int(t)
                if not bool(playable[ci]):
                    break
                out.append((1, ci, self._cell_for(ceq, ci)))
        return out

    def act(self, step_i: int):
        pol, (cq_m, ceq, gq_m, playable) = self.greedy_action()
        if self.interval <= 0 or (step_i % self.interval) or self.env.eng.done:
            return pol, False
        cands = self.candidates(cq_m, ceq, playable)
        if len(cands) < 2:
            return pol, False
        t0 = time.perf_counter()
        scores = [self._rollout(a) for a in cands]
        self.rollout_s += time.perf_counter() - t0
        self.cands += len(cands)
        best = int(max(range(len(cands)), key=lambda i: scores[i]))
        pick = cands[best] if not self.force_policy else pol
        self.searched += 1
        srt = sorted(scores, reverse=True)
        self.margins.append(srt[0] - srt[1])
        if pol[0] == 0:
            self.policy_wait += 1
        if pick[0] == 0:
            self.search_wait += 1
        if pick != pol:
            self.disagree += 1
            if pick[0] == 0 and pol[0] == 1:
                self.wait_over_play += 1
            elif pick[0] == 1 and pol[0] == 0:
                self.play_over_wait += 1
        return pick, True


# ---------------------------------------------------------------------------- diagnostics

def spell_geometry(env, card_id, cell):
    """Section 4r's probe, inline: distance to the nearest enemy and how many enemies sit inside
    the spell's OWN radius at the instant of the cast. A DUMP = zero enemies in radius."""
    spec = env.specs[card_id]
    c = env.actions.deploy_clamp(card_id in env.anywhere_ids, cell)
    nx, ny = env.actions.cell_center(c % env.gw, c // env.gw)
    rad = float(spec.spell_radius or 2.0)
    best, inside = 1e9, 0
    for u in env.eng.units:
        if u.team != 1 or u.hp <= 0:
            continue
        d = math.hypot((nx - u.x) * TILES_X, (ny - u.y) * TILES_Y)
        best = min(best, d)
        inside += d <= rad
    return spec.base, (None if best > 1e8 else best), inside


# ---------------------------------------------------------------------------- match loop

def play_match(env, searcher, seed, max_steps=2000):
    env.rng.seed(seed)
    env.reset()
    dmg_spells = set(getattr(env, "damage_spell_ids", set()))
    rec = {"seed": seed, "steps": 0, "plays": 0, "elixir_sum": 0.0, "ge6": 0,
           "casts": 0, "dumped": 0, "cast_rows": []}
    t0 = time.perf_counter()
    for i in range(max_steps):
        act, _did = searcher.act(i)
        rec["elixir_sum"] += float(env.eng.elixir[0])
        rec["ge6"] += float(env.eng.elixir[0]) >= 6.0
        if act[0] == 1:
            rec["plays"] += 1
            if act[1] in dmg_spells or env.specs[act[1]].kind == "spell":
                base, dist, inside = spell_geometry(env, act[1], act[2])
                rec["casts"] += 1
                rec["dumped"] += inside == 0
                rec["cast_rows"].append([base, dist, inside])
        _o, _r, done, info = env.step(act)
        rec["steps"] = i + 1
        if done:
            rec["outcome"] = info.get("outcome")
            rec["crowns"] = list(info.get("crowns", (0, 0)))
            break
    else:
        rec["outcome"] = "timeout"
        rec["crowns"] = [env.eng.crowns(0), env.eng.crowns(1)]
    eng = env.eng
    rec["t_end"] = float(eng.t)
    rec["our_tower"] = Scorer.tower_frac(eng, 0)
    rec["their_tower"] = Scorer.tower_frac(eng, 1)
    rec["tower_delta"] = rec["our_tower"] - rec["their_tower"]
    rec["crown_delta"] = rec["crowns"][0] - rec["crowns"][1]
    rec["wall_s"] = time.perf_counter() - t0
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=60)
    ap.add_argument("--seed0", type=int, default=900000)
    ap.add_argument("--horizon", type=float, default=0.0, help="0 = baseline, policy alone")
    ap.add_argument("--interval", type=int, default=5, help="search every Nth decision")
    ap.add_argument("--topk", type=int, default=4)
    ap.add_argument("--crown", type=float, default=1.0)
    ap.add_argument("--tag", default="arm")
    ap.add_argument("--out", default=None)
    ap.add_argument("--force-policy", action="store_true",
                    help="roll everything out, then play the POLICY's action anyway (leak probe)")
    ap.add_argument("--ckpt", default=r"C:\Users\benpe\ClashBot\scratchpad\_rs_policy.pt")
    args = ap.parse_args()

    torch.set_num_threads(1)
    torch.manual_seed(0)
    np.random.seed(0)
    random.seed(0)

    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=12345)
    env.domain_rand.enabled = False
    env.domain_rand.resample()
    env.opponent_provider = None                 # LADDER pool, exactly the trainer's default eval
    device = torch.device("cpu")
    net = load_net(args.ckpt, env, device)
    gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))

    interval = args.interval if args.horizon > 0 else 0
    s = Searcher(env, net, device, max(args.horizon, 1e-6), interval, args.topk, args.crown,
                 gate_tau, force_policy=args.force_policy)

    recs = []
    wall0 = time.perf_counter()
    for m in range(args.matches):
        recs.append(play_match(env, s, args.seed0 + m))
        if (m + 1) % 10 == 0:
            wr = 100.0 * sum(r["outcome"] == "win" for r in recs) / len(recs)
            print(f"  [{args.tag}] {m+1}/{args.matches}  wr={wr:.1f}%  "
                  f"{(time.perf_counter()-wall0)/(m+1):.2f} s/match", flush=True)

    out = {
        "tag": args.tag, "horizon": args.horizon, "interval": args.interval, "topk": args.topk,
        "crown_w": args.crown, "matches": args.matches, "seed0": args.seed0,
        "ckpt": os.path.basename(args.ckpt),
        "wall_s": time.perf_counter() - wall0,
        "rollout_s": s.rollout_s, "candidates": s.cands,
        "searched": s.searched, "disagree": s.disagree,
        "policy_wait": s.policy_wait, "search_wait": s.search_wait,
        "wait_over_play": s.wait_over_play, "play_over_wait": s.play_over_wait,
        "crown_fires": s.scorer.crown_fires,
        "margin_mean": float(np.mean(s.margins)) if s.margins else 0.0,
        "records": recs,
    }
    path = args.out or rf"C:\Users\benpe\ClashBot\scratchpad\rs_{args.tag}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    wr = 100.0 * sum(r["outcome"] == "win" for r in recs) / max(1, len(recs))
    print(f"[{args.tag}] wr={wr:.1f}%  towerdelta={np.mean([r['tower_delta'] for r in recs]):.4f}  "
          f"searched={s.searched} disagree={s.disagree} "
          f"wait->play={s.play_over_wait} play->wait={s.wait_over_play}  "
          f"wall={out['wall_s']:.1f}s -> {path}", flush=True)


if __name__ == "__main__":
    main()
