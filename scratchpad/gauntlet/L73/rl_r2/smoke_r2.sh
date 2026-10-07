#!/bin/bash
# CPU smoke of the R2 config (run_r2.sh overrides) through rl_royale --smoke (E=4 G=2, 1 actor, 2 updates, resume check).
# CPU only, 2+2 threads, below-normal priority (inherited by the spawned actor). Output: scratchpad/gauntlet/L68/rl/<run>
# and icebow/data/bench/rl_royale/<run> (rl_royale's fixed RUN_ROOT / CKPT_ROOT; the run name is the only knob).
cd /c/Users/benpe/ClashBot
O=scratchpad/gauntlet/L73/rl_r2
export CUDA_VISIBLE_DEVICES=-1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 ROYALE_RUNTIME=20261006
export "PYTHONPATH=C:/Users/benpe/ClashBot/research/ext/Royale-20261006/runtime;C:/Users/benpe/ClashBot"
OVR=(init=icebow/data/pipeline/gen_v32_s0/gen_s0.pt proagree_data_gen=icebow/data/pipeline/gen_dataset_v32_fv5.npz league=true
     noise_off=all opp_elixir=counter action_delay_ticks=26 extrapolate_ticks=26 "screen_seeds=[0]" league_learner_icebow_share=1.0
     forms_mode=deck advantage=gae gae_gamma_unit=tick critic_warmup_updates=5 hero_abilities=true ability_policy=v2
     tau=0.35 T=0.3 league_decks=$O/loadable_decks_ladder.json league_deck_alpha=1.0 league_deck_floor=0 league_icebow_share=0.02
     "league_mix={latest: 0.35, older: 0.25, init: 0.2, s1: 0.02}"
     actor_device=cpu learner_device=cpu actor_threads=2 in_flight=4 screen_entries=2)
research/ext/Royale/.venv/Scripts/python.exe -m pipeline.rl_royale \
    --config scratchpad/gauntlet/L69/rl/r1_rl_royale.yaml --run rseries_r2l_smoke --smoke "${OVR[@]}" > $O/smoke.out 2> $O/smoke.err
echo "smoke exit $?" >> $O/smoke.out
