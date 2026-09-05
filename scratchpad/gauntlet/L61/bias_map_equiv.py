"""Equivalence check for the cell_bias_map change: an old checkpoint (no key) must load strictly and
produce bit-identical outputs to the pre-change model (git stash of model.py is not needed: the zero map
adds 0.0 exactly, so we compare against the same forward with the parameter zeroed vs. the saved outputs
of the ORIGINAL file, which we import from git show HEAD:...)."""
import subprocess, importlib.util, sys, torch
from pathlib import Path
ROOT = Path("C:/Users/benpe/ClashBot/icebow")
src = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:icebow/src/clashrl/model.py"], capture_output=True, text=True, check=True).stdout
old_p = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L61/_model_old.py"); old_p.write_text(src, encoding="utf-8")
spec = importlib.util.spec_from_file_location("model_old", old_p); old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
sys.path.insert(0, str(ROOT / "src"))
from clashrl.model import PolicyNet as New
ck = torch.load(ROOT / "data" / "bench" / sys.argv[1], map_location="cpu")
kw = dict(in_ch=int(ck["in_ch"]), n_cards=int(ck["n_cards"]), n_cells=int(ck["n_cells"]), threat_dim=int(ck["threat_dim"]))
a = old.PolicyNet(**kw); a.load_state_dict(ck["model"]); a.eval()
b = New(**kw); b.load_state_dict(ck["model"]); b.eval()          # strict load of a keyless checkpoint
assert "cell_bias_map" in b.state_dict()
torch.manual_seed(0)
x = torch.rand(4, kw["in_ch"], 96, 64); hand = torch.zeros(4, kw["n_cards"]); hand[:, :4] = 1
nxt = torch.zeros(4, kw["n_cards"]); nxt[:, 5] = 1; elx = torch.rand(4, 1); thr = torch.rand(4, kw["threat_dim"])
with torch.no_grad():
    za, ca, la = a.forward_parts(x, hand, nxt, elx, thr); zb, cb, lb = b.forward_parts(x, hand, nxt, elx, thr)
print("z equal", torch.equal(za, zb), "cards equal", torch.equal(ca, cb), "cells equal", torch.equal(la, lb), "max|d|", (la - lb).abs().max().item())
# and the compat path
dropped = New.load_compat(New(**kw), ck["model"]); print("load_compat dropped:", dropped)
# round trip: new checkpoint carries the key; nonzero map changes cells only
with torch.no_grad(): b.cell_bias_map[0, 100] = 3.0
sd = b.state_dict(); c = New(**kw); c.load_state_dict(sd)
with torch.no_grad(): zc, cc, lc = c.forward_parts(x, hand, nxt, elx, thr)
print("nonzero map: cards equal", torch.equal(ca, cc), "cell[0,100] moved", (lc[:, 0, 100] - la[:, 0, 100]).abs().min().item() > 0, "other cells equal", torch.equal(lc[:, 1:], la[:, 1:]))
