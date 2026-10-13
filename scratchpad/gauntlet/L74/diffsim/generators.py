"""Seeded suite descriptions; policy proposals are frozen by the oracle runner."""
from collections import Counter
from copy import deepcopy
from itertools import product
import hashlib
import json
from pathlib import Path
import random
import re

from .adapters import NATIVE
from .core import HZ

ICEBOW = ["Tornado", "Tesla", "IceWizard", "Xbow", "Rocket", "Knight", "Log", "Skeletons"]
FILLERS = ["Knight", "Archer", "Goblins", "Giant", "Musketeer", "Fireball", "Arrows", "Skeletons"]
ALIASES = {"archers": "Archer", "thelog": "Log", "royalghost": "Ghost", "wallbreakers": "Wallbreakers",
           "barbarianbarrel": "BarbLog", "giantsnowball": "Snowball", "motherwitch": "WitchMother",
           "icespirit": "IceSpirits", "firespirit": "FireSpirits", "zappies": "MiniSparkys", "healspirit": "Heal"}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def catalog(snapshot=None):
    path = NATIVE / "native_core/data/live_card_catalog.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    cards = {}
    for c in raw["cards"]:
        if c["standard_1v1"]:
            cards[c["internal_name"]] = dict(card_id=c["card_id"], kind=c["type"], cost=c["elixir"],
                forms=[0] + ([1] if c["evolution_form"] else []) + ([2] if c["hero_form"] else []),
                cycles=c.get("evolution_cycles") or 0, ability=bool(c["active_ability"]))
    sources = {str(path): digest(path)}
    if snapshot:
        data = json.loads(Path(snapshot).read_text(encoding="utf-8"))
        stats = data["card_stats"]
        for name, c in cards.items():
            if name in stats and stats[name].get("elixir") is not None:
                c["cost"] = stats[name]["elixir"]
            for suffix, form in (("_EV1", 1), ("_hero", 2)):
                if name + suffix in stats and form not in c["forms"]:
                    c["forms"].append(form)
        sources[str(snapshot)] = digest(snapshot)
    return cards, sources


def chosen_cards(cards, names=None, census=None, top=60):
    """Top usage must come from a real census, never a made-up popularity list.

    Accept CRAPI tier card_usage or the project's frequency-weighted deck census.
    Unrecognized names fail visibly, not silently drop high-frequency cards.
    """
    normalized = {re.sub(r"[^a-z0-9]", "", n.lower()): n for n in cards}
    def resolve(n):
        key = re.sub(r"[^a-z0-9]", "", n.split("@")[0].lower())
        name = ALIASES.get(key, normalized.get(key))
        if name not in cards:
            raise ValueError("unmapped census/card name: " + n)
        return name
    if names:
        return list(dict.fromkeys(resolve(n) for n in names))
    if not census:
        raise ValueError("provide --census for icebow + top 60, or --cards for an explicit chosen set")
    data = json.loads(Path(census).read_text(encoding="utf-8"))
    counts = Counter()
    if "decks" in data:
        for deck in data["decks"]:
            for name in set(deck["engine"]):
                counts[resolve(name)] += deck["sides"]
    else:
        source = data.get("tier1_ranked", data)
        for row in source["card_usage"]:
            counts[resolve(row["card"])] += row["n"]
    if len(counts) < top:
        raise ValueError(f"census has only {len(counts)} mapped cards, need {top}")
    ranked = sorted(counts, key=lambda n: (-counts[n], n))[:top]
    return list(dict.fromkeys(ICEBOW + ranked))


def deck(first, level=11):
    names = list(dict.fromkeys(first + FILLERS))[:8]
    return [dict(card=n, form=0, level=level) for n in names]


def scenario(seed, suite, name, decks=None, duration=600):
    return dict(schema_version=1, id=f"{suite}-{seed}-{name}", suite=suite, seed=seed,
                decks=decks or [deck([]), deck([])], arena=54000000,
                tower_troops=[159000000, 159000000], tower_levels=[11, 11], side=seed % 2,
                duration_ticks=duration, units=[], plays=[])


def play(tick, side, card, form=0, x=9000, y=None):
    return dict(type="deploy", tick=tick, side=side, card=card, form=form,
                x=x*18, y=(12000 if side == 0 else 20000)*18 if y is None else y*18)


