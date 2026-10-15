"""Alias table + matcher on synthetic decks.  icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/mix/test_live_pool.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_pool as L  # noqa: E402

census, A = L._imports()
MAP = census.aliases(L.engine_names())


def cc(slug):
    return L.card_canon(slug, MAP, A.canon)


def test_aliases():
    # slug spelling (RoyaleAPI) -> the canon of the engine/live spelling
    pairs = {"the-log": "Log", "x-bow": "Xbow", "elite-barbarians": "AngryBarbarians", "mini-pekka": "MiniPekka",
             "ice-spirit": "IceSpirits", "dart-goblin": "BlowdartGoblin", "skeleton-army": "SkeletonArmy",
             "royal-recruits": "RoyalRecruits", "fire-spirit": "FireSpirits", "mega-knight": "MegaKnight", "skeleton-barrel": "SkeletonBalloon",
             "mother-witch": "WitchMother", "zappies": "MiniSparkys", "royal-ghost": "Ghost", "bandit": "Assassin", "firecracker": "Firecracker"}
    for slug, eng in pairs.items():
        assert cc(slug) == A.canon(eng), (slug, cc(slug), A.canon(eng))
    assert cc("battle-ram-ev1") == cc("battle-ram") and cc("wizard-hero") == cc("wizard")


def test_no_alias_collisions():
    from pipeline import vocab
    seen = {}
    for n in L.engine_names():
        for k in {census.key(n), census.key(vocab.engine_key(n) or n)}:
            assert seen.setdefault(k, n) == n, (k, seen[k], n)


def test_conversion_forms():
    deck = ("battle-ram-ev1", "wizard-hero", "the-log", "x-bow", "mega-knight", "fireball", "ice-spirit", "skeletons")
    eng = L.to_engine(sorted(deck), MAP, census.deck)
    assert eng == tuple(sorted(["BattleRam@evolution", "Wizard@hero", "Log", "Xbow", "MegaKnight", "Fireball", "IceSpirits", "Skeletons"]))
    assert L.to_engine(["knight"] * 8, MAP, census.deck) is None                  # not 8 distinct
    assert L.to_engine(["nonexistent-card"] + list(deck[:7]), MAP, census.deck) is None


def test_matcher():
    d = lambda *c: frozenset(c)  # noqa: E731
    lib = [(d("a", "b", "c", "d"), "top"), (d("a", "b", "x", "y"), "second"), (d("a", "z", "w", "v"), "third"), (d("q", "r"), "far")]
    ok = lambda k: True  # noqa: E731
    pk = lambda seen, usable=ok, k=L.K: L.pick(L.candidates(seen, lib, k), usable)  # noqa: E731
    # most frequent containing deck wins, forms identity untouched (ident is opaque)
    assert [c[0] for c in L.candidates({"a", "b"}, lib)] == ["top", "second"] and L.candidates({"a", "b"}, lib)[0][2]
    assert pk({"a", "b", "x"})[:3] == ("second", 3, True)
    # unusable first choice -> next candidate, skipped counted
    assert pk({"a"}, lambda k: k != "top") == ("second", 1, True, 1)
    # no deck contains all: max overlap, then frequency
    assert pk({"a", "b", "q"})[:3] == ("top", 2, False)
    assert pk({"z", "q"})[:3] == ("third", 1, False)                               # tie on overlap 1 -> higher rank (third before far)
    # nothing seen -> no match; k bounds the candidates tried
    assert pk(set())[0] is None
    assert pk({"a"}, lambda k: False, k=2)[0] is None


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
