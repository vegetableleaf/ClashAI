

### §5cs.25 -- c2r STOPPED ON OWNER ORDER at 36,375 eps (2026-09-04 18:18, L55); the live "Tesla in one tile" behaviour IS the sim policy: `policy_rl.pt` is byte-identical to `policy_c2r_20260903_best.pt` (max |diff| 0.0 on model and gate), and in the SIM the same greedy rule puts Tesla at cell 234 (row 13, col 0 -- the far-left riverside corner) in 52/82 = 63% of its Tesla plays over 3 seeds, X-Bow there in 21/34 = 62%, Skeletons at cell 423 (in front of the king) in 153/154. Live (36 matches, 09-03/09-04): Tesla at cell 235 in 39/101, X-Bow 63/85 -- the same corner, one column over. Learned in the sim, not a live-path artifact. The oscillation is real and its instruments are recorded; its cause is (b)

**Owner (18:2x):** "Stop the PPO. it's just oscillating at this point, which is another problem. Why is it oscillating
instead of improving? also, during live training the model literally places tesla in one tile and one tile only
[...] did it learn this atrocious behavior from the sim? are you telling me it achieved 30% winrate in-sim with such
a stupid strategy?"

**Stop (per §7).** Endpoint: log line `36375 episodes: winrate= 12% ... 3359W-25310L-11D`, 18:18:07. `_best.pt` =
EVAL@36000 ladder avg-5 31% (best_wr 30.67 in the state dict, matches 36000); backed up byte-for-byte to
`data/bench/c2r_best_36k_backup.pt` (cmp ok). Before: 17 python procs (1 Nucleo uvicorn 63608, c2r tree 58128 ->
30584 -> 12 spawn workers, watchdog 56376 -> 73368). `taskkill /T /F` on 58128 and 56376 from PowerShell: 16
terminated. After: 1 python proc (63608, Nucleo, untouched). Free RAM 4.2 -> 6.8 GB. Snapshots kept:
`data/bench/c2r_m30k.pt`, `c2r_m35k.pt`, `c2r_best_36k_backup.pt`.

**(a) measured -- the Tesla question.**
- Live play_logs (`data/reward_stats/live_20260903_*.jsonl`, `live_20260904_*.jsonl`; 36 matches, 34 L / 1 W /
  1 unknown): tesla n=101, 25 distinct cells, cell 235 x39, cell 374 x20; x_bow n=85, 12 distinct, cell 235 x63;
  tesla_evo 19, cell 235 x12; tornado 44, cell 235 x10; skeletons 124, cell 423 x26; knight 101, cell 341 x25;
  ice_wizard 123, cell 374 x24. First play of the match: x_bow@235 x11, tesla@235 x3, knight@341 x4,
  skeletons@423 x3. Cell = row*18 + col on the 18x24 action grid; 235 = row 13, col 1 = the leftmost playable
  column, 1-2 tiles behind the river.
