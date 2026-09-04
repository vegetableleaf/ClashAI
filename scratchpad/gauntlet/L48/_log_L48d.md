- L48d (2026-09-04 ~12:40-13:15): owner order -- hogeq re-synced to icebow (2f9cd8e..6cca0a0): 12 shared files
  byte-copied (crown fix included), 7 declared-different files hand-ported (lock-aware targets, bot attack floor,
  eage/schema-2 gate prior, cast-delay leads, slot-5 switch, rl_gate_tau, tower anchors, play-again guard, and a
  NEW play.py Log corridor assist = live behaviour change for hogeq, untested on a screen), config keys at icebow's
  values, tools (schema-2 gate_prior, probe, latency timer, watchdog drift detector, real_run_gates), 4 deck-neutral
  tests. NOT ported: nado reach fix, xbow ramp (no bow/nado). Parity strict OK both decks; hogeq suite 1,322 OK /
  64 skip (3 bow-only tests removed). hogeq's OWN schema-2 table fitted (595 replays): quiet 4.6/4.3/5.5% vs
  pressure 8.8/8.8/9.7% at 5/6/7 elixir. "CHEAP CARDS" MEASURED on hogeq best (m2000, 3 seeds, sampled probe):
  mean play cost 2.02-2.05 vs pros 2.61, elixir mean 1.83, >=6 share 0.2%, hog in NO bucket's top-4, P(play) at
  1-3 elixir 0.5-0.56 vs pros 0.05-0.075. --force-bank 4 (1 seed): same card head picks mm 36 / hog 31 / tesla
  30, cost 2.96 -> the GATE is the cause, not the card head; same mechanism as icebow 18k. HANDOFF 5cs.18.
