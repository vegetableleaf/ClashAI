"""The D3 (LIVE_OPTIONS) decision stack as a league_opp_live dict: DecisionOptions fields only, minus the keys the fast
loop refuses (producer.UNSUPPORTED_CFG). Prints the dict as one-line YAML flow + the dropped keys."""
import sys, json
sys.path[:0] = [r"C:\Users\benpe\ClashBot", r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\livecal"]
import livecal
from pipeline.decision_options import DecisionOptions, options_from_config

UNSUP = ("posture", "spell_track", "crown_track", "habit_track", "record_ctx", "record_elixir", "pipeline_decisions",
         "tap_loss", "tap_slow", "follow_ups", "own_effects", "predict_drops", "afford_ticks")   # producer.py:47
fields = set(DecisionOptions.__dataclass_fields__)
live = dict(livecal.LIVE)
default = DecisionOptions()
keep = {k: v for k, v in live.items() if k in fields and k not in UNSUP and getattr(default, k, object()) != v}
drop_unsup = {k: v for k, v in live.items() if k in UNSUP}
not_field = {k: v for k, v in live.items() if k not in fields}
options_from_config(keep)                     # raises on a bad dict
print("KEEP", json.dumps(keep, sort_keys=True))
print("DROPPED (fast loop refuses)", json.dumps(drop_unsup, sort_keys=True))
print("NOT DecisionOptions fields (gap.py / runner flags)", json.dumps(not_field, sort_keys=True, default=str))
