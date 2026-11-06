"""Checkpoint loading and board geometry shared by the trainer and the evaluators."""
from __future__ import annotations

import time
from pathlib import Path

from pipeline.model_v3 import S1Model, cell_xy
from pipeline.obs_contract import ENGINE_X, ENGINE_Y

RESULT_CODE_NAMES = {0: "accepted", 9: "card_not_in_hand", 13: "not_enough_elixir_13", 22: "rejected", 1014: "ability_exhausted",
                     1050: "not_enough_elixir"}
_ENT_KEYS = ("side", "x", "y", "name", "hp", "max_hp", "card_id")


def cell_center(cell: int, grid: str = "floor") -> tuple[float, float]:
    """Inverse of the checkpoint's label convention (``model_v3.cell_xy``): board-frame (x, y) in [0, 1]."""
    return cell_xy(cell, grid)


def board_to_engine(x: float, y: float, mirror: bool) -> tuple[float, float]:
    """Exact algebraic inverse of ``obs_contract._engine_xy`` (board frame, me at the bottom -> engine units)."""
    X = x * ENGINE_X
    Y = (1.0 - y) * ENGINE_Y
    if mirror:
        X, Y = ENGINE_X - X, ENGINE_Y - Y
    return X, Y


def cell_to_engine(cell: int, mirror: bool, grid: str = "floor") -> tuple[int, int]:
    x, y = cell_center(cell, grid)
    X, Y = board_to_engine(x, y, mirror)
    return int(round(X)), int(round(Y))


def compact_raw(state: dict) -> dict:
    """The state dict reduced to what ``dataset._as_compact`` leaves a PLAY row: entities with no ``kind``, no effects /
    projectiles. Still the dict shape, so ``from_engine`` takes its raw branch."""
    return {"tick": int(state["tick"]),
            "players": state.get("players", []),
            "entities": [{k: e[k] for k in _ENT_KEYS if k in e} for e in state.get("entities", [])],
            "episode": {"crown_towers": (state.get("episode") or {}).get("crown_towers", [])}}


def load_model(ckpt: Path, device: str, retries: int = 5):
    import torch
    last = None
    for _ in range(retries):
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
                   "grid": args.get("grid", "floor"),
                   "val_cell_tile_top1": (ck.get("val") or {}).get("cell_tile_top1")}


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
