"""Public APIs only. NativeEngine is source-reviewed, VM-UNTESTED.

Coordinates are integer 1/18000 tiles (RoyaleSim subtiles). Native millitiles
are multiplied by 18, never rounded. Elixir uses 1/10000 elixir, but the fork
public API exposes only millielixir: that precision limitation is recorded.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

from .core import Unsupported, validate

ROOT = Path(__file__).resolve().parents[4]
NATIVE = ROOT / "research/ext/cr-native-sandbox"


def check_tick(engine, tick):
    if tick != engine.state()["tick"]:
        raise ValueError("deploy/ability tick must equal current tick; runner owns scheduling")


def setup_supported(s):
    if s["arena"] != 54000000 or s["tower_troops"] != [159000000, 159000000]:
        raise Unsupported("RoyaleSim public reset supports standard arena / Princess towers only")


class ForkEngine:
    """Also wraps an arbitrary separately installed royalesim wheel.

    Do not switch wheels in-process. Runtime activation belongs to worker.py.
    The optional module parameter supports contract tests without loading an engine.
    """
    def __init__(self, module=None, options=None):
        if module is None:
            import royalesim as module
        self.sim = module
        if getattr(module, "SUBTILE_PER_MILLITILE", 18) != 18:
            raise Unsupported("unsupported public coordinate scale")
        self._raw = None
        self.battle = module.Battle(None, [[0, 1, 2], [0, 1, 2]], **(options or {}))
        self.catalog = [dict(zip(module.CATALOGUE_FIELDS, r, strict=True))
                        for r in json.loads(self.battle.catalogue_json())]
        self.names = [r["name"] for r in self.catalog]
        self.ids = {name: i for i, name in enumerate(self.names)}
        self.unit_types = json.loads(self.battle.unit_types_json())
        self.provenance = dict(kind="royalesim", version=getattr(module, "__version__", "unknown"),
                               engine=self.battle.provenance(), options=options or {},
                               qualification="runtime_unverified_until_run",
                               limitations=["public elixir is quantized to 1/1000", "public timers may be rounded to ticks"])

    def reset(self, scenario):
        s = validate(scenario)
        setup_supported(s)
        self.scenario = deepcopy(s)
        spawns = []
        for e in s.get("units", []):
            if e.get("form", 0) or e.get("level", 11) != 11:
                raise Unsupported("public initial spawns cannot specify individual form/level")
            spawns.append((e["side"], self.ids[e["card"]], e["x"], e["y"], e["hp"]))
        self.battle.reset(s["seed"], [[self.ids[c["card"]] for c in d] for d in s["decks"]],
                          0, 0, None, None, spawns,
                          forms=[[c["form"] for c in d] for d in s["decks"]],
                          levels=[[c["level"] for c in d] for d in s["decks"]],
                          tower_levels=s["tower_levels"])
        self._raw = None

    def raw(self):
        if self._raw is None:
            self._raw = json.loads(self.battle.state_json())
        return self._raw

    def step(self, n):
        if not isinstance(n, int) or n < 0:
            raise ValueError("step requires nonnegative integer")
        self.battle.step([], n)
        self._raw = None

    def _slot(self, side, card, form):
        configured = next((c for c in self.scenario["decks"][side] if c["card"] == card), None)
        if configured is None or configured["form"] != form:
            return None
        hand = next(p for p in self.raw()["players"] if p["team"] == side)["hand"]
        cid = self.ids[card]
        return hand.index(cid) if cid in hand else None

    def can_deploy(self, side, card, form, x, y):
        slot = self._slot(side, card, form)
        return slot is not None and self.battle.check_deploy(side, slot, x, y) == 0

    def deploy(self, side, card, form, x, y, tick):
        check_tick(self, tick)
        slot = self._slot(side, card, form)
        if slot is None:
            return {"accepted": False}
        row = self.battle.step([(side, slot, x, y)], 0)[0]
        self._raw = None
        return {"accepted": row[1] == 0}

    def ability(self, side, card, tick, **kwargs):
        check_tick(self, tick)
        deck = self.scenario["decks"][side]
        buttons = [c["card"] for c in deck if c["form"] == 2]
        buttons += [c["card"] for c in deck if c["form"] != 2 and self.catalog[self.ids[c["card"]]]["champion"]]
        if card not in buttons:
            return {"accepted": False}
        slot = self.sim.HAND_SIZE + buttons.index(card)
        row = self.battle.step([(side, slot, 0, 0)], 0)[0]
        self._raw = None
        return {"accepted": row[1] == 0}

    def state(self):
        raw = self.raw()
        units, towers = [], []
        for row in raw["entities"]:
            e = dict(zip(self.sim.ENTITY_FIELDS, row, strict=True))
            tower = e["card_id"] == -1
            card = f"tower-{e['tower_slot']}" if tower else self.names[e["card_id"]]
            flags = e["status_flags"]
            body = dict(id=e["uid"], spawn_order=e["uid"], card=card,
                        form=2 if flags & 16 else 1 if flags & 8 else 0, side=e["team"],
                        x=e["x"], y=e["y"], hp=e["hp"], max_hp=e["max_hp"], shield=e["shield"],
                        target=None if e["target_uid"] == -1 else e["target_uid"],
                        mount=None if e["mount_uid"] == -1 else e["mount_uid"],
                        status={"buffs": sorted(e["buffs"]), "deploy_ms": e["deploy_ticks"]*50,
                                "stun_ms": e["stun_ticks"]*50, "knockback_ms": e["knockback_ticks"]*50,
                                "ability_ms": e["ability_ticks"]*50, "flags": flags},
                        level=e["level"], unit_type=self.unit_types[e["unit_type"]])
            # Retain every remaining public entity field for wheel-vs-wheel checks.
            mapped = {"uid", "card_id", "team", "tower_slot", "target_uid", "mount_uid", "unit_type",
                      "status_flags", "buffs", "deploy_ticks", "stun_ticks", "knockback_ticks", "ability_ticks"}
            body["extra"] = {k: v for k, v in e.items() if k not in mapped and k not in body}
            (towers if tower else units).append(body)
        players = sorted(raw["players"], key=lambda p: p["team"])
        projectiles = []
        for row in raw["projectiles"]:
            p = dict(zip(self.sim.PROJECTILE_FIELDS, row, strict=True))
            p["target"] = None if p.pop("target_uid") == -1 else row[list(self.sim.PROJECTILE_FIELDS).index("target_uid")]
            p["firer_card_id"] = self.names[p["firer_card_id"]] if p["firer_card_id"] >= 0 else "tower"
            projectiles.append(p)
        extra = deepcopy({k: v for k, v in raw.items() if k not in ("entities", "projectiles")})
        def name(cid):
            return self.names[cid] if cid >= 0 else None
        for p in extra["players"]:
            for field in ("hand", "deck"):
                if field in p:
                    p[field] = [name(cid) for cid in p[field]]
            for field in ("next_card", "mirror_target"):
                if field in p:
                    p[field] = name(p[field])
            for e in p.get("evo", []):
                e[0] = name(e[0])
            for b in p.get("abilities", []):
                b[3] = name(b[3])
            for pending in p.get("pending", []):
                if pending[0] == 0:
                    pending[1] = name(pending[1])
        for spell in extra.get("spells", []):
            spell[1] = name(spell[1])
        return dict(tick=raw["tick"], units=units, towers=towers,
                    elixir=[p["elixir_milli"]*10 for p in players],
                    clock={k: raw[k] for k in ("tick_ms", "regular_ticks", "overtime_ticks", "overtime")},
                    result=dict(terminal=raw["game_over"], winner=None if raw["winner"] == -1 else raw["winner"],
                                crowns=[p["crowns"] for p in players]),
                    projectiles=projectiles,
                    extra=extra)

    def close(self):
        pass


class NativeEngine:
    """Uses native_core.env/decks, never private memory, worker lifecycle or live scripts.

    UNTESTED against a VM. Current bindings manifest is 150535029. A manifest
    for 160402012, updated catalog and already-running documented sandbox are
    required. No connection is made during construction or validation.
    """
    def __init__(self, manifest=None, template=None, env=None, host="127.0.0.1", port=37031):
        manifest = Path(manifest or NATIVE / "bindings/runtime-manifest.json")
        self.manifest = json.loads(manifest.read_text(encoding="utf-8"))
        if str(self.manifest["runtime_version"]) != "160402012":
            raise Unsupported("NativeEngine requires sandbox build 160402012; local bindings are "
                              + str(self.manifest["runtime_version"]) + "; VM adapter UNTESTED")
        # Only loopback documented sandbox transport, never external network.
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("native sandbox must be local/loopback")
        sys.path.insert(0, str(NATIVE))
        from native_core.env import NativeRoyaleEnv
        from native_core.decks import build_replay
        from native_core.card_catalog import catalog
        self.build_replay = build_replay
        self.catalog = catalog()
        catalog_file = NATIVE / "native_core/data/live_card_catalog.json"
        catalog_version = json.loads(catalog_file.read_text(encoding="utf-8"))["game_version"]
        if env is None and not catalog_version.startswith("16.402"):
            raise Unsupported("native bindings card catalog also needs the 16.402 build update")
        self.ids = {v["internal_name"]: k for k, v in self.catalog.items()}
        self.env = env or NativeRoyaleEnv(host=host, port=port)
        self._raw = None
        self.template = json.loads(Path(template or NATIVE / "examples/eight-card-bootstrap.json").read_text(encoding="utf-8"))
        self.provenance = dict(kind="native", qualification="VM_UNTESTED", manifest=self.manifest,
                               limitations=["buffs/shield v2 are unverified in sandbox docs",
                                            "cross-engine projection omits unmatched internal/timer fields",
                                            "native reset deck deal and coordinate/tower mapping need VM validation"])

    def reset(self, scenario):
        s = validate(scenario)
        if s.get("units"):
            raise Unsupported("native documented replay API cannot inject initial units; use deploy plays")
        self.scenario = deepcopy(s)
        decks = [[dict(card_id=self.ids[c["card"]], level=c["level"],
                       form=("base", "evolution", "hero")[c["form"]]) for c in d] for d in s["decks"]]
        replay = self.build_replay(self.template, *decks, seed=s["seed"])
        replay["cmd"] = []
        replay["time"] = 0
        battle = replay["battle"]
        battle["arena"] = s["arena"]
        for side in (0, 1):
            level = s["tower_levels"][side]
            battle[f"avatar{side}"].update(expLevel=level, kt=level, arena=s["arena"])
            battle["hbd"][side]["kt"] = level
            battle[f"deck{side}"]["sc"] = [dict(d=s["tower_troops"][side], l=level-1, t=0, c=0)]
        self.env.reset(replay, warmup_steps=0)
        self._raw = None

    def raw(self):
        if self._raw is None:
            self._raw = self.env.observe()
        return self._raw

    def step(self, n):
        if not isinstance(n, int) or n < 0:
            raise ValueError("step requires nonnegative integer")
        if n:
            self.env.step(n)
            self._raw = None

    def _deck_index(self, side, card, form):
        return next((i for i, c in enumerate(self.scenario["decks"][side])
                     if c["card"] == card and c["form"] == form), None)

    @staticmethod
    def _xy(x, y):
        if x % 18 or y % 18:
            raise Unsupported("native deploy coordinates must be whole millitiles")
        return x // 18, y // 18

    def can_deploy(self, side, card, form, x, y):
        index = self._deck_index(side, card, form)
        if index is None:
            return False
        x, y = self._xy(x, y)
        return bool(self.env.probe(side=side, deck_index=index, x=x, y=y)["accepted"])

    def deploy(self, side, card, form, x, y, tick):
        check_tick(self, tick)
        index = self._deck_index(side, card, form)
        if index is None:
            return {"accepted": False}
        x, y = self._xy(x, y)
        result = self.env.act(side=side, deck_index=index, x=x, y=y)
        self._raw = None
        return {"accepted": bool(result["accepted"])}

    def ability(self, side, card, tick, **kwargs):
        check_tick(self, tick)
        raw = self.raw()
        candidates = [e for e in raw["entities"] if e["side"] == side
                      and e.get("base_card_id") == self.ids[card] and e.get("ability_available")]
        if not candidates:
            return {"accepted": False}
        # Button semantics target the newest eligible body; public generation handle.
        entity = max(candidates, key=lambda e: e["creation_ordinal"])
        result = self.env.use_ability(side=side, entity_id=entity["entity_id"])
        self._raw = None
        return {"accepted": bool(result["accepted"])}

    def state(self):
        raw = self.raw()
        if raw.get("coherent") is not True:
            raise Unsupported("incoherent native observation")
        self.last_native_observation = raw
        handles = {e["id"]: e["entity_id"] for e in raw["entities"]}
        units, towers = [], []
        for e in raw["entities"]:
            # Standard arena crown towers are at these documented public positions.
            tower = e["card_id"] < 0
            if tower:
                slot = 0 if 7000 <= e["x"] <= 11000 else 1 if e["x"] < 9000 else 2
                card = f"tower-{slot}"
            else:
                card = self.catalog[e["base_card_id"]]["internal_name"]
            buffs = e["buffs"]  # Missing v2 data is an error, not an empty status.
            target = e["target"]
            if target is not None and target not in handles:
                raise Unsupported("native target outside observable entity set")
            body = dict(id=e["entity_id"], spawn_order=e["creation_ordinal"], card=card,
                        form={"base": 0, "evolution": 1, "hero": 2}.get(e.get("card_form"), 0) if tower else
                             {"base": 0, "evolution": 1, "hero": 2}[e["card_form"]],
                        side=e["side"], x=e["x"]*18, y=e["y"]*18, hp=e["hp"], max_hp=e["max_hp"],
                        shield=sum(b["shield_hp"] for b in buffs), target=handles.get(target),
                        status={"buffs": sorted([[b["name"], b["remaining_ms"]] for b in buffs]),
                                "ability_cooldown_ms": e["ability_cooldown_remaining_ms"],
                                "ability_pending_ms": e["ability_pending_ms"],
                                "event_timer_ms": e["event_timer_ms"],
                                "attack_progress_ms": e["attack_progress_ms"],
                                "attack_load_timer_ms": e["attack_load_timer_ms"]}, level=e["level"])
            (towers if tower else units).append(body)
        episode = raw["episode"]
        terminal = episode["terminated"]
        # Use host episode result; do not infer a winner from sampled HP.
        winner = episode.get("winner_side", episode.get("winner"))
        if terminal and episode.get("outcome") == "draw":
            winner = 2
        if terminal and winner is None:
            raise Unsupported("native terminal episode lacks explicit winner/draw mapping")
        return dict(tick=raw["tick"], units=units, towers=towers,
                    elixir=[p["elixir_raw"] for p in sorted(raw["players"], key=lambda p: p["side"])],
                    clock={"tick_ms": 50},
                    result=dict(terminal=terminal, winner=winner, crowns=episode["crowns"]),
                    extra={"native_observation": raw})

    def close(self):
        self.env.close()  # Close only our TCP connection, never shut down the host.


class FakeEngine:
    """Deterministic toy mechanics, expressly not a CR simulator.

    Planted bug: opposing Knight/Archers interaction deals one extra HP/tick.
    """
    def __init__(self, bug=False):
        self.bug = bug
        self.provenance = {"kind": "fake", "bug": bug}

    def reset(self, scenario):
        self.scenario = deepcopy(validate(scenario))
        self.tick = 0
        self.units = []
        self.elixir = [100000, 100000]
        self.next_id = 0
        self.bugged = False
        for u in scenario.get("units", []):
            self.spawn(**u)

    def spawn(self, side, card, x=9000*18, y=10000*18, hp=100, form=0, **kwargs):
        self.units.append(dict(id=self.next_id, spawn_order=self.next_id, card=card, form=form, side=side,
                               x=x, y=y, hp=hp, max_hp=hp, shield=0, target=None, status={"buffs": []}))
        self.next_id += 1

    def can_deploy(self, side, card, form, x, y):
        return self.elixir[side] >= 30000 and any(c["card"] == card and c["form"] == form
                                                for c in self.scenario["decks"][side])

    def deploy(self, side, card, form, x, y, tick):
        check_tick(self, tick)
        ok = self.can_deploy(side, card, form, x, y)
        if ok:
            self.elixir[side] -= 30000
            self.spawn(side, card, x, y, form=form)
        return {"accepted": ok}

    def ability(self, side, card, tick, **kwargs):
        check_tick(self, tick)
        units = [u for u in self.units if u["side"] == side and u["card"] == card]
        if units:
            units[-1]["shield"] += 10
        return {"accepted": bool(units)}

    def step(self, n):
        if not isinstance(n, int) or n < 0:
            raise ValueError("step requires nonnegative integer")
        for _ in range(n):
            if self.tick >= self.scenario.get("fake_terminal_tick", 80):
                break
            self.tick += 1
            self.elixir = [min(100000, e + 100) for e in self.elixir]
            for u in self.units:
                enemies = [v for v in self.units if v["side"] != u["side"]]
                if u["card"] == "Knight":
                    enemies.sort(key=lambda v: v["card"] != "Archers")
                u["target"] = enemies[0]["id"] if enemies else None
                if self.bug and u["card"] == "Knight" and any(v["card"] == "Archers" for v in enemies):
                    u["hp"] -= 1
                    self.bugged = True

    def state(self):
        terminal = self.tick >= self.scenario.get("fake_terminal_tick", 80)
        return deepcopy(dict(tick=self.tick, units=self.units, towers=[], elixir=self.elixir,
                             clock={"tick_ms": 50}, result=dict(terminal=terminal,
                             winner=(1 if self.bugged else 2) if terminal else None, crowns=[0, 0])))

    def close(self):
        pass
