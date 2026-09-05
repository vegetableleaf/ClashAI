> # !! READ FIRST -- THE PAIR IS NOT RUNNING !!
> **The engine is down, and it is not something I was allowed to fix.** At 15:16 local on 2026-09-05 the
> VM (qemu PID 54304) was up but BOTH in-guest worker services were dead --
> `native_core.worker status` -> `{"vm_ready": true, "services": [false, false]}` -- so every trainer
> start dies on its first `env.reset()` with `WinError 10054`. This CONTRADICTS the brief's premise that
> "the VM and its worker service are UP and idle". The one recovery command
> (`native_core.worker start --workers 2 --base-port 37031`, the author's own `_boot.ps1` line) was
> attempted once and **denied by the harness permission classifier**, so it was never executed.
>
> Consequently: **engB was NOT launched. There are no PIDs and no m30-50 gate readouts.**
> `engB_launch.ps1` is written, checked, and refuses to start until both slots answer.
>
> Everything that does NOT need the engine IS done and measured: the gate prior is implemented and
> unit-checked (27/27), it is proven byte-for-byte inert at coef 0.0 against the exact file engA ran,
> the new collapse readouts are in the update line, the m0 checkpoint reproduces the init exactly
> (v1 15.44/46.61, v2 15.00/43.51), and a sim-driven smoke runs the patched `update()` for 6 updates
> with no NaN. Sections 4, 6.1 and 6.2 carry three findings the brief did not have.

# L62 -- engine_ppo v2: the GATE PRIOR added, engB pair relaunched
Written incrementally, 2026-09-05. Every claim labelled (a) measured on this box / (b) plausible-untested /
(c) contradicted. Predecessor: engine_ppo.md (engA, killed at m=422 on a collapsed play gate).

## 0. Inputs read (not re-derived)
- (a) `icebow/src/clashrl/train_sim_ppo.py` l.340-385 (gate-prior setup + the semantics comment), l.1322-1339
  (`_gpr`: how the prior row is keyed per rollout row), l.1758-1772 (the loss term + its stat block).
- (a) `icebow/config/gate_prior.json`: schema 1, side blue, dt 0.6, regulation_s 180.0, overtime_s 120.0,
  519 replays / 23620 plays. `p_play[phase][elixir bucket 0..10]`:
  - single `[0.0100, 0.0244, 0.0415, 0.0626, 0.0580, 0.0418, 0.0420, 0.0426, 0.0828, 0.2033, 0.1838]`
  - double `[0.0094, 0.0372, 0.0624, 0.1028, 0.1165, 0.1099, 0.1320, 0.1609, 0.2673, 0.4463, 0.3421]`
  - triple `[0.0211, 0.0487, 0.0907, 0.1568, 0.1793, 0.1901, 0.2413, 0.2771, 0.3518, 0.4587, 0.3161]`
- (a) `scratchpad/gauntlet/L62/engine_ppo.py` (520 lines, the file being edited), `engine_ppo.md` s2/s2.1
  (s2.1 records "NOT used (doctrine/scaffold) ... gate prior coef 2.0"), `engine_env.py`, `gate_probe.py`,
  `engA_launch.ps1`.

## 1. Box + prerequisites at start (MEASURED)
- (a) Free RAM 7980 MB (`\Memory\Available MBytes`) before any launch.
- (a) qemu-system-x86_64-headless PID 54304 ALIVE (WS 434 MB). Not restarted, not touched.
- (a) The killed engA workers are gone: `engA_pids.json` = ctrl 51956 / kl 32284, neither exists.
  Live pythons are only the crawler PIDs 29444 + 53824 and the owner's uvicorn 63608 -- all left alone.
- (a) No `engB_*` file exists anywhere under `scratchpad/gauntlet/L62/` or `icebow/data/bench/` (checked
  before writing anything).
- (a) `diff engine_ppo_launched_20260905.py engine_ppo.py` = ONE hunk: the `--kl_in_warmup` flag (default 1)
  and its use in the warm-up branch. The engA log header's config JSON has NO `kl_in_warmup` key, i.e. engA
  ran the pre-flag file => engA's warm-up behaviour == `--kl_in_warmup 0`. engB therefore passes
  `--kl_in_warmup 0` explicitly to match. (a)

## 2. What I changed in `scratchpad/gauntlet/L62/engine_ppo.py` (v2)
17 exact-string edits, 521 -> 627 lines. Nothing else in the file moved. Diff summary:

| # | where | change |
| --- | --- | --- |
| 1 | module docstring | "no ... gate prior" -> the two optional loss terms, with engA's collapse numbers as the reason |
| 2 | imports | `TICK_S` added to the `engine_env` import (engine_env.py itself UNTOUCHED) |
| 3 | constants | `GATE_TAU = 0.25` (= sim.ppo_gate_threshold, the number gate_probe.py uses). MONITORING ONLY |
| 4 | `__init__` out_prefix guard | `icebow/data/bench/engA_*` -> `engA_*` OR `engB_*` |
| 5 | `__init__` | loads the prior table when `--gate_prior_coef > 0`; asserts schema 1 and shape (3, 11); derives the phase boundaries; builds `self.gprior_note` for the log |
| 6 | `save()` | the checkpoint's `engine_ppo` dict now also carries `gate_prior_coef` |
| 7 | new `Trainer.gp_target()` | the per-decision lookup (below) |
| 8 | `rollout()` | 3 new `B` keys: `gp` (prior target), `pg` (p(play)), `pgm` (row unmasked) |
| 9 | `rollout()` | `gp_row = self.gp_target()` taken BEFORE `env.step()` -- step advances tick AND elixir |
| 10 | `rollout()` | stores `gp`, `pg = sigmoid(g_play - g_wait)` on the RAW gate, `pgm = playable.any()` |
| 11 | `rollout()` | rollout-level `pg_mean` / `pg_p90` / `pg_gt_tau` / `pg_rows` over the unmasked rows |
| 12 | `update()` | `gp_f` target tensor (None when off) + a `gps` stat dict |
| 13 | `update()` | THE LOSS TERM (below), added after the warm-up branch |
| 14 | `update()` | `gp_ce` / `gp_target` / `gp_rows` outputs + an explicit non-finite guard when the prior is on |
| 15 | `run()` | one extra line: `[engine_ppo] GATE PRIOR <note>` |
| 16 | the per-update log line | new `| GATE ...` tail; EVERY existing field and name unchanged |
| 17 | CLI | `--gate_prior_coef` (default 0.0) and `--gate_prior_path` (default `icebow/config/gate_prior.json`) |

### 2.1 The loss term (semantics copied from train_sim_ppo.py)
```python
if gp_f is not None:
    gpk = (gq_m[:, 1] > _NEG * 0.5)          # rows where PLAY is not masked
    if bool(gpk.any()):
        gpt = gp_f[mb][gpk]
        gce = -(gpt * lp_g[gpk, 1] + (1.0 - gpt) * lp_g[gpk, 0])
        loss = loss + a.gate_prior_coef * gce.mean()
```
- (a) Identical in form to `train_sim_ppo.py` l.1758-1768. Bernoulli CE on the GATE head only; card and cell
  heads get no gradient from it (`lp_g` is `log_softmax(gq_m)`, and `gq_m` comes only from `self.net.gate`).
- (a) The excluded-row rule is the sim's, byte-for-byte: `gq_m[:, 1] > _NEG * 0.5`. The sim ALSO ANDs a
  drill mask (`gpm_f`, "match rows only"); engine_ppo has no drills, so every row is a match row and that
  conjunct is a no-op -- omitted deliberately, not forgotten.
- (a) It is added OUTSIDE the value-warmup branch, matching the sim, whose term at l.1758 sits after the
  warm-up split at l.1617-1627 (same treatment as its search CE and hazard CE: supervised, critic-independent).
- (a) `--gate_prior_coef 0.0` is OFF byte-for-byte: `self.gprior` stays None, the JSON is never read,
  `gp_f` is None, and the `if` never fires. `gp_target()` returns a constant 0.0 that nothing consumes.
- (a) schema 2 / `ppo_gate_prior_pressure_s` is NOT implemented; the loader asserts `schema == 1`.

### 2.2 tick -> phase and elixir -> bucket (STATE IT EXACTLY)
- ELIXIR (a): `env.sim.eng.elixir[0]` -- the ENGINE's own number. `EngineMatchEnv._frame_of` puts
  `players[side]["elixir_exact"]` into the frame (engine_env.py l.177-178); `frame_to_engine` copies it
  straight into `eng.elixir[0]` (L61/build_bc_v2.py l.155-157); `sim/env.py` l.621 sets
  `elixir_vec[0] = eng.elixir[0] / 10.0` with no clamp. So `elixir_vec[0] * 10` and the engine value are
  THE SAME NUMBER, not an approximation -- I read the engine value directly (asserted in the unit check).
  Bucket = `clip(floor(elixir + 1e-6), 0, 10)`, which is the sim's `floor(elx * 10 + 1e-6)` (l.1326-1327).
- PHASE (b): `t_s = env.tick * TICK_S` with `TICK_S = 0.05` (engine_env.py l.61), against
  `double >= regulation_s - 60 = 120 s` and `triple >= regulation_s + max(0, overtime_s - 60) = 240 s`,
  the sim trainer's own arithmetic on gate_prior.json's `regulation_s` 180 / `overtime_s` 120.
  **(b) NOT VERIFIED**: that engine tick 0 is the same instant as the sim's `t = 0`. EngineMatchEnv skips a
  4.5 s pre-battle countdown (ticks 0-90, engine_env.md l.107). If the engine's own regulation clock starts
  AFTER that countdown, this mapping flips phase up to 4.5 s early out of a 120 s window (<= 3.8% of the
  single-elixir phase, and the flip is the same for both arms so it cannot bias the A/B). Measuring it needs
  a probe that keeps our elixir off the 10 cap and watches the regen rate double -- NOT run; proposal only.
- The engine's phase rule itself (does the engine really double elixir at its own t = 120 s?) is likewise
  (b) unverified; only the sim's constants were used.

## 3. Unit check -- `scratchpad/gauntlet/L62/gate_prior_unit.py` (MEASURED, 27/27 PASS)
Run: `PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L62/gate_prior_unit.py`
(from `icebow/`). No engine, no VM, read-only. Tolerance 5e-5 for table values, because the hand-checked
numbers in the brief are the JSON rounded to 4 dp (the JSON carries e.g. 0.062606, not 0.0626).

Table, straight from gate_prior.json: single/3 **0.062606** (hand 0.0626), single/9 **0.203290** (0.2033),
double/9 **0.446343** (0.4463), single/4 0.058034, triple/6 0.241291; regulation 180.0, overtime 120.0,
so double from **120 s**, triple from **240 s**.

`Trainer.gp_target()` driven through a stub (tick, engine elixir) -> p:
| tick | t_s | elixir | phase | bucket | p |
| --- | --- | --- | --- | --- | --- |
| 0 | 0.0 | 3.00 | single | 3 | 0.062606 |
| 1200 | 60.0 | 9.40 | single | 9 | 0.203290 |
| 2399 | 119.95 | 9.0 | single | 9 | 0.203290 |
| 2400 | 120.00 | 9.0 | **double** | 9 | 0.446343 |
| 4799 | 239.95 | 6.0 | double | 6 | 0.131995 |
| 4800 | 240.00 | 6.0 | **triple** | 6 | 0.241291 |
| 0 | 0.0 | 10.0 | single | 10 (clip) | 0.183766 |
| 0 | 0.0 | 0.0 | single | 0 | 0.010026 |
| 0 | 0.0 | 2.999 | single | 2 | 0.041543 |
| 0 | 0.0 | 2.9999995 | single | 3 (the +1e-6 nudge) | 0.062606 |
| 1200 | 60.0 | 0.94*10 | single | 9 | 0.203290 |
`gprior is None` -> 0.0.

CE term: the `gq_m[:,1] > _NEG*0.5` mask drops the masked row and keeps the other 2; CE at pi=0.5 is
ln 2 = 0.693147; a hand-computed row matches to 1e-5; CE(p, pi=p) = H(p) = 0.504943 at p = 0.2033.
And the number that says what the term is FOR: a gate parked at engA's collapsed max pi = 0.2326 against a
double-elixir/9-elixir target of 0.4463 pays CE **0.7975** vs the 0.6874 floor it would pay at pi = 0.4463 --
at coef 2.0 that is a standing ~0.22 of loss pushing the gate up, which coef 0 did not have.

## 4. BLOCKER FOUND BEFORE THE SMOKE: both engine slots were DEAD (this CONTRADICTS the brief)
- (c) The brief states "The VM (qemu PID 54304) and its worker service are UP and idle -- reuse them."
  The VM is up. **The worker service was not.** Measured, 15:16-15:18 local:
  - `engine_ppo.py --port 38031` and `--port 38032`, both: `ConnectionResetError [WinError 10054]` on the
    FIRST `env.reset()` (the engine `{"op": "reset"}` RPC), before a single decision. Reproduced 3x.
  - A bare `NativeRoyaleEnv(port=P).observe()` -- no training code at all -- fails the same way on both
    ports: `ConnectionAbortedError [WinError 10053]`. So this is NOT my change: the plain read-only RPC
    dies too. (The host redirs still LISTEN, because qemu owns 38031/38032; nothing answers inside.)
  - `python -m native_core.worker status --workers 2 --base-port 37031` (read-only, no start, no stop):
    `{"vm_ready": true, "services": [false, false]}`.
- (a) Host processes all alive and untouched: qemu-system-x86_64-headless PID 54304 (6128 s CPU),
  adb PID 59132, emulator PID 66236. Crawler 29444/53824 and uvicorn 63608 alive.
- (b) Cause not established. The engA workers were killed around 15:04 (last log write) and the in-guest
  services were gone by 15:16. Guest-side death after the clients were killed is the obvious suspect but
  it is NOT measured, and I did not go looking inside the guest.

- (a) I did NOT restart the service. `worker start` was attempted once and was **denied by the harness
  permission classifier**, so the recovery was never executed. Nothing was started, stopped or redeployed.
  `research/ext/cr-native-sandbox/artifacts/libnative_core_probe.so` still hashes **82887463deee1f2c...**,
  unchanged, and nothing under `research/ext/` was written.
- (a) Re-probed at 15:31: still down (38031 ConnectionAbortedError, 38032 ConnectionResetError).

### 4.1 CONSEQUENCE: the pair is NOT LAUNCHED
`engB_launch.ps1` is written and ready, but the launch would die on its first `env.reset()`. **The single
blocking action is restarting the two in-guest engine services** -- exactly the command the author's own
`_boot.ps1` runs, and which is idempotent for the VM while `vm_ready` is true:

```
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox; . .\runtime.env.ps1
.\.venv\Scripts\python.exe -m native_core.worker start --workers 2 --base-port 37031
```

Then `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\engB_launch.ps1`,
which re-probes both slots itself and refuses to start if they are still dead.

## 5. Smoke -- what I COULD and COULD NOT run
### 5.1 On the engine: NOT RUN (blocked, section 4)
Three attempts (38031 x2, 38032 x1) all died at the first reset. They did prove three things before dying:
- (a) the config header now carries `"gate_prior_coef": 2.0` and `"gate_prior_path": ...gate_prior.json`,
- (a) the new banner prints and the table loads:
  `GATE PRIOR ON coef 2.000 | ...gate_prior.json schema 1 (519 replays, 23620 plays, dt 0.6) |
   double from 120s, triple from 240s | single P(play) at 4 / 7 / 9 elixir = 0.0580 / 0.0426 / 0.2033`,
- (a) the `_m0` checkpoint saves before any update, and the crash-save path still works.

### 5.2 CHECKPOINT FORMAT TEST -- PASSED (MEASURED)
`read_ckpt.py ../scratchpad/gauntlet/L62/smoke2/gp_smoke_m0.pt` (the m0 written by the patched trainer):
- `[v1 sim boards] n 1004 top1 **15.44** top5 **46.61**` -- the init's numbers exactly.
- `[v2 engine boards] n 1333 top1 **15.00** top5 **43.51**` -- the init's numbers exactly.
- `[rails] frac |raw|>8 = 0.025  p99 10.9  mean 2.6`; `[bias map] max 5.32 min -1.41`.
- Stronger still, a direct tensor compare against `bc_bias_native_s0.pt`: all 27 `model` tensors and all
  `gate` tensors `torch.equal` -> **True**. `engine_ppo` meta reads
  `{'kl_coef': 0.0, 'gate_prior_coef': 2.0, 'seed': 41, 'updates': 0, 'decisions': 0, 'wld': [0,0,0], 'port': 38032}`.

### 5.3 OFFLINE TRAINING SMOKE -- `gate_prior_offline_smoke.py` (MEASURED)
Since the engine is down, I drove a real `SimMatchEnv` (as `gate_probe.py` does) to build rollouts of the
same shape and called the **patched `Trainer.update()`** on them, with the launch argument set
(coef 2.0, kl 0, epochs 4, minibatch 512, lr 2.5e-4, clip 0.2, head cap 2.0) and `value_warmup 8` so both
the warm-up branch and the normal branch are exercised. 512 decisions x 6 updates.

**[A] the term touches the GATE HEAD ONLY** -- backward through only `coef * mean(CE)`:
`gate.weight |grad| 33.93`, `policy.card_head.weight.grad None`, `policy.cell_conv[-1].weight.grad None`.
130 of 256 rows unmasked; the rest excluded by `gq_m[:,1] > _NEG*0.5`. PASS.

**[B] six updates** (`pl` / `vl` are the existing fields; the rest are the new readouts):
| upd | pl | vl | gp_ce | gp_target | gp_rows | p_gate | p90 | frac>tau | warm_mb |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | +0.0440 | 0.9196 | 0.3116 | 0.0707 | 0.525 | 0.2478 | 0.4172 | 0.4312 | 4 |
| 2 | +0.0246 | 0.9822 | 0.3013 | 0.0658 | 0.561 | 0.1888 | 0.3582 | 0.2091 | 4 |
| 3 | +0.0332 | 0.9958 | 0.3065 | 0.0789 | 0.600 | 0.1651 | 0.3039 | 0.1987 | 0 |
| 4 | +0.0199 | 1.3366 | 0.2935 | 0.0767 | 0.711 | 0.1487 | 0.2719 | 0.1374 | 0 |
| 5 | +0.0020 | 2.7029 | 0.2600 | 0.0715 | 0.715 | 0.1212 | 0.2148 | 0.0355 | 0 |
| 6 | +0.0035 | 0.6149 | 0.3253 | 0.0816 | 0.789 | 0.1204 | 0.2239 | 0.0668 | 0 |
- (a) **No NaN anywhere** -- the trainer's own guards (including the new gate-prior one) never fired, and
  the smoke re-checks every output field itself.
- (a) `gp_ce` finite throughout, 0.3116 -> 0.2600 by update 5, 0.3253 at update 6: **stable, not diverging**,
  but NOT monotone on 6 updates of a moving state distribution. Its floor is the binary entropy of the
  targets on those rows, ~0.25-0.30 for targets around 0.07-0.08, so 0.26-0.33 is *at* the floor already.
- (a) `gp_rows` (the fraction of rows that survive the mask) rises 0.525 -> 0.789: the policy is spending
  more time with something affordable, as it plays less.
- (a) `p_gate` 0.2478 -> 0.1204 and `frac>tau` 0.4312 -> 0.0668. **This is the prior working, not a
  collapse**: `gp_target` on these rows is 0.07-0.08, i.e. the prior is pulling the gate DOWN from the
  init's 0.25 toward the pro rate, and the gate is following. See 6.1 before reading these as a failure.
- (b) This is the SIM, six updates, one seed. It does not establish what happens on the engine at m=250.

## 6. Two things the brief did not know, both flagged before the launch
### 6.1 A gate that MATCHES the pro prior does NOT sit above tau -- `frac_gt_tau` cannot return to 0.22
(a) Computed directly from `gate_prior.json`'s own `windows` counts (212,265 pro decision windows):
- the mean prior target over the pro state distribution is **0.1109** (identically the raw pro play rate),
- only **8.14%** of pro windows have a table value above tau = 0.25,
- **the largest single-elixir value in the whole table is 0.2033 (at 9 elixir) -- below tau.**
So a policy that fitted the prior perfectly would, under `gate_probe.py`'s greedy `p > 0.25` rule, deploy
essentially NEVER during single elixir and only at 8-10 elixir in double/triple. Its `frac_gt_tau` would be
about **0.08**, not the init's 0.22. (b) That 0.08 assumes the engine's state distribution resembles the
pro window distribution, which is untested.
- CONSEQUENCE FOR THE BRIEF'S STOP RULE: "`frac_gt_tau` below 0.02 in both arms by m50" is still a sound
  alarm (0.02 is well under 0.08), but "not collapsing" should be read as *settling near 0.05-0.10*, not
  *staying at 0.22*. A drift to 0.22 would mean the gate is IGNORING the prior.
- The thing engA actually broke is not the level but the STATE DEPENDENCE: at m253 its p(play) had
  mean 0.155 / p90 0.2325 / max 0.2326 -- a constant. The prior's targets span 0.010 to 0.459, so a gate
  that fits it CANNOT be constant. That is the mechanism by which this fix addresses the failure, and it
  is (b) until the engine run shows it.

### 6.2 (b) A dt mismatch nobody has written down: the table is per 0.6 s, engine_ppo decides every 0.5 s
(a) `gate_prior.json` has `dt: 0.6`, and the sim's `sim.agent_dt` is **0.6** (config.yaml l.1522) -- so in
the sim trainer the table's per-decision probability matches the decision period exactly.
(a) `engine_ppo.py` runs `--decision_ticks 10` x `TICK_S 0.05` = **0.5 s** per decision (engA's value, kept).
(b) Therefore engB asks the gate for a per-0.6 s pro probability once every 0.5 s: ~20% more plays per
second of game time than pros make. It errs toward MORE deployment, i.e. away from the failure being fixed,
and it is IDENTICAL IN BOTH ARMS so it cannot bias the A/B.
PROPOSAL, DELIBERATELY NOT IMPLEMENTED (one change per experiment): either run `--decision_ticks 12`
(= 0.6 s, matching the fit) or scale the target by `agent_dt_engine / dt_table` = 0.833. Both change the
run's meaning; neither belongs in the same experiment as turning the prior on.


### 6.3 `--gate_prior_coef 0.0` IS byte-for-byte the old trainer -- PROVEN, not asserted (MEASURED)
`gate_prior_zero_equiv.py` runs the PRE-PATCH `Trainer.update()` (loaded from
`engine_ppo_launched_20260905.py`, the file engA actually ran) and the PATCHED one with `gprior = None`
on the SAME 512-decision rollout, from the same init, with identical weights and the numpy RNG reseeded
identically before each call, at `--kl_coef 0.3` so the KL path is live too:
```
update 1: shared output fields identical 18/18 | parameter tensors differing: 0
update 2: shared output fields identical 18/18 | parameter tensors differing: 0
PASS: all 33 parameter tensors torch.equal after 2 updates
```
The three new fields read `gp_ce nan gp_target nan gp_rows 0.0` when off -- which is why they are appended
AFTER the trainer's non-finite guard rather than inside it.

## 7. LAUNCH -- NOT DONE. `engB_launch.ps1` is written and ready
`scratchpad/gauntlet/L62/engB_launch.ps1`, cloned from `engA_launch.ps1` with three differences:
1. `--gate_prior_coef 2.0` in the `$common` block, i.e. **ON IN BOTH ARMS**, so the only between-arm
   variable is still `--kl_coef` (ctrl 0, KL arm 0.3);
2. `--kl_in_warmup 0` passed explicitly (engA ran the pre-flag file; see 1);
3. new out_prefixes `icebow/data/bench/engB_{ctrl,kl}` and logs `engB_{ctrl,kl}_20260905.log`, plus two
   preflights it runs before starting anything: (a) refuse if ANY `engB_*` output exists, (b) refuse
   unless both slots answer a read-only `observe()`.
Everything else is identical to the killed run: same init (sha `a1273d5d*`, asserted in-process, never
written), seed 41, rollout 1024, matches 2000, save_every 250, value_warmup 60, one slot each on the
DIRECT ports 38031 (control) / 38032 (KL), and the bcA_run.yaml hyper-parameter VALUES that are
engine_ppo.py's defaults.
- (a) No `engB_*` file exists anywhere -- verified at the start and again now. `engB_pids.json` does not
  exist BECAUSE NOTHING WAS LAUNCHED; writing a fake one would be worse than its absence.
- (a) Free RAM 15:27 local: **7865 MB** (was 7980 at start). Two trainers at ~2-3 GB each fit; the engine
  slots' own memory is inside the VM (qemu 54304, WS 419 MB on the host), so a service restart is the
  larger unknown, not the trainers.
- (a) Untouched throughout: qemu 54304, adb 59132, emulator 66236, crawler 29444 / 53824, uvicorn 63608.
  Nothing under `research/ext/` written; `libnative_core_probe.so` still `82887463deee1f2c...`.
  No `git add`, no commit. `engA_*` and `engine_ppo_launched_20260905.py` read only.

## 8. NOT ESTABLISHED (the honest list)
1. **(c) The brief's premise that the worker service was up.** It was not, and I could not restart it
   (permission denied). The pair is NOT running and no `m30-50` gate readouts exist.
2. **(b) That the gate prior prevents engA's collapse on the ENGINE.** What IS measured: the term is
   wired exactly like the sim's, it moves only the gate head, it is finite and stable over 6 sim updates,
   and its targets span 0.010-0.459 so a gate that fits it cannot be the constant engA became. Whether
   that survives 250 matches of engine PPO is the experiment, and it has not been run.
3. **(b) The engine tick -> phase mapping** (section 2.2): `tick * 0.05` vs a possible 4.5 s countdown
   offset, and whether the engine's own elixir rate really flips at its t = 120 s. Identical in both arms.
4. **(b) The 0.6 s table applied at a 0.5 s cadence** (section 6.2). Identical in both arms; unimplemented
   proposal recorded, not applied.
5. **(b) The predicted "healthy" `frac_gt_tau` of ~0.08** (section 6.1) assumes the engine's state
   distribution resembles the pro window distribution.
6. **NOT MEASURED AT ALL**: the on-engine smoke (no NaN over real rollouts, gp_ce trend on engine states,
   s/match with the extra term), and therefore the launch, the PIDs, and the m30-50 verification.
7. (b) Why the guest services died at ~15:04-15:16. Not investigated; I did not enter the guest.

## 9. Files
| path | state |
| --- | --- |
| `scratchpad/gauntlet/L62/engine_ppo.py` | EDITED (the 17 changes in section 2) |
| `scratchpad/gauntlet/L62/gate_prior_unit.py` | NEW -- the lookup + CE unit check, 27/27 pass |
| `scratchpad/gauntlet/L62/gate_prior_offline_smoke.py` | NEW -- sim-driven smoke of the patched update() |
| `scratchpad/gauntlet/L62/gate_prior_zero_equiv.py` | NEW -- coef 0.0 == the pre-patch trainer, proven |
| `scratchpad/gauntlet/L62/engB_launch.ps1` | NEW -- ready, NOT RUN |
| `scratchpad/gauntlet/L62/smoke2/gp_smoke*` | the 3 failed engine smoke attempts + the m0 that passed read_ckpt |
| `scratchpad/gauntlet/L62/engine_ppo_v2.md` | this file |
| `engine_env.py`, `engine_view.py`, `gate_probe.py`, `engA_*`, `engine_ppo_launched_20260905.py` | untouched |
| `icebow/src/**`, `icebow/data/bc_pro/models/*`, `icebow/config/gate_prior.json`, `research/ext/**` | read only |

STATUS: complete
