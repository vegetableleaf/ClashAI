"""Critic lens 2: is 'hold the owner's six at 60% of draws' really incompatible with S2's core boost?
decks_hist.json keeps the sides of the six and of non-core decks unchanged (mk_hist_decks.py), so the control's mass can
be reconstructed from the six's 60.0% control share. Then: the core presence reachable with the six held at 60%."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "weekend"))
import archetypes as A
d = json.load(open(sys.argv[1], encoding="utf-8"))["decks"]
CORE = {"megaknight", "witch", "firecracker", "hogrider", "electrogiant", "elixirgolem", "goldenknight"}
s = [float(x["sides"]) for x in d]
six = [A.unfavorable(A.classify(x["engine"])) for x in d]
core = [bool(CORE & {A.canon(n) for n in x["engine"]}) for x in d]
S6 = sum(v for v, a in zip(s, six) if a); S6c = sum(v for v, a, c in zip(s, six, core) if a and c)
SR = sum(v for v, a, c in zip(s, six, core) if not a and not c); SCh = sum(v for v, a, c in zip(s, six, core) if not a and c)
SC0 = S6 / 0.60 - S6 - SR                                  # control mass of core-not-six decks
T0, Th = S6 + SR + SC0, S6 + SR + SCh
print(f"control: six {100*S6/T0:.1f}%  core-in-six {100*S6c/T0:.1f}%  core-not-six {100*SC0/T0:.1f}%  rest {100*SR/T0:.1f}%  any core {100*(S6c+SC0)/T0:.1f}%")
print(f"S2 file: six {100*S6/Th:.1f}%  core-in-six {100*S6c/Th:.1f}%  core-not-six {100*SCh/Th:.1f}%  rest {100*SR/Th:.1f}%  any core {100*(S6c+SCh)/Th:.1f}%")
for f in (0.5, 0.75, 1.0):                                  # move a fraction f of the 'rest' mass onto core-not-six decks
    sc = SC0 + f * SR; sr = (1 - f) * SR
    print(f"six held at 60%, {int(100*f)}% of rest moved to core-not-six: any core {100*(S6c+sc)/T0:.1f}%, rest {100*sr/T0:.1f}%")
