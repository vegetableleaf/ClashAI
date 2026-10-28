"""Float-op agreement probe (LOOP-IW): numpy dot order, np.exp / math.exp, pow(x,.5) vs sqrt, pow(1-p, dt).
Writes inputs + Python results as raw float64 hex for FpProbe.java to recompute."""
import json, math, random, struct, sys
import numpy as np
M = json.load(open(sys.argv[1]))['models']
rng = random.Random(7)
out = open('fp_in.txt', 'w')
h = lambda v: struct.pack('>d', float(v)).hex()
fma = lambda a, b, c: float(np.float64(a) * np.float64(b) + np.float64(c))  # placeholder, not used
nd = {'seq': 0, 'n': 0}
for name, m in M.items():
    if m['type'] != 'logistic_timing':
        continue
    mean, scale, coef = np.asarray(m['mean']), np.asarray(m['scale']), np.asarray(m['coefficients'])
    for _ in range(4000):
        x = np.array([rng.uniform(0, 60), rng.random(), rng.uniform(0, 40), rng.uniform(0, 40), rng.randrange(6),
                      rng.randrange(6000), rng.randrange(8), rng.randrange(9000), rng.randrange(2), rng.uniform(0, 40),
                      rng.uniform(0, 10), rng.randrange(4), rng.randrange(1, 4), rng.randrange(-3, 4)], float)
        z = ((np.atleast_2d(x) - mean) / scale)
        d = (z @ coef)[0]
        s = 0.0
        for a, b in zip(z[0], coef):
            s += a * b
        nd['n'] += 1; nd['seq'] += int(s == d)
        out.write('D ' + ' '.join(h(v) for v in z[0]) + ' ' + ' '.join(h(v) for v in coef) + ' ' + h(d) + '\n')
print('dot: python sequential non-FMA == numpy', nd)
ne = 0
for _ in range(200000):
    zv = rng.uniform(-40, 40)
    a, b = np.exp(np.array([-zv]))[0], math.exp(-zv)
    ne += int(a != b)
    out.write('E %s %s %s\n' % (h(-zv), h(a), h(b)))
print('np.exp(1-elem) != math.exp:', ne, '/ 200000')
ns = 0
for _ in range(300000):
    n = rng.randrange(0, 330000) ** 2 + rng.randrange(0, 580000) ** 2
    a, b = float(n) ** .5, math.sqrt(n)
    ns += int(a != b)
    out.write('S %s %s\n' % (h(n), h(a)))
print('pow(n,.5) != sqrt(n):', ns, '/ 300000')
for _ in range(200000):
    p = rng.random() * rng.choice([1, .1, .01, .001])
    dt = rng.choice([0.5, 1.0, 1.5, 0.25, 0.75, 2.0, 1.3, 0.05 * rng.randrange(1, 80)])
    out.write('P %s %s %s\n' % (h(1 - p), h(dt), h((1 - p) ** dt)))
