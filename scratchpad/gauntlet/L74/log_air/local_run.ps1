# Laptop SIM runner (VM gone): below-normal priority, at most 4 worker processes, no GPU.
#   powershell -File local_run.ps1 -Name base_air -Census air -Seeds 0:60 [-LogAir retarget|block]
param([string]$Name, [string]$Census, [string]$Seeds, [string]$LogAir = '', [int]$Workers = 4)
(Get-Process -Id $PID).PriorityClass = 'BelowNormal'
$R = 'C:\Users\benpe\ClashBot\.claude\worktrees\agent-a93fc9a12f7a33091'
Set-Location $R
$env:ROYALE_RUNTIME = '20261006'; $env:OMP_NUM_THREADS = '1'; $env:MKL_NUM_THREADS = '1'; $env:CUDA_VISIBLE_DEVICES = ''
$cen = @{ evo = 'scratchpad/gauntlet/L70/pool_forms/loadable_decks.json'; lad = 'scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json'; air = 'scratchpad/gauntlet/L74/log_air/air_census.json' }[$Census]
$O = 'C:\Users\benpe\AppData\Local\Temp\logair_local'; New-Item -ItemType Directory -Force "$O\fires_$Name" | Out-Null
$env:FIRE_DIR = "$O\fires_$Name"
$ck = 'icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt'
$a = @('scratchpad/gauntlet/L74/log_air/log_fire_s0.py', '--out', "$O\$Name", '--seeds', $Seeds, '--opps', 'gen', '--arms', 'plain',
  '--gen', $ck, '--opp-gen', 'icebow/data/pipeline/gen_v1_s0/gen_s0.pt', '--forms-mode', 'deck', '--device', 'cpu', '--workers', $Workers,
  '--tail-cap', '7200', '--tau-plain', '0.35', '--census', $cen, '--hero-abilities', '--ability-policy', 'v2', '--opp-policy', 'sample',
  '--opp-T', '0.3', '--xbow-class', 'class_sample', '--xbow-class-floor', '0.3', '--tau-phase', '0.35', '0.45', '0.55',
  '--spell-aim', 'rocket_area', '--own-effects', '--gate-decode', 'hazard_below_tau', '--gate-hazard-min-elixir', '9',
  '--log-aim', 'log_barrel', '--lethal-rocket', 'ot_behind', '--xbow-dead-lane', 'block', '--gate-hazard-threatened', '2')
if ($LogAir) { $a += @('--log-air', $LogAir) }
& 'C:\Users\benpe\ClashBot\research\ext\Royale\.venv\Scripts\python.exe' @a *> "$O\$Name.log"
"$Name rc=$LASTEXITCODE $(Get-Date -Format T)" | Add-Content "$O\done.log"
