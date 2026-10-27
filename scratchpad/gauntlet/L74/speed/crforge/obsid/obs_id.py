"""S3b-3a (plan1026 Pillar 4): byte identity of the Java observation builders against the production GenModel row.

At EVERY decision of facade-driven self-play (ROYALE_ENGINE=crforge, e1_eval.run_selfplay_batch, CLXIII on both seats,
search_s0.live_cfg + action delay 26 + feature_version 6, as F1's accept_f1 obs), the hook on ``e1_eval.Match.gen_row``
takes (1) the production row (``prepare`` + ``gen_row``, unchanged) and (2) every builder in ``BUILDERS`` run on the
SAME facade battle at the same tick, and compares each GenModel key byte for byte (dtype, shape, bytes). A key no
builder produces is NOT_PORTED. Per key: rows, rows equal, rows that differ at each last-axis index, first diffs.

Adding a port = one function in BUILDERS returning {key: array in the production dtype}; nothing else changes.

usage (pod 32657): obsid/run.sh [--n 56] [--set extrapolate_ticks=0 ...]   (compiles, then runs this file)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RL = Path(os.environ.get("OBSID_RL", "/workspace/f1/rl"))       # the facade work tree (pipeline/ at HEAD)
os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
os.environ["ROYALE_ENGINE"] = "crforge"
sys.path[:0] = ["/workspace/cfspeed/pylib", str(RL)]

import jpype  # noqa: E402
import numpy as np  # noqa: E402

DECKS = Path("/workspace/cfspeed/decks.tsv")
CLXIII = "/workspace/f1/models/succ48_o_s91_u0075_grafted.pt"
SFX = {0: "", 1: "@evolution", 2: "@hero"}
OPP_EL = 5            # sc index of the opponent's elixir: the Java builder reads the TRUTH there; replaced, never logged
NO_VALUES = {"sc"}    # keys whose first diffs record indices only (sc carries elixir)


def start_jvm(build: Path) -> None:
    """The facade's JVM (crforge_core._jvm skips startJVM when one runs) with the builders' classes beside CfCore."""
    from pipeline import crforge_core as cc
    cp = sorted(str(p) for p in cc.LIB.glob("*.jar")) + [str(build)]
    jpype.startJVM(f"-Xmx{os.environ.get('CRFORGE_XMX', '4g')}", classpath=cp, convertStrings=True)


def census():
    out = []
    for line in DECKS.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            f = line.split("\t")
            out.append((f[3].split(","), [int(v) for v in f[4].split(",")]))
    return out


# ---------------------------------------------------------------------------------------------------- builders
class JavaMain:
    """CfSpeed.Match.obs (S3's P3 builder) on the facade battle: tok / mask / sc / unit_form. The name tables are
    filled from body_map.json (a body's first entry) and the facade's spell objects (that card's vocab spell id).
    ponytail: name-only lookup, so the 9 by-root names take their first entry; the facade's root-play table in Java
    is the upgrade."""

    def __init__(self):
        from pipeline import crforge_core as cc
        J = cc._jvm()
        self.cc, self.tables = cc, J["tables"]
        self.CfSpeed, self.Bind = jpype.JClass("CfSpeed"), jpype.JClass("CfObsBind")
        self.names = self.CfSpeed.Names()
        self.bm = json.loads(cc.BODY_MAP.read_text())
        self.spell_card = {k: v[0] for k, v in cc.spell_objects().items()}
        self.match = {}                                   # id(core) -> CfSpeed.Match reading that core's battle
        BB = jpype.JClass("java.nio.ByteBuffer")
        order = jpype.JClass("java.nio.ByteOrder").nativeOrder()
        self.b = {k: BB.allocateDirect(n).order(order) for k, n in
                  (("tok", 64 * 14 * 4), ("mask", 64), ("sc", 70 * 4), ("form", 64))}
        self.tokF, self.scF = self.b["tok"].asFloatBuffer(), self.b["sc"].asFloatBuffer()
        self.v = {k: np.frombuffer(memoryview(b), dt) for (k, b), dt in
                  zip(self.b.items(), (np.float32, np.uint8, np.float32, np.int8))}
        self.Int = jpype.JArray(jpype.JInt)

    def resolve(self) -> None:
        from pipeline import vocab
        for s in self.names.takeMissing():
            kind, name = s[:2], s[2:]
            if kind == "U:":
                v = self.bm.get(name)
                e = v["entries"][0] if v and not name.startswith("_") and v.get("entries") else None
                cid = -1 if e is None or e.get("vocab_id") is None else int(e["vocab_id"])
                self.names.putUnit(name, cid, int(e["form"]) if e else 0)
            else:
                card = self.spell_card.get(name)
                cid = vocab.engine_spell_id(card) if card else None
                self.names.putSpell(name, -1 if cid is None else int(cid))

    def _obs(self, m, seat):
        m.obs(seat, self.names, self.tokF, 0, self.b["mask"], 0, self.scF, 0, self.b["form"], 0)

    def __call__(self, s) -> dict:
        from pipeline.dataset_gen import SC_SLOT_COLS
        core = s.env.core
        m = self.match.get(id(core))
        if m is None:
            m = self.match[id(core)] = self.CfSpeed.Match(self.tables)
        # crforge deck index = the env's deal order (RoyaleSelfPlayEnv.deal, ShuffleMode.NONE); our slots index env.decks
        slot_of = {i: slot for slot, i in s.deck_index_of_slot.items()}
        decks, deal = s.env.decks[s.side], s.env.deal[s.side]
        inv = [slot_of.get(list(decks).index(n), 8) for n in deal]
        self.Bind.bind(m, core._cf, int(s.side), self.Int(inv))
        self._obs(m, int(s.side))
        if self.names.missing.size():                     # new names: fill the tables, build again
            self.resolve()
            self._obs(m, int(s.side))
        sc = self.v["sc"].copy()
        sc[OPP_EL] = -1.0                                 # the truth is never compared or logged (port: the counter)
        sc_pre = sc.copy()
        sc[SC_SLOT_COLS] = 0.0                            # GenPolicy.row's zeroing (the key the model reads)
        mask = self.v["mask"].copy()
        assert mask.max() <= 1
        return {"tok": self.v["tok"].reshape(64, 14).copy(), "mask": mask.astype(bool), "sc": sc,
                "unit_form": self.v["form"].copy(), "_sc_prepare": sc_pre, "_tick": int(core._cf.tick())}


BUILDERS: list = []   # filled in main (they need the JVM); a later ticket appends one builder per ported key


# ---------------------------------------------------------------------------------------------------- comparison
class Report:
    def __init__(self, first: int):
        self.first, self.keys, self.rows, self.tick_mismatch = first, {}, 0, 0

    def _k(self, key):
        return self.keys.setdefault(key, dict(rows=0, equal=0, not_ported=0, dtype_shape_diff=0, per_index=None,
                                              first_diffs=[]))

    def add(self, s, prod: dict, java: dict, prod_sc_prepare) -> None:
        self.rows += 1
        tick = int(s._cur[0])
        if java.pop("_tick", tick) != tick:
            self.tick_mismatch += 1
        aux = {"_sc_prepare": np.array(prod_sc_prepare, copy=True)}
        aux["_sc_prepare"][OPP_EL] = -1.0                 # both sides' slot 5 out of this aux check (see OPP_EL)
        for key in sorted(set(prod) | {k for k in java if not k.startswith("_")}) + ["_sc_prepare"]:
            a = aux[key] if key in aux else prod.get(key)
            r = self._k(key)
            r["rows"] += 1
            if key not in java:
                r["not_ported"] += 1
                continue
            b = java[key]
            a, b = np.asarray(a), np.asarray(b)
            if a.dtype != b.dtype or a.shape != b.shape:
                r["dtype_shape_diff"] += 1
                if len(r["first_diffs"]) < self.first:
                    r["first_diffs"].append(dict(tag=s.tag, tick=tick, prod=[str(a.dtype), a.shape],
                                                 java=[str(b.dtype), b.shape]))
                continue
            if a.tobytes() == b.tobytes():
                r["equal"] += 1
                continue
            a, b = np.atleast_1d(a), np.atleast_1d(b)
            u = f"u{a.itemsize}"                       # element bits, so -0.0 vs 0.0 and NaNs count as bytes do
            ne = np.ascontiguousarray(a).view(u) != np.ascontiguousarray(b).view(u)
            per = ne.reshape(-1, ne.shape[-1]).any(0).astype(np.int64)
            r["per_index"] = per if r["per_index"] is None else r["per_index"] + per
            if len(r["first_diffs"]) < self.first:
                d = dict(tag=s.tag, side=int(s.side), tick=tick, index=np.argwhere(ne)[:6].tolist())
                if key not in NO_VALUES and not key.startswith("_sc"):
                    rows = sorted({int(i[0]) for i in np.argwhere(ne)[:3]}) if a.ndim > 1 else []
                    d.update(prod=[a[i].tolist() for i in rows] if rows else a.tolist()[:16],
                             java=[b[i].tolist() for i in rows] if rows else b.tolist()[:16])
                r["first_diffs"].append(d)

    def result(self) -> dict:
        out = {}
        for k, r in self.keys.items():
            st = ("NOT_PORTED" if r["not_ported"] == r["rows"] else
                  "IDENTICAL" if r["equal"] == r["rows"] else "DIFF")
            per = r["per_index"]
            out[k] = dict(status=st, **{x: r[x] for x in ("rows", "equal", "not_ported", "dtype_shape_diff")},
                          rows_diff_at_last_axis_index=({int(i): int(per[i]) for i in np.flatnonzero(per)}
                                                        if per is not None else {}),
                          first_diffs=r["first_diffs"])
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=56, help="matches (both seats CLXIII): about 900 seat-rows each")
    ap.add_argument("--inflight", type=int, default=8)
    ap.add_argument("--threads", type=int, default=4, help="torch threads")
    ap.add_argument("--set", action="append", default=[], help="cfg override k=v (JSON value), both seats")
    ap.add_argument("--min-rows", type=int, default=38400)
    ap.add_argument("--first-diffs", type=int, default=5)
    ap.add_argument("--build", default=str(HERE / "build"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    start_jvm(Path(a.build))
    import torch
    torch.set_num_threads(a.threads)
    from pipeline import e1_eval as E
    from pipeline import search_s0 as S
    from pipeline.royale_env import RoyaleSelfPlayEnv
    from pipeline.royale_runtime import ENGINE

    assert ENGINE == "crforge", ENGINE
    BUILDERS.append(JavaMain())
    model, info = E.load_policy(CLXIII)
    cfg = S.live_cfg(0.5, info["grid"])
    cfg.update(action_delay_ticks=26, feature_version=6)
    over = {k: json.loads(v) for k, v in (x.split("=", 1) for x in a.set)}
    cfg.update(over)
    rep = Report(a.first_diffs)
    orig = E.Match.gen_row

    def gen_row(self, policy):
        row = orig(self, policy)
        java = {}
        for b in BUILDERS:
            java.update(b(self))
        rep.add(self, row, java, self._obs[2])
        return row

    E.Match.gen_row = gen_row
    jobs = []
    for i, (d1, f1) in enumerate(census()[: a.n]):
        jobs.append((i, {"tag": f"obsid{i}", "seed": 5000 + i, "learner_side": i % 2,
                         "learner_deck": list(E.ICEBOW_ENGINE_DECK), "opp_deck": [n + SFX[f] for n, f in zip(d1, f1)],
                         "opp": {"id": "clxiii"}}, 0))
    envs, done, skips, t0 = [], [], [], time.time()

    def make():
        envs.append(RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck"))
        return envs[-1]

    def on_result(r):
        done.append(r["tag"])
        print(json.dumps(dict(tag=r["tag"], decisions=r.get("decisions"), seat_rows=rep.rows,
                              wall_s=round(time.time() - t0))), flush=True)

    E.run_selfplay_batch(make, model, {"clxiii": (model, dict(cfg))}, jobs, cfg, min(a.n, a.inflight), on_result,
                         on_skip=lambda spec, exc: skips.append((spec["tag"], repr(exc))))
    keys = rep.result()
    core4 = ("tok", "mask", "sc", "unit_form")
    out = dict(
        ticket="S3b-3a", matches=len(done), skipped=skips, seat_rows=rep.rows, tick_mismatch=rep.tick_mismatch,
        wall_s=round(time.time() - t0, 1), cfg_overrides=over, feature_version=cfg["feature_version"],
        gen_row_keys=list(E.gen_row_keys(model.model)),
        acceptance=dict(min_rows=a.min_rows, rows_ok=rep.rows >= a.min_rows,
                        core_keys_identical={k: keys.get(k, {}).get("status") == "IDENTICAL" for k in core4}),
        status_by_key={k: v["status"] for k, v in sorted(keys.items())}, keys=keys,
        stamp=envs[0].core.card_table_stamp() if envs else None,
        note=("prod = e1_eval prepare + gen_row; java = BUILDERS on the same facade battle and tick. Keys starting '_' "
              "are aux checks, not GenModel keys: _sc_prepare = prepare()'s sc before GenPolicy.row zeroes the hand "
              f"one-hots. sc[{OPP_EL}] (opponent elixir) of the Java builder is the engine truth: replaced by -1, "
              "never compared as equal and never logged."))
    Path(a.out).write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("seat_rows", "tick_mismatch", "acceptance", "status_by_key")}, default=str))


if __name__ == "__main__":
    main()
