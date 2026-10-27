"""S3b-4 (plan1026 Pillar 4b): core-s per match of the FULL Java observation inside the crforge loop (CfLoop: S3's Rollout
path on the F1 facade, every ported builder on, at the live cfg), plus engine core-s per match.

Like cf_loop.py: C cohorts of N facade matches on T Java threads each, served in turn by this process (the policy is a
Java-side stand-in: CfLoop's random legal play, p 0.3 per decision, + a rare ability press). Measured over a window
after a warm-up: process CPU (all threads: engine, obs, GC, JIT, this thread), the pool threads' CPU split into engine
(acts + 10 ticks + resets) and obs (every builder for both seats), matches, rows. --no-obs = the engine-only baseline.
Tables: per cohort, filled between its rounds from production code (obs_id.JavaMain / JavaPub resolvers; the detector
body keys from a raw()-shaped entity of the key, as RoyaleSelfPlayEnv.raw would give it).

usage (pod 30408): OBSID_RL=... OBSID_CLXIII=... CRFORGE_XMX=24g obsid/run_loop.sh OUT.json [--envs 2048 --cohorts 2
                   --threads 24 --warm 90 --seconds 120] [--no-obs]
"""
from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import obs_id  # noqa: E402  (sets the pipeline path, ROYALE_ENGINE=crforge)
import jpype  # noqa: E402


def proc_cpu() -> float:
    u = resource.getrusage(resource.RUSAGE_SELF)
    return u.ru_utime + u.ru_stime


def setups(n_pairs: int):
    """Per census pair (Icebow on side i % 2, as obs_id's jobs): the CfCore.reset arguments RoyaleSelfPlayEnv.reset +
    CrforgeCore.reset give (deal order names, forms, catalogue ids), captured from a real reset."""
    from pipeline import e1_eval as E
    from pipeline.royale_env import RoyaleSelfPlayEnv
    env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck")
    got = []
    orig = env.core.reset
    env.core.reset = lambda seed, setup: (got.append(setup), orig(seed, setup))
    names = {c.card_id: c.name for c in env.core.cards()}
    decks, forms, ids = [], [], []
    for i, (d1, f1) in enumerate(obs_id.census()[:n_pairs]):
        ice, opp = list(E.ICEBOW_ENGINE_DECK), [n + obs_id.SFX[f] for n, f in zip(d1, f1)]
        env.reset(*((ice, opp) if i % 2 == 0 else (opp, ice)), 5000 + i)
        s = got[-1]
        for side in (0, 1):
            ids.append([int(c) for c in s.decks[side]])
            decks.append([names[c] for c in ids[-1]])
            forms.append([int(v) for v in (s.forms[side] if s.forms else [0] * 8)])
    return env, decks, forms, ids


class Cohort:
    def __init__(self, a, tables, tmpl, env, decks, forms, ids, model):
        from pipeline.dataset_gen import card_key
        J = jpype.JClass
        JStr, JInt = jpype.JArray(jpype.JString), jpype.JArray(jpype.JInt)
        self.L = J("CfLoop")(tables, tmpl._cf, jpype.JArray(JStr)([JStr(d) for d in decks]),
                             jpype.JArray(JInt)([JInt(f) for f in forms]), jpype.JArray(JInt)([JInt(i) for i in ids]),
                             a.envs, a.threads, 10, a.extrap)
        self.L.buildObs = not a.no_obs
        self.L.pPress = a.p_press
        names = dict(env.names)
        for cid in {c for d in ids for c in d}:
            self.L.putGid(int(cid), int(model.gid[card_key(names[cid])]))
        # the table fillers of obs_id, pointed at this cohort's tables
        main = obs_id.JavaMain()
        main.names, main.keys, main.gid, main.card_names = self.L.names, self.L.keys, model.gid, names
        shim = SimpleNamespace(env=SimpleNamespace(names=names, feature_version=6), state={"projectiles": []})
        main.spell_table(shim)
        pub = obs_id.JavaPub(main, model)
        pub.T = self.L.pub
        pub.tables(shim)
        self.main, self.pub, self.names = main, pub, names
        self.jc = None
        if not a.no_cue:                                   # S3b-3f: CfCue's tables, filled by its own filler
            from pipeline import e1_eval as E
            self.jc = obs_id.JavaCue(main, E)
            self.L.cue = self.jc.T
        self.L.start()

    def fill(self) -> int:
        """Python's share between rounds: every table key the last round missed. Returns how many were filled."""
        from pipeline import royale_heroiw as heroiw, vocab
        from pipeline.dataset_gen import card_key
        from pipeline.obs_contract import catalog_card_form
        from pipeline.opp_elixir_count import _catalog_names
        from pipeline.public_observation import public_frame
        k = 0
        if self.L.names.missing.size():
            k += int(self.L.names.missing.size())
            self.main.resolve()
        for miss in self.L.keys.takeMissing():                 # JavaMain.resolve_opp on the entity raw() would give
            key, _ = str(miss).rsplit("#", 1)
            card, body, form = key.split("|")
            ent = dict(side=1, x=0.0, y=0.0, hp=1, max_hp=1, entity_id=0, name=self.names.get(int(card), card),
                       card_id=int(card), status_flags={2: 16, 1: 8}.get(int(form), 0))
            if heroiw.ENABLED and heroiw.public_identity(body) is not None:
                ent.update(name="IceWizard", public_card_id=heroiw.public_identity(body), public_form=2)
            f = public_frame({"tick": 0, "entities": [ent]}, source="sim")["entities"]
            name = _catalog_names().get(f[0]["card_id"]) if f else None
            self.L.keys.putBody(key, self.main.key_index(vocab.engine_key(name) if name else None),
                                int(catalog_card_form(f[0]["card_id"])[1]) if f else 0)
            k += 1
        if self.L.pub.missing.size():
            k += int(self.L.pub.missing.size())
            self.pub.resolve()
        if self.jc is not None and self.jc.T.missing.size():
            k += int(self.jc.T.missing.size())
            self.jc.fill()
        cyc, CP = list(self.L.pub.cyc), jpype.JClass("CfPubObj")
        if len(cyc) < int(self.L.detKeys()):
            for i in range(len(cyc), int(self.L.detKeys())):
                cyc.append(self.pub.key(card_key(str(CP.detKey(self.L.keys, i)))))
            self.L.pub.cyc = jpype.JArray(jpype.JInt)(cyc)
        return k


