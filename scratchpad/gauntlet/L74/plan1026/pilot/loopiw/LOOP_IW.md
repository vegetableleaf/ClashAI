# LOOP-IW: the hero ability press observation in Java (royale_env.ability_commands / ability_options)

Ticket: port the ability inputs + press decisions to Java for the fast loop, byte-identical to production on >= 38,400
seat-rows at the live cfg (succ48_x_s101), through the facade, CF-CLONE lib. Consumer: LOOP-INT. Labels (a) measured,
(b) untested, (c) contradicted.

## STATUS (keep current)
- Base: b84b440. Pod 33920 (moved 14:30 from 32657: there load 85 on the 54-core quota, 433k throttled periods; my
  runs there stopped by PID). Tree /workspace/loopiw/cb = /workspace/cb_stepd (cp -al: icebow/data; the 13 config
  data files md5-equal to 32657's d2x copy) + HEAD code overlay (git archive) + mine.tar (loopiw/, CfAbil, ability_id)
  + the cheap-win e1_eval.py; CF-CLONE lib_fix (core 3e86169b, from 30408 /workspace/cfclone/lib_fix) at
  /workspace/loopiw/lib; the old lib (e94447c0, from 32657 cfspeed) at /workspace/loopiw/oldlib; jpype at
  /workspace/loopiw/pylib (from 32657 cfspeed/pylib).
- DONE (a): cheap win committed (bffcb94; smokes = the known shas). CfAbil identical to production on 657,699 actor
  seat-rows (liw_full1, see Results). LOOP-INT messaged with the interface (7a747da). No runs of mine left on 33920.
- Restart / re-check: `cd /workspace/loopiw/cb/scratchpad/gauntlet/L74/plan1026/pilot/loopiw && ./abilcheck.sh RUN 12
  max_updates=1` (pod 33920), then `/workspace/venvf16/bin/python abil_sum.py /workspace/loopiw/RUN OUT.json`.
  Smokes: `cd /workspace/loopiw && ./smoke.sh crforge|royalesim RUN /workspace/loopiw/oldlib`.
- OPEN (b): _near (a hero button with neither a v2 model nor the live IW rule) never ran (nNear 0); self-play vs
  RoyalePoolEnv screen rows not counted apart (the 702-match init screen ran through the hook: all its rows are in the
  totals); numpy exp == glibc exp only measured on these AMD EPYC pods (no AVX512); a CfCore.load fork (search) would
  reset CfAbil's state (not on the live cfg's path).

## Float exactness (a, pod 32657: AMD EPYC 7702, glibc 2.39, numpy + scipy-openblas, no AVX512)
fp/ (fp_gen.py, FpProbe.java, Libm.java):
- numpy (1,14) @ (14,) == a sequential non-FMA sum: 88,000 / 88,000 (Java: the same loop is exact).
- np.exp on a 1-element array == math.exp (glibc): 200,000 / 200,000.
- Java vs glibc: StrictMath.exp 90.3%, Math.exp 99.74%, Math.pow 99.9%; Python `float(n) ** .5` != math.sqrt(n) on
  240 / 300,000 integers (glibc pow(x, .5) is not correctly rounded), so Java sqrt is NOT exact.
- glibc exp / pow through JDK 17's incubator FFI (jdk.incubator.foreign CLinker): 200,000 / 200,000 exp, 300,000 /
  300,000 pow(n, .5), 200,000 / 200,000 pow(1-p, dt); works under JPype with
  JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED". ~250 ns per call.
  So the port calls libm through FFI (exact on the machine it runs on) and falls back to Math.* without the flags
  (CfAbil.EXACT false: not byte-exact).
- (b) on an AVX512 machine numpy's float64 exp may be numpy's own SIMD code, not glibc: re-run fp/ there.

## Cheap win (pipeline/e1_eval.py, Match.prepare)
In head mode (cfg ability mode sample / greedy) the learner side's ability_commands result was replaced by [] right
after the call; the call (LiveIWPolicy observe = a second raw() + PublicObserver.update, plus the gates) is now not
made. Why identity-safe: its leftovers are my side's IW observer / frame, _ability_check[my side], _v2_dt and
_v2_info entries; the first three are read only by my side's own ability_commands (never called in head mode:
_fire_abilities uses _scan(_any_gate) for learned sides); _v2_dt is rewritten by every ability_commands before its
own _v2_q, and ability_options is called with rule None in head mode (no _v2_q); _v2_info entries are setdefault'ed
with the same values by ability_options at the same tick.

## Results (a)
- hs1 (first trial): commands 4,085/4,085, recheck 20/20, options float32 2,191/2,191; options float64 2,185/2,191:
  the freeze around() elixir sums (feature 46 / 49) 1 ulp off. Cause (a): CPython 3.12's sum() of floats is Neumaier's
  compensated sum (bltinmodule.c), not left to right. Fixed: CfAbil.PySum, used for every production sum() of floats
  (freeze around(), the IW geometry value, the hazard model's cost sums); explicit += loops stay left to right.
  Also: the IW observers' spell table is now filled at the first reset (2 calls had raised before the first fill).
- hs3 (fixed): commands 5,150/5,150 (32 with a press), options float64 2,795/2,795 incl. label q on 900 rows,
  recheck 32/32, CfAbil pending queue = production's after every fire 0 diffs; self-tests 0 mismatches: draw vs
  random.Random(str).random() 3,000, libm 20,000, PySum vs sum() 20,000.
- Cost (hs3, b: 1 actor, includes the first calls): production ability_commands + ability_options 670 us per seat-row;
  CfAbil 43 us per seat-row inside the JVM (177 us with JPype + the harness's Python wrappers).
- Cheap win smokes (old lib e94447c0, pod 33920): crforge u0000 e816a6a499f7c706, fin16 u0000 d4ef5467f45f2f06 = the
  known shas; u0001 pending.
- liw_full1 (12 actors, max_updates=1, CF-CLONE lib, pod 33920; results_liw_full1_sum.json): warm start 128 rule
  rollouts (label mode, 13,095 labels) + init held-out screen 702 matches (RoyalePoolEnv, greedy head) + the u0000
  rollout (sample head; batch_sha 4754a08f33d21453). 657,699 seat-rows, every check IDENTICAL, 0 errors:
  commands 360,633/360,633 (1,606 with a press), options (head) 297,066/297,066 (99,687 with a button), options label
  43,084/43,084 (13,095 with a button, q incl.), float32 feat 340,150/340,150, recheck 2,712/2,712; pending queue
  0 diffs / 1,128,637 fires. Rule paths run: IW live gate 14,450 (hazard model 730), v2 model + draw 47,080, _near 0.
  Self-tests 0 mismatches in all 12 actors. Cost per seat-row: production ability_commands + ability_options 329 us
  (with the cheap win); CfAbil 13.3 us inside the JVM, 43.7 us through JPype + the harness wrappers.
