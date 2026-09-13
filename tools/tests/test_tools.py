"""Offline tests for tools/ -- no network, no engine, temp folders only.

run from the repo root:  icebow\\.venv\\Scripts\\python.exe -m unittest tools.tests.test_tools
"""
from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
_VENV_PY = REPO / "icebow" / ".venv" / "Scripts" / "python.exe"
PY = str(_VENV_PY) if _VENV_PY.is_file() else sys.executable

from tools import hf_download  # noqa: E402

# the icebow-only filter of the old scratchpad/gauntlet/L67/hf_to_crawl.py, copied verbatim
ICEBOW_OLD = frozenset({"tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons"})


def run_main(fn, argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(argv)
    return rc, buf.getvalue()


def no_network(*_a, **_k):
    raise AssertionError("network access attempted")


class HfDownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "src"
        self.dest = self.root / "dest"
        self.blobs = {"replays/part-000000.parquet": b"alpha" * 100, "replays/part-000001.parquet": b"beta" * 77,
                      "actions/part-000000.parquet": b"gamma"}
        files = []
        for p, data in self.blobs.items():
            (self.src / p).parent.mkdir(parents=True, exist_ok=True)
            (self.src / p).write_bytes(data)
            files.append({"path": p, "rows": 1, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        self.manifest = self.root / "manifest.json"
        self.manifest.write_text(json.dumps({"files": files}), encoding="utf-8")
        self.base_url = self.src.as_uri() + "/"

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, p):
        (self.dest / p).parent.mkdir(parents=True, exist_ok=True)
        (self.dest / p).write_bytes(self.blobs[p])

    def test_dry_run_lists_and_touches_nothing(self):
        self.put("replays/part-000000.parquet")
        with mock.patch.object(hf_download.urllib.request, "urlopen", side_effect=no_network) as m:
            rc, out = run_main(hf_download.main, ["--manifest", str(self.manifest), "--dest", str(self.dest), "--dry-run"])
        self.assertEqual(rc, 0)
        m.assert_not_called()
        self.assertIn("replays/part-000000.parquet have", out)
        self.assertIn("replays/part-000001.parquet would fetch", out)
        self.assertNotIn("actions/", out)                                  # --prefix replays/ by default
        self.assertIn("DONE (dry run) have 1 would-fetch 1", out)
        self.assertFalse((self.dest / "replays" / "part-000001.parquet").exists())

    def test_dry_run_cli(self):
        r = subprocess.run([PY, str(REPO / "tools" / "hf_download.py"), "--manifest", str(self.manifest),
                            "--dest", str(self.dest), "--dry-run", "--base-url", "http://127.0.0.1:9/"],
                           capture_output=True, text=True, cwd=REPO, timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("would-fetch 2", r.stdout)
        self.assertFalse(self.dest.exists())

    def test_resume_skips_files_with_matching_size_and_sha(self):
        self.put("replays/part-000000.parquet")
        self.put("replays/part-000001.parquet")
        with mock.patch.object(hf_download.urllib.request, "urlopen", side_effect=no_network) as m:
            rc, out = run_main(hf_download.main, ["--manifest", str(self.manifest), "--dest", str(self.dest)])
        self.assertEqual(rc, 0)
        m.assert_not_called()
        self.assertEqual(out.count("skipped"), 2)
        self.assertIn("DONE ok 2 bad 0", out)

    def test_corrupt_local_file_is_refetched(self):
        (self.dest / "replays").mkdir(parents=True)
        (self.dest / "replays" / "part-000000.parquet").write_bytes(b"x" * len(self.blobs["replays/part-000000.parquet"]))
        rc, out = run_main(hf_download.main, ["--manifest", str(self.manifest), "--dest", str(self.dest),
                                              "--base-url", self.base_url, "--retries", "1"])
        self.assertEqual(rc, 0, out)
        self.assertIn("DONE ok 2 bad 0", out)
        self.assertEqual((self.dest / "replays" / "part-000000.parquet").read_bytes(), self.blobs["replays/part-000000.parquet"])

    def test_bad_sha_counts_bad_and_exits_nonzero(self):
        (self.src / "replays" / "part-000001.parquet").write_bytes(b"tampered" * 10)
        rc, out = run_main(hf_download.main, ["--manifest", str(self.manifest), "--dest", str(self.dest),
                                              "--base-url", self.base_url, "--retries", "1"])
        self.assertEqual(rc, 1)
        self.assertIn("DONE ok 1 bad 1", out)
        self.assertTrue((self.dest / "replays" / "part-000000.parquet").is_file())
        self.assertFalse((self.dest / "replays" / "part-000001.parquet").exists())
        self.assertEqual(list(self.dest.rglob("*.part")), [])

    def test_manifest_path_cannot_escape_dest(self):
        with self.assertRaises(SystemExit):
            hf_download.safe_rel("replays/../../evil.parquet")


def _play(t, card, side, idx, x=1000, y=2000):
    return {"kind": "play_card", "card_key": card, "side": side, "source_index": idx,
            "source_fields": {"data_t": t, "data_x": x, "data_y": y, "data_i": 0}}


def _replay(team_deck, opp_deck, events):
    def side(deck):
        return {"players": [{"deck": [{"card_key": c} for c in deck], "elixir_leaked": 1.5}], "crowns": 1}
    return {"battle": {"team": side(team_deck), "opponent": side(opp_deck), "battle_type": "pathOfLegend",
                       "game_mode": "Ladder", "result": "win"}, "events": events}


ICEBOW_HF = ["tornado", "tesla-ev1", "ice-wizard", "x-bow", "rocket", "knight-ev1", "the-log", "skeletons"]
OTHER_HF = ["hog-rider", "musketeer", "fireball", "the-log", "ice-spirit", "skeletons", "cannon", "ice-golem"]


class HfToCrawlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import hf_to_crawl
        cls.mod = hf_to_crawl

    def setUp(self):
        import polars as pl
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.hf = self.root / "hf"
        self.hf.mkdir()
        ice = _replay(ICEBOW_HF, OTHER_HF, [
            _play(40, "x-bow", "team", 0), _play(60, "hog-rider", "opponent", 1),
            {"kind": "ability", "card_key": "", "side": "team", "source_index": 2, "source_fields": {"data_t": 70}},
            _play(90, "tesla-ev1", "team", 3)])
        other = _replay(OTHER_HF, OTHER_HF, [_play(30, "cannon", "team", 0)])
        unpos = _replay(OTHER_HF, ICEBOW_HF, [_play(30, "rocket", "opponent", 0, x=None)])
        pl.DataFrame({"replay_tag": ["r_ice", "r_other", "r_unpos"],
                      "payload_json": [json.dumps(ice), json.dumps(other), json.dumps(unpos)]}
                     ).write_parquet(self.hf / "part-000000.parquet")

    def tearDown(self):
        self.tmp.cleanup()

    def convert(self, argv, missing_default=True):
        real = self.mod.load_rule
        if missing_default:     # point the deck's default crawl at a folder that does not exist
            rule = mock.patch.object(self.mod, "load_rule",
                                     lambda d: real(d)[:2] + (self.root / "no_such_deck" / "crawl2",))
        else:
            rule = contextlib.nullcontext()
        with rule:
            return run_main(self.mod.main, argv)

    def test_icebow_rule_equals_old_icebow_only_filter(self):
        want, aliases, _ = self.mod.load_rule("icebow")
        self.assertEqual(want, ICEBOW_OLD)
        self.assertEqual(aliases, {})
        decks = [ICEBOW_HF, ["tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons"],
                 ICEBOW_HF[:7] + ["cannon"], ICEBOW_HF[:7], OTHER_HF, ["tornado", "cannon"] + ICEBOW_HF[2:]]
        for deck in decks:
            ks = {self.mod.base(c) for c in deck}
            self.assertEqual(bool(self.mod.match(ks, want, aliases)), ks == ICEBOW_OLD, deck)

    def test_hogeq_alias_is_read_from_yaml(self):
        want, aliases, _ = self.mod.load_rule("hogeq")
        self.assertEqual(aliases, {"cannon": "tesla"})
        swapped = (set(want) - {"tesla"}) | {"cannon"}
        self.assertEqual(self.mod.match(swapped, want, aliases), "alias:cannon->tesla")

    def test_filter_and_dedupe_skipped_when_default_crawl_missing(self):
        out = self.root / "out"
        rc, log = self.convert(["icebow", "--hf", str(self.hf), "--out", str(out)])
        self.assertEqual(rc, 0)
        self.assertIn("skipping dedupe", log)
        rep = json.loads((out / "dedupe_report.json").read_text(encoding="utf-8"))
        self.assertIsNone(rep["dedupe_against"])
        self.assertEqual(rep["stats"]["kept"], 1)
        self.assertEqual(rep["stats"]["skip_unpositioned"], 1)
        self.assertEqual(json.loads((out / "tags.json").read_text(encoding="utf-8")), ["r_ice"])
        with (out / "battles.csv").open(encoding="utf-8", newline="") as h:
            battles = list(csv.DictReader(h))
        with (out / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
            plays = list(csv.DictReader(h))
        self.assertEqual(len(battles), 1)
        self.assertEqual(battles[0]["deck"], ",".join(ICEBOW_HF))
        self.assertEqual([p["attr_ability"] for p in plays], ["0", "0", "1", "0"])   # abilities kept, tick order
        self.assertEqual([p["attr_s"] for p in plays], ["blue", "red", "blue", "blue"])
        self.assertEqual(battles[0]["plays"], "4")

    def test_dedupe_against_drops_a_replay_already_in_the_crawl(self):
        first = self.root / "first"
        self.convert(["icebow", "--hf", str(self.hf), "--out", str(first)])
        second = self.root / "second"                  # the first output IS crawl2-shaped, so use it as "our crawl"
        rc, _ = self.convert(["icebow", "--hf", str(self.hf), "--out", str(second), "--dedupe-against", str(first)])
        self.assertEqual(rc, 0)
        rep = json.loads((second / "dedupe_report.json").read_text(encoding="utf-8"))
        self.assertEqual(rep["stats"].get("kept", 0), 0)
        self.assertEqual(rep["stats"]["dup_of_our_crawl"], 1)
        self.assertEqual(rep["our_keys"], 1)

    def test_explicit_missing_dedupe_folder_and_empty_hf_fail_cleanly(self):
        with self.assertRaises(SystemExit):
            self.convert(["icebow", "--hf", str(self.hf), "--out", str(self.root / "o"),
                          "--dedupe-against", str(self.root / "nope")])
        (self.root / "empty").mkdir()
        with self.assertRaises(SystemExit):
            self.convert(["icebow", "--hf", str(self.root / "empty"), "--out", str(self.root / "o2")])
        with self.assertRaises(SystemExit):
            self.mod.load_rule("not_a_deck")


class CliSmokeTests(unittest.TestCase):
    def test_every_tool_help_runs(self):
        for tool in ("hf_download.py", "hf_to_crawl.py", "build_degraded.py", "merge_aug.py"):
            with self.subTest(tool=tool):
                r = subprocess.run([PY, str(REPO / "tools" / tool), "--help"], capture_output=True, text=True,
                                   cwd=REPO, timeout=300)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("usage:", r.stdout)

    def test_build_degraded_and_merge_aug_import_cleanly(self):
        r = subprocess.run([PY, "-c", "import tools.build_degraded as b, tools.merge_aug as m; "
                                      "print(b.REPO.name, callable(b.main), callable(m.main))"],
                           capture_output=True, text=True, cwd=REPO, timeout=300)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.split()[1:], ["True", "True"])
        self.assertEqual(Path(r.stdout.split()[0]).name, REPO.name)


if __name__ == "__main__":
    unittest.main()