def unit_suites(seed, names, cards):
    """Ordered duels include mirror matchups and both orientations.

    Eight-card decks are accepted by both documented reset APIs. Suites use
    ordinary deploys, so there is no hidden editor-only initialization to port.
    """
    rng = random.Random(seed)
    def make(suite, label, ds, duration=900):
        return scenario(rng.randrange(2**32), suite, label, ds, duration)
    for name in names:
        s = make("single", name, [deck([name]), deck([])])
        s["plays"] = [play(500, 0, name)]
        yield s
    for a, b in product(names, repeat=2):
        s = make("duel", f"{a}-vs-{b}", [deck([a]), deck([b])])
        s["plays"] = [play(500, 0, a, y=14000), play(500, 1, b, y=18000)]
        yield s
    troops = [n for n in names if cards[n]["kind"] == "troop"]
    spells = [n for n in names if cards[n]["kind"] == "spell"]
    buildings = [n for n in names if cards[n]["kind"] == "building"]
    for spell in spells:
        s = make("spell_group", spell, [deck([spell]), deck(["Skeletons", "Goblins"])])
        s["plays"] = [play(500, 1, "Skeletons", x=8500, y=18000),
                      play(501, 1, "Goblins", x=9500, y=18000),
                      play(520, 0, spell, y=14000 if spell in ("Log", "BarbLog") else 18000)]
        yield s
    for building, troop in product(buildings, troops):
        s = make("building", f"{building}-vs-{troop}", [deck([building]), deck([troop])])
        s["plays"] = [play(500, 0, building), play(500, 1, troop)]
        yield s
    for name in names:
        forms = [f for f in cards[name]["forms"] if f] or ([0] if cards[name]["ability"] else [])
        for form in forms:
            s = make("forms", f"{name}-form-{form}", [deck([name]), deck(["Knight"])], duration=3000)
            s["decks"][0][0]["form"] = form
            s["policy"] = dict(seed=s["seed"], interval=10, focus=name, ability=True,
                               ability_cards=[name], active_sides=[0, 1])
            s["coverage_required"] = {"card": name, "form": form, "ability": form == 2 or cards[name]["ability"]}
            yield s


def random_scenario(seed, cards, names, full=False):
    rng = random.Random(seed)
    if len(names) < 8:
        raise ValueError("random standard matches require at least eight chosen cards")
    ds = []
    for _ in (0, 1):
        selected = rng.sample(sorted(names), 8)
        # Standard deck limits: max two evo and one hero/champion.
        evo, hero = 0, 0
        d = []
        for name in selected:
            eligible = [0] + ([1] if 1 in cards[name]["forms"] and evo < 2 else [])
            if 2 in cards[name]["forms"] and hero < 1:
                eligible.append(2)
            form = rng.choice(eligible)
            evo += form == 1
            hero += form == 2 or cards[name]["ability"]
            if hero > 1:
                # Replace a second base champion with an unused non-champion.
                replacements = [n for n in sorted(names) if n not in selected and not cards[n]["ability"]]
                if not replacements:
                    raise ValueError("chosen set cannot make a legal single-champion deck")
                name, form = rng.choice(replacements), 0
                selected.append(name)
                hero -= 1
            d.append(dict(card=name, form=form, level=rng.randint(9, 16)))
        ds.append(d)
    s = scenario(seed, "full" if full else "skirmish", "random", ds,
                 duration=7200 if full else rng.randint(10, 30)*HZ)
    s["tower_levels"] = [rng.randint(9, 16), rng.randint(9, 16)]
    s["policy"] = dict(seed=rng.randrange(2**32), interval=rng.randint(10, 30), ability=True,
                       ability_cards=[c["card"] for d in ds for c in d
                                      if c["form"] == 2 or cards[c["card"]]["ability"]], active_sides=[0, 1])
    return s


class LegalPolicy:
    """Random but engine-validated hand, elixir and placement legality.

    Only the oracle proposes plays. Those exact accepted commands are frozen
    and replayed on the candidate, including after the first divergence.
    """
    def __init__(self, spec):
        self.spec = spec
        self.rng = random.Random(spec["seed"])

    def choose(self, engine, s, tick):
        if tick < 100 or tick % self.spec["interval"]:
            return []
        actions = []
        for side in self.spec.get("active_sides", [0, 1]):
            entries = deepcopy(s["decks"][side])
            self.rng.shuffle(entries)
            focus = self.spec.get("focus")
            entries.sort(key=lambda c: c["card"] != focus)
            # Ability attempts are explicit events; rejected ones are kept out of
            # generated legal sequences by runner (but counted in diagnostics).
            bodies = [u for u in engine.state()["units"] if u["side"] == side
                      and (u["form"] == 2 or u["card"] in self.spec.get("ability_cards", []))]
            if self.spec.get("ability") and bodies and self.rng.random() < .35:
                actions.append(dict(type="ability", side=side, card=self.rng.choice(bodies)["card"], tick=tick))
                continue
            for c in entries:
                found = False
                for _ in range(12):
                    x = self.rng.randrange(2, 16)*1000 + 500
                    # Own-half cells also legal for most spell deploy rules;
                    # try opponent-half cells too, relying on engine validation.
                    y = self.rng.randrange(2, 30)*1000 + 500
                    p = play(tick, side, c["card"], c["form"], x, y)
                    if engine.can_deploy(side, c["card"], c["form"], p["x"], p["y"]):
                        actions.append(p)
                        found = True
                        break
                if found:
                    break
        return actions