def snap(cs):
    s = lambda f: sum(int(getattr(c.L, f).get()) for c in cs)  # noqa: E731
    return dict(t=time.perf_counter(), cpu=proc_cpu(), py=time.thread_time(),
                **{f: s(f) for f in ("matches", "ticks", "decisions", "plays", "presses", "engineNs", "obsNs", "rows",
                                     "missOpp", "missPub", "missCue", "crashes")})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--envs", type=int, default=2048, help="matches per cohort")
    ap.add_argument("--cohorts", type=int, default=2)
    ap.add_argument("--threads", type=int, default=24, help="Java threads per cohort")
    ap.add_argument("--pairs", type=int, default=56, help="census pairs (obs_id's first --n)")
    ap.add_argument("--extrap", type=int, default=26, help="extrapolate_ticks (live cfg 26)")
    ap.add_argument("--p-press", type=float, default=0.05)
    ap.add_argument("--warm", type=float, default=90.0)
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--no-obs", action="store_true", help="engine-only baseline (no builder runs)")
    ap.add_argument("--no-cue", action="store_true", help="every builder but CfCue (the S3b-3d-era total)")
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    shas = obs_id.src_shas()
    obs_id.start_jvm(Path(a.build))
    from pipeline import crforge_core as cc
    from pipeline import e1_eval as E
    model, _ = E.load_policy(obs_id.CLXIII)
    env, decks, forms, ids = setups(a.pairs)
    cs = [Cohort(a, cc._jvm()["tables"], env.core, env, decks, forms, ids, model) for _ in range(a.cohorts)]
    for c in cs:
        c.L.stepAsync()
    t_start, win, filled = time.perf_counter(), None, dict(warm=0, window=0)
    rounds = 0
    while True:
        now = time.perf_counter()
        if win is None and now - t_start >= a.warm:
            win, rounds = snap(cs), 0
        if win is not None and now - win["t"] >= a.seconds:
            break
        for c in cs:
            c.L.await_()
            filled["window" if win else "warm"] += c.fill()
            c.L.stepAsync()
            rounds += 1
    end = snap(cs)
    for c in cs:
        c.L.await_()
    d = {k: end[k] - win[k] for k in end}
    m = max(d["matches"], 1)
    out = dict(ticket="S3b-4", envs_per_cohort=a.envs, cohorts=a.cohorts, threads_per_cohort=a.threads,
               build_obs=not a.no_obs, extrapolate_ticks=a.extrap, census_pairs=a.pairs, warm_s=a.warm, wall_s=d["t"],
               matches=d["matches"], matches_per_h=d["matches"] / d["t"] * 3600,
               core_s_per_match=d["cpu"] / m, cores_busy=d["cpu"] / d["t"],
               python_main_core_s_per_match=d["py"] / m,
               engine_thread_core_s_per_match=d["engineNs"] / 1e9 / m, obs_thread_core_s_per_match=d["obsNs"] / 1e9 / m,
               obs_us_per_seat_row=d["obsNs"] / 1e3 / d["rows"] if d["rows"] else None, seat_rows=d["rows"],
               seat_rows_per_match=d["rows"] / m, decisions_per_match=d["decisions"] / m,
               ticks_per_match=d["ticks"] / m, plays_per_match=d["plays"] / m, presses_per_match=d["presses"] / m,
               rows_missing_opp_key=d["missOpp"], rows_missing_pub_key=d["missPub"], rows_missing_cue_key=d["missCue"], engine_crashes=d["crashes"],
               first_crash=next((str(c.L.firstCrash) for c in cs if c.L.firstCrash is not None), None), table_keys_filled=filled,
               rounds=rounds, round_ms=d["t"] / max(rounds, 1) * 1e3,
               peak_rss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024,
               builders=["FacadeMatch tok/mask/sc/unit_form", "CfOppElixir sc[5]/opp_past", "CfIdent past+ids",
                         "CfPubObj projectiles/effects/own_ability/opp_cycle"] + ([] if a.no_cue else ["CfCue cue"]),
               not_built=["cue (--no-cue)"] if a.no_cue else [],
               src_sha256=shas | {"builder/CfLoop.java": __import__("hashlib").sha256((HERE / "CfLoop.java").read_bytes()).hexdigest(),
                                  "builder/cf_loop_obs.py": __import__("hashlib").sha256(Path(__file__).read_bytes()).hexdigest()})
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps(out))
    for c in cs:
        c.L.close()


if __name__ == "__main__":
    main()
