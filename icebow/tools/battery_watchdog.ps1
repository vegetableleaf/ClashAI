# Battery watchdog for a detector training run.
#
# Polls the battery and stops board training if it falls to the threshold, so the run ends at a
# RESUMABLE checkpoint instead of dying when the machine does. Ultralytics writes last.pt every
# epoch, so `tools\detect\train.py --resume board-N` picks up with the epoch count, best.pt and
# patience state intact -- at most one epoch is lost.
#
# Deliberately narrow:
#   * kills ONLY the detector training (the GPU job). train-sim-ppo is CPU-only and draws far less,
#     so killing it would buy little and cost the run.
#   * exits by itself when training finishes, so it leaves nothing running.
#   * refuses to kill if last.pt is missing -- without it the run is NOT resumable and stopping
#     would throw the work away, which is worse than letting the battery decide.
param(
    [int]$Threshold = 10,
    [int]$PollSeconds = 60,
    [string]$Run = "board-21"
)

$ErrorActionPreference = "SilentlyContinue"
$log  = "c:\Users\benpe\ClashBot\icebow\data\battery_watchdog.log"
$last = "c:\Users\benpe\ClashBot\icebow\runs\detect\$Run\weights\last.pt"

function Note($m) {
    $line = "{0}  {1}" -f (Get-Date -Format "HH:mm:ss"), $m
    Add-Content -Path $log -Value $line
}

Note "watchdog START  run=$Run  threshold=$Threshold%  poll=${PollSeconds}s"

while ($true) {
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
               Where-Object { $_.CommandLine -like '*detect*train*' })
    if ($procs.Count -eq 0) {
        Note "training no longer running -- watchdog exiting, nothing to do"
        break
    }

    $bat = Get-CimInstance Win32_Battery
    $pct = [int]$bat.EstimatedChargeRemaining
    $st  = [int]$bat.BatteryStatus          # 1 = discharging, 2 = on AC

    if ($pct -le $Threshold) {
        if (-not (Test-Path $last)) {
            Note "battery $pct% but NO last.pt at $last -- NOT killing (run would be unrecoverable)"
        } else {
            Note "battery $pct% (status $st) <= $Threshold% -- stopping $Run"
            foreach ($p in $procs) {
                Note "  stopping PID $($p.ProcessId)"
                Stop-Process -Id $p.ProcessId -Force
            }
            Start-Sleep -Seconds 3
            $left = @(Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
                      Where-Object { $_.CommandLine -like '*detect*train*' }).Count
            Note "stopped. remaining detect-train procs: $left"
            Note "RESUME WITH:  tools\detect\train.py --resume $Run"
            break
        }
    }
    Start-Sleep -Seconds $PollSeconds
}
Note "watchdog END"
