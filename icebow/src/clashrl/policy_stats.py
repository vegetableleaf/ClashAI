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


def policy_stats(cfg, ckpt: Optional[str] = None, matches: int = 60, envs: int = 8,
                 seed: int = 4242, epsilon: float = 0.0, out: Optional[str] = None) -> None:
    try:
        import torch
    except ImportError as exc:  # noqa: BLE001
        print(f"[policy-stats] PyTorch required ({exc}).")
        return
    import random

    import numpy as np

    from .sim.env import SimMatchEnv
    from .train_rl import _build_net, _pick_device

    data_dir = cfg.path("data")
    if ckpt:
        ck_path = Path(ckpt)
        if not ck_path.is_absolute():
            ck_path = cfg.path(ckpt)
    else:
        best = data_dir / "policy_sim_best.pt"
        ck_path = best if best.exists() else data_dir / "policy_sim.pt"
    if not ck_path.exists():
        print(f"[policy-stats] checkpoint not found: {ck_path}")
        return

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
    net = _build_net(cfg, device, n_cards, n_cells, threat_dim)

    try:
        state = torch.load(ck_path, map_location="cpu", weights_only=True)
    except Exception:                           # noqa: BLE001 -- older checkpoints are plain pickles
        state = torch.load(ck_path, map_location="cpu")
    ck_cards = int(state.get("n_cards", n_cards))
    ck_cells = int(state.get("n_cells", n_cells))
    if ck_cards != n_cards or ck_cells != n_cells:
        print(f"[policy-stats] checkpoint does not match the current config: "
              f"checkpoint has n_cards={ck_cards} n_cells={ck_cells}, current is {n_cards}/{n_cells}.")
        print("[policy-stats] The deck in cards.yaml or action.grid does not agree with the "
              "checkpoint; analysis aborted.")
        return
    net.policy.load_state_dict(state["model"])
    if "gate" in state:
        net.gate.load_state_dict(state["gate"])
    net.eval()

    anywhere_ids = set(e0.anywhere_ids)
    yourhalf_mask = torch.tensor(e0.actions.deployable_mask(False), dtype=torch.bool, device=device)
    allcells_mask = torch.ones(n_cells, dtype=torch.bool, device=device)
    card_costs_t = torch.tensor([float(s.elixir) for s in e0.specs], dtype=torch.float32,
                                device=device)

    def to_obs_t(o):
        return torch.from_numpy(o).float().permute(2, 0, 1).to(device) / 255.0

    def to_vec_t(v):
        return torch.from_numpy(np.asarray(v, np.float32)).to(device)

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

    print(f"[policy-stats] {ck_path.name} on {device}: {matches} greedy matches, {K} envs, "
          f"deck {', '.join(e0.deck_keys)}", flush=True)
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
                              torch.stack([to_vec_t(t) for t in thr]))
        cq = cq.masked_fill(hand_t < 0.5, float("-inf"))
        acts = []
        for i in range(K):
            steps += 1
            if not any(v > 0.5 for v in hand[i]):
                wait_forced += 1
                acts.append((0, 0, 0))
                continue
            cq_i = cq[i].masked_fill(card_costs_t > pool[i].elixir + 1e-6, float("-inf"))
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
                ceq_i = ceq[i].masked_fill(~cmask, float("-inf"))
                if gq[i, 0] >= gq[i, 1] + cq_i.max() + ceq_i.max():
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
        "never_played": [e0.deck_keys[i] for i in range(n_cards) if plays[i] == 0],
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
    for c in sorted(cards_out, key=lambda c: -c["plays"]):
        print(f"[policy-stats]   {c['display']:<24} {c['plays']:>6} plays "
              f"({100 * c['share']:4.1f}%)", flush=True)
    if result["never_played"]:
        print(f"[policy-stats] NEVER played: {', '.join(result['never_played'])}", flush=True)
    print(f"[policy-stats] -> {out_path}", flush=True)
