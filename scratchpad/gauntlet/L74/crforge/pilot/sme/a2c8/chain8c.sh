#!/usr/bin/env bash
# a2c8 round 8 sub-rounds, sequential
S=/workspace/pilot/sme_live; I=/workspace/pilot
BASE=$S/r78 INPUTS=$I/inputs_v19/inputs_rngfree.jsonl ./run8.sh r80
BASE=$S/r80 INPUTS=$I/inputs_v20/inputs_rngfree.jsonl ./run8.sh r81
BASE=$S/r81 INPUTS=$I/inputs_v21/inputs_rngfree.jsonl ./run8.sh r82
BASE=$S/r82 INPUTS=$I/inputs_v21/inputs_rngfree.jsonl ./run8.sh r83 SME_MECH_CROSS=1
BASE=$S/r83 INPUTS=$I/inputs_v22/inputs_rngfree.jsonl ./run8.sh r84 SME_MECH_CROSS=1 SME_HIDDEN=1
BASE=$S/r84 INPUTS=$I/inputs_v22/inputs_rngfree.jsonl ./run8.sh r85 SME_MECH_CROSS=1 SME_HIDDEN=1 SME_BANNER=1
