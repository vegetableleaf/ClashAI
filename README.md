# ClashAI

A research project that trains a Clash Royale agent for the X-Bow control deck ("icebow") in a fast
simulator. It starts from imitation learning on professional replays and improves with self-play
reinforcement learning. Not affiliated with or endorsed by Supercell.

Results are in [RESULTS.md](RESULTS.md).

## What is here

| Path | What it is |
| :--- | :--------- |
| `pipeline/` | Observation contract, imitation dataset and model, PPO trainer (`rl_royale.py`), evaluation (`e1_eval.py`), scoring and gates. |
| `icebow/`, `hogeq/` | Deck configuration, card data and the small `clashrl` helper package. |
| `tools/` | Public replay download and dataset helpers. |

## Simulator

The code in this repository trains and evaluates on the public [RoyaleSim](https://pypi.org/project/royalesim/) package.
Some models in RESULTS.md were trained with other engines, which are not part of this repository.

In this code the observation holds only what a player can see. The opponent's hand, next card and elixir are never
fed to a model; opponent elixir is estimated from public events (`pipeline/opp_elixir_count.py`).

## Running

These steps have not been tested on a clean install.

```
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
export ROYALE_RUNTIME=unpinned-linux   # the RoyaleSim and RoyaleGym installed in this venv

# reinforcement learning on the simulator: --smoke runs a tiny check, key=value overrides pipeline/rl_royale.yaml
python -m pipeline.rl_royale --config pipeline/rl_royale.yaml --run smoke --smoke

# paired evaluation of a checkpoint
python -m pipeline.e1_eval --help
```

Checkpoints and datasets are not in this repository, so training needs an initial checkpoint and a replay pool of your own
(see the `init` and `pool` keys in `pipeline/rl_royale.yaml`). `tools/` downloads a public replay set.

