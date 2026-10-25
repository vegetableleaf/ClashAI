"""Memory skew probe (lead 10-25, Plan A S2 gap): gap.py's ``--worker-all16`` (one plain SIM eval chunk, the D3 live stack)
plus per-match dumps of the learner's match memory. Read-only hooks; the decisions change only in SKEW_MODE=empty.

    SKEW_MODE=real|empty|none SKEW_DUMP=DIR [SKEW_BASE=base.pt] python skew_worker.py --worker-all16 <gap worker args>

SKEW_MODE  real  = unchanged decisions; per learner decision also logs gate p / card probs / the top card's cell of the SAME
                   model with an EMPTY memory and of SKEW_BASE (no memory) on the same row (extra no_grad forwards)
           empty = the memory model decides with an EMPTY memory (match_memory.empty_rows) at every decision; the real
                   memory is still built (and dumped)
           none  = unchanged (the base arm)
           shadow = the BASE (SKEW_BASE) decides every learner decision (its outputs are returned); the memory model
                   is evaluated on the base trajectory with the memory built from it (diag as in real)
SKEW_DUMP  one pickle per match: the learner's MatchMemory (table, samples, plays, tower events), env.public_plays (truth),
           own ability events, the match row and the per-decision diag."""
import os
import pickle
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get('SKEW_GAP', '/workspace/cb_mem/scratchpad/gauntlet/L74/gap'))
import gap  # noqa: E402  (puts the repo + livecal on sys.path)
import numpy as np  # noqa: E402
import torch  # noqa: E402
from pipeline import e1_eval as E, match_memory as MM, search_s0 as S  # noqa: E402

MODE, DUMP = os.environ.get('SKEW_MODE', 'none'), os.environ.get('SKEW_DUMP')
if MODE not in ('real', 'empty', 'none', 'shadow'):
    raise SystemExit(f'SKEW_MODE {MODE!r}')
DIAG, NOW, BASE = [], {}, []

_memory0 = E.Match._memory


def _memory(self, policy, deck):
    f = _memory0(self, policy, deck)
    NOW.update(t=int(self._cur[0]), deck=np.asarray(deck).copy())
    if MODE == 'empty':
        f = {k: v[0] for k, v in MM.empty_rows(1, getattr(policy.model.mem, 'version', 'v1')).items()}
    return f


E.Match._memory = _memory
_fb0 = E.GenPolicy.forward_batch


def _sm(x):
    x = x.double()
    return torch.softmax(x, -1).cpu().numpy() if torch.isfinite(x).any() else np.zeros(x.shape[-1])


def forward_batch(self, rows, device='cpu'):
    out = _fb0(self, rows, device)
    if MODE not in ('real', 'shadow') or getattr(self.model, 'mem', None) is None or len(rows) != 1:   # 1 row
        return out
    if not BASE:
        BASE.append(E.load_policy(os.environ['SKEW_BASE'])[0])
    emp = {k: v[0] for k, v in MM.empty_rows(1, getattr(self.model.mem, 'version', 'v1')).items()}
    var = {'m': out, 'e': _fb0(self, [dict(rows[0], **emp)], device), 'b': _fb0(BASE[0], rows, device)}
    top = int(torch.argmax(out[1]['card'][0]))
    d, lc = {'t': NOW.get('t')}, {}
    with torch.no_grad():
        for k, (enc, h, p, _) in var.items():
            lc[k] = torch.log_softmax((BASE[0] if k == 'b' else self).cell_logits(enc, torch.tensor([top]))[0].double(), -1)
            d.update({'p' + k: float(p[0]), 'card' + k: _sm(h['card'][0]), 'cell' + k: int(torch.argmax(lc[k]))})
        for a, b in (('m', 'b'), ('e', 'b'), ('m', 'e')):    # KL(a || b) of the top card's cell distribution
            d[f'klcell_{a}{b}'] = float((lc[a].exp() * (lc[a] - lc[b])).sum())
    DIAG.append(d)
    if MODE == "shadow":                                  # the BASE decides; the memory model is only evaluated
        return var["b"]
    return out


E.GenPolicy.forward_batch = forward_batch
_play0 = S.Runner.play


def play(self, arm, m, deadline=None):
    DIAG.clear()
    row = _play0(self, arm, m, deadline)
    L = m.learner
    if DUMP and getattr(L, 'mem', None) is not None:
        mm = L.mem
        rec = dict(mode=MODE, row=row, side=L.side, deck=NOW.get('deck'), gid=L._mem_gid, table=mm.table(L._mem_gid),
                   t=list(mm.t), hp=list(mm.hp), alive=list(mm.alive), el=list(mm.el), plays=list(mm.plays),
                   tower_ev=list(mm.tower_ev), late=mm.late, truth=[dict(p) for p in getattr(m.env, 'public_plays', [])],
                   abil=[dict(e) for e in getattr(m.env, 'own_ability_events', [])], diag=list(DIAG))
        chunk = Path(sys.argv[sys.argv.index('--out') + 1]).name
        Path(DUMP).mkdir(parents=True, exist_ok=True)
        with open(Path(DUMP) / f'{chunk}_{row["seed"]}.pkl', 'wb') as fh:
            pickle.dump(rec, fh)
    return row


S.Runner.play = play

if __name__ == '__main__':
    raise SystemExit(gap.worker_all16())