- `data/policy_rl.pt` (what play.py auto-prefers) vs `policy_c2r_20260903_best.pt`: max |diff| 0.0 on `model` and
  `gate`. The live policy IS c2r_best. (`policy_rl_prev.pt` differs by 0.67 -- an earlier session's weights.)
- Sim placement probe `scratchpad/gauntlet/L55/place_probe.py` (same env setup as gate_prior_probe: 6 envs, seeds
  4242+i, 400 steps; greedy card + greedy cell from the chosen card's own map, own-half mask, gate sampled --
  play.py's rule at lines 582/634), c2r_best, seeds 0/1/2: tesla -> cell 234 in 14/24, 18/30, 20/28 (63%; the rest
  spread over 219/246/230/216 -- all row 12-13 left side); x_bow -> 234 in 9/13, 8/11, 4/10 (62%); tesla_evo ->
  234 in 7/9, 6/8, 6/10; tornado -> 234 10/23; ice_wizard -> 234 21/47 or 219; skeletons -> 423 in 53/53, 50/51,
  50/50; knight -> 426 (row 23, col 12) 19/39, 16/39, 25/39; the_log -> 219 (row 12, col 3) 21/44. Cell 234 =
  row 13, col 0. Live 235 = row 13, col 1: same spot, one column over (the live path clamps/snaps; the exact
  step that moves col 0 -> 1 is untested). First sim play of a match: tesla@234 is the modal first play on seeds
  1 and 2 (4/10, 3/10), knight@426 on seed 0.
- Cell-head spread (ppo_watchdog, `cell_struct`): 3350-5235x an untrained net, within-card entropy 0.65-0.81 of
  5.08 max, 23-27 distinct greedy cells across the deck. The head has learned ONE cell per card, hard.
- So: the corner Tesla is learned in the sim, deployed unchanged, and the same checkpoint's numbers are: ladder
  (scripted meta bots, opponent levels 13-16) avg-5 31% at 36k; fair (equal L15) 21%; training winrate vs the
  training opponent 8.9% (32-36k window); live 1/35. Yes -- the 30% was achieved with this placement policy,
  against scripted bots. It is not evidence the placement is good; it is evidence the scripted bots do not
  punish it.

**(a) measured -- the oscillation question (instruments only, from the run log).**
- >=6 share by checkpoint (gate probe, 3-6 seeds): m5k 3.9 -> m10k 5.5 -> m20k 1.2 -> m30k 3.3 -> m35k 1.3.
- Every other series flat 8k-36k: ladder avg-5 28-31, fair 19-21, per-4k training winrate 10.2/9.7/8.9%, drill
  pass-all 45-47%, policy entropy 0.05-0.08, clip 0.03, pl +0.00x.
- Gate-update diagnostic printed by the trainer (930 samples over the run): "gate drift on PLAY" is NEGATIVE in
  every sampled batch (-0.05 to -0.95) with n_play 5-20 per batch vs n_wait 188-377; drift on WAIT -0.0001 to
  -0.008. The gate's play logit is pushed down every batch from a handful of play samples.
- Match steps with an affordable card: 14.2%; P(play) given a choice 0.168; behaviour P(play) 0.030 vs
  sampled-play 0.024 (last block).

**(b) plausible, untested -- why it oscillates instead of improving.** Entropy 0.06 and a one-cell-per-card cell
head mean PPO has almost nothing to explore with: the policy is at a fixed point of its own data (it only ever sees
the outcomes of its own corner-Tesla/king-Skeletons plays), and the only head still moving is the gate, whose
update comes from 5-20 play samples per batch -- a noisy signal that drifts the spend/hold balance back and forth
without any card/cell change behind it. That fits every number above but none of them proves it. The measurement
that would: one arm with a higher entropy coefficient (or a placement-exploration schedule) from c2r_best, same
config otherwise, read by the placement probe (distinct cells per card, tesla@234 share) and the gate probe at
m5k/m10k. That is a training change -> one experiment, box now free.

**(b) plausible, untested -- why the sim rewards a riverside-corner Tesla.** Cell 234 is 1-2 tiles behind the
river at the left edge: in range of the left bridge, out of the enemy princess tower's range, and the scripted
bots (L52: they push lanes open-loop) may simply walk their left-lane pushes past/into it while never Rocketing
or lane-switching against it. Untested. Measurement: a Tesla-outcome probe (adapt `tools/xbow_probe.py`: damage
dealt / damage taken / lifetime / pulls) for a forced Tesla at 234 vs a centre cell (e.g. row 17, col 8) over the
same seeds, plus the scripted bots' lane split. If the corner Tesla out-earns the centre one in the sim, that is a
sim-vs-live gap with a name; if it does not, the head is stuck on it for a different reason (b).

**(c) contradicted.** "It is a train-rl epsilon issue" (owner's own ruling-out, now measured): the greedy sim
probe with NO exploration reproduces the corner Tesla on 3 seeds, and the deployed file is the sim checkpoint
unchanged.

**What this changes.** The placement head is the first thing to fix, ahead of the oracle work: a policy that
puts every building in one corner and every Skeletons in front of the king cannot be evaluated against the real
game in any useful way, whatever the sim's mechanics say. Queue (§6): (1) Tesla-outcome probe in the sim (cheap,
~15 min, decides whether the sim itself rewards the corner); (2) the entropy/exploration arm from c2r_best (one
change); (3) then oracle step 2. The live-path column shift (234 -> 235) is a separate, small parity question.

**Traps found.** (1) `policy_rl.pt` carries no lineage field (`explore_step` only); identity has to be checked by
weight diff, and it was 0.0 -- assume the deployed policy is the last sim checkpoint until the diff says otherwise.
(2) `PolicyNet.forward_parts` returns cell logits of shape (B, n_cards, n_cells): argmax over dim 1 is a card
index, not a cell; take `cells[i, card]` first (play.py 618). (3) A 30% ladder number is against scripted bots
with no punishment for out-of-position buildings; it says nothing about placement quality.
