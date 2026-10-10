"""SIM v3 jobs for the rocket_value2 variants on a Linux box (RunPod pod or VM), P single-worker search_s0 processes at a time.
  ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python pod_driver.py --repo /workspace/wt_rocket --out /workspace/results/rocket/s1 --jobs jobs.json --p 28 [--wrap PATH] [--py PYTHON]
jobs.json = [{"arm": "cb7", "census": "evo|lad|air", "seeds": [1, 5, ...], "wrap": "optional per job"}], arm flags from --armfile
(name flags... lines; `base` = none). The deployed LIVE_OPTIONS decision bundle (SIM-accepted flags) is added to every arm.
Every job writes <out>/chunks/<arm>_<census>_<k>/ and logs into <out>/fires_<arm>_<census>/; at the end the chunk matches are merged
into <out>/<arm>_<census>/matches.jsonl (the layout sim_summary2.py reads).  Wrap with `flock /workspace/cpu.lock` on a shared pod.
Env knobs: CK (live checkpoint), GEN1 (opponent generalist), CENSUS_EVO / CENSUS_LAD / CENSUS_AIR (paths relative to --repo or absolute)."""
import argparse, glob, json, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

ap = argparse.ArgumentParser()
ap.add_argument('--repo', required=True); ap.add_argument('--out', required=True); ap.add_argument('--jobs', required=True)
ap.add_argument('--p', type=int, default=28); ap.add_argument('--chunk', type=int, default=10, help='seeds per process')
ap.add_argument('--py', default=sys.executable)
ap.add_argument('--wrap', default='scratchpad/gauntlet/L74/rocket_value2/rv2_diag_s0.py')
ap.add_argument('--armfile', default='scratchpad/gauntlet/L74/rocket_value2/arms_all.txt')
a = ap.parse_args()

CK = os.environ.get('CK', 'icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt')
GEN1 = os.environ.get('GEN1', 'icebow/data/pipeline/gen_v1_s0/gen_s0.pt')
CEN = {'evo': os.environ.get('CENSUS_EVO', 'scratchpad/gauntlet/L70/pool_forms/loadable_decks.json'),
       'lad': os.environ.get('CENSUS_LAD', 'scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json'),
       'air': os.environ.get('CENSUS_AIR', 'scratchpad/gauntlet/L74/rocket_value2/air_census.json')}
LV = ('--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects '
      '--gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-threatened 2 --log-aim log_barrel '
      '--lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on '
      '--behaviour-telemetry').split()
flags = {}
for line in open(os.path.join(a.repo, a.armfile) if not os.path.isabs(a.armfile) else a.armfile):
    t = line.split()
    if t:
        flags[t[0]] = t[1:]
jobs = json.load(open(a.jobs))
os.makedirs(os.path.join(a.out, 'chunks'), exist_ok=True)
work = []
for j in jobs:
    seeds = list(j['seeds'])
    for k in range(0, len(seeds), a.chunk):
        work.append((j['arm'], j['census'], k // a.chunk, seeds[k:k + a.chunk], j.get('wrap') or a.wrap))


def run(w):
    arm, cen, k, seeds, wrap = w
    d = os.path.join(a.out, 'chunks', f'{arm}_{cen}_{k}')
    if os.path.exists(os.path.join(d, 'DONE')):
        return w, 0
    fire = os.path.join(a.out, f'fires_{arm}_{cen}')
    os.makedirs(fire, exist_ok=True)
    env = dict(os.environ, FIRE_DIR=fire, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
    env.pop('PLACEBO', None)
    if arm.startswith('plc'):
        env['PLACEBO'] = '1'
    c =(CEN[cen] if os.path.isabs(CEN[cen]) else os.path.join(a.repo, CEN[cen]))
    cmd = [a.py, wrap, '--out', d, '--seeds', ','.join(map(str, seeds)), '--opps', 'gen', '--arms', 'plain', '--gen', CK, '--opp-gen', GEN1,
           '--forms-mode', 'deck', '--device', 'cpu', '--workers', '1', '--tail-cap', '7200', '--tau-plain', '0.35', '--census', c,
           '--hero-abilities', '--ability-policy', 'v2', '--opp-policy', 'sample', '--opp-T', '0.3'] + LV + flags.get(arm, [])
    with open(d + '.log', 'w') as lg:
        rc = subprocess.call(cmd, cwd=a.repo, env=env, stdout=lg, stderr=subprocess.STDOUT)
    if rc == 0:
        open(os.path.join(d, 'DONE'), 'w').close()
    return w, rc


print(f'{len(work)} chunks of <= {a.chunk} seeds, {sum(len(w[3]) for w in work)} games, P={a.p}', flush=True)
done = 0
with ThreadPoolExecutor(a.p) as pool:
    for w, rc in pool.map(run, work):          # pool.map keeps submission order, so the priority order of jobs.json holds
        done += 1
        if rc:
            print('FAILED', w[:3], rc, flush=True)
        elif done % 10 == 0:
            print(f'{done}/{len(work)} chunks', flush=True)
for arm_cen in sorted({(w[0], w[1]) for w in work}):
    arm, cen = arm_cen
    dst = os.path.join(a.out, f'{arm}_{cen}')
    os.makedirs(dst, exist_ok=True)
    seen, rows = set(), []
    for f in sorted(glob.glob(os.path.join(a.out, 'chunks', f'{arm}_{cen}_*', 'matches.jsonl'))):
        for line in open(f):
            r = json.loads(line)
            if r.get('arm') == 'plain' and r['tag'] not in seen:
                seen.add(r['tag']); rows.append(line)
    with open(os.path.join(dst, 'matches.jsonl'), 'w') as o:
        o.writelines(rows)
    print(arm, cen, len(rows), 'matches merged', flush=True)
open(os.path.join(a.out, 'DRIVER_DONE'), 'w').close()
