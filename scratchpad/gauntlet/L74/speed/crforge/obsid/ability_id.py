"""LOOP-IW: CfAbil (the hero ability press observation in Java) driven beside production, with its tables filled from
production's own functions. ``JavaAbil`` is the builder the fast loop uses; ``install`` hooks royale_env so every
ability_commands / ability_options / fire-time recheck of a live env is compared with CfAbil on the same facade battle
at the same tick (actor-path identity check, pilot/loopiw/hook).

Tables (process-wide, CfAbil.Tables): per RoyaleSim card id from RoyalePoolEnv's own attributes (_hero_ranges,
_hero_buildings, _hero_radius; _body_elixir / _card_cost formulas), the L70 v2 models (ability_policy.load('v2')), the
Hero IW hazard model (live_reader ability_ice_wizard), royale_iw_policy's WINCONS / BUILDINGS / unit values, and on
first sight: a body's public_frame card id (public_frame on the raw() entity of that body), a public card id's
geometry facts, a detector key's make_play row, the IW observers' detector keys (obs_id.JavaMain's resolvers)."""
from __future__ import annotations

import math

import jpype
import numpy as np


class JavaAbil:
    def __init__(self, freeze: bool = True):
        from pipeline import royale_env as R
        self.R, self.freeze = R, freeze
        self.C = jpype.JClass("CfAbil")
        self.T = self.C.Tables()
        self.Int, self.Dbl, self.Bool = jpype.JArray(jpype.JInt), jpype.JArray(jpype.JDouble), jpype.JArray(jpype.JBoolean)
        self.ready = self.ranges = False
        self.main = None
        self.all = []                                        # every CfAbil made (diagnostic counters)

    # ---------------------------------------------------------------- tables
    def setup(self, env) -> None:
        """Once per process, from the first env: everything indexed by card id (catalogue = env.names)."""
        from pipeline import vocab
        from pipeline.dataset_gen import card_key
        from pipeline.obs_contract import _catalog_names
        from pipeline.public_observation import _native_ids
        from pipeline.royale_iw_policy import WINCONS, hazard_module
        R, T = self.R, self.T
        names = env.names
        nc = max(names) + 1
        cards = {c.card_id: c for c in env.core.cards()}
        T.bodyElixir = self.Dbl([cards[c].elixir / max(1, int(cards[c].count)) if c in cards else 0. for c in range(nc)])
        T.cardCost = self.Dbl([float(cards[c].elixir) if c in cards else 0. for c in range(nc)])
        T.abilityCard = self.Int([R.ABILITY_CARDS.index(names[c]) if names.get(c) in R.ABILITY_CARDS else -1 for c in range(nc)])
        T.nCards = len(R.ABILITY_CARDS)
        T.iceWizard = self.Bool([names.get(c) == "IceWizard" for c in range(nc)])
        T.wincon = self.Bool([names.get(c) in WINCONS for c in range(nc)])
        cat = _catalog_names()
        T.tesla = self.Bool([c in names and cat.get(_native_ids().get((vocab.engine_key(names[c]), 0), -1), "") == "Tesla"
                             for c in range(nc)])
        hz = hazard_module()
        hm = hz.load_model()
        self.hz, self.cards = hz, hm["cards"]
        ck = [card_key(names[c]) if c in names else None for c in range(nc)]
        T.iwSlug = self.Bool([k == "ice-wizard" for k in ck])
        T.ownCost = self.Dbl([float(self.cards.get(k, [3])[0]) for k in ck])
        T.goblins = int(env.ids.get("Goblins", -1))
        T.hzIntercept, T.hzShift = float(hm["intercept"]), float(hm.get("calibration_shift", 0.0))
        T.hzIdx = self.Int([hz.FEATURE_NAMES.index(n) for n in hm["feature_names"]])
        T.hzMean, T.hzScale, T.hzCoef = (self.Dbl([float(v) for v in hm[k]]) for k in ("mean", "scale", "coefficients"))
        # v2 models, by V2_KEYS order
        bundle = R._v2_policy().load("v2")["models"]
        idx = {}
        for key in dict.fromkeys(R.V2_KEYS.values()):
            m = bundle[key]
            gbt = m["type"] == "gbt_timing"
            assert m["type"] in ("logistic_timing", "gbt_timing"), (key, m["type"])
            i = T.addModel(float(m["intercept"]), float(m.get("second_charge_offset", 0.)), self.Dbl(m["mean"]),
                           self.Dbl(m["scale"]), None if gbt else self.Dbl(m["coefficients"]),
                           self.Dbl(m["timing"]["knots"]), self.Dbl(m["timing"]["values"]),
                           float(m["trees_scale"]) if gbt else 0., float(m["learning_rate"]) if gbt else 0.,
                           2 if key == "boss-bandit" else 1)
            for tree in (m["trees"] if gbt else []):
                f, th, lo, hi, v = [], [], [], [], []
                for node in tree:
                    leaf = "value" in node
                    f.append(-1 if leaf else int(node["feature"]))
                    th.append(0. if leaf else float(node["threshold"]))
                    lo.append(-1 if leaf else int(node["left"]))
                    hi.append(-1 if leaf else int(node["right"]))
                    v.append(float(node["value"]) if leaf else 0.)
                T.addTree(i, self.Int(f), self.Dbl(th), self.Int(lo), self.Int(hi), self.Dbl(v))
            idx[key] = i
        T.v2Key = self.Int([idx[R.V2_KEYS[names[c]]] if names.get(c) in R.V2_KEYS else -1 for c in range(nc)])
        nan = float("nan")
        T.rangeChamp = T.rangeHero = T.rangeOther = self.Dbl([nan] * nc)
        T.heroRadius = self.Dbl([0.] * nc)
        self.names, self.nc = dict(names), nc
        # the IW observers' detector keys: obs_id.JavaMain's tables + resolvers (its own Keys)
        import obs_id
        self.main = obs_id.JavaMain()
        self.main.gid = {}
        T.keys = self.main.keys
        self.ready = True

    def fill_ranges(self, env) -> None:
        """_hero_ranges / _hero_buildings / _hero_radius (set by _reset_abilities on an env's first match with heroes)."""
        names, nc = self.names, self.nc
        hr, hb, rad = env._hero_ranges, env._hero_buildings, getattr(env, "_hero_radius", {})
        g = lambda nm: float(hr[nm]) if nm in hr else float("nan")     # noqa: E731
        T = self.T
        T.rangeChamp = self.Dbl([g(names[c]) if c in names else float("nan") for c in range(nc)])
        T.rangeHero = self.Dbl([g(names[c] + "_hero") if c in names else float("nan") for c in range(nc)])
        T.rangeOther = self.Dbl([g(hb.get(c, names[c] + "_hero")) if c in names else float("nan") for c in range(nc)])
        T.heroRadius = self.Dbl([float(rad.get(c, 0.)) for c in range(nc)])
        self.ranges = True

    def fill(self, env) -> None:
        """Every missing key: CfAbil's (P: body -> public card id, N: public card id facts, K: detector key row) and the
        IW observers' detector keys (obs_id.JavaMain.resolve_opp / spell_table on this env's raw())."""
        from types import SimpleNamespace
        from pipeline import royale_heroiw as heroiw
        from pipeline.obs_contract import _catalog_names
        from pipeline.public_observation import public_frame
        from pipeline.royale_iw_policy import BUILDINGS, WINCONS, unit_values
        T = self.T
        s = SimpleNamespace(env=env, state=env.raw())
        if self.main.spell_cards is None:
            self.main.spell_table(s)
        self.main.resolve_opp(s)
        for m in T.takeMissing():
            m = str(m)
            if m.startswith("P:"):
                card, body, bits = m[2:].split("|")
                ent = dict(side=0, x=0.0, y=0.0, hp=1, max_hp=1, name=self.names.get(int(card), card), card_id=int(card),
                           entity_id=0, status_flags=int(bits))
                if heroiw.ENABLED and heroiw.public_identity(body) is not None:     # raw()'s unit_types rule
                    ent.update(name="IceWizard", public_card_id=heroiw.public_identity(body), public_form=2, unit_name=body)
                f = public_frame({"tick": 0, "entities": [ent]}, source="sim")["entities"]
                T.putPub(m[2:], int(f[0]["card_id"]) if f else -1)
            elif m.startswith("N:"):
                nm = _catalog_names().get(int(m[2:]), "")
                T.putNat(int(m[2:]), float(unit_values().get(nm, .5)), nm in BUILDINGS, nm in WINCONS)
        nk = int(jpype.JClass("CfPubObj").detKeys(self.main.keys))
        if nk > len(T.keyCost):
            cost, speed, kind, win = list(T.keyCost), list(T.keySpeed), list(T.keyKind), list(T.keyWincon)
            for k in range(len(cost), nk):
                slug = self.hz._slug(str(jpype.JClass("CfPubObj").detKey(self.main.keys, k)))
                c, kd, _, sp = self.cards.get(slug, [3, "troop", 1, 0.0])
                cost.append(float(c)); speed.append(float(sp))
                kind.append({"troop": 0, "spell": 1, "building": 2}.get(kd, 0))
                win.append(slug in self.hz.WINCON_SLUGS)
            T.keyCost, T.keySpeed, T.keyKind, T.keyWincon = self.Dbl(cost), self.Dbl(speed), self.Int(kind), self.Bool(win)

    # ---------------------------------------------------------------- per env
    def of(self, env):
        core = env.core
        j = core.__dict__.get("_liw")
        if j is None:
            j = core._liw = self.C(core._cf, self.T, self.freeze)
            self.all.append(j)
        return j

    def reset(self, env) -> None:
        if not self.ready:
            self.setup(env)
        if not self.ranges and hasattr(env, "_hero_ranges"):
            self.fill_ranges(env)
        if self.main.spell_cards is None:                    # the IW observers' spell table before their first update
            from types import SimpleNamespace
            self.main.spell_table(SimpleNamespace(env=env, state=env.raw()))
        self.of(env).reset(int(env.seed), str(getattr(env, "entry", {}).get("tag", "")), int(env.decision_ticks),
                           getattr(env, "_iw_policy", None) is not None, bool(env._iw_never))

    def _retry(self, env, f):
        for _ in range(50):
            r = f()
            if r is not None:
                return r
            self.fill(env)
        raise RuntimeError("CfAbil: tables still missing after 50 fills")

    def commands(self, env, side: int) -> list:
        r = list(self._retry(env, lambda: self.of(env).commands(int(side))))
        return [tuple(r[i:i + 3]) for i in range(0, len(r), 3)]

    def options(self, env, side: int, rule) -> list:
        flat = None if rule is None else self.Int([v for c in rule for v in c])
        r = np.asarray(self._retry(env, lambda: self.of(env).options(int(side), flat)), np.float64)
        w = 4 + 44 + (11 if self.freeze else 0)
        return [r[i:i + w] for i in range(0, len(r), w)]

    def recheck(self, env, side: int, learned: bool) -> list:
        r = list(self.of(env).recheck(int(side), bool(learned)))
        return [tuple(r[i:i + 3]) for i in range(0, len(r), 3)]


