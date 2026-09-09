"""L67h: SimEngine -> obs_contract.BoardState, so the S1 student can act inside the RL sim.

Why this file exists: the rollout search that licenses distillation runs in `clashrl.sim` over the OLD CNN's
action space, while the student consumes `obs_contract` BoardStates built from the sandbox engine's
`observe()`. To ask "does search help the STUDENT" at all, the student first has to be able to act in the sim.

The conversion is nearly free because the sim already uses the CONTRACT'S board frame: sim team 0's princess
towers sit at y 0.797 and its king at 0.906, exactly where `obs_contract` puts MINE (verified in
`assert_frame()` below, which is run by the self-test). Nothing is mirrored for side 0.

What the sim gives that the LIVE path cannot: ground-truth unit HP, exact elixir, and the opponent's real
elixir. That is a PRIVILEGED view -- the same privileged-teacher gap the distillation spec warns about
(HANDOFF 6-PRIORITY-B) -- so `degrade_to_live=True` blanks the three fields the live student never has, and
any search result must say which view it was measured under.

self-test: python scratchpad/gauntlet/L67/sim_contract.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "icebow" / "src"))

from pipeline import vocab                                              # noqa: E402
from pipeline.obs_contract import BoardState, Deck, Tower, Unit, _phase  # noqa: E402

TOWER_ORDER_SIM = (2, 0, 1)          # sim towers[team] = [L princess, R princess, king]; contract wants K,L,R


def _cls_id(base: str) -> Optional[int]:
    try:
        return vocab.unit_id(str(base))
    except Exception:
        return None


def from_sim(env, deck: Deck, *, my_team: int = 0, degrade_to_live: bool = False) -> BoardState:
    """One SimMatchEnv step -> BoardState in MY frame. `my_team` 0 is the trainer's own side."""
    eng = env.eng
    units: list[Unit] = []
    spells: list[Unit] = []
    for u in eng.units:
        if u.hp <= 0:
            continue
        cid = _cls_id(u.spec.base)
        if cid is None:
            continue                                    # not in the vocab -> the student cannot name it
        hp = None if degrade_to_live else max(0.0, min(1.0, float(u.hp) / max(1e-6, float(u.spec.hp))))
        side = 0 if int(u.team) == int(my_team) else 1
        un = Unit(cid, side, float(u.x), float(u.y), (1.0 if (degrade_to_live and hp is None) else hp),
                  None, None, 1.0)
        (spells if vocab.is_spell(cid) else units).append(un)

    towers: list[Tower] = []
    for side_i, team in ((0, my_team), (1, 1 - my_team)):
        row = eng.towers[team]
        for slot, kind, lane in ((2, "king", None), (0, "princess", "left"), (1, "princess", "right")):
            t = row[slot]
            alive = float(t.hp) > 0.0
            frac = max(0.0, min(1.0, float(t.hp) / max(1e-6, float(t.max_hp)))) if alive else 0.0
            towers.append(Tower(side_i, kind, lane, frac, alive))

    t_sec = float(getattr(eng, "t", 0.0) or 0.0)
    dbl, ot = _phase(t_sec)
    hand = [deck.card_id_of(_base_of(env, c)) for c in list(env._hand_ids())[:4]]
    while len(hand) < 4:
        hand.append(-1)
    nxt = env._queue_ids()
    my_el = float(eng.elixir[int(my_team)])
    opp_el = None if degrade_to_live else float(eng.elixir[1 - int(my_team)])
    return BoardState(source="engine", t_sec=t_sec, t_source="engine", double_elixir=dbl, overtime=ot,
                      my_elixir=(float(int(my_el)) if degrade_to_live else my_el),
                      my_elixir_exact=(not degrade_to_live), opp_elixir=opp_el,
                      my_hand=tuple(hand),                                    # type: ignore[arg-type]
                      my_next=deck.card_id_of(_base_of(env, nxt[0]) if nxt else None),
                      towers=tuple(towers), units=tuple(units), spells=tuple(spells), deck=deck.card_ids)


def _base_of(env, card_id) -> Optional[str]:
    if card_id is None or int(card_id) < 0:
        return None
    keys = list(getattr(env, "deck_keys", []) or [])
    return str(keys[int(card_id)]) if int(card_id) < len(keys) else None


def assert_frame(env) -> None:
    """The whole conversion rests on the sim sharing the contract's board frame. Check it, loudly."""
    a = env.eng._anchors
    assert abs(a[0][0][1] - 0.797) < 1e-3 and abs(a[0][2][1] - 0.906) < 1e-3, f"my towers moved: {a[0]}"
    assert abs(a[1][0][1] - 0.203) < 1e-3 and abs(a[1][2][1] - 0.094) < 1e-3, f"enemy towers moved: {a[1]}"


def _selftest() -> int:
    from clashrl.config import Config
    from clashrl.sim.env import SimMatchEnv
    from pipeline.obs_contract import load_deck, to_tokens

    cfg = Config.load()
    env = SimMatchEnv(cfg, seed=7)
    env.reset()
    assert_frame(env)
    deck = load_deck("icebow")
    bs = from_sim(env, deck)
    tok, mask, sc = to_tokens(bs)
    ty = [round(t.hp_frac if t.hp_frac is not None else -1, 3) for t in bs.towers]
    print(f"units {len(bs.units)} spells {len(bs.spells)} hand {bs.my_hand} next {bs.my_next}")
    print(f"my_elixir {bs.my_elixir} exact {bs.my_elixir_exact} opp {bs.opp_elixir} tower hp {ty}")
    print(f"tokens {tok.shape} scalars {sc.shape} mask sum {int(mask.sum())}")
    assert len(bs.towers) == 6 and bs.towers[0].kind == "king" and bs.towers[0].side == 0
    assert all(h >= 0 for h in bs.my_hand), f"hand did not map to deck slots: {bs.my_hand}"
    bl = from_sim(env, deck, degrade_to_live=True)
    assert bl.opp_elixir is None and bl.my_elixir_exact is False
    print("degraded view: opp_elixir None, my_elixir_exact False -- OK")
    print("SELFTEST PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
