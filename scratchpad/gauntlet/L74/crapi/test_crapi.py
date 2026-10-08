"""Mocked-HTTP tests (no network, no real key):  python3 -m unittest test_crapi -v"""
import contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crapi, census  # noqa: E402

FAKE_KEY = "FAKEKEY-eyJ0eXAiOiJKV1Qi-do-not-leak"


def card(name, cid, evo=0, **kw):
    c = {"name": name, "id": cid, "level": 14, "maxLevel": 14, "elixirCost": 3, "iconUrls": {"medium": "u"}}
    if evo:
        c["evolutionLevel"] = evo
    c.update(kw)
    return c


ICE = [card("Tornado", 1), card("Tesla", 2, 1), card("Ice Wizard", 3), card("X-Bow", 4), card("Rocket", 5),
       card("Knight", 26000000, 1), card("The Log", 7), card("Skeletons", 8)]
HOG = [card("Hog Rider", 11), card("Musketeer", 12), card("Fireball", 13), card("The Log", 7), card("Ice Golem", 15),
       card("Skeletons", 8), card("Ice Spirit", 17), card("Cannon", 18)]


def battle(t, a, b, deck_a, deck_b, ca, cb, typ="pathOfLegend"):
    side = lambda tag, d, c: {"tag": tag, "name": tag, "crowns": c, "cards": d, "supportCards": [{"name": "Tower Princess"}]}
    return {"type": typ, "battleTime": t, "team": [side(a, deck_a, ca)], "opponent": [side(b, deck_b, cb)]}


class FakeHttp:
    def __init__(self, routes):
        self.routes, self.calls, self.auth = routes, [], []

    def __call__(self, url, key):
        self.calls.append(url)
        self.auth.append(key)
        path = url[len(crapi.API):].split("?")[0]
        r = self.routes.get(path)
        if callable(r):
            r = r()
        if r is None:
            return 404, b'{"reason":"notFound"}', {}
        st, body = r if isinstance(r, tuple) else (200, r)
        return st, json.dumps(body).encode(), {}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        crapi.DATA = root / "data"
        crapi.KEY_PATH = root / "key"
        crapi.KEY_PATH.write_text(FAKE_KEY + "\n")
        os.chmod(crapi.KEY_PATH, 0o600)
        self._orig = crapi.http_get
        self.sleeps = []

    def tearDown(self):
        crapi.http_get = self._orig
        self.tmp.cleanup()

    def api(self, routes):
        crapi.http_get = self.fake = FakeHttp(routes)
        return crapi.Api(crapi.read_key(), sleep=self.sleeps.append)


