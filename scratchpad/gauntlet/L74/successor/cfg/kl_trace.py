"""KL-leash trace of a run's train_log.jsonl: is the KL leash (kl_target / beta) binding?
    python kl_trace.py TRAIN_LOG.jsonl [EVERY=10]   -> update, winrate, elixir@play, kl gate/card/cell, beta_used/next
Prints the 'update' rows only (first, every EVERY-th, last)."""
import json
import sys

rows = [r for r in map(json.loads, open(sys.argv[1], encoding="utf-8")) if r.get("type") == "update"]
every = int(sys.argv[2]) if len(sys.argv) > 2 else 10
print("upd  win   e@play  kl_gate  kl_card  kl_cell  beta_used beta_next driver")
for i, r in enumerate(rows):
    if i % every and i != len(rows) - 1:
        continue
    print(f"{r['update']:3d} {r['winrate']:.3f} {r.get('elixir_at_play_mean', float('nan')):6.2f} "
          f"{r.get('kl_gate', 0):8.4f} {r.get('kl_card', 0):8.4f} {r.get('kl_cell', 0):8.4f} "
          f"{r.get('beta_used', 0):9.3f} {r.get('beta_next', 0):9.3f} {r.get('kl_driver')}")
