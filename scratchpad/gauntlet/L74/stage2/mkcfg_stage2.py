"""S2-02: the Phase C matched Hog pair. Both arms = the O2 exploiter recipe (cfg/base_exploit.yaml = the resolved
rlarm_exploit.yaml of 10-16, i.e. L74/rlarms/mkcfg_arms.py 'exploit') with the Stage-2 settings; they differ ONLY in init.
    python mkcfg_stage2.py       -> cfg/s2_hog_e4.yaml, cfg/s2_hog_il.yaml (+ prints the raw diff)
Shared: league_decks = stage2/pools/decks_hog_train.json (Hog slice of the TRAIN pool), learner icebow share 0, the only
opponent = Mark CXXXVIII grafted (sha-checked, decoded 'live' = greedy), PFSP off, no externals, opp_style off,
live_levels false + no opp_tower_troops (objection 9: the trainer swaps those between seats), save_every 5, 65 updates,
seed 74. Run with ROYALE_HEROIW_FORM=hero, ROYALE_RUNTIME=fork36-linux."""
import hashlib, os, sys
import yaml
H = os.path.dirname(os.path.abspath(__file__))
RL = "icebow/data/bench/rl_royale"
CXXXVIII, CXXXVIII_SHA = f"{RL}/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt", "0fba110cb883ec1c3ffae0502a90a4bff1ba92b2c8937feef8f039c1590c1d83"
INITS = {"s2_hog_e4": (f"{RL}/rdef_e4/rdef_e4_u0020.pt", "7fb666811d8b46de12463bc497aded98fcfde62f732917f64b0f76244b24a830"),   # RAW E4 (the RL output, no grafted refine heads): the grafted w2 file failed the smoke round trip (cell_nll 2.92876994 vs 2.92876984, float non-determinism in cell_refine); RL inits are ungrafted everywhere else too (cue arm precedent), and gen_v32_s0 has no refine heads either
         "s2_hog_il": ("icebow/data/pipeline/gen_v32_s0/gen_s0.pt", "61011b6ce5e655c0f66c875ee844685373cc6370051f9eccba1e1d79de1a0569")}
root = sys.argv[1] if len(sys.argv) > 1 else "."          # checkout root for the sha checks (laptop repo or pod cb_tt)
for p, s in [(CXXXVIII, CXXXVIII_SHA)] + list(INITS.values()):
    if hashlib.sha256(open(os.path.join(root, p), "rb").read()).hexdigest() != s:
        raise SystemExit(f"{p}: sha256 is not {s[:16]}...")
base = yaml.safe_load(open(os.path.join(H, "cfg/base_exploit.yaml")))
assert base["seed"] == 74 and base["max_updates"] == 65 and base["save_every"] == 5 and base["advantage"] == "gae"
S2 = dict(league_decks="scratchpad/gauntlet/L74/stage2/pools/decks_hog_train.json", league_learner_icebow_share=0.0,
          league_frozen_opponent=CXXXVIII, league_pfsp="off", league_external=[], opp_style="off", league_opp_policy="live",
          live_levels=False)
out = {}
for arm, (init, _) in INITS.items():
    c = {**base, **S2, "init": init}
    c.pop("opp_tower_troops", None)
    yaml.safe_dump(c, open(os.path.join(H, f"cfg/{arm}.yaml"), "w", newline="\n"), sort_keys=False)
    out[arm] = c
a, b = out["s2_hog_e4"], out["s2_hog_il"]
diff = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
assert diff == ["init"], diff
print("raw diff s2_hog_e4 vs s2_hog_il:", diff, "| changed vs base_exploit:", sorted(k for k in set(a) | set(base) if a.get(k) != base.get(k)))
