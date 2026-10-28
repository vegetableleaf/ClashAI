# P2-OPP1: human-like opponent v0 (plan1026 Pillar 2) -- how to re-run

Code: `pipeline/model_gen.py` (GenModel options `timing`, `ability`, `deck_enc` + `n_decks`, `ctx_tokens`; `slot_nll`;
`DeckEncoder`; `add_memory(zero_init=False)`), `pipeline/train_gen.py` (`--opp-*`, `--memory`, `--init` -> `main_opp`).
Tests: `pipeline/tests/test_opp_model.py` (incl. the 8010d5a legacy fingerprint, `opp_identity.py`).

Re-run after a new crforge build (D1 / D2), pod 33308:
```bash
# 0. code copies: /workspace/opp/cb = the re-drive's code copy (driving), /workspace/opp/cbt = git archive of HEAD (training)
# 1. slot-row re-drive (wait_stride 10, play_window 0) + sidecars + memory tables; resumable per shard
bash cb/scratchpad/gauntlet/L74/plan1026/opp/run_slot.sh LIBDIR /workspace/opp/slot_NEW --chunk 250 --limit N --workers W
python cbt/.../opp/check_slot.py /workspace/opp/slot_NEW 5            # invariants: play_dt == wait_dt, grid holes, events
# 2. rows: training file (no-play slots 1/8, weight 8) and the level-A file (every slot, test split, same deck ids)
python cbt/.../opp/rows_to_npz.py --src slot_NEW --vocab cbt/.../opp/vocab_hf.json --hf-replays /workspace/hf_il_replay/data/replays --out hf_slot_NEW.npz
python cbt/.../opp/rows_to_npz.py --src slot_NEW --vocab ... --hf-replays ... --out hf_slot_NEW_test.npz --keep-wait 1 --only-split 2 --deck-map hf_slot_NEW.npz
# 3. pretrain (all heads + joint memory v2); curve_<tag>_s0.jsonl = held-out NLL every 2,500 steps
bash cbt/.../opp/run_pretrain.sh hf_slot_NEW.npz runs/NAME NAME 320 7 STEPS GPU
# 4. level A (THRESHOLDS.json v3, sha-checked)
python cbt/.../opp/level_a.py selftest
python cbt/.../opp/level_a.py --ckpt runs/NAME/opp_NAME_s0.pt --data hf_slot_NEW_test.npz --memory-tables hf_slot_NEW_test_memory.npz --split 2 --out A.json
```
Live split: `live_split.json` (frozen 2026-10-28 09:06 EDT, never rewritten; sealed = every log from 20261028_090648).
