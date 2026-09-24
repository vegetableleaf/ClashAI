# Generalist (multi-deck) S1 -- plan (lead, 2026-09-24)

Owner rulings 2026-09-24: build a generalist that can pilot many decks (action head scores the 4 cards IN HAND by
card identity, deck = 8 cards); IL from the HF IL_Replay set (= FirstLight 252k, local
`scratchpad/gauntlet/L67/hf/replays`); first slice = top-100 decks, then top-1,000 if results are good; scope = "strong
on the top ~1,000 decks, rough elsewhere"; later multi-deck self-play in RoyaleSim (frozen generalist opponent first).

## Measured facts (HANDOFF §BT, L68/generalist/deck_census.json, scout report)
- 47,800 base decks; top 100 = 41.4% of sides, top 1,000 = 73.7%; rank-1,000 deck has 58 games, rank-5,000 has 6.
- Pilot slice: top-100 decks capped at 200 games each = 20,000 deck-sides from 17,857 replays (~5 VM-h).
- tools/hf_to_crawl.py already takes a deck param (one yaml per call); replay_batch/replay_drive `--crawl` drives ANY
  deck, BOTH sides. Sandbox gap: `card has no native evolution form` failed 163/766 icebow replays (§5cs.96).
- Deck-locked today: dataset.py `deck_sides` (rows only for one 8-card deck), labels `y_slot` 0-7; to_tokens sc
  `hand_slot_onehot_4x9` / `next_slot_onehot_9` over DECK SLOTS; model_v3 card_head/wait_head/card_emb/past_slot/
  hand_mask_from_sc (N_SLOTS=8). Board UNIT tokens already use vocab ids (deck-agnostic).
- Free starter data, no VM: the already-driven corpora hold full board states for BOTH sides:
  corpus_v6/icebow 2,241 replays, corpus_v6/hogeq 1,162 -> ~3,400 opponent sides of arbitrary decks + our sides.

## Design
Card vocabulary: base card keys (RoyaleAPI slugs, forms stripped) + a form id (base / evo / hero) per card slot.
Row = one decision of one side (play or wait), same board tokens and scalar features as S1 EXCEPT the hand/next deck-slot
one-hots are replaced by identity arrays: `hand_card[4]`, `hand_form[4]`, `next_card`, `deck_card[8]`, `deck_form[8]`
(pad id for unknown/empty). Labels: `y_card` (card id of the played card), `y_hand_pos` (0-3), `y_xy`, `y_gate`,
`y_wait_card`, `y_wait_dt`, past plays as card ids. Keep every S1 convention and trap fix: lattice grid labels
(§5cs.70), i=1 rotation (§5cs.67), `--record-every 20` wait frames (§5cs.69), compact-row parity (no row-TYPE leak,
§5cs.61), split by replay tag (and hold out whole OPPONENT groups like pool v1 where feasible).
Model (`model_gen.py`): S1 trunk unchanged (unit/patch/global tokens, same d/layers) + card-identity embeddings for hand,
next, deck and past; card head = pointer over the 4 hand cards (dot of global state with each hand card's embedding),
masked to cards actually in hand; cell head query conditioned on the CARD IDENTITY embedding (not a slot); wait head =
pointer over the 8 deck cards; gate and value heads as S1.
Gates: (1) on the icebow v3 VAL rows (same replays/sides as s1_dataset.npz split==1, converted) the generalist's exact
cell / card top-1 vs v6aug_s1's 0.2073 / 0.6394 -- report, and per-deck agreement vs games-per-deck; (2) later,
RoyaleSim held-out winrate as icebow.

## Order
G2 dataset builder on the EXISTING corpora (now) -> G3 model + trainer + icebow eval (after G2 accepted) -> G1 VM pilot
drive of the top-100 slice (when ssh works) -> G4 retrain on starter + pilot data -> self-play env (policy vs policy).
