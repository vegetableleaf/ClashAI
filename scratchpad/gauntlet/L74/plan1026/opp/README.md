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

## STATUS (P2-OPP1, updated 2026-10-28 ~13:57 EDT pod clock; keep current)
Done + pushed: step 1 model / trainer options + tests (70cd720); live split frozen (0bc4874); slot re-drive, rows_to_npz,
level_a (3c1bcdd, 27988a7, + spool converter).
Running (pod 33308, root@157.157.221.29 -p 33308):
- slot re-drive `/workspace/opp/slot_bec5811a` (log `/workspace/opp/slot_bec5811a.log`, 241 shards = 60k HF replays,
  14 workers, nice 10). Restart (resumable per shard):
  `cd /workspace/opp && setsid nohup bash cb/scratchpad/gauntlet/L74/plan1026/opp/run_slot.sh /workspace/redrive/rd_lib_bec5811a /workspace/opp/slot_bec5811a --chunk 250 --limit 60000 --workers 14 > slot_bec5811a.log 2>&1 &`
- v0 rows `/workspace/opp/v0/hf_slot_v0.npz` (+ `_memory.npz`) from the shards finished at launch (log v0/rows_to_npz.log).
  Code copies: `/workspace/opp/cb` (driving, = pass-1 copy), `/workspace/opp/cbt` (training, git archive + opp/ + humanlike/).
  The 33308 container limit is 125 GB (others use ~80 GB): the in-memory converter was OOM-killed once; it now spools to disk.
Running: v0 pretrain on 33308 GPU1 (log /workspace/opp/v0/m10/train.log, curve v0/m10/curve_m10_s0.jsonl), data = the EXTRACTED dir
/workspace/opp/v0/hf_slot_v0 (6,754,230 rows, 36,727 replays from 168 shards; the 26.7 GB npz was deleted: disk hit 98%).
Restart (fresh; no mid-run resume): `bash cbt/.../opp/run_pretrain.sh /workspace/opp/v0/hf_slot_v0 /workspace/opp/v0/m10 m10 320 7 40000 1`
(11.2 M params, ~1.45k rows/s measured), then the level-A test file + level_a.py on HF split 2.
Not started (need their own tickets): live slot rows for opponent seats (step 3), SIM timing-head decoder + level B (step 4).
