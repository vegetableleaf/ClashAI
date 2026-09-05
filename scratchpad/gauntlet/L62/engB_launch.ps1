# engB: the engA pair RELAUNCHED with the GATE PRIOR ON IN BOTH ARMS (coef 2.0), so the only
# between-arm variable is still --kl_coef (control 0 vs KL-to-frozen-init 0.3).
# engA was killed at m=422 because the play gate collapsed to 0.0% of decisions above tau=0.25;
# `gate_prior_coef 2.0` is the sim trainer's term that exists to stop exactly that (engine_ppo_v2.md).
#
# EVERYTHING ELSE IS IDENTICAL TO THE KILLED RUN: same init (sha a1273d5d*, asserted in-process and
# never written), seed 41, rollout 1024, 2000 matches, save_every 250, value_warmup 60,
# --kl_in_warmup 0 (engA ran the pre-flag file, i.e. that behaviour), the bcA_run.yaml hyper-parameter
# VALUES baked into engine_ppo.py's defaults, and one VM slot each on the DIRECT ports 38031 / 38032.
# NEW out_prefixes and log names, so nothing overwrites engA's evidence.
#
# PREFLIGHT: refuses to launch unless both engine slots actually answer. At 15:16 on 2026-09-05 the
# worker service was DOWN on both slots (`worker status` -> services [false, false]) while the VM was
# up, and a trainer started against a dead slot dies on its first reset with WinError 10054.
$ErrorActionPreference = "Stop"
$py   = "C:\Users\benpe\ClashBot\icebow\.venv\Scripts\python.exe"
$scr  = "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\engine_ppo.py"
$L62  = "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62"
$env:PYTHONPATH = "src"
$env:PYTHONHASHSEED = "0"

# ---- preflight 1: no engB output may already exist -------------------------------------------------
$clash = @()
$clash += Get-ChildItem "C:\Users\benpe\ClashBot\icebow\data\bench\engB_*" -ErrorAction SilentlyContinue
$clash += Get-ChildItem "$L62\engB_*.log" -ErrorAction SilentlyContinue
$clash += Get-ChildItem "$L62\engB_*.std*" -ErrorAction SilentlyContinue
if ($clash.Count -gt 0) { throw "engB outputs already exist, refusing to overwrite: $($clash.FullName -join ', ')" }

# ---- preflight 2: both engine slots must answer a read-only observe --------------------------------
$probeOut = & "C:\Users\benpe\ClashBot\icebow\.venv\Scripts\python.exe" "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\engB_preflight.py"
$probeOut
if ($LASTEXITCODE -ne 0) { throw "engine slots are not serving; fix the worker service before launching" }

# ---- launch ----------------------------------------------------------------------------------------
$common = "--matches 2000 --seed 41 --rollout 1024 --save_every 250 --value_warmup 60 --kl_in_warmup 0 --gate_prior_coef 2.0"
$arms = @(
  @{ name="ctrl"; port=38031; kl="0";   prefix="C:/Users/benpe/ClashBot/icebow/data/bench/engB_ctrl"; log="$L62/engB_ctrl_20260905.log" },
  @{ name="kl";   port=38032; kl="0.3"; prefix="C:/Users/benpe/ClashBot/icebow/data/bench/engB_kl";   log="$L62/engB_kl_20260905.log" }
)
$pids = @{}
foreach ($a in $arms) {
  $args = "$scr --port $($a.port) --kl_coef $($a.kl) $common --out_prefix $($a.prefix) --log $($a.log)"
  $p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory "C:\Users\benpe\ClashBot\icebow" `
        -RedirectStandardOutput "$L62/engB_$($a.name)_20260905.stdout" -RedirectStandardError "$L62/engB_$($a.name)_20260905.stderr" `
        -WindowStyle Hidden -PassThru
  $pids[$a.name] = $p.Id
  "$($a.name): pid $($p.Id) port $($a.port) kl $($a.kl) gate_prior 2.0 -> $($a.log)"
}
$pids | ConvertTo-Json | Out-File -Encoding utf8 "$L62/engB_pids.json"
