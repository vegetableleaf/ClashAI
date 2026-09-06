"""Play the S1 imitation model (``pipeline.model_v3.S1Model``) on the REAL engine against the L62 ghost pool.

    python -m pipeline.engine_play icebow --ckpt icebow/data/pipeline/s1_icebow_s0.pt --port 37031 \
        --matches 2 --seed 0 --out scratchpad/gauntlet/L64/engine_play/

World and opponent are ``scratchpad/gauntlet/L62/engine_env.py``'s ``EngineMatchEnv`` (real engine on a running
worker-service port, ghost = one mined human opponent replayed from their 20 Hz command timeline, non-reactive).
Only its reset / deck-deal / ghost driving / termination are used; its OLD-policy observation path (FakeEngine ->
SimMatchEnv) is bypassed: ``_render`` is overridden to hand back the RAW ``observe()`` dict, which goes through
``pipeline.obs_contract.from_engine`` exactly as the training rows did.

Observation parity with training (``pipeline.dataset``): PLAY rows are built from ``_as_compact(play_frame)`` --
entities WITHOUT ``kind`` (so ``deploying`` is unknown), NO ``effects`` / ``projectiles`` (so no spell tokens), no
entity history (``age`` unknown). ``compact_raw`` strips the raw state the same way before ``from_engine`` so the
model sees the row format it was trained on, not a richer one.

Decision rule (``decide``): every ``decide_every`` engine ticks build the obs, run the model; play iff
sigmoid(gate) > ``tau`` (``--gate threshold``), with probability sigmoid(gate) (``--gate sample``), or
never (``--gate none``, the per-tag no-plays control); card =
argmax of the hand-masked card logits; cell = argmax of that card's 2,304 cell logits; the cell CENTRE goes
back to engine (x, y) through ``board_to_engine`` (the inverse of ``obs_contract._engine_xy``) and is played
with ``NativeRoyaleEnv.act``. A refused play is counted and the loop continues. Every decision is appended to
``<out>/<tag>_m<i>.jsonl``; one summary json line per match on stdout and a final summary line.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from pipeline import vocab                                                            # noqa: E402
from pipeline.dataset import _past                                                    # noqa: E402
from pipeline.model_v3 import GRID_X, GRID_Y, N_SLOTS, S1Model, hand_mask_from_sc     # noqa: E402
from pipeline.obs_contract import ENGINE_X, ENGINE_Y, TICK_S, from_engine, load_deck, to_tokens  # noqa: E402

ENGINE_ENV = REPO / "scratchpad" / "gauntlet" / "L62" / "engine_env.py"
MAX_U = 64                                   # train_s1.MAX_U (not imported: train_s1 pulls torch at import)
RESULT_CODE_NAMES = {0: "accepted", 9: "card_not_in_hand", 13: "not_enough_elixir_13", 22: "native_rejected", 1014: "ability_exhausted",
                     1050: "not_enough_elixir"}


# ------------------------------------------------------------------------------------------------------
# geometry: cell -> board (x, y) -> engine (x, y)
# ------------------------------------------------------------------------------------------------------
def cell_center(cell: int, gx: int = GRID_X, gy: int = GRID_Y) -> tuple[float, float]:
    """Inverse of ``model_v3.cell_index`` at the cell centre: board-frame (x, y) in [0, 1]."""
    cell = int(cell)
    return (cell % gx + 0.5) / gx, (cell // gx + 0.5) / gy


def board_to_engine(x: float, y: float, mirror: bool) -> tuple[float, float]:
    """Exact algebraic inverse of ``obs_contract._engine_xy`` (board frame, me at the bottom -> engine units)."""
    X = x * ENGINE_X
    Y = (1.0 - y) * ENGINE_Y
    if mirror:
        X, Y = ENGINE_X - X, ENGINE_Y - Y
    return X, Y


def cell_to_engine(cell: int, mirror: bool) -> tuple[int, int]:
    x, y = cell_center(cell)
    X, Y = board_to_engine(x, y, mirror)
    return int(round(X)), int(round(Y))


# ------------------------------------------------------------------------------------------------------
# raw engine state -> the training row format
# ------------------------------------------------------------------------------------------------------
_ENT_KEYS = ("side", "x", "y", "name", "hp", "max_hp", "card_id")


def compact_raw(state: dict) -> dict:
    """The raw ``observe()`` dict reduced to what ``dataset._as_compact`` leaves a PLAY row: entities with no
    ``kind``, no effects / projectiles. Still the RAW (dict) shape, so ``from_engine`` takes its raw branch."""
    return {"tick": int(state["tick"]),
            "players": state.get("players", []),
            "entities": [{k: e[k] for k in _ENT_KEYS if k in e} for e in state.get("entities", [])],
            "episode": {"crown_towers": (state.get("episode") or {}).get("crown_towers", [])}}


def list_frame(state: dict) -> dict:
    """The recorder's compact list frame (replay_drive.snapshot + players) for the parity check only."""
    players = {int(p["side"]): p for p in state["players"]}
    return {"tick": int(state["tick"]),
            "elixir": [players[s].get("elixir_exact", players[s].get("elixir")) for s in (0, 1)],
            "entities": [[int(e["side"]), int(e["x"]), int(e["y"]), e.get("name", str(e.get("card_id"))),
                          int(e["hp"]), int(e["max_hp"])] for e in state.get("entities", [])],
            "towers": [[int(t["side"]), t.get("type"), t.get("lane"), int(t["x"]), int(t["y"]), int(t["hp"]),
                        int(t["max_hp"])] for t in state["episode"].get("crown_towers", [])],
            "players": [{"side": int(p["side"]), "hand": [h["name"] for h in p["hand"]],
                         "next": p.get("next_deck_index")} for p in state["players"]]}


