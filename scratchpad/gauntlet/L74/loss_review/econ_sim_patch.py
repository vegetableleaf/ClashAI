"""Patch an ISOLATED copy of the VM pipeline (~/loss_review/repo/pipeline, never ~/ClashBot) for the econ-gap SIM runs.
Adds, all opt-in / default-neutral:
  * learner decision log 'lr_dec': [tick, p_gate, play, why, view elixir (model input, +26 forecast), raw elixir now, view opp elixir]
  * telemetry 'lr_frames' every 10 ticks: [tick, my elixir, [[card, x, y, hp, id] enemy bodies], [[side, kind, x, y, hp] towers]]
    and 'lr_plays': every accepted play/ability [tick, side, card, elixir at deploy (own side only), ability]
  * env LR_OPP_BIAS (float, default 0): added to the opponent-elixir counter the model sees (live counter over-reads +0.34).
Run on the VM:  ~/venv/bin/python econ_sim_patch.py ~/loss_review/repo/pipeline"""
import sys, pathlib

P = pathlib.Path(sys.argv[1])


def sub(path, old, new, count=1):
    t = (P / path).read_text()
    if new in t: return                                   # idempotent
    assert t.count(old) == count, (path, old[:60], t.count(old))
    (P / path).write_text(t.replace(old, new))


sub("e1_eval.py", "opp_elixir=self.public.estimate_at(tick+h) if self.opp_mode else None))",
    "opp_elixir=(min(10.0, max(0.0, self.public.estimate_at(tick+h) + float(__import__('os').environ.get('LR_OPP_BIAS', '0')))) if self.opp_mode else None)))")
sub("e1_eval.py", "        self.p_gates.append(p)\n",
    "        self.p_gates.append(p)\n"
    "        if not hasattr(self, 'lr_dec'): self.lr_dec = []\n"
    "        _me = next((q for q in (self.state or {}).get('players', []) if q.get('side') == self.side), {})\n"
    "        self.lr_dec.append([int(tick), round(float(p), 4), bool(d['play']), d.get('why'), round(float(view.my_elixir), 3),\n"
    "                            round(float(_me.get('elixir_exact', -1)), 3), None if view.opp_elixir is None else round(float(view.opp_elixir), 3)])\n")
sub("e1_eval.py", "\"unmapped\": sorted(self.unmapped), \"wall_s\": round(time.perf_counter() - self.t0, 1),",
    "\"unmapped\": sorted(self.unmapped), \"wall_s\": round(time.perf_counter() - self.t0, 1), **({'lr_dec': self.lr_dec} if hasattr(self, 'lr_dec') else {}),")
sub("search_s0.py", "                **({'behaviour': r['behaviour']} if 'behaviour' in r else {}),",
    "                **({'behaviour': r['behaviour']} if 'behaviour' in r else {}),\n                **({'lr_dec': r['lr_dec']} if 'lr_dec' in r else {}),")
sub("behaviour_telemetry.py", "\n        return out",
    "\n"
    "        out['lr_frames']=[[f['tick'],round(f['elixir'].get(side,-1),3),[[b['card'],b['x'],b['y'],b['hp'],b['id']] for b in f['bodies'] if b['side']!=side and b['hp']>0],\n"
    "                           [[t['side'],t['kind'],t['x'],t['y'],t['hp']] for t in f['towers']]] for f in self.frames if f['tick']%10==0]\n"
    "        out['lr_plays']=[[q['tick'],q['side'],q['card'],q.get('elixir'),bool(q['ability'])] for q in self.plays]\n"
    "        return out")
# env LR_DECIDE_EVERY (default 10): the LEARNER's decision cadence only (live_cfg is shared with the opponent, so it is not touched)
sub("search_s0.py", "    learner_cfg = live_cfg(args.get('tau_plain', TAU_PLAIN), gi['grid'], dev)\n",
    "    learner_cfg = live_cfg(args.get('tau_plain', TAU_PLAIN), gi['grid'], dev)\n"
    "    learner_cfg['decide_every'] = int(__import__('os').environ.get('LR_DECIDE_EVERY', '10'))\n")
print("patched", P)
