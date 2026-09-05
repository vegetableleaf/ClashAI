from pathlib import Path
R = Path("C:/Users/benpe/ClashBot/icebow")
def sub(path, old, new, count=1):
    p = R / path; s = p.read_text(encoding="utf-8")
    assert s.count(old) == count, (path, old[:60], s.count(old))
    p.write_text(s.replace(old, new), encoding="utf-8")

# 6.3 -> snapshot close penalty inside placement_credit
sub("src/clashrl/geometry_reward.py",
    '      building: min(CAP, p1_pull_band * (0.5 + 0.5 * p2_cover) + p6_siege) + max(FLOOR, p1_close_penalty)',
    '      building: min(CAP, p1_pull_band * (0.5 + 0.5 * p2_cover) + p6_siege) + max(FLOOR, p1_close_snapshot)\n'
    '                (L59 lead ruling 6.3: the close penalty is for dropping ON TOP of the unit -- the snapshot\n'
    '                gap -- not for sitting in its path; `p1_close_penalty` (d_path form) stays logged)')
sub("src/clashrl/geometry_reward.py",
    '        return min(CREDIT_CAP, max(0.0, pos)) + max(CREDIT_FLOOR, min(0.0, g("p1_close_penalty")))',
    '        return min(CREDIT_CAP, max(0.0, pos)) + max(CREDIT_FLOOR, min(0.0, g("p1_close_snapshot")))')

# 6.1 -> timing paid only with a positive placement part
sub("src/clashrl/sim/env.py",
    '''    def _geo_credit(self, terms, kind: str) -> float:
        """w_time * timing_credit + w_geom * placement_credit(kind) * gate (only the PLACEMENT part is gated)."""
        place = GR.placement_credit(terms, kind, p7_enabled=self.geo_p7_enabled)
        credit = (self.geo_w_time * GR.timing_credit(terms)
                  + self.geo_w_geom * place * float(terms.get("gate", 1.0)))
''',
    '''    def _geo_credit(self, terms, kind: str) -> float:
        """(w_time * timing_credit + w_geom * placement_credit(kind) * gate) if placement_credit > 0 else 0.
        Only the PLACEMENT part is gated; the TIMING part is paid only alongside a positive placement
        part (L59 lead ruling 6.1: a right-role card dropped behind the king at the right time earns
        nothing, as the old binary's `intercept` required; a building with pull_ok = 0 earns nothing)."""
        place = GR.placement_credit(terms, kind, p7_enabled=self.geo_p7_enabled)
        if place > 0.0:
            credit = (self.geo_w_time * GR.timing_credit(terms)
                      + self.geo_w_geom * place * float(terms.get("gate", 1.0)))
        else:
            credit = 0.0
''')

# 6.5 -> X-Bow offensive branch pays w_wincon * P6
sub("src/clashrl/sim/env.py",
    '''                    # L59 arm G: the flat offensive credit -> w_geom * P6 (the siege band: bow-to-tower gap''',
    '''                    # L59 arm G: the flat offensive credit -> w_wincon * P6 (shape, not scale -- lead ruling
                    # 6.5: the same weight the flat credit had; the siege band: bow-to-tower gap''')
sub("src/clashrl/sim/env.py",
    '''                    val = self.geo_w_geom * float(self._geo_terms(card_id, nx, ny).get("p6_siege", 0.0))''',
    '''                    val = self.w_wincon * float(self._geo_terms(card_id, nx, ny).get("p6_siege", 0.0))''')

# Part C (b): ship env.geometry from the parent into the workers
sub("src/clashrl/sim/remote_pool.py",
    '''def _worker(conn, n_envs: int, seed0: int, drill_frac=None,
            spell_min_value=None) -> None:''',
    '''def _worker(conn, n_envs: int, seed0: int, drill_frac=None,
            spell_min_value=None, geometry=None) -> None:''')
sub("src/clashrl/sim/remote_pool.py",
    '''    cfg = Config.load()
    from clashrl.sim.drill_env import make_train_env
''',
    '''    cfg = Config.load()
    # L59 arm G: `env.geometry` ARRIVES FROM THE PARENT for the same reason as drill_frac -- this
    # worker re-reads config.yaml from disk, so a `--config <run yaml>` override of the block would
    # otherwise be ON in the learner's local twin and OFF in every rollout env, with no error.
    if geometry is not None:
        cfg.data.setdefault("env", {})["geometry"] = dict(geometry)
    from clashrl.sim.drill_env import make_train_env
''')
sub("src/clashrl/sim/remote_pool.py",
    '''    def __init__(self, n_envs: int, workers: int, seed: int = 0, drill_frac=None,
                 spell_min_value=None):''',
    '''    def __init__(self, n_envs: int, workers: int, seed: int = 0, drill_frac=None,
                 spell_min_value=None, geometry=None):''')
sub("src/clashrl/sim/remote_pool.py",
    '''                             args=(child_c, n, s0, drill_frac, spell_min_value),''',
    '''                             args=(child_c, n, s0, drill_frac, spell_min_value, geometry),''')
sub("src/clashrl/train_sim_ppo.py",
    '''            spell_min_value=float(cfg.get("sim", "ppo_spell_min_value", default=0.0)))''',
    '''            spell_min_value=float(cfg.get("sim", "ppo_spell_min_value", default=0.0)),
            # L59 arm G: the resolved `env.geometry` block, shipped down (workers re-read config.yaml)
            geometry=cfg.get("env", "geometry", default=None))''')
print("rulings applied")
