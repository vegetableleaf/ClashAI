# hogeq live-path port plan (L67m prep — NOT executed)

Owner ruling 2026-09-10: port the S1 student stack to hogeq **after** the hogeq corpus work. The corpus drive is
parked until a long idle session (3.9 GB free vs a 4 GB engine AVD), so this is preparation only. No file under
`hogeq/src` has been edited.

## Why a port and not a flag

- `pipeline/` is shared by both decks (contract, dataset, trainer, deck aliases). Nothing to port there.
- The **live path is a fork**: `hogeq/src/clashrl` is a 68-file copy. `Config.load()` derives `root` from the
  module's own location (`parents[2]`), so `icebow/run.py --config hogeq/config/config.yaml` still resolves
  cards, templates and data under `icebow/` — measured: it loaded icebow's 10 deck identities.
- hogeq's tree has **no `student_live.py`** and no `--student` flag, so today it cannot load an S1 checkpoint.
- Last sync: `d0bbe1d` (5cs.18) — "12 shared files byte-copied, 7 declared-different files hand-ported,
  parity strict OK both decks, hogeq suite 1,322 OK". Follow the same discipline.

## Inventory: `icebow/src/clashrl` since d0bbe1d (15 files, +1,686 / −35)

### A. Needed for the live student — port these

| file | icebow Δ | what it carries | method |
|---|---|---|---|
| `student_live.py` | new, 336 | StudentPolicy, HandMemory (30 s TTL + invalidate), anti-stall, affordability mask, low-gate capture, state digest | **byte-copy** (deck-agnostic; takes the deck name) |
| `play.py` | +147 | student construction + decide + WAIT/PLAY logging + record_play, gate/search bypass, `student_opp_elixir` default off, HandMemory wiring (model view only), tower latch paused in grace hold, `reset_match`, barrel landing aim, overlay `end_match` | **hand-port** — hogeq's play.py already differs by 306 lines of its own deck logic |
| `cli.py` | +33 | `--student`, `--student-gate-tau`, `--student-deck` (plus sim-view `--radii`, gate_rule use — see B) | hand-port the `play` hunk only |
| `detect.py` | +26 | `keep_clips` folder retention, `end_match` path | hand-port hunk (whole-file diff vs hogeq is large) |
| `opponent_elixir.py` | +19 | re-baseline on saturation, `_rebase` counter | hand-port hunk |
| `reward.py` | +41 | `SPAWN_SPELL_BASES`, `spawn_spell_landing` | hand-port hunk |
| `hogeq/config/config.yaml` | — | document `play.student_opp_elixir`, `stall_elixir`, `stall_seconds`, `barrel_landing_aim`, `overlay_replay.keep_clips` | optional: code defaults already apply |

### B. Training / sim side since the sync — NOT needed for live student play; decide separately, do not bundle

`gate_rule.py` (new), `geometry_reward.py` (new, 716), `train_sim_ppo.py` (+47), `sim/env.py` (+134),
`sim/remote_pool.py` (+42), `sim_view.py` (+114), `policy_stats.py`, `model.py` (CNN `cell_bias_map`),
`config.py` (`Config.source` for rollout workers).

## hogeq-specific checks after the port

1. Inside hogeq's own tree, `Vision(cfg).deck_keys` must list hogeq's cards (not icebow's) and its own
   `hand_slots` (0.308 / 0.485 / 0.660 / 0.854 — differs from icebow's calibration).
2. `mine_classes(load_deck("hogeq"))` = {earthquake, firecracker, hog_rider, ice_spirit, mighty_miner,
   skeletons, tesla, the_log} — already verified; evo fold resolves firecracker_evo → 43, tesla_evo → 1.
3. The cannon alias is harmless live (my hand never holds a cannon; unit tokens never pass through slot_of).
4. HandMemory matters more for hogeq: two evolutions + a champion, and a faster cycle (more dimmed frames).
5. **Mighty Miner's ability is out of scope** — it is wired nowhere (play.py ignores `hand.ability_button`,
   env.py reads a `vision.ability_key` that does not exist, `N_SLOTS = 8`, drives skip ability presses).
   A separate feature, not part of this port.

## Verification before telling the owner it runs

- hogeq test suite (1,322 OK at the last sync) + pipeline contract tests (23/23).
- Parity: shared byte-copied files identical between trees.
- Offline dry-run of the student on a hogeq session video (no clicks) — confirm hogeq sessions exist first.
- Only then a live command, with the checkpoint chosen from the v6lat grade (or v5lat if v6 is not better on
  the same v3 VAL instrument).
