p='hogeq/config/config.yaml'
s=open(p,encoding='utf-8').read()
def rep(old,new):
    global s
    assert s.count(old)==1,(old[:70],s.count(old)); s=s.replace(old,new)

rep('''  use_interactions: true
''','''  use_interactions: true
  lock_aware_targets: false  # HANDOFF §5cb: true = the sim's interaction vector + predictive canvas use the
                             # LOCK-AWARE predictor (engine lock state, deploy time, building reach). LIVE has
                             # no track memory today, so this is a sim-to-real seam until live supplies the
                             # same hint (interactions.Hint). false = the memoryless read every ckpt was trained on.
''')
rep('''  rl_epsilon_start: 0.70
  rl_epsilon_end: 0.15
''','''  rl_epsilon_start: 0.70
  rl_epsilon_end: 0.15
  rl_gate_tau: 0.25        # (2026-09-03, HANDOFF 5cr; hogeq 5cs.18) live GREEDY wait/play rule = the sim's: WAIT iff sigmoid(Q_play - Q_wait)
                           # <= this. train-rl used Q(wait) >= Q(play) (= 0.5) while the sim trains/evals and play.py use
                           # sim.ppo_gate_threshold 0.25. MEASURED on ICEBOW gatec2_m10k, 5,371 sim decisions: p(play) never reaches
                           # 0.5 (p99 0.358) -> the 0.5 rule drops 99% of the policy's plays. Remove the key = legacy rule.
''')
rep('''  rocket_base_time: 0.3          # fixed part of rocket flight time (s)
''','''  rocket_base_time: 0.3          # fixed part of rocket flight time (s)
  opp_mem_slot5: opp_estimate    # LIVE ONLY (2026-09-03, HANDOFF 5cr.8): what train-rl/env put in opponent-memory slot 5 (threat
                                 # slot 31). The SIM trains the policy with OUR elixir there; "opp_estimate" (legacy live) feeds the
                                 # opponent-elixir estimate instead, and the gate reads it as ~0 elixir -> waits. MEASURED on ICEBOW s2:
                                 # p(play)>0.25 at >=9 elixir 1.7% vs 96.9% with "own_elixir". Set "own_elixir" for parity with the trained policy.
  spell_cast_delay_s: 1.0        # LIVE ONLY (2026-09-03, owner): seconds between the tap and the spell
                                 # actually existing on the board. The log/rocket lead is scaled by it
                                 # (rocket: this + flight; log: this alone, the corridor covers the roll).
                                 # 1.0 s for ALL spells -- owner-confirmed from online sources (2026-09-03
                                 # 19:1x); the sim engine's spell_delay (0.4) is the one that is wrong.
                                 # Floors rocket_base_time.
''')
rep('''  backline_support_until_s: 45.0      # only in the first N seconds (the opening); later a support comes as part of a push, not a backline drop
''','''  backline_support_until_s: 45.0      # only in the first N seconds (the opening); later a support comes as part of a push, not a backline drop
  bot_attack_floor: 0.0               # OPPONENT CADENCE (HANDOFF §5cc, training bots only -- eval bots stay historical): a
                                      # cycle/control/siege bot banks to this many elixir before it ATTACKS (defence and
                                      # punish plays unaffected). 0 = attack on the first affordable step (the historical bot:
                                      # 46-52% of single-elixir steps pressured, 5 s quiet median vs pros 37% / 9 s, §5bw.4).
''')
rep('''  drill_tiers: null          # null = every registered drill; else e.g. [foundational]
''','''  drill_tiers: null          # null = every registered drill; else e.g. [foundational]
  aggro_drills: false        # HANDOFF §5bt-§5bu / §5ca: true = `sim/aggro_drills.py` (tank_for_bow,
                             # bow_lane_choice; graded on the engine's LOCK state) join the pool and the
                             # two old aggro drills (knight_guards_the_bow, nado_the_sneaky_lock) leave it.
                             # false = the gate05 pool exactly. HOGEQ: the aggro drills are X-Bow drills
                             # (icebow's wincon); this deck has no bow, so leave false until hogeq drills exist.
''')
open(p,'w',encoding='utf-8').write(s); print("config patched")