def selftest_draw(n: int = 3000) -> int:
    """CfAbil.draw vs CPython random.Random(str).random() on n production-shaped seeds (+ odd lengths): mismatches."""
    import random
    D, rng, bad = jpype.JClass("CfAbil").draw, random.Random(11), 0
    for i in range(n):
        s = f"ability:{rng.randrange(10 ** rng.randrange(1, 9))}:{'x' * (i % 7)}{rng.choice(['', 'sp0001_3', 'ü'])}:" \
            f"{i % 2}:{rng.randrange(100000)}:{rng.randrange(7000)}"
        bad += int(float(D(s)) != random.Random(s).random())
    return bad


def selftest_libm(n: int = 20000) -> int:
    import random
    C, rng, bad = jpype.JClass("CfAbil"), random.Random(5), 0
    for _ in range(n):
        z, q = rng.uniform(-40, 40), float(rng.randrange(1, 10 ** 12))
        bad += int(float(C.libmExp(z)) != math.exp(z)) + int(float(C.libmPow(q, .5)) != q ** .5)
    return bad


def selftest_sum(n: int = 20000) -> int:
    """CfAbil.PySum vs CPython sum() of floats (3.12: Neumaier) on n random lists: mismatches (bits)."""
    import random
    S, rng, bad = jpype.JClass("CfAbil$PySum").of, random.Random(9), 0
    Dbl = jpype.JArray(jpype.JDouble)
    for _ in range(n):
        v = [rng.choice([0.5, 0.8, 1.6, 3.0, 0.1, 1 / 3, 2.2, 1e-9]) * rng.choice([1, -1, 7]) for _ in range(rng.randrange(0, 9))]
        bad += int(float(S(Dbl(v))).hex() != float(sum(v)).hex())
    return bad