class TestCrawl(Base):
    def routes(self):
        return {"/cards": {"items": [card("Knight", 26000000, maxEvolutionLevel=1)], "supportItems": []},
                "/locations/global/seasons": {"items": [{"id": "2026-09"}]},
                "/locations/global/pathoflegend/2026-09/rankings/players": {"items": [{"tag": "#AAA"}]},
                "/players/%23AAA/battlelog": [battle("20261007T120000.000Z", "#AAA", "#BBB", ICE, HOG, 1, 0),
                                              battle("20261004T120000.000Z", "#AAA", "#CCC", ICE, HOG, 0, 3)],
                "/players/%23BBB/battlelog": [battle("20261007T120000.000Z", "#BBB", "#AAA", HOG, ICE, 0, 1)]}

    def test_crawl_dedup_resume_and_no_key_leak(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            n1 = crapi.crawl(self.api(self.routes()))
        # #AAA seeded, #BBB/#CCC added as ranked opponents; the BBB-side copy of the same battle is a duplicate
        self.assertEqual(n1, 2)
        lines = (crapi.DATA / "battles.jsonl").read_text().splitlines()
        self.assertEqual(len(lines), 2)
        st = json.loads((crapi.DATA / "state.json").read_text())["players"]
        self.assertEqual(set(st), {"#AAA", "#BBB", "#CCC"})
        self.assertTrue(all(p["last"] for p in st.values()))
        # second run within RECRAWL_H: nobody due, nothing appended (resumable, append-only)
        with contextlib.redirect_stdout(out):
            self.assertEqual(crapi.crawl(self.api(self.routes())), 0)
        self.assertEqual(len((crapi.DATA / "battles.jsonl").read_text().splitlines()), 2)
        # the key reached only the Authorization path, never stdout or any file on disk
        self.assertTrue(all(k == FAKE_KEY for k in self.fake.auth))
        self.assertTrue(all(u.startswith("https://api.clashroyale.com/v1/") for u in self.fake.calls))
        self.assertNotIn(FAKE_KEY, out.getvalue())
        for p in crapi.DATA.rglob("*"):
            if p.is_file():
                self.assertNotIn(FAKE_KEY, p.read_text(encoding="utf-8"), p)

    def test_torn_line_is_isolated(self):
        crapi.DATA.mkdir(parents=True)
        bp = crapi.DATA / "battles.jsonl"
        bp.write_text('{"fetched":"x","battle":{"battleTime":"1"')       # crash mid-write
        crapi.append_jsonl(bp, [{"battle": {"battleTime": "2"}}])
        self.assertEqual(len(crapi.load_seen(bp)), 1)

    def test_429_backoff_then_success(self):
        seq = iter([(429, {"reason": "requestThrottled"}), (503, {}), {"items": []}])
        api = self.api({"/cards": lambda: next(seq)})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(api.get("/cards"), {"items": []})
        self.assertEqual(len(self.fake.calls), 3)
        self.assertGreaterEqual(sum(self.sleeps), 2.0 + 4.0)               # exponential backoff was applied

    def test_rate_limit_spacing(self):
        t = [0.0]
        crapi.http_get = FakeHttp({"/cards": {"items": []}})
        api = crapi.Api(FAKE_KEY, min_interval=0.5, sleep=lambda s: t.__setitem__(0, t[0] + s), clock=lambda: t[0])
        for _ in range(5):
            api.get("/cards")
        self.assertGreaterEqual(t[0], 2.0)                                 # 5 calls -> >= 4 gaps of 0.5 s

    def test_403_is_auth_error_without_key(self):
        api = self.api({"/cards": (403, {"reason": "accessDenied.invalidIp", "message": "Invalid authorization"})})
        with self.assertRaises(crapi.AuthError) as cm:
            api.get("/cards")
        self.assertNotIn(FAKE_KEY, str(cm.exception))

    def test_missing_key_message(self):
        crapi.KEY_PATH.unlink()
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(crapi.main(["selftest"]), 2)
        self.assertIn(".cr_api", err.getvalue())
        self.assertIn("34.148.91.90", err.getvalue())

    def test_selftest_calls_cards_once(self):
        crapi.http_get = self.fake = FakeHttp({"/cards": {"items": [card("Knight", 1, maxEvolutionLevel=1)]}})
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(crapi.main(["selftest"]), 0)
        self.assertEqual(len(self.fake.calls), 1)
        self.assertIn("SELFTEST OK", out.getvalue())
        self.assertNotIn(FAKE_KEY, out.getvalue())


class TestCensus(unittest.TestCase):
    def test_tiers_archetypes_icebow_matchups_and_diff(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            rows = [{"battle": battle("20261007T120000.000Z", "#A", "#B", ICE, HOG, 1, 0)},
                    {"battle": battle("20261008T120000.000Z", "#A", "#C", ICE, HOG, 0, 2)},
                    {"battle": battle("20261006T120000.000Z", "#A", "#D", ICE, HOG, 3, 0)},     # boundary
                    {"battle": battle("20261001T120000.000Z", "#A", "#E", ICE, HOG, 3, 0, typ="PvP")}]
            (d / "battles.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            (d / "cards_latest.json").write_text(json.dumps({"items": [
                card("Knight", 26000000, maxEvolutionLevel=1), card("Brand New", 26999999),
                card("X-Bow", 27000008, maxEvolutionLevel=2, iconUrls={"medium": "u", "heroMedium": "h"})]}))
            with contextlib.redirect_stdout(io.StringIO()):
                census.main(["--data", str(d)])
            rep = json.loads((d / "census" / "census_latest.json").read_text())
        self.assertEqual(rep["tiers"], {"post": 2, "boundary": 1, "pre": 1})
        t1 = rep["tier1_ranked"]
        self.assertEqual(t1["sides"], 4)
        self.assertEqual({a["arch"]: a["n"] for a in t1["archetypes"]}, {"X-Bow": 2, "Hog Rider": 2})
        fam = t1["icebow_family"]
        self.assertEqual(fam["exact_8"]["n"], 2)
        self.assertEqual(fam["by_opp_arch"]["Hog Rider"]["W"], 1)
        self.assertEqual(fam["by_opp_arch"]["Hog Rider"]["win_rate"], 0.5)
        tesla = next(c for c in t1["card_usage"] if c["card"] == "Tesla")
        self.assertEqual(tesla["forms"], {"1": 2})
        self.assertEqual(rep["tier2_all"]["sides"], 8)
        cd = rep["card_diff"]
        self.assertEqual(cd["api_maxEvolutionLevel_ge2"], ["X-Bow"])
        self.assertEqual(cd["api_hero_icon"], ["X-Bow"])
        if isinstance(cd.get("vs_ckpt_vocab"), dict):                     # refs.json present
            self.assertIn("Brand New", cd["vs_ckpt_vocab"]["api_not_in_vocab"])
            self.assertNotIn("X-Bow", cd["vs_ckpt_vocab"]["api_not_in_vocab"])

    def test_slug(self):
        self.assertEqual(census.slug("Mini P.E.K.K.A"), "mini-pekka")
        self.assertEqual(census.slug("The Log"), "the-log")


if __name__ == "__main__":
    unittest.main()
