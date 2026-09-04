- L49 (2026-09-04 ~13:00-13:35): COMPOUND-DRILL instrument read (drill_compound_frac forced 1.0 in-process; never
  enabled on disk). Verdict fires on every board (0 timeouts), ~12-13 s, 2-3 components. Pass pooled n=96: nothing
  ~1%, doctrine 35.4%, c2r_m20k 26.0%, gatec2_m10k 29.2%; seed band 4-6pp -> checkpoints indistinguishable, doctrine
  6-12pp above. Doctrine's spell/log components 0/N; full-elixir override does not recover them (scarcity
  contradicted). ROOT CAUSE = GRADING: 12 success predicates in drills_icebow.py read e.units board-globally, so
  compound_verdict's per-component tag is dead code -- AND the same unused helper is the only thing hiding the
  drill_noise distractor, which is ON (0.5) in the running c2r and in hogeq (identical pattern, drills_hogeq.py:29).
  Measured on 10 affected drills, doctrine, n=250/arm: noise 0 78.0%, noise 0.5 66.8%, noise 0.5 + grader hides the
  distractor 70.4% -> grading bug ~3.6pp (small, real in sign), behavioural ~7.6pp (bow_defends 72->44,
  bridge_spam 48->20 not recovered). Learner impact untested. Fix (swap to all_enemies_dead/enemy_units, both decks)
  NOT landed: c2r depends on the drill files; its own experiment after m30k. c2r 27,325 eps at 13:20, 0.5 ep/s,
  m30k ~14:50; last-epoch gate drift on PLAY -1.08 (largest of 12) -- watch only. HANDOFF 5cs.19.
