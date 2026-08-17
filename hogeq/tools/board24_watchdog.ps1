# Overnight watchdog for the board-24 detector run.
#
# The run has died twice already for environment reasons, not training reasons:
#   * WinError 1455 (paging file too small) when a 32-env CPU train-sim-ppo was running alongside it
#     and every dataloader worker tried to load torch, and
#   * CUDA OOM when a previous hung train.py was still holding ~7.7 GB of the 8 GB card.
# Both are transient, and ultralytics keeps its own epoch counter + last.pt, so resuming loses nothing.
# This script restarts the run whenever the process disappears before training finished, and stops
# once best.pt exists and no further epochs are pending.

$ErrorActionPreference = 'SilentlyContinue'
$root = 'C:\Users\benpe\ClashBot\icebow'
$py = Join-Path $root '.venv\Scripts\python.exe'
$runDir = Join-Path $root 'runs\detect\board-24'
$log = Join-Path $root 'runs\board24_train.out'
$err = Join-Path $root 'runs\board24_train.err'
$wdLog = Join-Path $root 'runs\board24_watchdog.log'

function Write-Wd($msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $msg" | Add-Content -Path $wdLog
}

function Get-TrainProc {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'detect[\\/]train\.py' } |
        Select-Object -First 1
}

Write-Wd "watchdog started"

while ($true) {
    Start-Sleep -Seconds 60

    # Finished? ultralytics writes results.csv row-per-epoch and best.pt at the end of each better epoch.
    $results = Join-Path $runDir 'results.csv'
    if (Test-Path $results) {
        $rows = (Get-Content $results | Measure-Object -Line).Lines - 1
        if ($rows -ge 120) { Write-Wd "training reached $rows epochs -- watchdog done"; break }
    }

    $proc = Get-TrainProc
    if ($proc) { continue }

    # Process is gone. Free any VRAM still held by a hung sibling, then resume.
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'multiprocessing.spawn' } |
        ForEach-Object {
            if ($_.CommandLine -match 'parent_pid=(\d+)') {
                $pp = [int]$Matches[1]
                if (-not (Get-Process -Id $pp -ErrorAction SilentlyContinue)) {
                    Stop-Process -Id $_.ProcessId -Force
                }
            }
        }
    Start-Sleep -Seconds 10

    $last = Join-Path $runDir 'weights\last.pt'
    if (Test-Path $last) {
        Write-Wd "run stopped with a checkpoint present -- resuming board-24"
        $args = @('tools/detect/train.py', '--resume', 'board-24')
    } else {
        Write-Wd "run stopped before any checkpoint -- restarting board-24 from scratch"
        Remove-Item -Recurse -Force $runDir
        $args = @('tools/detect/train.py', '--model', 'yolo11s.pt', '--epochs', '120',
                  '--imgsz', '960', '--batch', '4', '--patience', '30', '--workers', '4',
                  '--name', 'board-24')
    }
    $p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $root `
        -RedirectStandardOutput $log -RedirectStandardError $err -WindowStyle Hidden -PassThru
    Write-Wd "relaunched as PID $($p.Id)"
}
