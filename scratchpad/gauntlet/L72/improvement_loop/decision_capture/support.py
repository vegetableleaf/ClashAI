"""Fixed engineering fixtures and provenance; no live actions or private serialization."""
import copy
import hashlib
import json
import platform
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
CKPT = ROOT / 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt'
CHECKPOINT_SHA = '76fdfaacbd9c2049cc88792278f06e3f73a56eaf9653791e922d9332dd6751cd'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    paths = list((ROOT / 'pipeline').glob('*.py'))
    paths += list(HERE.glob('*.py'))
    paths += [HERE / 'PLAN.md', HERE / 'METRICS.md', ROOT / 'scratchpad/gauntlet/L68/live_reader/live_play.py']
    paths += list((HERE.parent / 'reader_character_identity').glob('*.py'))
    paths += [ROOT / 'research/ext/Royale/RoyaleSim/data/derived/cards.json',
              ROOT / 'research/ext/Royale/RoyaleSim/data/calibration.json',
              ROOT / 'research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json',
              ROOT / 'icebow/config/cards.yaml', ROOT / 'pipeline/tests/test_live_mem.py',
              ROOT / 'pipeline/tests/test_public_observation.py']
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in sorted(set(paths))}


def manifest(pilot, checkpoint=CKPT):
    from dataclasses import asdict
    return dict(schema=1, checkpoint_path=str(Path(checkpoint).resolve()),
                checkpoint_sha256=sha(checkpoint), sources=sources(),
                capture_id='public-decision-capture-20261006',
                settings=dict(feature_version=pilot.feature_version, grid=pilot.grid,
                    gate_tau=pilot.gate_tau, use_counter=pilot.use_counter,
                    extrapolate_ticks=pilot.ext_h, decision_options=asdict(pilot.decision_options),
                    decision_seed=pilot.decision_seed, public_audit=pilot.public_audit,
                    card_vocab=dict(pilot.gid), anti_leak=False, hand_reader=False,
                    model_eval=not pilot.model.training,
                    pilot_class=type(pilot).__module__ + '.' + type(pilot).__name__,
                    character_identity_enabled=type(pilot).__name__ == 'IdentityPilot'),
                environment=dict(torch_version=str(torch.__version__), numpy_version=np.__version__,
                    python_version=platform.python_version(), torch_threads=torch.get_num_threads(),
                    torch_interop_threads=torch.get_num_interop_threads(), device=str(pilot.dev),
                    platform=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                    deterministic=torch.are_deterministic_algorithms_enabled(),
                    mkldnn_enabled=torch.backends.mkldnn.enabled))


def execution_environment():
    return dict(machine=platform.machine(), processor=platform.processor(),
                deterministic=torch.are_deterministic_algorithms_enabled(),
                mkldnn_enabled=torch.backends.mkldnn.enabled,
                torch_config=torch.__config__.show())


def make_pilot():
    sys.path.insert(0, str(HERE.parent / 'reader_character_identity'))
    from live_play_identity import IdentityPilot, install_catalog
    install_catalog()
    return IdentityPilot(CKPT, device='cpu', gate_tau=.35, extrapolate_ticks=26, public_audit=True)


def fixed_frames():
    from pipeline.tests.test_live_mem import FRAME, T
    from pipeline.tests.test_public_observation import spell
    frames = []
    for i in range(24):
        f = copy.deepcopy(FRAME)
        f['game_tick'] = (220, 2420, 4820)[i % 3] + 10 * i
        f['chain'] = {'battle': 'fixture-' + str(i)}
        f['sample_monotonic_us'] = i * 1000000
        f['character_identity'] = {'schema': 1, 'build': 160402012}
        f['players'][1]['elixir_raw'] = (0, 19000, 41000, 100000)[i % 4]
        if i % 6 == 5:
            f['players'][1]['hand_deck_indices'][3] = -1
        if i % 3:
            for j, name in enumerate(('IceWizardHero', 'IceWizardHeroFloatingCube', 'IceWizardHero_IceCube')):
                e = T(9000000 + j, 15, 1, 4000 + 500 * j, 22000, 911, 911, 203000023, hex(300 + j))
                e.update(native_name=name, native_name_status='ok', attached_owner='0x12c', attached_owner_read_ok=True)
                f['entities'].append(e)
        f['projectiles'] = [spell('goblin_barrel', side=0, x=3500, y=25500)] if i % 4 == 3 else []
        f['effects'] = []
        # Alternate physical orientation while keeping each own-frame fixture coherent.
        if i % 2:
            for p in f['players']:
                p['side'] = 1 - p['side']
            for e in f['entities'] + f['projectiles']:
                e['side'] = 1 - e['side']
                for k, limit in [('x', 18000), ('y', 32000), ('target_x', 18000), ('target_y', 32000)]:
                    if k in e:
                        e[k] = limit - e[k]
        # Sentinels must never enter capture records or provenance.
        f['private_future_sentinel'] = 'PRIVATE_FUTURE_SENTINEL'
        f['players'][0]['private_sentinel'] = 'OPPONENT_PRIVATE_SENTINEL'
        frames.append(f)
    return frames


def prepare_case(pilot, frame):
    pilot.reset_match()
    for offset in (20, 10, 0):
        f = copy.deepcopy(frame)
        f['game_tick'] -= offset
        pilot.observe(f)


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')


def weight_hash(model):
    h = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        h.update(name.encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()
