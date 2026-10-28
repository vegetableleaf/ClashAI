"""LOOP-OPS boot gate (LOOP-IW requirements, LOOP_IW.md 55fe195): float exactness of THIS machine before any rollout.

    cd $CB && PYTHONPATH=$CB:<pylib> JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED" \
      python -B scratchpad/gauntlet/L74/plan1026/pilot/ops/exact_gate.py CRFORGE_LIB FACADE_BUILD

Python side (fp/fp_gen.py's checks): np.exp on a 1-element float64 array == math.exp (glibc) on 200,000 values; numpy
(1,14) @ (14,) == the sequential non-FMA sum on 20,000 random rows. Java side (CfAbil, in a JVM started like the loop's):
CfAbil.EXACT (libm through the JDK 17 incubator FFI; false without the JAVA_TOOL_OPTIONS flags) and LOOP-IW's self-tests
(ability_id.selftest_draw / selftest_libm / selftest_sum) with 0 mismatches. Prints one line per check, then
EXACT_GATE PASS or EXACT_GATE FAIL (exit 1) naming what differs.
"""
import math
import os
import platform
import random
import sys
from pathlib import Path


def cpu():
    try:
        info = Path('/proc/cpuinfo').read_text()
        name = next((ln.split(':', 1)[1].strip() for ln in info.splitlines() if ln.startswith('model name')), '?')
        return name, ('avx512f' in info)
    except OSError:
        return platform.processor(), None


def main(lib, build):
    import numpy as np
    fails = []
    name, avx512 = cpu()
    print(f'cpu: {name}; avx512f {avx512}; numpy {np.__version__}; JAVA_TOOL_OPTIONS {os.environ.get("JAVA_TOOL_OPTIONS")!r}')
    rng = random.Random(7)
    bad = 0
    for _ in range(200000):
        z = rng.uniform(-40, 40)
        bad += int(np.exp(np.array([z]))[0] != math.exp(z))
    print(f'np.exp(1-elem) != math.exp: {bad} / 200000')
    if bad:
        fails.append(f'numpy exp differs from glibc exp on {bad} / 200000 (AVX512 SIMD exp?)')
    nrng, bad = np.random.default_rng(7), 0
    for _ in range(20000):
        z, c = nrng.normal(size=(1, 14)) * nrng.choice([.1, 1, 10]), nrng.normal(size=14)
        s = 0.0
        for a, b in zip(z[0], c):
            s += a * b
        bad += int((z @ c)[0] != s)
    print(f'numpy (1,14)@(14,) != sequential non-FMA sum: {bad} / 20000')
    if bad:
        fails.append(f'numpy dot order differs from the sequential sum on {bad} / 20000')
    import jpype
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'speed' / 'crforge' / 'obsid'))
    import ability_id
    jpype.startJVM(classpath=sorted(str(p) for p in Path(lib).glob('*.jar')) + [str(build)], convertStrings=True)
    exact = bool(jpype.JClass('CfAbil').EXACT)
    print(f'CfAbil.EXACT: {exact}')
    if not exact:
        fails.append('CfAbil.EXACT is false (JVM without --add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED?)')
    st = dict(draw=ability_id.selftest_draw(), libm=ability_id.selftest_libm(), sum=ability_id.selftest_sum())
    print(f'CfAbil self-tests mismatches: {st}')
    fails += [f'CfAbil self-test {k}: {v} mismatches' for k, v in st.items() if v]
    print('EXACT_GATE ' + ('PASS' if not fails else 'FAIL: ' + '; '.join(fails)), flush=True)
    return not fails


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:3]) else 1)
