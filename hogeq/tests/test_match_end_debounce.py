"""A single unrecognised frame must not end a live match (2026-08-15 user report: the bot
stopped acting at OVERTIME and printed a 0-0 result while the match was still being played).

The live env's step() cannot run headless (it needs a capture device), so this drives the
debounce state machine exactly as step() does: a good frame clears the counter, bad frames
accumulate, and only the Nth consecutive bad frame is terminal."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT / "src"), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from clashrl.config import Config    # noqa: E402


class _Debounce:
    """The exact rule env.step() applies around its terminal branch."""

    def __init__(self, confirm):
        self.confirm = confirm
        self.n = 0

    def frame(self, in_match: bool) -> bool:
        """Feed one frame; True = the env would END the match here."""
        if in_match:
            self.n = 0
            return False
        self.n += 1
        return self.n >= self.confirm


class MatchEndDebounceTests(unittest.TestCase):
    def setUp(self):
        self.confirm = int(Config.load().get("env", "match_end_confirm", default=3))
        self.assertGreaterEqual(self.confirm, 2, "a debounce of 1 is no debounce at all")

    def test_a_single_bad_frame_does_not_end_the_match(self):
        d = _Debounce(self.confirm)
        self.assertFalse(d.frame(True))
        self.assertFalse(d.frame(False), "one hiccup (overtime banner, emote popup) must not end it")
        self.assertFalse(d.frame(True), "and a good frame afterwards resumes normally")

    def test_a_hiccup_run_shorter_than_the_window_is_absorbed(self):
        d = _Debounce(self.confirm)
        for _ in range(self.confirm - 1):
            self.assertFalse(d.frame(False))
        self.assertFalse(d.frame(True), "recovered before the window closed")
        self.assertEqual(d.n, 0, "the counter resets on recovery")

    def test_a_real_ending_still_terminates(self):
        d = _Debounce(self.confirm)
        out = [d.frame(False) for _ in range(self.confirm)]
        self.assertFalse(any(out[:-1]), "not before the window closes")
        self.assertTrue(out[-1], "a genuinely finished match must still end")

    def test_the_counter_does_not_bridge_two_matches(self):
        import clashrl.env as env_mod
        src = Path(env_mod.__file__).read_text(encoding="utf-8")
        # LiveMatchEnv.reset() -- not _DetHold.reset(), which is the first "def reset(" in the file
        i = src.index("self._canvas_stack.reset()")
        self.assertIn("_not_in_match = 0", src[i - 500:i + 1500],
                      "reset() must clear the debounce or a stale count could end match N+1 early")


if __name__ == "__main__":
    unittest.main(verbosity=1)
