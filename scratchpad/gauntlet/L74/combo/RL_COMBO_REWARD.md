# RL combo reward (L74, owner plan 2026-10-17)

Owner: *"train the combo with reinforcement learning, rewarding the model for eliminating or heavily damaging large clumps
with high elixir value, and even more so if an enemy princess tower is caught in the blast radius along with the clump ...
The goal is to eventually wean the model off of hardcoded rules once it learns how to perform combos by itself."*

This note says what the reward is, why its numbers are what they are, how it is measured, what each training arm tests,
and what is still unproven. Code: `pipeline/spell_value.py` (the reward and the measurement), wired into
`pipeline/rl_royale.py` (key `spell_value_reward`), `pipeline/royale_env.py`, `pipeline/e1_eval.py` (the measurement hooks)
and `pipeline/search_s0.py` (`--spell-log` for evals). Tests: `pipeline/tests/test_spell_value.py` (23).

## 1. The reward in one paragraph

Every time **our** Rocket lands, the game engine is read on the exact ticks of the impact: which enemy bodies were inside the
blast, how much of each one's HP the blast removed, whether an enemy crown tower was hit, and whether one of our Tornados set
it up. The Rocket earns the **elixir value of what it removed** (a Wizard killed = 5 elixir; a Knight left at 2/3 HP =
3 x 1/3 = 1 elixir, counted at half weight because it survived), **minus the Rocket's 6 elixir**, times a weight that turns
elixir into reward. If an enemy **princess** tower is in the same blast as at least 4 elixir of troops, the troop value gets a
**x1.5 bonus**. The reward is given to the decision that **chose** the Rocket (and, for a combo, partly to the decision that
chose the Tornado).

## 2. The formula and its numbers

