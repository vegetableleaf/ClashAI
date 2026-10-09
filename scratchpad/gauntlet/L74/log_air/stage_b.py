"""Stage B of the log_air A/B (VM): run the log_air arms only on the games log_air can change.
A log_air arm is game-identical to base until its first log_air touch, and a touch happens only at a Log play whose corridor
holds only flyers -- which the base arm logs (log_fire_s0.py: play and kind == only_air). So every base game WITHOUT such a Log
play has an identical retarget / block game (checked: det_check.py), and only the candidate games need the log_air arms.
Polls the base fires, launches one search_s0 job per (arm, census) for the candidate seeds not yet run, until base is DONE and
everything launched has finished.   python stage_b.py [workers=4] [nice=10]"""
import glob, json, os, subprocess, sys, time

HOME = os.path.expanduser('~')
O, REPO = f'{HOME}/log_air/sim', f'{HOME}/log_air/repo'
W, NICE = (sys.argv[1] if len(sys.argv) > 1 else '4'), (sys.argv[2] if len(sys.argv) > 2 else '10')
CEN = dict(evo='scratchpad/gauntlet/L70/pool_forms/loadable_decks.json', lad='scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json',
           air='scratchpad/gauntlet/L74/log_air/air_census.json')
CK = f'{HOME}/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt'
LV = ('--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects '
      '--gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind '
      '--xbow-dead-lane block --gate-hazard-threatened 2').split()
X = dict(retarget=['--log-air', 'retarget'], block=['--log-air', 'block'])
launched, procs, n = {}, [], 0


def candidates(s):
    out = set()
    for f in glob.glob(f'{O}/fires_base_{s}/fires_*.jsonl'):
        for line in open(f):
            try:
                x = json.loads(line)
            except ValueError:                  # a line still being written
                continue
            if x.get('play') and x.get('kind') == 'only_air':
                out.add(int(x['tag'].split(':')[-1]))
    return out


def launch(arm, s, seeds):
    global n
    n += 1
    name = f'{arm}_{s}_b{n}'
    fire = f'{O}/fires_{name}'
    os.makedirs(fire, exist_ok=True)
    env = dict(os.environ, ROYALE_RUNTIME='20261006-linux', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', FIRE_DIR=fire)
    cmd = ['nice', '-n', NICE, f'{HOME}/venv/bin/python', 'scratchpad/gauntlet/L74/log_air/log_fire_s0.py', '--out', f'{O}/{name}',
           '--seeds', ','.join(map(str, sorted(seeds))), '--opps', 'gen', '--arms', 'plain', '--gen', CK, '--opp-gen',
           'icebow/data/pipeline/gen_v1_s0/gen_s0.pt', '--forms-mode', 'deck', '--device', 'cpu', '--workers', W, '--tail-cap', '7200',
           '--tau-plain', '0.35', '--census', CEN[s], '--hero-abilities', '--ability-policy', 'v2', '--opp-policy', 'sample',
           '--opp-T', '0.3', *LV, *X[arm]]
    procs.append(subprocess.Popen(cmd, cwd=REPO, env=env, stdout=open(f'{O}/{name}.log', 'w'), stderr=subprocess.STDOUT))
    print(time.strftime('%T'), 'launched', name, sorted(seeds), flush=True)


BATCH = 8                                   # fewer, bigger jobs: each one reloads the models
while True:
    base_done = os.path.exists(f'{O}/sim_base.log') and 'DONE' in open(f'{O}/sim_base.log').read()
    for s in CEN:
        new = candidates(s) - launched.setdefault(s, set())
        if new and (len(new) >= BATCH or base_done):
            for arm in X:
                launch(arm, s, new)
            launched[s] |= new
    if base_done and all(p.poll() is not None for p in procs):
        # one last sweep: candidates that appeared after the last poll
        if all(not (candidates(s) - launched[s]) for s in CEN):
            break
    time.sleep(120)
print(time.strftime('%T'), 'stage B done', {s: len(v) for s, v in launched.items()}, flush=True)
