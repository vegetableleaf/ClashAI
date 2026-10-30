#!/bin/bash
# GROW-SMOKE PPO arm (33903): ppo_arm.sh RUN CPUS INIT LR [k=v]: 16 matches / update, 1 critic warm-up (tower_phat refuses 0), 12 epochs (250-ish steps,
# so kl_stop_prev 0.02 can bind at this small batch), u0 = warm-up + 4 PPO updates. u0 rollouts are identical across arms (same seed, init = same fn).
R=$1; C=$2; I=$3; LR=$4; shift 4
exec bash /workspace/grow/run_rl.sh $R $C $I learner_device=cuda lr=$LR E=8 G=2 n_actors=1 ppo_epochs=12 critic_warmup_updates=1 \
  max_updates=5 screen_every=100000 proagree_every=1000 screen_entries=2 proagree_rows=200 stored_values=false "$@"
