# engA: first PPO on the real engine -- control (kl 0) on slot 0 (direct port 38031) vs KL arm (kl 0.3) on slot 1 (38032).
# Requires the VM up with 2 slots (scratchpad/gauntlet/L62/_boot.ps1). Refuses to overwrite existing outputs (asserts inside).
$ErrorActionPreference = "Stop"
$py   = "C:\Users\benpe\ClashBot\icebow\.venv\Scripts\python.exe"
$scr  = "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\engine_ppo.py"
$L62  = "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62"
$env:PYTHONPATH = "src"
$env:PYTHONHASHSEED = "0"
$common = "--matches 2000 --seed 41 --rollout 1024 --save_every 250 --value_warmup 60"
$arms = @(
  @{ name="ctrl"; port=38031; kl="0";   prefix="C:/Users/benpe/ClashBot/icebow/data/bench/engA_ctrl"; log="$L62/engA_ctrl_20260905.log" },
  @{ name="kl";   port=38032; kl="0.3"; prefix="C:/Users/benpe/ClashBot/icebow/data/bench/engA_kl";   log="$L62/engA_kl_20260905.log" }
)
$pids = @{}
foreach ($a in $arms) {
  $args = "$scr --port $($a.port) --kl_coef $($a.kl) $common --out_prefix $($a.prefix) --log $($a.log)"
  $p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory "C:\Users\benpe\ClashBot\icebow" `
        -RedirectStandardOutput "$L62/engA_$($a.name)_20260905.stdout" -RedirectStandardError "$L62/engA_$($a.name)_20260905.stderr" `
        -WindowStyle Hidden -PassThru
  $pids[$a.name] = $p.Id
  "$($a.name): pid $($p.Id) port $($a.port) kl $($a.kl) -> $($a.log)"
}
$pids | ConvertTo-Json | Out-File -Encoding utf8 "$L62/engA_pids.json"
