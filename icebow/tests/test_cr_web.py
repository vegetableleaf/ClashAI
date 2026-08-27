"""cr_web: blocked-source fetching (Scrapling) + the raw api.php route.

NETWORK TESTS SKIP THEMSELVES when offline or when scrapling is absent -- the suite must stay
runnable on a machine with no connection. The pure-logic parts always run.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl import cr_web    # noqa: E402


def _online() -> bool:
    try:
        return bool(cr_web.fetch_raw("https://clashroyale.fandom.com/api.php?action=query&format=json",
                                     max_age_s=3600, timeout=10))
    except Exception:  # noqa: BLE001
        return False


class BlockDetectionTests(unittest.TestCase):
    """A Cloudflare interstitial answers 200, so status alone cannot decide."""

    def test_interstitial_is_treated_as_blocked(self):
        self.assertTrue(cr_web._looks_blocked("<html><title>Just a moment...</title>" + "x" * 900))
        self.assertTrue(cr_web._looks_blocked("<html>Attention Required! | Cloudflare" + "x" * 900))

    def test_short_or_empty_body_is_blocked(self):
        self.assertTrue(cr_web._looks_blocked(""))
        self.assertTrue(cr_web._looks_blocked("<html></html>"))

    def test_a_real_page_is_not_blocked(self):
        self.assertFalse(cr_web._looks_blocked("<html><body>" + "card stats " * 200 + "</body></html>"))

    def test_cache_keys_separate_raw_from_html(self):
        u = "https://example.com/x"
        self.assertNotEqual(cr_web._cache_path(u), cr_web._cache_path("RAW::" + u))


class LiveSourceTests(unittest.TestCase):
    def setUp(self):
        if not _online():
            self.skipTest("offline (or scrapling unavailable)")

    def test_wiki_stats_match_our_knowledge_base(self):
        """The api.php route must return the #vardefine table the KB was built from."""
        st = cr_web.card_stats("Hog Rider")
        self.assertIn("hp_11", st)
        from clashrl.config import Config
        from clashrl.sim.env import SimMatchEnv
        from clashrl.sim.engine import build_spec
        env = SimMatchEnv(Config.load(), seed=0)
        spec = build_spec(env.db, "hog_rider", 11)
        self.assertAlmostEqual(float(st["hp_11"]), spec.hp, delta=2.0)
        self.assertAlmostEqual(float(st["dmg_11"]), spec.hit_dmg, delta=2.0)

    def test_the_sources_THIS_PIPELINE_READS_still_fetch(self):
        """Both Fandom routes the importer depends on must come back with a real body.

        This test used to also assert that `royaleapi.com/card/hog-rider` fetches, under the name
        `test_previously_blocked_sources_now_fetch`. That premise expired. MEASURED 2026-08-27:

            https://clashroyale.fandom.com/wiki/Hog_Rider          461,770 bytes   not blocked
            https://clashroyale.fandom.com/api.php?...&prop=wikitext 33,161 bytes  not blocked
            https://royaleapi.com/card/hog-rider                         0 bytes   BLOCKED

        RoyaleAPI, Deck Shop and StatsRoyale are behind Cloudflare again and the sim-parity
        research confirmed it independently. The right response is not to assert that a third
        party stays blocked -- that is just as brittle in the other direction, and would go red
        the day Cloudflare relaxes. It is to assert what we actually depend on. NOTHING in
        card_import.py reads RoyaleAPI: the importer walks Fandom pages and api.php, which is why
        api.php is asserted here and was not before."""
        for url in ("https://clashroyale.fandom.com/wiki/Hog_Rider",
                    "https://clashroyale.fandom.com/api.php?action=parse&page=Hog_Rider"
                    "&prop=wikitext&format=json"):
            r = cr_web.fetch(url)
            self.assertTrue(r["html"], "no body from %s" % url)
            self.assertFalse(cr_web._looks_blocked(r["html"]), "blocked by %s" % url)


if __name__ == "__main__":
    unittest.main(verbosity=1)
