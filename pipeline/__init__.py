"""Deck-agnostic observation pipeline shared by icebow and hogeq (S0 step 2, L63).

Nothing here imports either deck's ``clashrl`` copy at module load; ``obs_contract.from_live`` pulls
``BoardWarp`` from ``icebow/src/clashrl/actions.py`` lazily (the deck yaml names the src dir).
"""
