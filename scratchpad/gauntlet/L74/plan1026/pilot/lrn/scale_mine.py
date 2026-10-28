"""LEARNER-SCALE: pipeline/rl_royale.py = the shared working copy minus the OTHER workers' uncommitted hunks (GB-DECOY's
barrel_decoy_sim), i.e. HEAD + only my hunks -> OUT (for pod tests and the commit).    python scale_mine.py OUT
Each removal must match exactly once; a stale pattern fails loudly (re-check the shared file then)."""
import re
import subprocess
import sys

out = sys.argv[1]
raw = open("pipeline/rl_royale.py", "rb").read()
crlf = b"\r\n" in raw
s = raw.decode("utf-8").replace("\r\n", "\n")
head = subprocess.run(["git", "show", "HEAD:pipeline/rl_royale.py"], capture_output=True, check=True).stdout.decode("utf-8")
cuts = [
    (r"\ndef barrel_decoy_sim_cfg\(cfg: dict\) -> bool:\n.*?    return True\n\n", "\n", re.S),
    (r"        barrel_decoy_sim_cfg\(cfg\) [^\n]*\n", "", 0),
    (r'"micro_batch",\n\s+"barrel_decoy_sim"\)', '"micro_batch")', 0),
]
if "barrel_decoy_sim" in head:
    cuts = []                                                 # landed in HEAD meanwhile: nothing to strip
for pat, rep, fl in cuts:
    s, n = re.subn(pat, rep, s, flags=fl)
    assert n == 1, (pat, n)
assert "barrel_decoy" not in s or "barrel_decoy" in head
open(out, "w", encoding="utf-8", newline="\r\n" if crlf else "\n").write(s)
