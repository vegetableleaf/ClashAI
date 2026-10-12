"""Offline tests only: no policy update, engine, live reader or deployment."""
import copy
from pathlib import Path
from contextlib import nullcontext
import unittest
import numpy as np
import torch
from pipeline import live_phi as LP, rl_royale as RL
from pipeline.tests.test_rl_shaping import _module_at
from pipeline.tests.test_rl_royale import _tiny_model, _results, _monitor_fields
from pipeline.tests.test_rl_gae import SPEC
from pipeline.tests.test_value_phi import _with_tick

PRE_COMMIT="a10e4fd50190b29dea8b408b0b3325939613b5dd"


class TestLivePhi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_default_config_hash_and_collate_unchanged(self):
        old=_module_at(PRE_COMMIT)
        path=Path(RL.REPO)/"pipeline/rl_royale.yaml"
        a=RL.load_config(path,[],False); b=old.load_config(path,[],False)
        self.assertEqual(a,b); self.assertEqual(RL.config_sha(a),old.config_sha(b))
        self.assertEqual(RL.adv_cfg(a),old.adv_cfg(b))
        rs=_with_tick(_monitor_fields(_results(_tiny_model(6),SPEC,seed=13)))
        for kw in ({},{"advantage":"gae"}):
            x,s=RL.collate(copy.deepcopy(rs),2.,**kw); y,t=old.collate(copy.deepcopy(rs),2.,**kw)
            self.assertEqual(s,t); self.assertEqual(x.keys(),y.keys())
            for k in x: self.assertEqual(x[k].tobytes(),y[k].tobytes(),k)
        self.assertNotIn("record_tick",RL.actor_cfg(dict(a,grid="lattice"),"rollout",0,"cpu"))

    def test_config_and_actor(self):
        cfg={"advantage":"gae","shaping":"live_phi","critic_warmup_updates":1}
        c=RL.adv_cfg(cfg); self.assertEqual(c["shaping_phi_window_s"],10)
        base=RL.load_config(Path(RL.REPO)/"pipeline/rl_royale.yaml",[],False)
        self.assertTrue(RL.actor_cfg(dict(base,**cfg,grid="lattice"),"rollout",0,"cpu")["record_tick"])
        with self.assertRaises(SystemExit): RL.adv_cfg(dict(cfg,critic_warmup_updates=0))
        with self.assertRaises(SystemExit): RL.adv_cfg(dict(cfg,shaping_critic_scale=1.1))

    def test_potential_form_terminal_and_causality(self):
        raw=np.array([-.7,.2,.8,-.1]); ticks=np.array([0,90,190,400]); gamma=np.array([.9,.8,.95,.99])
        cfg={"gamma":gamma,"w_value":.5,"window_ticks":200}
        r=RL.value_phi_rewards(raw,ticks,cfg); next_phi=np.r_[r["phi"][1:],0.]
        np.testing.assert_allclose(r["F"],gamma*next_phi-r["phi"])
        self.assertEqual(r["F"][-1],-r["phi"][-1])
        discounts=np.r_[1.,np.cumprod(gamma[:-1])]
        self.assertAlmostEqual(float(discounts@r["F"]),-r["phi"][0])
        changed=raw.copy(); changed[2:]=-1
        np.testing.assert_array_equal(RL.value_phi_rewards(changed,ticks,cfg)["phi"][:2],r["phi"][:2])

    def test_frozen_file_loading_and_public_allowlist(self):
        root=Path(RL.REPO)/"scratchpad/gauntlet/L74/livephi/test_tmp"
        root.mkdir(exist_ok=True)
        with nullcontext(root) as td:
            model=LP.LivePhi(); path=Path(td)/"phi.pt"
            torch.save(dict(schema=LP.SCHEMA,feature_dim=35,feature_versions=[4,5,6],hidden=32,state_dict=model.state_dict()),path)
            learner=object.__new__(RL.Learner); learner.dev=torch.device("cpu")
            learner.cfg=dict(advantage="gae",shaping="live_phi",critic_warmup_updates=1,shaping_phi_ckpt=str(path))
            learner.phi_net=learner._load_phi_net({"args":{"feature_version":6}})
            self.assertFalse(learner.phi_net.training); self.assertFalse(any(p.requires_grad for p in learner.phi_net.parameters()))
            b={"tok":np.zeros((4,8,14),np.float32),"mask":np.zeros((4,8),bool),"sc":np.zeros((4,70),np.float32)}
            p=learner._phi_values(b)
            poisoned={**b,"opponent_hand":np.ones(4)*999,"outcome":np.ones(4)*999,"played":np.ones(4)*999}
            np.testing.assert_array_equal(p,learner._phi_values(poisoned))
            self.assertLessEqual(np.abs(p).max(),1.)
            self.assertTrue(all(q.grad is None for q in learner.phi_net.parameters()))
            with self.assertRaises(SystemExit): learner._load_phi_net({"args":{"feature_version":7}})

    def test_live_mode_collate_uses_same_potential_math(self):
        rs=_with_tick(_monitor_fields(_results(_tiny_model(6),SPEC,seed=12)))
        shp=dict(mode="live_phi",gamma=.99,w_value=.5,window_ticks=200,phi_fn=lambda b:np.tanh(b["sc"][:,3]))
        x,s=RL.collate(copy.deepcopy(rs),2.,advantage="gae",shaping=shp)
        y,t=RL.collate(copy.deepcopy(rs),2.,advantage="gae",shaping=dict(shp,mode="value_phi"))
        np.testing.assert_array_equal(x["phi"],y["phi"])
        self.assertEqual(s["shaping"]["mode"],"live_phi")
        self.assertEqual({k:v for k,v in s["shaping"].items() if k!="mode"},{k:v for k,v in t["shaping"].items() if k!="mode"})


if __name__=="__main__": unittest.main()
