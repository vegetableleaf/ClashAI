
### §5cs.45 -- L62f (2026-09-05 18:1x-18:4x UTC): **THE m250 GRADE SEPARATES THE ARMS AND THE KL ARM IS NOT PINNED** -- control (kl 0) fell to 11.25/32.97 (v1) and 10.95/33.53 (v2) from the init's 15.44/46.61 and 15.00/43.51, i.e. **-4.2 top-1 / -13.6 top-5** in 250 matches; the KL arm (kl 0.3) is at **16.73/44.02 (v1) and 16.28/42.69 (v2) -- top-1 ABOVE the init on both val sets (+1.29 / +1.28) with top-5 essentially held** (-2.59 / -0.82). Arm gap at m250: **+5.48 top-1 / +11.05 top-5** (v1). Plus: the bridge RE (owner-authorised) produced a full offset table and a built, uncommitted-to-deploy v2 bridge exporting buffs and area effects, with a **(c) contradiction of the v1 bridge's core assumption** -- area-effect objects are the 3M global-id series, not 4M, which is exactly why zones never appeared in `effects`.

Sources: this section's grades measured by the lead with `L61/read_ckpt.py` on `icebow/data/bench/engA_ctrl_m250.pt` and
`engA_kl_m253.pt` (deterministic instrument, fixed val sets -- re-running reproduces exactly); RE from
`scratchpad/gauntlet/L62/bridge_re.md` (agent, STATUS complete), artifacts `scratchpad/gauntlet/ext/re/bridge_v2/`.
(a) unless marked.

**A. The m250 grade (the result).**

| arm | v1 top1/top5 | v2 top1/top5 | rails frac>8 / p99 | vs init |
| --- | --- | --- | --- | --- |
| init `bc_bias_native_s0` | 15.44 / 46.61 | 15.00 / 43.51 | -- / 6.3 (train-log) | -- |
| control kl 0, m250 | **11.25 / 32.97** | **10.95 / 33.53** | 0.026 / 9.6 | -4.19 / -13.64 |
| KL 0.3, m253 | **16.73 / 44.02** | **16.28 / 42.69** | 0.015 / 8.9 | **+1.29 / -2.59** |

Reading: the control is reproducing bcA's collapse (15.44/46.61 -> 6.47/21.12 at m2k) on the same trajectory and at the
same early rate; the KL arm is NOT pinned to the init -- it MOVED, and moved toward the pro placements on top-1 while
trading a little top-5 mass, which is a sharpening (rails also lower than the control: p99 8.9 vs 9.6). This is the
outcome named in advance as the interesting one, not a post-hoc reading. **Where the control loses first is the
low-frequency cards:** rocket 1.9/18.9 vs the KL arm's 13.2/32.1, tornado 1.4/5.6 vs 2.8/22.2, skeletons 6.1/19.4 vs
12.2/35.0 -- consistent with a policy contracting onto a few cards/cells that the unshaped reward tolerates.
**Limits, stated plainly:** ONE checkpoint, ONE seed, ONE coefficient. `read_ckpt.py` is deterministic on a fixed val
set, so the numbers carry no instrument noise -- but the across-seed band for a 250-match engine run is UNMEASURED (b),
and a 1.3-point top-1 rise is inside what a second seed could plausibly erase. What is far outside any plausible band
is the 5.5 / 11.1-point ARM GAP. Confirmation is m500/m1000/m2000 on this pair, then a second seed.

**B. RE of the bridge (owner order "reverse engineer the remaining features, you have my permission").** Static work
only, on the §5ax live libg dump (15.535.29, x86_64); no VM touched while the pair trains. Sandbox commit **`81e5dff`**
`bridge: export buffs + area_effects (RE, unverified)` (sandbox's own git, on top of 7c66f92); nothing committed to
ClashBot. Every offset in bridge_re.md cites a function RVA + instruction.
- **(c) The v1 bridge's series assumption is wrong.** Object type is vtable slot 2 (`0xf6dd60: mov eax,3` area effect,
  `0xf7f250: mov eax,4` projectile) and global ids are `type*1M + n`, so **area effects are 3M..4M and 4M is
  projectiles only** (dispatch 0x10b90db/0x10b913b). The bridge gated `effects` on the 4M series -> it was listing
  projectiles a second time. That is the mechanism behind §5cs.43's measurement that `effects == projectiles` in
  23,169/23,169 frames: the two findings, reached independently and by different methods, agree.
