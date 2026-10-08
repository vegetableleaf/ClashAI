"""Patch the ISOLATED VM pipeline copy (~/econ2/repo/pipeline, already patched by ../loss_review/econ_sim_patch.py) so the
LEARNER's GenModel input row at every decision is pickled (env LR_DUMP_DIR; unset = unchanged). The jsonl row gets
'lr_rows_file'. For the econ2 input-swap diagnostic only.   ~/venv/bin/python dump_patch.py ~/econ2/repo/pipeline"""
import sys, pathlib

P = pathlib.Path(sys.argv[1])


def sub(path, old, new):
    t = (P / path).read_text()
    if new in t: return
    assert t.count(old) == 1, (path, old[:60], t.count(old))
    (P / path).write_text(t.replace(old, new))


sub("e1_eval.py", "class GenPolicy:\n",
    "def _lr_dump_rows(m):\n"
    "    import os, pickle, uuid\n"
    "    f = os.path.join(os.environ['LR_DUMP_DIR'], f'rows_{uuid.uuid4().hex}.pkl')\n"
    "    pickle.dump(m.lr_rows, open(f, 'wb')); return f\n\n\n"
    "class GenPolicy:\n")
sub("e1_eval.py", "                            round(float(_me.get('elixir_exact', -1)), 3), None if view.opp_elixir is None else round(float(view.opp_elixir), 3)])\n",
    "                            round(float(_me.get('elixir_exact', -1)), 3), None if view.opp_elixir is None else round(float(view.opp_elixir), 3)])\n"
    "        if cfg.get('dump_rows') and getattr(self, '_gen_row', None) is not None:\n"
    "            if not hasattr(self, 'lr_rows'): self.lr_rows = []\n"
    "            self.lr_rows.append((int(tick), round(float(p), 5), {k: np.array(v) for k, v in self._gen_row.items()}))\n")
sub("e1_eval.py", "**({'lr_dec': self.lr_dec} if hasattr(self, 'lr_dec') else {}),",
    "**({'lr_dec': self.lr_dec} if hasattr(self, 'lr_dec') else {}), **({'lr_rows_file': _lr_dump_rows(self)} if hasattr(self, 'lr_rows') else {}),")
sub("search_s0.py", "                **({'lr_dec': r['lr_dec']} if 'lr_dec' in r else {}),",
    "                **({'lr_dec': r['lr_dec']} if 'lr_dec' in r else {}),\n                **({'lr_rows_file': r['lr_rows_file']} if 'lr_rows_file' in r else {}),")
sub("search_s0.py", "    learner_cfg['decide_every'] = int(__import__('os').environ.get('LR_DECIDE_EVERY', '10'))\n",
    "    learner_cfg['decide_every'] = int(__import__('os').environ.get('LR_DECIDE_EVERY', '10'))\n"
    "    learner_cfg['dump_rows'] = bool(__import__('os').environ.get('LR_DUMP_DIR'))\n")
print("patched", P)
