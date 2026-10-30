"""A/B 10-30 ``critic_warmup_minibatch`` (rl_royale._ppo_steps): the critic warm-up (vf policy False) uses its own
minibatch; policy updates keep ``minibatch``; absent / null = byte-identical and the historical config hash.

    icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_critic_warmup_mb -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline import rl_royale as RL
from pipeline.tests.test_learner_fast_accum import BASE, REPO, VF, TestMicroBatch


class TestCriticWarmupMinibatch(unittest.TestCase):
    WARM = {**VF, "policy": False}
    setUpClass = classmethod(TestMicroBatch.setUpClass.__func__)   # the accum test's tiny model + trajectories
    run_update = TestMicroBatch.run_update
    pbytes = staticmethod(TestMicroBatch.pbytes)

    def test_warmup_uses_its_own_minibatch(self):
        small, m_small = self.run_update({**BASE, "minibatch": 8}, vf=self.WARM)
        keyed, m_keyed = self.run_update({**BASE, "minibatch": 64, "critic_warmup_minibatch": 8}, vf=self.WARM)
        big, m_big = self.run_update({**BASE, "minibatch": 64}, vf=self.WARM)
        self.assertEqual(self.pbytes(m_keyed), self.pbytes(m_small))
        self.assertEqual(keyed["steps"], small["steps"])
        self.assertGreater(keyed["steps"], big["steps"])

    def test_absent_null_and_policy_updates_unchanged(self):
        for vf in (self.WARM, VF, None):
            base, m0 = self.run_update({**BASE, "minibatch": 16}, vf=vf)
            null, m1 = self.run_update({**BASE, "minibatch": 16, "critic_warmup_minibatch": None}, vf=vf)
            self.assertEqual(self.pbytes(m1), self.pbytes(m0))
            if vf is not self.WARM:                           # policy updates ignore the key
                on, m2 = self.run_update({**BASE, "minibatch": 16, "critic_warmup_minibatch": 4}, vf=vf)
                self.assertEqual(self.pbytes(m2), self.pbytes(m0))
                self.assertEqual(on["steps"], base["steps"])

    def test_config_validation_and_hash(self):
        import yaml
        cfg = yaml.safe_load((REPO / "pipeline" / "rl_royale.yaml").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as d:
            def load(**kv):
                p = Path(d) / "c.yaml"
                p.write_text(yaml.safe_dump({**cfg, **kv}), encoding="utf-8")
                return RL.load_config(p, [], smoke=False)
            self.assertEqual(RL.config_sha(load()), RL.config_sha(load(critic_warmup_minibatch=None)))
            self.assertNotEqual(RL.config_sha(load()), RL.config_sha(load(critic_warmup_minibatch=256)))
            for bad in (0, -1, 1.5, True, "256"):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    load(critic_warmup_minibatch=bad)


del TestMicroBatch                                            # imported for its fixtures; it runs in its own file

if __name__ == "__main__":
    unittest.main()
