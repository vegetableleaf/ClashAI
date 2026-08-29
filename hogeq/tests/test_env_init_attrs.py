"""Attributes the live env reads DIRECTLY must exist before the first read.

`_last_mass` broke a train-rl run with
    AttributeError: 'LiveMatchEnv' object has no attribute '_last_mass'
because the fast-tick branch reads it directly while the ONLY assignment lives in that branch's
`else`. A run whose FIRST decision was perception-woken hit the read before the write. Timing
dependent, which is why it survived so long -- and the same shape as hogeq's `_terms`, which had
six uses and zero definitions and made train-sim-ppo unrunnable on that deck.

This test walks the class for that shape generally rather than pinning one name, so the next
instance is caught at test time instead of in somebody's run.
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


class EnvInitAttrTests(unittest.TestCase):

    def test_last_mass_is_ASSIGNED_in_init(self):
        """The specific regression -- and it must test for an ASSIGNMENT, not a mention.

        /!\ My first version asserted `"_last_mass" in getsource(__init__)` and PASSED with the
        initialiser deleted. __init__ is 34k characters and defines closures, one of which reads
        `getattr(self, "_last_mass", 0.0)` -- so the substring was satisfied by a READ. A negative
        control caught it: removing the init changed nothing. Match the assignment.
        """
        src = inspect.getsource(LiveMatchEnv.__init__)
        self.assertRegex(src, r"self\._last_mass\s*=",
                         "_last_mass is never ASSIGNED in __init__; a perception-woken first "
                         "decision reads it before the else-branch has ever run")

    def test_no_attribute_is_read_bare_without_ever_being_assigned(self):
        """The GENERAL shape. Any `self._x` read by the class must be assigned somewhere in it --
        a read with no write anywhere is the `_terms` / `_last_mass` bug waiting for the right
        timing. Names only ever touched via getattr(self, "_x", default) are exempt: that idiom is
        explicitly tolerant of absence, and two of _last_mass's three readers used it correctly.
        """
        src = inspect.getsource(LiveMatchEnv)
        read = set(re.findall(r"self\.(_[a-z][a-z0-9_]*)\b", src))
        assigned = set(re.findall(r"self\.(_[a-z][a-z0-9_]*)\s*(?:[-+*/|&]?=|:[^=]+=)", src))
        guarded = set(re.findall(r'getattr\(\s*self\s*,\s*"(_[a-z][a-z0-9_]*)"\s*,', src))
        methods = {n for n, _ in inspect.getmembers(LiveMatchEnv, callable)}
        missing = sorted(read - assigned - guarded - methods)
        self.assertEqual(missing, [],
                         f"read but never assigned anywhere in the class: {missing}")


if __name__ == "__main__":
    unittest.main()
