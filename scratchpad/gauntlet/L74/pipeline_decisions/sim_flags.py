"""Print the deployed LIVE_OPTIONS as the SIM decision flags: the file's tokens minus the live-only switches (input path, afford window,
extrapolation horizon, IW press bar, hero-ability spec, identity extension, card levels -- the SIM has its own cfg for those).

    python sim_flags.py [LIVE_OPTIONS]        -> one line for `pipeline.search_s0`  (e.g. "--xbow-class class_sample ... --own-effects")
"""
import shlex
import sys
from pathlib import Path

LIVE_ONLY_VALUE = {"--iw-press-pstar", "--hero-ability-spec", "--tap-gap-ms", "--afford-ticks", "--early-release-margin",
                   "--extrapolate", "--identity-ext"}
LIVE_ONLY_FLAG = {"--fast-input"}
LIVE_ONLY_MULTI = {"--card-levels"}                    # takes values until the next --flag

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "L70/live/LIVE_OPTIONS"
tokens = shlex.split(path.read_text(encoding="utf-8-sig"), comments=True)
out, skip_value, multi = [], False, False
for t in tokens:
    if t.startswith("--"):
        multi = False
        skip_value = False
        if t in LIVE_ONLY_FLAG:
            continue
        if t in LIVE_ONLY_VALUE:
            skip_value = True
            continue
        if t in LIVE_ONLY_MULTI:
            multi = True
            continue
        out.append(t)
    elif skip_value:
        skip_value = False
    elif not multi:
        out.append(t)
print(" ".join(shlex.quote(t) for t in out))
