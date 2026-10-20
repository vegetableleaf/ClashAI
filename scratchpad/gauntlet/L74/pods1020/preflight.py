"""Readiness checks only: no training loop, optimizer step, or evaluation match."""
import importlib.metadata as metadata
import json
from pathlib import Path
import sys

import numpy as np
import torch
import yaml

sys.path.insert(0, "icebow/src")
from pipeline.royale_runtime import activate
from pipeline import royale_env as env, royale_iw_policy as iw
from pipeline import body_identity, obs_contract, public_observation, dataset_gen
from pipeline import decision_options, public_geometry, opp_elixir_count
from pipeline import train_gen, eval_gen, model_gen

state = activate()
assert torch.cuda.is_available()
assert torch.__version__ == "2.11.0+cu128"
env._v2_policy().load("v2")
iw.hazard_module().load_model()
iw.unit_values()
body_identity.tables()
body_identity.ext_tables()
obs_contract._catalog_names()
obs_contract.catalog_card_form(0)
public_observation._native_ids()
dataset_gen.evolution_cycles()
decision_options._catalog_cards()
public_geometry.constants()
public_geometry.load_calibration(public_geometry.CALIBRATION_PATH)
opp_elixir_count.card_db()

cfg = yaml.safe_load(Path("scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_s74.yaml").read_text())
assert cfg["live_levels"] == "all16"
for key in ("init", "pool", "proagree_data", "proagree_data_gen", "league_decks", "league_specialist"):
    assert Path(cfg[key]).is_file(), (key, cfg[key])
for path in cfg["league_external"]:
    assert Path(path).is_file(), path
for path in (
    "icebow/data/bench/rl_royale/rlarm_succ_levels/rlarm_succ_levels_u0065_grafted.pt",
    "icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt",
    "icebow/data/bench/rl_royale/s2_all_il_sA/s2_all_il_sA_u0130.pt",
    "icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt",
    "icebow/data/pipeline/stepd_il/gen_cuew_s0.pt",
    "icebow/data/pipeline/gen_v32_s0/gen_s0.pt",
    ".foreman/codex_autopilot/runs/public_context_v32_w4/artifact.json",
    "/workspace/stepd/d1/v32_cue.npz",
    "/workspace/stepd/v32_w3.npy",
):
    assert Path(path).is_file(), path
with np.load(cfg["proagree_data_gen"]) as data:
    assert data.files
with np.load("/workspace/stepd/d1/v32_cue.npz") as cues:
    assert cues.files
# Load the actual pro-imitation checkpoint onto CUDA without fitting or evaluating.
model, _ = eval_gen.load_model(Path("icebow/data/pipeline/stepd_il/gen_cuew_s0.pt"), "cuda")
assert next(model.parameters()).is_cuda
torch.cuda.synchronize()
print(json.dumps({
    "runtime": state["runtime_id"],
    "torch": torch.__version__,
    "cuda": torch.cuda.is_available(),
    "gpu": torch.cuda.get_device_name(0),
    "royalegym": metadata.version("royalegym"),
    "royalesim": metadata.version("royalesim"),
    "numpy": np.__version__,
    "imitation_model_loaded_on_cuda": True,
}))
print("DEPENDENCY PREFLIGHT PASS")