For one Rocket impact (`spell_value.event_reward`):

    V      = (elixir of bodies killed, at their HP share)  +  0.5 x (elixir of HP removed from bodies that survived)
    G      = V x 1.5   if an enemy princess tower is in the blast and V >= 4 elixir,   else V
    reward = 0.02 x (G - 6)      (the 6 = the Rocket's cost; NOT charged when an enemy princess tower was hit)
    reward clipped to [-0.3, +0.3] per Rocket, and a match's running total to [-0.5, +0.5]

| Situation | V | reward |
|---|---|---|
| Rocket hits nothing (a miss) | 0 | **-0.12** |
| Rocket + Tornado, 2 elixir caught (the owner's "pulled in too late" miss) | 2 | -0.08, split -0.053 Rocket / -0.027 Tornado |
| Rocket kills Wizard + Musketeer | 9 | +0.06 |
| Combo kills a 14-elixir clump | 14 | +0.16 |
| Combo kills 14 elixir AND hits a princess | 14 x 1.5 = 21 | +0.42 -> clipped **+0.30** |
| Rocket on a princess, no troops (tower chip / Rocket cycle) | 0 | **0** (neutral, as today) |
| Rocket on the king tower, no troops | 0 | -0.12 (no exemption: owner doctrine "never the king") |

Keys (all optional; absent = the defaults above): `spell_value_w` 0.02, `spell_value_dmg_w` 0.5, `spell_value_cost_w` 1.0,
`spell_value_tower_bonus` 0.5, `spell_value_tower_min` 4.0, `spell_value_event_cap` 0.3, `spell_value_match_cap` 0.5.

**Body values** are the rule's own table (`decision_options.rocket_unit_table`: card cost / bodies the card puts out), looked
up by the engine's own unit name, so a Witch's Skeleton is worth 1/3 (the Skeletons card's share), not the Witch's 5;
evolution / hero forms count as the base unit. Measured mapping coverage on the 225 engine unit types: 174 by unit name,
the rest by their card (e.g. RascalGirl = Rascals' 5/3). Known ceiling (marked `ponytail:` in the code): an unknown child of
a one-body card is valued as that card's body (a Balloon's bomb would read 5).

### Why 0.02 per elixir (scale vs the win reward)

* The win reward is +1 / -1, so the gap between winning and losing is 2.
* In Mark CXXXVIII's last training update the advantage spread before normalisation was **adv_std = 0.179**, and the model
  played **0.43 Rockets per match** (card mix 1.0% of 43.2 plays). So one Rocket's reward of +0.06 to +0.16 is about
  **0.3 to 0.9 of a typical advantage** on the Rocket row: strong enough to steer that one decision, small next to winning.
* Per match the spell term is expected around 0.43 Rockets x ~0.1 = **~0.04 of the win reward**. The monitor `dominates`
  (mean |match spell reward|) flags it if it ever passes ~0.25. The match cap 0.5 is a hard ceiling.
* "A combo worth 10+ elixir should matter, 6 elixir for nothing should cost": a 10-elixir combo = +0.08, a miss = -0.12.
* (b) **Untested:** whether 0.02 is the best weight. The measurement is the arm-1 result; a 0.01 / 0.04 sweep only after it.

### Why net of cost, and why princess Rockets are not charged

* Net of cost = an even elixir trade scores 0, so misses are punished (owner: "punish combo misses") and Rocketing cheap
  swarms does not pay (4 Skeletons = 1.3 elixir -> -0.09).
* A gross-only reward (no cost) would pay for any Rocket that touches anything: that rewards spending, the main hack risk.
* Princess-tower Rockets stay **neutral** (0 when no troops are caught) because Rocket cycling on a tower is a legitimate late
  plan the owner is already watching (late-game rocket-cycle concern, 10-17); charging them 6 elixir would teach the model to
  stop doing it, which this reward was never meant to decide. The win reward keeps judging tower Rockets exactly as today.

## 3. Credit assignment (which decision gets the reward)

* The reward is placed on the **decision row that chose the Rocket** (mapped exactly: the event's first-seen tick -> the
  accepted Rocket play that landed just before it -> that play's decision tick -> its row). It is not placed at the impact.
* Why: between the decision and the impact there are 26 ticks of tap delay plus 20-60 ticks of flight = 5-9 more decisions,
  mostly "wait" decisions that did not cause the hit. GAE (generalised advantage estimation: each decision's advantage is
  its own reward plus a decaying sum of what came after, lambda 0.95) would smear an impact-row reward onto those rows and
  give the Rocket row only a decayed share. On the decision row the Rocket gets the full reward, and GAE still passes a
  decayed share BACK to the decisions just before it (e.g. "waited for the clump"), which is the direction that makes sense.
* **Combo split:** if one of our Tornados was first seen at most 40 ticks before the impact with its centre within 5.5 tiles
  (its radius) of the Rocket's aim, it "set up" the Rocket. The event's reward is then split by elixir cost, Rocket 6/9 and
  Tornado 3/9, between the two decision rows. Both choices made the combo, so a miss charges both, which is the owner's
  described failure (Tornado too late -> Rocket missed). A Tornado that sets up nothing gets nothing (defensive Tornados are
  not touched).
* **Critic:** the value head predicts P(win) - P(loss), bounded to [-1, 1]; with this reward a return can reach 1.5. So with
  the key on, the critic becomes the existing residual critic with Phi = 0 and scale `shaping_critic_scale` = 1.5 (the
  trainer refuses a scale below 1 + match cap, and refuses `critic_warmup_updates` 0). The control arm uses the same critic.

## 4. The measurement (SpellTracker) and the proof it changes nothing

* The engine normally advances ~10 ticks per step. While our Rocket is armed (accepted) or in flight, the env steps **one tick
  at a time**, so the impact is read exactly: bodies inside the blast on the last tick the Rocket is seen, their HP one tick
  after it is gone (the fast-plays worker's `scenarios.impact` rule). Inside = centre within 2.0 tiles (Rocket radius) + body
  radius + 0.25; a tower counts when its centre is within 2.0 + its radius AND its HP dropped.
* **Measured, laptop (RoyaleSim 20261006 runtime), scripted matches, 4 seeds:** with vs without the tracker, every stop's
  full state (entities, HP, positions, spells, elixir, hands) and the outcome were **identical** (233-391 stops each); 13
  Rocket events logged with sensible values (e.g. 4 Barbarians = 3.75 elixir killed; a princess hit = 342 tower HP).
* **Measured, pod P3 (fork36 runtime, Mark CXXXVIII, the exact promotion-eval D3 command, first job = 12 seeds):** with vs
  without `--spell-log`, **12 / 12 rows identical** (minus the `spell` field and wall time), both without and with the live
  combo rules (7 / 7 wins each). Those 12 matches logged 18 Rockets: 13 on an enemy princess, 1 rule combo (aim (13.5, 16.5),
  our right bridge: 11.4 elixir killed + 3.0 damaged = 12.9 -> +0.14), several princess Rockets catching 5-6 elixir (+0.16).
* **Measured, P3, three REAL `rl_royale --smoke` runs (E 4, G 2, 1 actor, 2 updates):** all three SMOKE PASS. Key absent on
  this code vs the git-HEAD modules: same config sha (f1f10fd6756f), update-0 rollouts identical (8 matches, wins, plays,
  rows, card mix), critic numbers equal to 1e-10 (GPU float noise between two processes); re-run with the learner on the
  CPU (`learner_device=cpu`, both sha 5a8c62e40ca0): update 0 **bit-identical** -- rollouts, KL, policy loss, entropy, clip
  fraction, ratio, gradient norm, critic numbers and value losses. Key on vs off: update-0 rollouts
  identical (the tracker never changes play), critic / returns differ (ret_mean 0.362 vs 0.247: the reward plus the 1.5
  critic scale). Key-on monitors: 0.75 Rockets / match, 0.625 on a princess, 1.48 elixir troop value / match, reward
  +0.027 / match (`dominates` 0.027), max one Rocket +0.15, 4 rewarded rows, 0 rows lost, 0 Rockets unmapped.
* Absent key = no tracker object = no extra engine step, no result key. Config hash: Mark CXXXVIII's own config still hashes
  to **99d87d08c498** (the 10-17 logged value) and fact02 to **a9a934a9a6c0** (its logged value) with the new code.

## 5. The rule is OFF in training; the opponent side

* Training rollouts never run the hard-coded rules: the learner samples (`policy: sample` -> `sample_decide_batch`), and the
  decision options (`rocket_tornado`, `rocket_value`, lethal Rocket, ...) only exist on the greedy `live` path when the cfg
  carries their keys. `rl_royale.actor_cfg` never adds them, for rollouts or for the held-out screens. So the model has to
  find the combo itself; nothing plays it for the model.
* Opponents: league self-play opponents (Mark CXXXVIII itself 25%, the run's own snapshots 75%, the 5 external weekend
  checkpoints by PFSP; `opp_style on` adaptive styles) also sample from their frozen policies: **no rule, no reward, no
  tracking** (only the learner's side is tracked and recorded).

## 6. The cadence problem (why arm 1 alone cannot learn the near-our-king combo)

* Measured (fast-plays worker): near our king the Rocket must deploy within gaps -24..+12 ticks of the Tornado (gap =
  Tornado deploy - Rocket deploy), near our princess -26..+10, at our bridge -16..+24, at the enemy king +32..+56.
* In training (and the SIM eval), a play lands 26 ticks after its decision and the next decision comes on the 10-tick grid
  after landing: two plays are never less than **30 ticks apart**. So at normal pace the model can only ever land the combo
  where the window allows >= 30 ticks: at the enemy king (+32..+56, Rocket first). **Arm 1 cannot learn the owner's original
  combo near our king, whatever the reward.**
* **Arm 2 = arm 1 + `learner_pipeline_frac: 0.3`**: in 30% of training matches the learner may decide again while a play is
  pending (the existing pipelined-decision mechanism = live's fast plays), on the 2-tick frame grid, so gaps of a few ticks
  (and Tornado-first) become possible. ONE change vs arm 1.
* (c) **Evidence against expecting a free win:** twice before, training with pipelining cost normal-pace play: NEWSIM v2
  (30% pipelining) -3.33 pp [-6.98, +0.31] fast-off and -1.46 [-4.98, +2.07] fast-on; l74-fastplay-rl fast-off 539 vs its
  control 613 / 960. And fast plays ON cost Mark CXXXVIII -6.8 pp [-10.3, -3.1] (607 -> 542). Arm 2's question is narrow:
  with the combo reward, does fast-ON play win at least as much as Mark CXXXVIII fast-OFF (607) while landing combos near
  our towers? If not, the alternative (not built: YAGNI until arm 2 answers) is a learned follow-up head like the ability
  head: one Bernoulli "Tornado now" decision right after a Rocket, so only the combo uses the fast second play.

## 7. Reward-hacking checks (what the eval report flags)

`combo/spell_report.py` prints, per arm and eval variant, next to the paired win delta:

| Hack | Detector column | Flag when (vs the control, same variant) |
|---|---|---|
| Rocketing cheap swarms | `swarm%` (Rockets whose every hit body is < 1 elixir, >= 3 hit), `val/rk` | swarm% up while val/rk down |
| Over-spending spells at the cost of wins | `Rplays`, `Tplays` per match + win delta | Rockets/Tornados up and wins down |
| Waiting for clumps instead of defending | `plays`, `crA` (crowns against), `ownHP` (own tower HP at the end) | plays down, crowns against / tower loss up |
| Reward louder than winning | train log `spell.dominates` | > 0.25 |

Plus the target behaviour itself: `comb/m` (combos per match), `myhalf/m` / `nearK/m` (combos on our half / Rockets near our
king), `miss%`, `rew/m`, and the Tornado-Rocket landing-gap list.

## 8. Arms, controls, commands

All arms: Mark CXXXVIII's own training config (`gae_cue_u250.yaml`: gae, tick discount, critic warm-up 5, cue inputs, league,
shaping none) with init = Mark CXXXVIII raw (`rlarm_gae_cue_u250_u0130.pt`), **seed 410 for all** (same rollout seeds:
common random numbers), 65 updates, fork36 runtime. Configs: `combo/cfg/`.

| Run | Change vs combo_ctl | Question |
|---|---|---|
| `combo_ctl` | - (`spell_value_reward: on`, `spell_value_w: 0`: tracker, rows, critic scale 1.5, NO reward) | the control: rule off, no reward |
| `combo_rew` (arm 1) | `spell_value_w: 0.02` | does the reward alone improve Rocket value / wins at normal pace? |
| `combo_rew_pipe` (arm 2) | + `learner_pipeline_frac: 0.3` (vs combo_rew: that ONE key) | can it then learn the fast near-tower combo? |
| `combo_ctl_pipe` (optional) | `learner_pipeline_frac: 0.3` only | the pipelining control for arm 2 |
| `ref_cxxxviii` | eval only | Mark CXXXVIII with `--spell-log` (its 'off'/'offc'/'on' must reproduce 607 / 610 / 542) |

Every run gets the promotion eval (fork36, Hero IW, live levels, card levels, opponent tower troops at live rates, habit log,
D3, seeds 741200 + 742000 = 960 paired) **three ways**: `off` (no live combo rules), `offc` (+ the live combo rules from
LIVE_OPTIONS = what deploying it today would mean), and `on` (+ fast plays; `_pipe` runs and the reference only). "Weaned"
= an arm's `off` >= Mark CXXXVIII's `offc` (610): the rules can then be dropped.

**Launch (after ~07:00, when the factorial pods are free; nothing was launched):**

    bash scratchpad/gauntlet/L74/combo/ship.sh build                 # laptop; rebuild after any commit
    for HP in 81.27.69.177:23363 64.247.206.79:19400 216.81.245.71:34210 216.81.245.71:29286; do
      bash scratchpad/gauntlet/L74/combo/ship.sh ${HP%:*} ${HP#*:}   # queue = combo/queue_<PORT>.txt
      ssh -i ~/.ssh/runpod_clashbot root@${HP%:*} -p ${HP#*:} \
        'cd /workspace/cb_tt && setsid nohup bash /workspace/combo/chain.sh > /dev/null 2>&1 < /dev/null &'
    done
    # 23363 combo_rew, 19400 combo_ctl, 34210 combo_rew_pipe, 29286 ref_cxxxviii (+ combo_ctl_pipe: uncomment in its queue)

The chain trains (`python -m pipeline.rl_royale --config scratchpad/gauntlet/L74/combo/cfg/<RUN>.yaml --run rlarm_<RUN>`,
under `flock /workspace/cpu.lock`), grafts the live heads from Mark CXXXVIII grafted (`weekend/graft_generic.py`), then runs
`mix/live_eval_pod.sh none <RUN> <ckpt>_grafted.pt D3` per variant with EXTRA =
`--habit-log --live-levels --card-levels Rocket=16 Log=15 --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 --spell-log --record-plays`
(+ `--log-air block --rocket-value 9 --rocket-value-mode damage --rocket-value-hitbox edge --rocket-tornado only --tornado-river on`
for `offc`, + `--pipeline-decisions --pipeline-tau-delta 0` for `on`), bundles `/workspace/combo/out/<RUN>.tgz` + `.sha`, and
never stops the pod or arms a timer. Wall time per run (factorial measurement): 2.9-3.6 h training + 3 evals. Copy back the
bundles to `C:/Users/benpe/pod_backup_weekend/pod1018_combo/` (sha-verified) and run `combo/spell_report.py`.

Pod checks before launch: `CB=<checkout> bash scratchpad/gauntlet/L74/combo/smoke.sh` (pyflakes, the 23 tests, cfgcheck,
three REAL `rl_royale --smoke` runs and `eval_inv.py`).

## 9. Still open (labelled)

* (b) Untested: the weight 0.02, the damage share 0.5, the bonus x1.5 and the 4-elixir threshold are reasoned, not tuned.
* (b) Untested: whether 65 updates is enough for a 0.43-Rocket-per-match signal to move the Rocket head; the per-update
  monitors (`spell.rockets_per_match`, `value_per_match`, `combos_per_match`) show the trend during training.
* (b) Untested: SIM fidelity of Rocket flight and Tornado pull (overall fight parity 0.941 on 145 matches, not Rocket-specific);
  a combo learned in the SIM still has to be checked live.
* Known simplification: other damage landing on the same bodies in the 2 ticks around the impact is counted as Rocket damage
  (one tower shot at most); bodies outside the blast are never counted.
