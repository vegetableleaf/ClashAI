r"""`run.py policy-stats` -- what does the trained policy ACTUALLY do?

Plays greedy matches in the headless simulator with a frozen checkpoint and counts
the decisions: plays per card, placement cells per card, and how the wait/play gate
splits. That is the read-out you need to judge reward shaping -- a card that is
never played, or a win condition that always lands in the same dead cell, does not
show up anywhere in the win-rate curve.

Deliberately a SEPARATE rollout rather than instrumentation inside train_sim: the
training loop's action distribution is smeared by epsilon-exploration and by the
self-play league, so it would answer a different question.

Usage (from icebow/):
    .\.venv\Scripts\python.exe run.py policy-stats --matches 60
    .\.venv\Scripts\python.exe run.py policy-stats --ckpt data/policy_sim.pt --matches 200
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Terms that are ONE-SIDED BY DESIGN: they report an outcome, not a judgement of a play, so having
# no positive fires is correct and must not be flagged as an action tax. `lose_own_tower` can only
# ever be negative in the same way `take_enemy_tower` can only ever be positive.
_ONE_SIDED_BY_DESIGN = {"lose_own_tower", "take_enemy_tower", "chip_offence", "chip_defence", "leak"}


def policy_stats(cfg, ckpt: Optional[str] = None, matches: int = 60, envs: int = 8,
                 seed: int = 4242, epsilon: float = 0.0, out: Optional[str] = None) -> None:
    # EVALUATION POOL, separate from the training weights. sim.meta_deck_boost skews the opponent
    # mix toward what the bot MEETS, which is right for training and wrong for measurement --
    # scoring a policy on the same skew it was tuned against flatters it. Measured: the same
    # checkpoint read 20.0% on the boosted pool and 21.2% on the flat one. The eval keys are
    # swapped in HERE, in this process only, so the training config on disk is untouched.
    _sim = cfg.data.setdefault("sim", {}) if hasattr(cfg, "data") else None
    if _sim is not None:
        _sim["meta_deck_boost"] = _sim.get("eval_deck_boost") or {}
        _sim["meta_deck_top_n"] = int(_sim.get("eval_deck_top_n") or 0)
        print("[policy-stats] opponent pool: EVAL weighting (training boosts disabled)", flush=True)

    try:
        import torch
    except ImportError as exc:  # noqa: BLE001
        print(f"[policy-stats] PyTorch required ({exc}).")
        return
    import random

    import numpy as np

    from .sim.env import SimMatchEnv
    from .train_rl import _build_net, _pick_device
    from .wincon_bank import apply_wincon_bank

    data_dir = cfg.path("data")
    if ckpt:
        ck_path = Path(ckpt)
        if not ck_path.is_absolute():
            ck_path = cfg.path(ckpt)
    else:
        # DEFAULT TO THE LIVE PPO LINEAGE (2026-08-15). The old default reached back to
        # data/policy_sim_best.pt -- an Aug 7 fossil from a previous architecture era -- and a
        # bare `policy-stats` run silently evaluated THAT: the user saw "cell spread 23,
        # x_bow 0" and nearly diagnosed a healthy run as collapsed.
        for name in ("policy_sim_ppo.pt", "policy_sim_ppo_best.pt",
                     "policy_sim_best.pt", "policy_sim.pt"):
            ck_path = data_dir / name
            if ck_path.exists():
                break
    if not ck_path.exists():
        print(f"[policy-stats] checkpoint not found: {ck_path}")
        return

    try:
        state = torch.load(ck_path, map_location="cpu", weights_only=True)
    except Exception:                           # noqa: BLE001 -- older checkpoints are plain pickles
        state = torch.load(ck_path, map_location="cpu")

    K = max(1, int(envs))
    pool = [SimMatchEnv(cfg, seed=seed + i) for i in range(K)]
    e0 = pool[0]
    for e in pool:                              # canonical rendering: this is a measurement, not training
        if getattr(e, "domain_rand", None) is not None:
            e.domain_rand.enabled = False
            e.domain_rand.resample()
    n_cards, n_cells, threat_dim = e0.n_cards, e0.n_cells, e0.threat_dim
    gw, gh = e0.gw, e0.gh
    device = _pick_device(cfg)

    # Recover architecture dimensions from checkpoint metadata first; fall back to state_dict shape.
    # This lets policy-stats read both pre-canvas (3ch) and canvas (9ch) checkpoints under one config.
    model_sd = state.get("model") or {}
    conv0_w = model_sd.get("features.0.weight")
    ck_in_ch = int(state.get("in_ch", 0) or 0)
    if ck_in_ch <= 0:
        ck_in_ch = int(conv0_w.shape[1]) if conv0_w is not None and hasattr(conv0_w, "shape") else 3
    thr_w = model_sd.get("threat_fc.0.weight")
    ck_threat_dim = int(state.get("threat_dim", 0) or 0)
    if ck_threat_dim <= 0:
        ck_threat_dim = int(thr_w.shape[1]) if thr_w is not None and hasattr(thr_w, "shape") else threat_dim

    net = _build_net(cfg, device, n_cards, n_cells, ck_threat_dim, ck_in_ch)
    ck_cards = int(state.get("n_cards", n_cards))
    ck_cells = int(state.get("n_cells", n_cells))
    if ck_cards != n_cards or ck_cells != n_cells:
        print(f"[policy-stats] checkpoint does not match the current config: "
              f"checkpoint has n_cards={ck_cards} n_cells={ck_cells}, current is {n_cards}/{n_cells}.")
        print("[policy-stats] The deck in cards.yaml or action.grid does not agree with the "
              "checkpoint; analysis aborted.")
        return
    obs_ch = int(e0.obs_shape[2])
    if ck_in_ch != obs_ch:
        print(f"[policy-stats] checkpoint expects in_ch={ck_in_ch}, env emits {obs_ch}; "
              "adapting observation channels for this analysis run.")
    if ck_threat_dim != threat_dim:
        print(f"[policy-stats] checkpoint expects threat_dim={ck_threat_dim}, env emits {threat_dim}; "
              "adapting threat vectors for this analysis run.")
    net.policy.load_state_dict(state["model"])
    if "gate" in state:
        net.gate.load_state_dict(state["gate"])
    net.eval()

    # THE GATE RULE IS PER-ALGORITHM AND MUST MATCH THE TRAINER'S. The DDQN gate is now a DIRECT
    # comparison of the two gate logits (wait vs play); a PPO gate is a two-logit CLASSIFIER
    # thresholded on its PROBABILITY (sim.ppo_gate_threshold). Reading a PPO gate with the DDQN rule
    # made this report claim the gate never held -- the same drift that once cost 33pp when the
    # benchmark used tau=0.5 on a gate whose median P(play) is ~0.05.
    # The DDQN rule was `wait >= play + best card + best cell` while it was trained as three heads
    # against one; train_rl now uses a dueling-style advantage baseline, so max over (card, cell) of
    # Q(play) IS gate[play] and the comparison is gate-only. Keep the two in lockstep.
    algo = str(state.get("algo", "") or "").lower()
    is_ppo = algo == "ppo" or (not algo and "ppo" in ck_path.name.lower())
    gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
    print(f"[policy-stats] checkpoint algo '{algo or 'unknown'}' -> gate rule "
          + (f"PPO sigmoid(play-wait) > {gate_tau}" if is_ppo else "DDQN gate-logit compare"))

    anywhere_ids = set(e0.anywhere_ids)
    yourhalf_mask = torch.tensor(e0.actions.deployable_mask(False), dtype=torch.bool, device=device)
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    card_costs_t = torch.tensor([float(s.elixir) for s in e0.specs], dtype=torch.float32,
                                device=device)
    # WIN-CONDITION BANK (shared with train_sim_ppo + its greedy benchmark)
    wincon_ids = sorted(set(e0.xbow_ids) | set(e0.rocket_ids))
    wincon_cost = min((float(e0.specs[i].elixir) for i in wincon_ids), default=0.0)
    bank_floor = float(cfg.get("sim", "wincon_bank_floor", default=0.0)) if wincon_ids else 0.0
    if bank_floor > 0.0:
        print(f"[policy-stats] win-condition bank ON (floor {bank_floor:.0f}, "
              f"wincon cost {wincon_cost:.0f}) -- same rule as the trainer")

    def to_obs_t(o):
        x = np.asarray(o)
        if x.shape[2] > ck_in_ch:
            x = x[:, :, :ck_in_ch]
        elif x.shape[2] < ck_in_ch:
            pad = np.zeros((x.shape[0], x.shape[1], ck_in_ch - x.shape[2]), dtype=x.dtype)
            x = np.concatenate([x, pad], axis=2)
        return torch.from_numpy(x).float().permute(2, 0, 1).to(device) / 255.0

    def to_vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

    def to_thr_t(v):
        t = np.asarray(v, np.float32)
        if t.shape[0] > ck_threat_dim:
            t = t[:ck_threat_dim]
        elif t.shape[0] < ck_threat_dim:
            t = np.pad(t, (0, ck_threat_dim - t.shape[0]))
        return torch.from_numpy(t).to(device)

    plays = [0] * n_cards
    heat = [[0] * n_cells for _ in range(n_cards)]
    total_heat = [0] * n_cells
    steps = wait_gate = wait_forced = play_n = 0
    outcomes = {"win": 0, "loss": 0, "draw": 0}
    elixir_at_play: List[float] = []

    obs = [e.reset() for e in pool]
    hand = [e.hand_vec.copy() for e in pool]
    nxt = [e.next_vec.copy() for e in pool]
    elx = [e.elixir_vec.copy() for e in pool]
    thr = [e.threat_vec.copy() for e in pool]

    print(f"[policy-stats] {ck_path.name} auf {device}: {matches} greedy matches, {K} envs, "
          f"Deck {', '.join(e0.deck_keys)}", flush=True)
    t0 = time.time()
    played = 0
    next_report = max(1, matches // 10)
    while played < matches:
        obs_t = torch.stack([to_obs_t(o) for o in obs])
        hand_t = torch.stack([to_vec_t(h) for h in hand])
        with torch.no_grad():
            cq, ceq, gq = net(obs_t, hand_t,
                              torch.stack([to_vec_t(n) for n in nxt]),
                              torch.stack([to_vec_t(e) for e in elx]),
                              torch.stack([to_thr_t(t) for t in thr]))
        cq = cq.masked_fill(hand_t < 0.5, float("-inf"))
        acts = []
        for i in range(K):
            steps += 1
            if not any(v > 0.5 for v in hand[i]):
                wait_forced += 1
                acts.append((0, 0, 0))
                continue
            cq_i = cq[i].masked_fill(card_costs_t > pool[i].elixir + 1e-6, float("-inf"))
            if bank_floor > 0.0 and wincon_ids:
                # WIN-CONDITION BANK -- the SAME rule the trainer and the greedy benchmark apply
                # (clashrl/wincon_bank.py). Measuring without it would report a different policy
                # than the one being trained, which is exactly the trainer/benchmark drift that
                # once cost ~33pp here.
                holds_wc = torch.tensor([[any(hand[i][w] > 0.5 for w in wincon_ids)]],
                                        dtype=torch.bool, device=device).view(-1)
                keep = apply_wincon_bank(
                    torch.isfinite(cq_i).view(1, -1),
                    torch.tensor([float(pool[i].elixir)], device=device),
                    card_costs_t, holds_wc, wincon_cost, bank_floor)
                cq_i = cq_i.masked_fill(~keep.view(-1), float("-inf"))
            if not torch.isfinite(cq_i).any():             # nothing affordable
                wait_forced += 1
                acts.append((0, 0, 0))
                continue
            if epsilon > 0 and random.random() < epsilon:
                cand = [j for j in range(n_cards) if torch.isfinite(cq_i[j])]
                ci = random.choice(cand)
                cells = [c for c in range(n_cells)
                         if ci in anywhere_ids or bool(yourhalf_mask[c])]
                cell = random.choice(cells or list(range(n_cells)))
            else:
                ci = int(cq_i.argmax())
                cmask = allcells_mask if ci in anywhere_ids else yourhalf_mask
                ceq_i = ceq[i, ci].masked_fill(~cmask, float("-inf"))   # PER-CARD map
                held = (float(torch.sigmoid(gq[i, 1] - gq[i, 0])) <= gate_tau if is_ppo
                        else bool(gq[i, 0] >= gq[i, 1]))
                if held:
                    wait_gate += 1                          # the GATE chose to hold, not a lack of options
                    acts.append((0, 0, 0))
                    continue
                cell = int(ceq_i.argmax())
            play_n += 1
            plays[ci] += 1
            heat[ci][cell] += 1
            total_heat[cell] += 1
            elixir_at_play.append(float(pool[i].elixir))
            acts.append((1, ci, cell))

        for i, env in enumerate(pool):
            nobs, _r, done, info = env.step(acts[i])
            if done:
                oc = info.get("outcome")
                if oc in outcomes:
                    outcomes[oc] += 1
                played += 1
                obs[i] = env.reset()
                if played >= next_report:
                    next_report += max(1, matches // 10)
                    print(f"[policy-stats] {played}/{matches} matches "
                          f"({played / max(1e-6, time.time() - t0):.1f} m/s)", flush=True)
            else:
                obs[i] = nobs
            hand[i], nxt[i] = env.hand_vec.copy(), env.next_vec.copy()
            elx[i], thr[i] = env.elixir_vec.copy(), env.threat_vec.copy()

    db = e0.db
    cards_out: List[Dict[str, Any]] = []
    for i, key in enumerate(e0.deck_keys):
        base = db.get(key.replace("_evo", "")) or {}
        rows = [c // gw for c in range(n_cells) for _ in range(heat[i][c])]
        cards_out.append({
            "key": key,
            "display": (base.get("display") or key) + (" (Evo)" if key.endswith("_evo") else ""),
            "elixir": base.get("elixir"),
            "level": e0.deck_card_levels[i] if i < len(e0.deck_card_levels) else None,
            "plays": plays[i],
            "share": plays[i] / max(1, play_n),
            "mean_row": (sum(rows) / len(rows)) if rows else None,
            "heat": heat[i],
        })

    # PER-TERM REWARD ACCOUNTING, summed over the env pool. A term that fires often and NEVER pays
    # positive is an ACTION TAX -- the shape that has collapsed three runs into "stop playing" -- and
    # this is the cheapest place to see it, because these are greedy rollouts with no exploration noise.
    rw_terms: Dict[str, Dict[str, float]] = {}
    for e in pool:
        stats = getattr(e, "rw_stats", None)
        if stats is None:
            continue
        for name, t in stats.run.items():
            acc = rw_terms.setdefault(name, {"fires": 0, "pos": 0, "neg": 0,
                                             "total": 0.0, "pos_total": 0.0, "neg_total": 0.0})
            acc["fires"] += t.fires
            acc["pos"] += t.pos
            acc["neg"] += t.neg
            acc["total"] += t.total
            acc["pos_total"] += t.pos_total
            acc["neg_total"] += t.neg_total
    tax_terms = [k for k, v in rw_terms.items()
                 if v["fires"] > 0 and v["pos"] == 0 and k not in _ONE_SIDED_BY_DESIGN]

    result = {
        "generated": time.time(),
        "ckpt": str(ck_path.relative_to(cfg.root)) if ck_path.is_relative_to(cfg.root) else str(ck_path),
        "matches": played, "envs": K, "seed": seed, "epsilon": epsilon,
        "grid": [gw, gh], "deck": list(e0.deck_keys),
        "steps": steps, "plays": play_n, "wait_gate": wait_gate, "wait_forced": wait_forced,
        "wait_rate_gate": wait_gate / max(1, steps),
        "wait_rate_total": (wait_gate + wait_forced) / max(1, steps),
        "avg_elixir_at_play": (sum(elixir_at_play) / len(elixir_at_play)) if elixir_at_play else None,
        "outcomes": outcomes,
        "winrate": 100.0 * outcomes["win"] / max(1, played),
        "cards": cards_out,
        "heat": total_heat,
        # PLACEMENT SPREAD -- the acceptance metric for the cell-head collapse. A policy whose cell
        # head has frozen reports a handful of cells and a top-cell share near 1.0; a healthy one
        # spreads over dozens. This is measured on GREEDY rollouts, so it reflects the deployed
        # behaviour, not the exploration noise the trainer adds.
        "cells_used": sum(1 for v in total_heat if v),
        "top_cell_share": (max(total_heat) / max(1, sum(total_heat))) if any(total_heat) else 0.0,
        "never_played": [e0.deck_keys[i] for i in range(n_cards) if plays[i] == 0],
        "reward_terms": rw_terms,
        "zero_positive_terms": tax_terms,
        "plays_per_match": play_n / max(1, played),
        "seconds": time.time() - t0,
    }
    out_path = Path(out) if out else cfg.path("data/policy_stats.json")
    if not out_path.is_absolute():
        out_path = cfg.path(str(out_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")

    print(f"[policy-stats] {played} matches, win rate {result['winrate']:.0f}% | "
          f"{play_n} plays, the gate held on {100 * result['wait_rate_gate']:.0f}% of ticks "
          f"(forced waits {100 * wait_forced / max(1, steps):.0f}%)", flush=True)
    print(f"[policy-stats] placement spread: {result['cells_used']} of {n_cells} cells used, "
          f"top cell {100 * result['top_cell_share']:.1f}% of plays", flush=True)
    # COLLAPSE WARNINGS. The placement head has collapsed twice in this project's history and both
    # times the headline win rate was FLAT or RISING while it happened -- champion 48/432 cells at
    # 41% top-cell, then 28/432 at 37% after the per-card head had briefly reached 62/432 at 20%.
    # An aggregate that only improves is exactly how it goes unnoticed, so the diagnosis is printed
    # next to the number rather than left to be spotted later.
    _row_share, _gw = {}, gw
    for _c, _n in enumerate(total_heat):
        if _n:
            _row_share[_c // _gw] = _row_share.get(_c // _gw, 0) + _n
    _plays_tot = max(1, sum(total_heat))
    _top_row, _top_row_n = max(_row_share.items(), key=lambda kv: kv[1], default=(-1, 0))
    warns = []
    if result["cells_used"] < 0.10 * n_cells:
        warns.append("only %d of %d cells ever used (<10%%)" % (result["cells_used"], n_cells))
    if result["top_cell_share"] >= 0.25:
        warns.append("one tile holds %.0f%% of all plays" % (100 * result["top_cell_share"]))
    if _top_row_n >= 0.60 * _plays_tot:
        warns.append("row %d holds %.0f%% of all plays" % (_top_row, 100 * _top_row_n / _plays_tot))
    _flat = [c["key"] for c in cards_out
             if c["plays"] >= 20 and len({i for i, v in enumerate(c["heat"]) if v}) <= 3]
    if _flat:
        warns.append("cards pinned to <=3 cells: %s" % ", ".join(_flat[:6]))
    for w in warns:
        print("[policy-stats] PLACEMENT COLLAPSE WARNING: %s" % w, flush=True)
    result["collapse_warnings"] = warns
    for c in sorted(cards_out, key=lambda c: -c["plays"]):
        print(f"[policy-stats]   {c['display']:<24} {c['plays']:>6} plays "
              f"({100 * c['share']:4.1f}%)", flush=True)
    if result["never_played"]:
        print(f"[policy-stats] NEVER played: {', '.join(result['never_played'])}", flush=True)
    if rw_terms:
        print(f"[policy-stats] reward terms ({result['plays_per_match']:.1f} plays/match), "
              f"most NEGATIVE first:", flush=True)
        for name, v in sorted(rw_terms.items(), key=lambda kv: kv[1]["total"]):
            print(f"[policy-stats]   {name:<20} total {v['total']:+10.1f}  fires {v['fires']:>7}  "
                  f"(+{v['pos']} / -{v['neg']})", flush=True)
        if tax_terms:
            print(f"[policy-stats] ACTION TAX -- fired but NEVER positive: {', '.join(tax_terms)}",
                  flush=True)
    print(f"[policy-stats] -> {out_path}", flush=True)