def engine_deck_names(order: list[dict]) -> list[str]:
    """``final_decks[side]`` naming (replay_drive.py:317): ``Name@form`` unless the form is base."""
    return [f"{it['name']}@{it['form']}" if it["form"] != "base" else str(it["name"]) for it in order]


# ------------------------------------------------------------------------------------------------------
# env: EngineMatchEnv with the raw state in place of the old observation
# ------------------------------------------------------------------------------------------------------
def _load_engine_env():
    spec = importlib.util.spec_from_file_location("l62_engine_env", str(ENGINE_ENV))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["l62_engine_env"] = mod
    spec.loader.exec_module(mod)
    return mod


class RawEngineEnv:
    """Built lazily so the L62 module (clashrl + native_core import roots) is only loaded when playing."""

    def __new__(cls, *a, **k):
        base = _load_engine_env().EngineMatchEnv

        class _Raw(base):
            def _resolve_decks(self, entry):
                final, hit = super()._resolve_decks(entry)
                self.final_decks = final
                return final, hit

            def _render(self, state):
                self.raw_state = state
                return state

        return _Raw(*a, **k)


# ------------------------------------------------------------------------------------------------------
# model
# ------------------------------------------------------------------------------------------------------
def load_model(ckpt: Path, device: str, retries: int = 5):
    import torch
    last = None
    for i in range(retries):
        try:
            ck = torch.load(ckpt, map_location=device)
            break
        except Exception as e:                      # the trainer rewrites this file at every best epoch
            last = e
            time.sleep(3.0)
    else:
        raise RuntimeError(f"torch.load({ckpt}) failed {retries}x: {last!r}")
    args = ck.get("args") or {}
    model = S1Model(d=int(args.get("d", 128)), layers=int(args.get("layers", 4))).to(device)
    model.load_state_dict(ck["model"])
    model.eval()
    return model, {"epoch": ck.get("epoch"), "n_params": ck.get("n_params"), "deck": ck.get("deck"),
                   "val_cell_tile_top1": (ck.get("val") or {}).get("cell_tile_top1")}


