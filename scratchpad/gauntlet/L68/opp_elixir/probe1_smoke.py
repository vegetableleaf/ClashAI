"""Smoke on the only real reader recording (L68/live_reader/probe1.jsonl, 10 frames, ticks 206-242, no opponent
plays): LiveOppElixir estimate vs the opponent's TRUE elixir_raw (read HERE only, to grade)."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]; sys.path.insert(0, str(REPO))
from pipeline.live_mem import my_side_of
from pipeline.opp_elixir_count import LiveOppElixir
live = LiveOppElixir()
for line in open(REPO / "scratchpad/gauntlet/L68/live_reader/probe1.jsonl"):
    f = json.loads(line)
    est = live.update(f)
    opp = next(p for p in f["players"] if p["side"] != my_side_of(f))
    print(f["game_tick"], "est", round(est, 4), "true", opp["elixir_raw"] / 1e4, "err", round(est - opp["elixir_raw"] / 1e4, 4))
print("plays", live.counter.plays, "spawns", live.detector.spawns, "unknown ids", live.detector.unknown_ids)
