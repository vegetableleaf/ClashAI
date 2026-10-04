"""Regression: the real R1t launcher must parse against its copied R1 YAML."""
import re
import shlex
import unittest
from pathlib import Path
from pipeline import rl_royale as RL

ROOT = Path(__file__).resolve().parents[2]


class R1tLaunchTests(unittest.TestCase):
    def test_exact_launcher_overrides_parse_and_enable_terminal_gap(self):
        script = (ROOT/'scratchpad/gauntlet/L70/rl/run_r1t_v3.sh').read_text()
        config = re.search(r'^CFG=(.+)$', script, re.M).group(1)
        overrides = re.search(r'^OVR="(.+)"$', script, re.M).group(1)
        overrides = overrides.replace('$V3', 'icebow/data/pipeline/gen_v3_s0/gen_s0.pt')
        cfg = RL.load_config(ROOT/config, shlex.split(overrides), smoke=False)
        self.assertTrue(RL.adv_cfg(cfg)['gae_terminal_gap'])
        self.assertEqual(cfg['max_updates'], 155)
        self.assertEqual(cfg['init'], 'icebow/data/pipeline/gen_v3_s0/gen_s0.pt')
        self.assertEqual(cfg['gae_gamma_unit'], 'tick')
        self.assertEqual(cfg['proagree_data_gen'], 'icebow/data/pipeline/gen_dataset_v3.npz')

    def test_r1_default_remains_off_and_bad_keys_still_fail(self):
        path = ROOT/'scratchpad/gauntlet/L69/rl/r1_rl_royale.yaml'
        cfg = RL.load_config(path, [], smoke=False)
        self.assertFalse(RL.adv_cfg(cfg)['gae_terminal_gap'])
        with self.assertRaisesRegex(SystemExit, 'unknown config key'):
            RL.load_config(path, ['gae_terminal_gap_typo=true'], smoke=False)


if __name__ == '__main__':
    unittest.main()