def decide(model, tok: np.ndarray, mask: np.ndarray, sc: np.ndarray, past: np.ndarray, *, tau: float = 0.5,
           gate: str = "threshold", rng: Optional[random.Random] = None, device: str = "cpu",
           policy: str = "model", p_random: float = 0.093) -> dict:
    """One decision. Returns {p_gate, play, slot, cell, p_card, p_cell}; slot/cell = -1 when not playing.
    ``policy="random"`` is the state-blind control: play with probability ``p_random`` per decision, a uniformly
    random hand card at a uniformly random own-half cell (rows GRID_Y/2..GRID_Y-1); the model still scores p_gate."""
    import torch
    with torch.no_grad():
        t_tok = torch.from_numpy(tok).unsqueeze(0).to(device)
        t_mask = torch.from_numpy(mask).unsqueeze(0).to(device)
        t_sc = torch.from_numpy(sc).unsqueeze(0).to(device)
        t_past = torch.from_numpy(past).unsqueeze(0).to(device)
        hm = hand_mask_from_sc(t_sc)
        enc = model.encode(t_tok, t_mask, t_sc, t_past)
        heads = model.heads(enc, hm)
        p_gate = float(torch.sigmoid(heads["gate"])[0])
        if gate == "none":                       # no-plays control: score the ghost alone, still log p_gate
            play = False
        elif gate == "sample":
            play = (rng or random).random() < p_gate
        else:
            play = p_gate > tau
        if policy == "random":
            r_ = rng or random
            play = r_.random() < p_random and bool(hm.any())
            if not play:
                return {"p_gate": p_gate, "play": False, "slot": -1, "cell": -1, "p_card": None, "p_cell": None}
            slot = r_.choice([i for i in range(int(hm.shape[-1])) if bool(hm[0, i])])
            cell = r_.randrange(GRID_X * (GRID_Y // 2)) + GRID_X * (GRID_Y // 2)
            return {"p_gate": p_gate, "play": True, "slot": slot, "cell": cell, "p_card": None, "p_cell": None}
        if not play or not bool(hm.any()):
            return {"p_gate": p_gate, "play": False, "slot": -1, "cell": -1, "p_card": None, "p_cell": None}
        card_p = torch.softmax(heads["card"], -1)[0]
        slot = int(card_p.argmax())
        cell_logits = model.cell_logits(enc, torch.tensor([slot], device=device))
        cell_p = torch.softmax(cell_logits, -1)[0]
        cell = int(cell_p.argmax())
        return {"p_gate": p_gate, "play": True, "slot": slot, "cell": cell,
                "p_card": float(card_p[slot]), "p_cell": float(cell_p[cell])}


# ------------------------------------------------------------------------------------------------------
# one match
# ------------------------------------------------------------------------------------------------------
def _outcome(env, state: dict) -> tuple[str, tuple[int, int]]:
    last = env.eng.last_episode or env.episode or (state.get("episode") or {})
    hp = env._tower_hp(state)
    cr = env._crowns(hp)
    crowns = last.get("crowns")
    if crowns is not None and len(crowns) == 2:
        cr = (int(crowns[env.side]), int(crowns[env.opp]))
    winner = last.get("winner")
    if winner is None or int(winner) < 0:
        outcome = "draw" if cr[0] == cr[1] else ("win" if cr[0] > cr[1] else "loss")
    else:
        outcome = "win" if int(winner) == env.side else "loss"
    return outcome, cr


def play_match(env, model, deck, entry: dict, *, decide_every: int, tau: float, gate: str, rng: random.Random,
               device: str, log_path: Path, parity_check: bool = True, policy: str = "model",
               p_random: float = 0.093) -> dict:
    t0 = time.perf_counter()
    state = env.reset(entry)
    side, mirror = env.side, env._mirror
    engine_deck = engine_deck_names(env.final_decks[side])
    deck_index_of_slot = {}
    for i, nm in enumerate(engine_deck):
        s = deck.slot_of(vocab.engine_key(nm))
        if s >= 0:
            deck_index_of_slot[s] = i
    if sorted(deck_index_of_slot) != list(range(N_SLOTS)):
        raise RuntimeError(f"{entry['tag']}: engine deck {engine_deck} does not cover the 8 deck slots")
    unmapped: set = set()
    done_plays: list[tuple[int, int, float, float]] = []
    n_dec = n_play = n_acc = n_ref = 0
    reject_reasons: dict[str, int] = {}
    p_gates: list[float] = []
    parity = None
    done = False
    with log_path.open("w", encoding="utf-8") as lf:
        while not done:
            tick = env.tick
            obs = compact_raw(state)
            bs = from_engine(obs, side, deck, engine_deck=engine_deck, unmapped=unmapped)
            if parity_check and parity is None:
                bs2 = from_engine(list_frame(state), side, deck, engine_deck=engine_deck, unmapped=set())
                parity = bool(bs == bs2)
            tok, mask, sc = to_tokens(bs, MAX_U)
            past = _past(done_plays, tick)
            d = decide(model, tok, mask, sc, past, tau=tau, gate=gate, rng=rng, device=device, policy=policy,
                       p_random=p_random)
            n_dec += 1
            p_gates.append(d["p_gate"])
            rec: dict[str, Any] = {"tick": tick, "t": round(tick * TICK_S, 2), "p_gate": round(d["p_gate"], 4),
                                   "card": d["slot"], "cell": d["cell"], "accepted": None,
                                   "elixir": round(bs.my_elixir, 2), "hand": list(bs.my_hand), "n_units": int(mask.sum())}
            if d["play"]:
                n_play += 1
                x, y = cell_center(d["cell"])
                X, Y = cell_to_engine(d["cell"], mirror)
                r = env.eng.act(side=side, deck_index=deck_index_of_slot[d["slot"]], x=X, y=Y)
                acc = bool(r["accepted"])
                code = int(r.get("result_code", -1))
                nm = RESULT_CODE_NAMES.get(code, f"native_{code}")
                if r.get("placement_valid") is False:
                    nm = f"{nm}/{r.get('placement_reason')}"
                rec.update({"accepted": acc, "result_code": code, "reason": None if acc else nm,
                            "x": X, "y": Y, "bx": round(x, 4), "by": round(y, 4),
                            "p_card": None if d["p_card"] is None else round(d["p_card"], 4),
                            "p_cell": None if d["p_cell"] is None else round(d["p_cell"], 4),
                            "card_name": deck.cards[d["slot"]]})
                if acc:
                    n_acc += 1
                    done_plays.append((tick, d["slot"], x, y))
                else:
                    n_ref += 1
                    reject_reasons[nm] = reject_reasons.get(nm, 0) + 1
            lf.write(json.dumps(rec) + "\n")
            env._advance_to(min(env.tick + decide_every, env.tail_cap))
            state = env.eng.observe()
            done = bool(env.terminated) or env.tick >= env.tail_cap
    outcome, crowns = _outcome(env, state)
    minutes = env.tick * TICK_S / 60.0
    wall = time.perf_counter() - t0
    return {"tag": entry["tag"], "side": side, "outcome": outcome, "crowns_for": crowns[0],
            "crowns_against": crowns[1], "ticks": env.tick, "seconds": round(env.tick * TICK_S, 1),
            "terminated": bool(env.terminated), "termination_reason": (env.eng.last_episode or {}).get("termination_reason"),
            "decisions": n_dec, "plays": n_play, "accepted": n_acc, "refused": n_ref,
            "refuse_reasons": reject_reasons, "plays_per_min": round(n_play / minutes, 2) if minutes else None,
            "accepted_per_min": round(n_acc / minutes, 2) if minutes else None,
            "ghost_ok": env.ghost_ok, "ghost_refused": env.ghost_rejected, "ghost_total": len(env._ghosts),
            "ghost_refuse_reasons": dict(env.ghost_reject_reasons),
            "p_gate_mean": round(float(np.mean(p_gates)), 4), "p_gate_p90": round(float(np.percentile(p_gates, 90)), 4),
            "unmapped": sorted(unmapped), "obs_parity_raw_vs_list": parity,
            "deal_cache_hit": env.deal_cache_hit, "wall_s": round(wall, 1), "log": str(log_path)}


# ------------------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("deck")
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--port", type=int, default=37031)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--matches", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=REPO / "scratchpad" / "gauntlet" / "L64" / "engine_play")
    ap.add_argument("--decide-every", type=int, default=10, help="engine ticks between decisions (10 = 0.5 s)")
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--policy", choices=("model", "random"), default="model",
                    help="random = state-blind control: random hand card at a random own-half cell, p_random per decision")
    ap.add_argument("--p-random", type=float, default=0.093, help="random policy's play probability per decision")
    ap.add_argument("--gate", choices=("threshold", "sample", "none"), default="threshold",
                    help="none = no-plays control (model scored, never acts)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--pool", type=Path, default=None, help="default <deck data_dir>/ghost_pool/pool_env_v0.jsonl")
    ap.add_argument("--no-parity-check", action="store_true")
    a = ap.parse_args(argv)

    deck = load_deck(a.deck)
    model, minfo = load_model(a.ckpt, a.device)
    ee = _load_engine_env()
    # L64: default pool = the deck's own (deck.data_dir/ghost_pool/pool_env_v0.jsonl; for icebow that IS
    # engine_env.POOL_DEFAULT, so icebow behaviour is unchanged); fall back to POOL_DEFAULT if it does not exist.
    pool_path = a.pool or (deck.data_dir / "ghost_pool" / "pool_env_v0.jsonl")
    pool = ee.load_pool(pool_path) if Path(pool_path).exists() else ee.load_pool()
    env = RawEngineEnv(port=a.port, host=a.host, pool=pool, decision_ticks=a.decide_every, seed=a.seed)
    a.out.mkdir(parents=True, exist_ok=True)
    order = random.Random(a.seed).sample(range(len(pool)), len(pool))       # seeded, no repeats within a run
    rng = random.Random(a.seed + 1)
    print(json.dumps({"ckpt": str(a.ckpt), **minfo, "pool": len(pool), "port": a.port, "gate": a.gate, "tau": a.tau,
                      "decide_every": a.decide_every, "device": a.device, "policy": a.policy, "p_random": a.p_random}), flush=True)
    results = []
    try:
        for i in range(a.matches):
            entry = pool[order[i % len(pool)]]
            log_path = a.out / f"{entry['tag']}_m{i}.jsonl"
            r = play_match(env, model, deck, entry, decide_every=a.decide_every, tau=a.tau, gate=a.gate, rng=rng,
                           device=a.device, log_path=log_path, parity_check=not a.no_parity_check, policy=a.policy,
                           p_random=a.p_random)
            r["match"] = i
            results.append(r)
            print(json.dumps(r), flush=True)
    finally:
        env.close()
    n = max(len(results), 1)
    summ = {"SUMMARY": a.deck, "matches": len(results),
            "wins": sum(r["outcome"] == "win" for r in results), "draws": sum(r["outcome"] == "draw" for r in results),
            "losses": sum(r["outcome"] == "loss" for r in results),
            "crowns_for": sum(r["crowns_for"] for r in results), "crowns_against": sum(r["crowns_against"] for r in results),
            "plays": sum(r["plays"] for r in results), "accepted": sum(r["accepted"] for r in results),
            "refused": sum(r["refused"] for r in results),
            "plays_per_min": round(sum(r["plays"] for r in results) / max(sum(r["seconds"] for r in results) / 60.0, 1e-9), 2),
            "ghost_ok": sum(r["ghost_ok"] for r in results), "ghost_refused": sum(r["ghost_refused"] for r in results),
            "wall_s_per_match": round(sum(r["wall_s"] for r in results) / n, 1)}
    (a.out / f"summary_{a.deck}_s{a.seed}.json").write_text(json.dumps({"args": {k: str(v) for k, v in vars(a).items()},
                                                                        "model": minfo, "results": results,
                                                                        "summary": summ}, indent=1), encoding="utf-8")
    print(json.dumps(summ), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
