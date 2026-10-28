# LOOP-IW: the hero ability press observation in Java (royale_env.ability_commands / ability_options)

Ticket: port the ability inputs + press decisions to Java for the fast loop, byte-identical to production on >= 38,400
seat-rows at the live cfg (succ48_x_s101), through the facade, CF-CLONE lib. Consumer: LOOP-INT. Labels (a) measured,
(b) untested, (c) contradicted.

## STATUS (keep current)
- Base: b84b440. Pod 32657 (54-core cgroup, shared). Tree /workspace/loopiw/cb = /workspace/d2x/cb (cp -al: icebow/data)
  + HEAD code overlay (git archive of pipeline/, L68 live_reader, L70 abilities, L74 code files); CF-CLONE lib_fix
  (core 3e86169b, from 30408 /workspace/cfclone/lib_fix) at /workspace/loopiw/lib.
- DONE: float-op probe (below). Cheap win written (pipeline/e1_eval.py prepare), smokes RUNNING:
  /workspace/loopiw/logs/liw_smoke_cf.log, liw_smoke_rs.log (old lib e94447c0: expect crforge e816a6a4 / f060b678,
  fin16 d4ef5467 / 6cd7292f). Restart: `cd /workspace/loopiw && ./smoke.sh crforge liw_smoke_cf
  /workspace/cfspeed/crforge/env/build/install/env/lib` (royalesim liw_smoke_rs for fin16).
- WRITTEN, UNVERIFIED: speed/crforge/obsid/CfAbil.java (3a + 3b + 3c in one class), obsid/ability_id.py (tables from
  production + JavaAbil builder), hook/ (actor_abil.py + sitecustomize.py: actor-path comparison), abilcheck.sh,
  abil_sum.py. Harness trial under --smoke: /workspace/loopiw/logs/liw_hs1.log, results /workspace/loopiw/liw_hs1/.
  Restart: `cd /workspace/loopiw/cb/scratchpad/gauntlet/L74/plan1026/pilot/loopiw && ./abilcheck.sh RUN NACT
  actor_device=cpu learner_device=cpu --smoke` (full run: `./abilcheck.sh RUN 12 max_updates=1`).
- NEXT: commit the cheap win once both shas match; fix harness trial findings; full identity run (>= 38,400 seat-rows,
  warm start = label mode + rollouts + screens); cost per seat-row; message LOOP-INT per part.

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
