"""Live memory-reader frame -> BoardState, via the engine adapter (L68 live reader).

The reader (upstream cr-native-sandbox ``mumu_live_private_sampler.c --unified``, re-mapped for the x86_64
libg build: manager RVA 0x1aeef98, manager->context 0x18) emits one JSON frame per sample with the SAME native
fields the sandbox engine's ``observe()`` has, so the frame is reshaped into that dict and handed to
``obs_contract.from_engine`` (which mirrors when ``my_side == 1``; in Training Camp the human is side 1).

Owner rule: NO opponent-side private info reaches the model. Only MY player block is passed on; the opponent's
hand / next / elixir are never read from the frame, and ``opp_elixir`` is forced to None (the model's
``opp_known = 0`` channel). Board units and tower HP are public (on screen) and are kept.
Not in the reader's verified contract, so absent here: spells/effects, projectiles, ability state.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from . import vocab
from .obs_contract import REPO, BoardState, Deck, _catalog_names, from_engine

KING_KIND, PRINCESS_KIND = 12, 13   # crown towers carry card_id -1 (probe1.jsonl: kings kind 12, princesses 13)


def my_side_of(frame: Mapping[str, Any]) -> int:
    """The side whose hand is visible (the other side's hand reads -1s in a live battle)."""
    vis = [int(p["side"]) for p in frame["players"] if any(i >= 0 for i in p["hand_deck_indices"])]
    if len(vis) != 1:
        raise ValueError(f"expected exactly one side with a visible hand, got {vis}")
    return vis[0]


def deck_of(frame: Mapping[str, Any], my_side: int) -> tuple[Deck, list[str]]:
    """(Deck of vocab keys, the 8 engine display names in the game's deck order) for my side."""
    me = next(p for p in frame["players"] if int(p["side"]) == my_side)
    names = [_catalog_names()[int(c)] for c in me["deck_card_ids"]]
    keys = tuple(vocab.engine_key(n) or n for n in names)
    deck = Deck(name="live", cards=keys, card_ids=tuple(vocab.unit_id(k) for k in keys),
                config=REPO, src_dir=REPO, crawl_dir=REPO, data_dir=REPO)
    return deck, names


def to_observe(frame: Mapping[str, Any], my_side: int, names: list[str]) -> dict:
    """Reader frame -> the raw engine ``observe()`` shape ``from_engine`` accepts. My player only."""
    me = next(p for p in frame["players"] if int(p["side"]) == my_side)
    hand = [{"hand_index": i, "name": names[d]} for i, d in enumerate(me["hand_deck_indices"]) if d >= 0]
    player = {"side": my_side, "elixir_exact": me["elixir_raw"] / 10000.0, "hand": hand,
              "next_deck_index": me["next_deck_index"]}
    towers, ents = [], []
    for e in frame["entities"]:
        if int(e["card_id"]) < 0:
            if e["kind"] in (KING_KIND, PRINCESS_KIND):
                towers.append({"side": e["side"], "type": "king" if e["kind"] == KING_KIND else "princess",
                               "x": e["x"], "y": e["y"], "hp": e["hp"], "max_hp": e["max_hp"]})
            continue
        name = _catalog_names().get(int(e["card_id"]), str(e["card_id"]))
        ents.append({"side": e["side"], "x": e["x"], "y": e["y"], "name": name, "card_id": e["card_id"],
                     "hp": e["hp"], "max_hp": e["max_hp"], "kind": e["kind"], "entity_id": e["address"]})
    return {"tick": frame["game_tick"], "players": [player], "entities": ents,
            "episode": {"crown_towers": towers}}


def board_state(frame: Mapping[str, Any], *, history: Optional[dict] = None,
                unmapped: Optional[set] = None) -> BoardState:
    if not frame.get("battle_active"):
        raise ValueError(f"frame not active: {frame.get('failure')}")
    side = my_side_of(frame)
    deck, names = deck_of(frame, side)
    bs = from_engine(to_observe(frame, side, names), side, deck, history=history, engine_deck=names,
                     unmapped=set() if unmapped is None else unmapped)
    return replace(bs, source="live_mem", opp_elixir=None)
