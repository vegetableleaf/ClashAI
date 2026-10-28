"""D2-T2 item 2a, first check: obs_id's Java builders (speed/crforge/obsid) compared with the production GenModel row
INSIDE rl_royale's actor processes (the production config's self-play rollouts), per key, byte for byte. Loaded by
hook/sitecustomize.py under D2T2_OBSCHECK=outdir; the Java classes come from CRFORGE_FACADE_BUILD (compiled there with
CfCore by obscheck.sh). Writes outdir/<pid>.json after every run_selfplay_batch call.

Which rows: every Match.gen_row call (both seats, learner and league opponents) whose policy is a feature-version >= 4
GenPolicy with the learner's card vocabulary (the builders hold one gid table); other rows are counted, not compared.
Only the keys production built for that row are compared. A builder exception is counted with its repr (the actor
goes on; the production row is untouched)."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

OUT = Path(os.environ["D2T2_OBSCHECK"])
sys.path.insert(0, os.environ["OBSID_DIR"])


def install(E) -> None:
    st = dict(B=None, rep=None, skip={}, err={}, gid=None, t0=time.time(), batches=0)
    run_sp, gen_row0, land0 = E.run_selfplay_batch, E.Match.gen_row, E.Match._land

    def setup(model):
        import obs_id as O
        main = O.JavaMain()
        main.opp_spells, main.gid = True, model.gid
        ident = O.JavaIdent(model)
        st["B"] = [main, ident, O.JavaCue(main, E), O.JavaPub(main, model)]
        st["ident"], st["rep"], st["gid"], st["O"] = ident, O.Report(5), dict(model.gid), O

    def count(d, k):
        d[k] = d.get(k, 0) + 1

    def run_selfplay_batch(make_env, model, *a, **kw):
        if st["B"] is None:
            setup(model)
        try:
            return run_sp(make_env, model, *a, **kw)
        finally:
            st["batches"] += 1
            dump()

    def _land(self, p, d, land, landed, cur=None):
        acc = land0(self, p, d, land, landed, cur)
        if acc and st["B"] is not None:
            try:
                st["ident"].played(self, d)
            except Exception as e:                          # noqa: BLE001 -- a check never stops the actor
                count(st["err"], "played " + repr(e)[:200])
        return acc

    def gen_row(self, policy):
        row = gen_row0(self, policy)
        if st["B"] is None:
            count(st["skip"], "before setup")
        elif getattr(policy.model, "feature_version", 1) < 4:
            count(st["skip"], "feature_version < 4")
        elif dict(policy.gid) != st["gid"]:
            count(st["skip"], "other card vocabulary")
        else:
            java = {}
            try:
                for b in st["B"]:
                    if b is st["B"][2] and "cue" not in row:     # JavaCue: only where production built a cue
                        continue
                    java.update(b(self))
            except Exception:                               # noqa: BLE001
                count(st["err"], traceback.format_exc(limit=3)[-400:])
                return row
            java.pop("_nospell_opp", None)
            java = {k: v for k, v in java.items() if k in row or k.startswith("_")}
            st["rep"].add(self, dict(row), java, self._obs[2])
        return row

    def dump():
        rep = st["rep"]
        keys = rep.result() if rep is not None else {}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / f"{os.getpid()}.json").write_text(json.dumps(dict(
            pid=os.getpid(), batches=st["batches"], wall_s=round(time.time() - st["t0"]),
            seat_rows=rep.rows if rep else 0, tick_mismatch=rep.tick_mismatch if rep else 0,
            diag=rep.diag if rep else {}, skipped=st["skip"], errors=st["err"],
            status_by_key={k: v["status"] for k, v in sorted(keys.items())}, keys=keys), default=str))

    E.run_selfplay_batch, E.Match.gen_row, E.Match._land = run_selfplay_batch, gen_row, _land
