"""Regression (10-12): NEWSIM actors crashed with KeyError 'seed' because Learner.actor_base() did not forward the keys
rollout_jobs() reads, and learner_pipeline_frac was silently dropped (fast arm would have trained at 0%)."""
from pathlib import Path
from types import SimpleNamespace

from pipeline import rl_royale as R


def _base(**over):
    cfg = R.load_config(Path(R.__file__).with_suffix(".yaml"), [f"{k}={v}" for k, v in over.items()], smoke=False)
    fake = SimpleNamespace(cfg=cfg, init_meta={"args": {}}, grid="floor")
    return R.Learner.actor_base(fake)


def test_actor_base_forwards_rollout_keys():
    b = _base(seed=7, learner_pipeline_frac=0.3, action_delay_ticks=6)
    assert b["seed"] == 7 and b["learner_pipeline_frac"] == 0.3


def test_actor_base_default_frac_is_zero():
    assert _base()["learner_pipeline_frac"] == 0
