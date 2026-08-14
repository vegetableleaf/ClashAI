"""The WIN-CONDITION BANK rule, in ONE place.

Why this is a module and not three copies: the card mask has to be identical in the
PPO rollout, the greedy benchmark and any offline measurement, or the numbers stop
describing the same policy. This codebase has already paid for that kind of drift
once -- the gate rule diverged between trainer and benchmark and cost ~33pp before
anyone noticed the benchmark was reading a PPO gate with the DDQN rule.

The rule: while a win condition (X-Bow / Rocket) is IN HAND and the bar has reached
``bank_floor`` but is still short of that card's cost, the cheaper cards -- the ones
that would drain the bar back down -- are masked out. Nothing is playable, so the
step becomes a forced wait, the bar climbs, and the win condition becomes SAMPLABLE.

This is a reachability fix, not a preference nudge. A masked action receives zero
policy gradient, and on the collapsed checkpoint X-Bow/Rocket sat in hand on 99.4%
of steps while affordable on 0.00% of them -- so no reward weight on the win
condition could ever fire, however large.

It is a pure function of (hand, elixir), the two inputs a rollout already stores, so
the sampling-time and update-time masks are identical and the PPO likelihood ratio
stays exact.
"""
from __future__ import annotations


def apply_wincon_bank(playable, elixir, card_costs, wincon_hand, wincon_cost, bank_floor):
    """Mask the cards that would drain the bar below a held win condition's cost.

    ``playable``    [B, C] bool  -- the in-hand AND affordable mask, modified copy returned
    ``elixir``      [B]   float  -- elixir in CARD units (0-10), not the normalised vector
    ``card_costs``  [C]   float  -- per-card elixir cost
    ``wincon_hand`` [B]   bool   -- is a win condition in hand this step
    ``wincon_cost`` float        -- the cheapest win condition's cost
    ``bank_floor``  float        -- start banking at this much elixir (0 disables the rule)

    Returns ``playable`` unchanged when the rule is off or nothing is being banked for.
    """
    if bank_floor <= 0.0 or wincon_cost <= 0.0:
        return playable
    banking = wincon_hand & (elixir >= bank_floor) & (elixir < wincon_cost)
    drains = card_costs.view(1, -1) < wincon_cost
    return playable & ~(banking.view(-1, 1) & drains)
