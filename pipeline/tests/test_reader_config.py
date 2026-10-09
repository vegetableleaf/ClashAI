"""Local-only reader config: loader contract, clear error when absent, and the live_play command is built from it."""
import json
import sys
from pathlib import Path

import pytest

from pipeline import reader_config

CFG = {"root_rva": "R", "root_ctx": "C",
       "readers": {"v2": {"binary": "/dev/b2", "args": " --a 1 --b"}, "v1": {"binary": "/dev/b1", "args": ""}}}


def write(tmp_path, cfg=CFG):
    p = tmp_path / "reader_config.json"
    p.write_text(json.dumps(cfg))
    return p


def test_load_and_shapes(tmp_path):
    p = write(tmp_path)
    cfg = reader_config.load(p)
    assert reader_config.readers(cfg) == {"v2": ("/dev/b2", " --a 1 --b"), "v1": ("/dev/b1", "")}
    assert reader_config.reader("v2", p) == ("/dev/b2", " --a 1 --b")


def test_missing_file_is_a_clear_exit(tmp_path):
    with pytest.raises(SystemExit) as e:
        reader_config.load(tmp_path / "absent.json")
    assert "reader config missing" in str(e.value) and "absent.json" in str(e.value)


@pytest.mark.parametrize("bad", [{}, {"root_rva": "R", "root_ctx": "C"}, {"root_rva": 1, "root_ctx": "C", "readers": {}},
                                 {"root_rva": "R", "root_ctx": "C", "readers": {"v1": {"binary": "x"}}}])
def test_invalid_file_is_a_clear_exit(tmp_path, bad):
    with pytest.raises(SystemExit) as e:
        reader_config.load(write(tmp_path, bad))
    assert "reader config invalid" in str(e.value)


def test_unknown_reader_name(tmp_path):
    with pytest.raises(SystemExit) as e:
        reader_config.reader("v9", write(tmp_path))
    assert "v9" in str(e.value)


def test_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(reader_config.ENV_VAR, str(write(tmp_path)))
    assert reader_config.load()["root_rva"] == "R"


def test_live_play_fills_from_config_and_requires_it(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scratchpad/gauntlet/L68/live_reader"))
    import live_play as lp
    monkeypatch.setattr(lp, "RVA", None)
    monkeypatch.setattr(lp, "ROOT_CTX", None)
    monkeypatch.setattr(lp, "READERS", {})
    monkeypatch.setenv(reader_config.ENV_VAR, str(tmp_path / "absent.json"))
    with pytest.raises(SystemExit):
        lp.apply_reader_config(strict=True)
    lp.apply_reader_config(strict=False)            # import-time mode: silent
    assert lp.RVA is None and lp.READERS == {}
    monkeypatch.setenv(reader_config.ENV_VAR, str(write(tmp_path)))
    lp.apply_reader_config(strict=True)
    sampler, extra = lp.READERS["v2"]
    assert (lp.RVA, lp.ROOT_CTX) == ("R", "C")
    assert f"{sampler} PID 100 {lp.RVA} {lp.ROOT_CTX}{extra}" == "/dev/b2 PID 100 R C --a 1 --b"
