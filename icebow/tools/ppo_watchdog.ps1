# Watchdog for train-sim-ppo that restarts the run when it collapses into very low or plateauing
# performance, while keeping the current checkpoint so the restart is cheap.

$ErrorActionPreference = 'SilentlyContinue'
$root = 'C:\Users\benpe\ClashBot\icebow'
$py = Join-Path $root '.venv\Scripts\python.exe'
$log = Join-Path $root 'runs\ppo_watchdog.log'
$trainLog = Join-Path $root 'runs\ppo_train.out'
$trainErr = Join-Path $root 'runs\ppo_train.err'
$ckpt = Join-Path $root 'data\policy_sim_ppo.pt'

function Write-Wd($msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Add-Content -Path $log
}

function Get-TrainProc {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'run\.py' -and $_.CommandLine -match 'train-sim-ppo' } |
        Select-Object -First 1
}

function Start-Training {
    $args = @('run.py', 'train-sim-ppo', '--size', '432', '--matches', '100000', '--envs', '32', '--device', 'cpu', '--resume')
    $p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $root `
        -RedirectStandardOutput $trainLog -RedirectStandardError $trainErr -WindowStyle Hidden -PassThru
    Write-Wd "restart -> PID $($p.Id)"
}

Write-Wd 'watchdog started'
$lastIntervention = $null

while ($true) {
    Start-Sleep -Seconds 60
    $proc = Get-TrainProc
    if (-not $proc) {
        if (Test-Path $ckpt) {
            Write-Wd 'process exited; restarting PPO from checkpoint'
            Start-Training
        } else {
            Write-Wd 'process exited and no checkpoint exists; starting fresh'
            Start-Training
        }
        continue
    }

    if (Test-Path $trainLog) {
        $tail = Get-Content $trainLog -Tail 40 -ErrorAction SilentlyContinue
        if ($tail -match 'intervention trigger') {
            if ($null -eq $lastIntervention) {
                $lastIntervention = Get-Date
            }
            Write-Wd 'intervention detected in logs; restarting PPO'
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 10
            Start-Training
            $lastIntervention = Get-Date
        }
    }
}