- **(c) There is no freeze/stun flag on a character.** The engine folds `HitSpeedMultiplier` / `SpawnSpeedMultiplier`
  over the buff list (0xfb2b00 / 0xfb2bc0); "frozen" IS a buff with -100 multipliers. So the generic buff export is not
  merely convenient, it is the only faithful representation -- a boolean stun/freeze channel would be an invention.
- Offsets (a): character components bitmask +0x30 / array +0x18 / count +0x24, **buff manager = component[3]**
  (getter 0xf852e0); manager vtable 0x196ec68, array +0x18, count +0x24 (ctor 0xfb08f0, update 0xfb0b10, add 0xfb1130,
  remove 0xfb2240); buff instance 0x70 B: +0x00 owner, **+0x08 remaining ms (-1 = permanent), +0x0C total ms**,
  +0x18 data*, +0x28 level, +0x38 instigator, +0x40 instigator side, +0x54 shield hp (tick 0xf78200 does
  `max([+8],50)-50` -- a 50 ms decrement, i.e. one tick). `LogicAreaEffectObject` vtable 0x19691f8, size 0x150,
  ctor 0xf6b410: +0x48 data, +0x78 side, +0x7c/+0x80 x/y, +0xfc level, +0x100 elapsed, +0x114 life override; life =
  `[+0x114]` if >=0 else `data+0x170 + level*data+0x174` (0xdd5ff5). Data columns: buff HitSpeedMultiplier +0xe0,
  SpeedMultiplier +0xe4, DamageReduction +0xc0, Invisible +0x108, Shield +0x140, HitpointMultiplier +0x19c,
  DamagePerSecond +0x1d0, LockTarget +0x200, SwitchTeam +0x220; AEO Radius +0x17c, MaxRadius +0xb8, LifeDuration
  +0x170/+0x174/+0x178, Damage +0x124, HitSpeed +0x118, OnlyEnemies +0x129, ControlsBuff +0x194 (full list §3).
- **What v2 exports**: per character `buffs:[{name, data_id, remaining_ms, total_ms, level, instigator_side, shield_hp,
  flags, hit_speed_multiplier, speed_multiplier, spawn_speed_multiplier, damage_reduction, hitpoint_multiplier,
  damage_per_second, heal_per_second, invisible, lock_target, switch_team, ...}]` + `buff_manager_count`; top level
  `area_effects:[{id, name, side, x, y, level, elapsed_ms, life_ms, remaining_ms, radius, max_radius, current_radius,
  grows, damage, hit_speed_ms, controls_buff, hits_air/ground, only_enemies, follow_behaviour, ...}]` +
  `class_histogram`, `bridge_ext:"buffs_area_effects_v2_unverified"`. ADD-ONLY: existing fields unchanged, new fields
  not hashed (state_hash preserved), compact path gains zero reads, selection is vtable-keyed so a wrong series
  assumption cannot leak junk.
- **Deployment state (important):** `artifacts/libnative_core_probe.so` was deliberately RESTORED to v1
  (sha 82887463..., verified by the lead at 18:36 UTC) because the worker pool's `_service_artifacts_current` hash
  check would otherwise redeploy the bridge and RESTART THE LIVE TRAINING WORKERS on the next `start_service()`.
  v2 (sha 9b63a7a0...) sits in `scratchpad/gauntlet/ext/re/bridge_v2/libnative_core_probe.v2.so`, deployed only by the
  runbook `L62/re_verify_bridge.py` (own remote root, port 37041, refuses 37031/37032/38031/38032).

**C. Verification, NOT run (b throughout).** `L62/re_verify_bridge.py`: `deploy --bridge v2`, `drive` (pool tag
092PPVPCRCPC carries Poison/Tornado/Graveyard/Ice Spirit/Log from both sides; `--synthetic` scripts Freeze/Zap/Rage
because the pool has none), `compare v1.jsonl v2.jsonl` asserting every pre-existing field and the state_hash are
byte-identical. Until that runs, EVERY offset above is static-only: the Name column -> data+0x28 is (b), shield +0x54
as live HP is (b), the tournament-cap branch is unexercised, AEO +0x94/+0x98/+0xac are exported raw with no meaning.
Per-hit events (splash flashes, chain arcs) were skipped by design.

**Not established / traps.** (1) Nothing here says the KL arm's advantage survives to m2000 or to a second seed --
m500 is ~19:30 UTC. (2) The arms share the ~1.15-nat critic-warm-up drift (§5cs.44), so this is a comparison of two
drifted starts, not init-vs-init. (3) Trap recorded: **the worker pool redeploys artifacts by hash on service start** --
never leave a modified `.so` in `artifacts/` while an experiment runs. (4) Trap: a bridge "effects" list validated only
by "is it non-empty" would have passed for months; it was listing projectiles twice.
