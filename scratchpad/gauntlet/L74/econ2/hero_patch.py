"""Patch the ISOLATED VM pipeline copy (~/econ2/repo_hero/pipeline; never ~/ClashBot) for the econ2 Hero IW SIM arms.
env LR_HERO_IW (learner only; unset = byte-identical):
  'unknown' : the learner's GenModel row shows my Ice Wizard as the HERO form (hand / next / deck / own history / slot
              forms 2, as live) and, while my Ice Wizard is alive, a hero ability-controller token in the live pre-fix
              encoding ('readiness unknown': ready_known 0, charges -1, cooldown -1)                     -> arm B
  'known'   : the same with the token computed by own_ability.tokens from my own deploy history + the catalog
              (the parity fix: ready_known 1; SIM never presses the ability, so after deploy it reads ready / 1 charge) -> arm C
The engine still plays the base Ice Wizard: only the observation changes.  ~/venv/bin/python hero_patch.py <pipeline dir>"""
import sys, pathlib

P = pathlib.Path(sys.argv[1])


def sub(path, old, new):
    t = (P / path).read_text()
    if new in t: return
    assert t.count(old) == 1, (path, old[:60], t.count(old))
    (P / path).write_text(t.replace(old, new))


sub("e1_eval.py", "class GenPolicy:\n",
    "def _hero_iw_row(m, policy, mode):\n"
    "    from pipeline.own_ability import tokens\n"
    "    from pipeline import vocab\n"
    "    iw = policy.gid.get('ice-wizard'); row = m._gen_row\n"
    "    if iw is None: return\n"
    "    for kc, kf in (('hand_card', 'hand_form'), ('deck_card', 'deck_form'), ('slot_card', 'slot_form')):\n"
    "        row[kf] = np.where(row[kc] == iw, 2, row[kf]).astype(row[kf].dtype)\n"
    "    if int(row['next_card']) == iw: row['next_form'] = np.int64(2)\n"
    "    row['past'] = row['past'].copy(); row['past'][:, 1] = np.where(row['past'][:, 0] == iw, 2, row['past'][:, 1])\n"
    "    tick = int(getattr(m, '_view_tick', m._cur[0]))\n"
    "    n = sum(1 for e in ((m.state or {}).get('entities') or []) if isinstance(e, dict) and e.get('side') == m.side and e.get('hp', 0) > 0\n"
    "            and vocab.base_key(vocab.engine_key(e.get('name', '')) or '') == 'ice_wizard')\n"
    "    if not n: m._iw_born = None; return\n"
    "    if getattr(m, '_iw_born', None) is None: m._iw_born = tick\n"
    "    ev = [dict(card='ice-wizard', tick=m._iw_born - 1, accepted=True, ability=False)] if mode == 'known' else []\n"
    "    tok = tokens([('ice-wizard', 2, n, -1., 0.)], policy.gid, ev, tick)[0]\n"
    "    oa = row['own_ability'] = np.array(row['own_ability'], copy=True); k = int((np.abs(oa).sum(-1) > 0).sum())\n"
    "    if k < len(oa): oa[k] = tok\n\n\n"
    "class GenPolicy:\n")
sub("e1_eval.py", "            self._gen_row.update(sim_v3_features(self, policy))\n",
    "            self._gen_row.update(sim_v3_features(self, policy))\n"
    "        if self.cfg.get('hero_iw') in ('unknown', 'known'):\n"
    "            _hero_iw_row(self, policy, self.cfg['hero_iw'])\n")
sub("search_s0.py", "    learner_cfg['decide_every'] = int(__import__('os').environ.get('LR_DECIDE_EVERY', '10'))\n",
    "    learner_cfg['decide_every'] = int(__import__('os').environ.get('LR_DECIDE_EVERY', '10'))\n"
    "    learner_cfg['hero_iw'] = __import__('os').environ.get('LR_HERO_IW')\n")
print("patched", P)
