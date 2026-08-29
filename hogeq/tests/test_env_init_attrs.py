"""Attributes the live env reads DIRECTLY must exist, and must be readable, before the first read.

Two crashes in one session came from this corner, and the second was caused by the fix for the
first:

  1. `_last_mass` was read directly by the fast-tick branch while the ONLY assignment lived in that
     branch's `else`. A run whose FIRST decision was perception-woken raised AttributeError.
  2. Initialising it to `None` then broke the two OTHER readers, which used
     `getattr(self, "_last_mass", 0.0)` and relied on the attribute being ABSENT to get that
     default. With it present-but-None, `None >= float` raised on the very first reset().

So the sentinel is right (None genuinely means "never measured, go measure") and the READERS have
to coerce. Both shapes are pinned below, along with the general sibling case -- hogeq's `_terms`,
six uses and zero definitions, which made train-sim-ppo unrunnable on that deck.
"""
from __future__ import annotations

import inspect
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from clashrl.env import LiveMatchEnv                                  # noqa: E402


def _code_only(obj) -> str:
    """Source with comments stripped.

    Scanning raw source flagged the initialiser's OWN explanation, which quotes the bad pattern
    verbatim in order to say why it is wrong. That false positive has now bitten three separate
    checks in this codebase, so strip comments before matching anything.
    """
    return "\n".join(line.split("#", 1)[0] for line in inspect.getsource(obj).split("\n"))


class EnvInitAttrTests(unittest.TestCase):

    def test_last_mass_is_ASSIGNED_in_init(self):
        """Must test for an ASSIGNMENT, not a mention.

        The first version of this asserted `"_last_mass" in getsource(__init__)` and PASSED with
        the initialiser deleted: __init__ is ~34k characters and defines closures, one of which
        READS the attribute via getattr. The substring was satisfied by a read. A negative control
        is the only thing that exposed it.
        """
        self.assertRegex(_code_only(LiveMatchEnv.__init__), r"self\._last_mass\s*=",
                         "_last_mass is never ASSIGNED in __init__; a perception-woken first "
                         "decision reads it before the else-branch has ever run")

    def test_no_reader_defaults_to_0_via_getattr(self):
        """With the attribute present-and-None, a `getattr(..., 0.0)` default NEVER applies -- so a
        numeric comparison on it raises. Readers must coerce: `(getattr(...) or 0.0)`."""
        bare = re.findall(r'getattr\(\s*self\s*,\s*"_last_mass"\s*,\s*0\.0\s*\)',
                          _code_only(LiveMatchEnv))
        self.assertEqual(bare, [],
                         "a reader still defaults to 0.0 via getattr; with _last_mass set to None "
                         "that default never applies and the comparison raises")

    def test_the_quiet_check_survives_an_unmeasured_sentinel(self):
        """The exact line that crashed reset(), exercised with nothing measured yet."""
        class _Stub:
            quiet_frac = 0.5
        s = _Stub()
        self.assertFalse((getattr(s, "_last_mass", None) or 0.0) >= s.quiet_frac)  # absent
        s._last_mass = None
        self.assertFalse((getattr(s, "_last_mass", None) or 0.0) >= s.quiet_frac)  # present, None
        s._last_mass = 0.8
        self.assertTrue((getattr(s, "_last_mass", None) or 0.0) >= s.quiet_frac)   # measured

    def test_no_attribute_is_read_bare_without_ever_being_assigned(self):
        """The GENERAL sibling shape. Any `self._x` the class reads must be assigned somewhere in
        it -- a read with no write anywhere is hogeq's `_terms` bug waiting for the right timing.
        Names only ever reached through getattr's default are exempt: that idiom tolerates absence.

        NOTE this does NOT catch `_last_mass`, which IS assigned, just too late. The two failures
        are different and both tests are needed.
        """
        src = _code_only(LiveMatchEnv)
        read = set(re.findall(r"self\.(_[a-z][a-z0-9_]*)\b", src))
        assigned = set(re.findall(r"self\.(_[a-z][a-z0-9_]*)\s*(?:[-+*/|&]?=|:[^=]+=)", src))
        guarded = set(re.findall(r'getattr\(\s*self\s*,\s*"(_[a-z][a-z0-9_]*)"\s*,', src))
        methods = {n for n, _ in inspect.getmembers(LiveMatchEnv, callable)}
        missing = sorted(read - assigned - guarded - methods)
        self.assertEqual(missing, [],
                         f"read but never assigned anywhere in the class: {missing}")


if __name__ == "__main__":
    unittest.main()
