# P6-MACRO: the macro library mined from human data (plan1026 PLAN P6)

Labels: (a) measured (number + source), (b) plausible, untested, (c) contradicted. Every lift here is an ASSOCIATION in
matched states, never a causal effect: humans choose a macro when it looks good, so a lift can be selection.

## STATUS (keep current)
- Code (this dir): `mine.py` (detectors + three source adapters -> episodes), `stats.py` (cell-matched lifts, cluster
  bootstrap, horizon, LIBRARY.json), `spec.json` (the fixed part of each entry: definition, start, prefix, window, default
  horizon), `live_index.py` (CLXIII live index, sealed block excluded), `epcheck.py` (sanity table), `rss_probe.py`
  (memory probe). Episodes are not committed (pod 33308 `/workspace/macros/ep/`; pro copy in `.foreman/scratch/p6macro/`).
- Pod 33308 `/workspace/macros` (code copy `cb/`, synced by tar from the laptop working tree): HF pass `hf_pass3.log`,
  pro pass `pro_pass3.log` (both relaunched 10-28 ~21:00 after the outcome change to princess-only margins). Memory: one
  HF worker peaks at 0.64 GB RSS (rss_probe, 4 shards), 8 workers on CPUs 64-71 = ~5 GB (lead budget 20 GB).
- Live: `live_index.py` caching 858 CLXIII logs (before the seal 20261028_090648; 108 sealed logs skipped) into
  `live_cache/` (laptop, nice 19, single process). Then `python -B mine.py live --out EP/live.jsonl.gz`.
- Codex: P6-MACRO_1 (low): verify the passes, run `stats.py --B 1000` on the pod, copy back (running).
- Restart: `cd /workspace/macros && PYTHONPATH=/workspace/redrive/pylib setsid nohup taskset -c 64-71 nice -n 5 python -B
  cb/scratchpad/gauntlet/L74/plan1026/macros/mine.py hf --rows /workspace/redrive/full_bec5811a/rows --hf
  /workspace/hf_il_replay/data --out /workspace/macros/ep/hf --workers 8 > hf_pass3b.log 2>&1 &` (skips finished files);
  pro: `cd cb && python -B scratchpad/gauntlet/L74/plan1026/macros/mine.py pro --out /workspace/macros/ep/pro.jsonl.gz`;
  stats: `python -B .../stats.py --ep /workspace/macros/ep --B 1000 --out-dir /workspace/macros`.

## Method
- Sources: (1) HF IL_Replay tier A after the crforge re-drive pass 1 (`/workspace/redrive/full_bec5811a`, crowns == HF):
  plays from the HF actions table, towers / own elixir / own hand from the re-drive rows of each side; both sides of a
  match are player-sides. (2) the icebow8 pro corpus (invlib.pro_matches: decisions + results real, frames = native
  re-drive). (3) CLXIII live (reader frames), the sealed block of `plan1026/opp/live_split.json` never read.
- Episode = one occurrence of a macro's start condition for one player-side; treated = the prefix played in its window.
- Lift = exact-stratification effect on the treated over cells (phase, crown diff, princess-HP margin band, own elixir
  band, opponent archetype, own archetype [, source] [, macro key]); 95% CI = Poisson bootstrap over matches.
- Outcomes: win, and the princess-HP margin change over 10 / 20 / 30 / 60 s / to the end (king HP excluded).
- Card costs / types: the native live card catalogue (hablib's CardDB lacks 91 of 118 HF cards; on pod 33308 it also
  returned x_bow -> 3.0 / None), patched in-process only.
