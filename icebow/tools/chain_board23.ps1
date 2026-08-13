<#
Unattended chain: board-22 -> sprite-bank rebuild -> synth -> board-23.

WHY THIS EXISTS. board-23 is the ISOLATED test of the per-sprite scaling fix (commit 9d4b9cd):
`run.py sprites` re-cuts the bank so every sprite carries its source frame width as a `_w<px>` tag,
and `synth_images` then scales each paste to the base frame it lands on. Bank size, synth count,
coverage and the real images all stay exactly as board-21/22 had them, so the ONLY variable is that
pastes are now correctly sized. Seed 0 makes it directly comparable to board-21.

DO NOT add the KataCR segments here -- that is board-24, and bundling them would reproduce the
board-15/17/18 mistake of changing two things at once and getting an unattributable result.

Every step is GUARDED: a failure aborts before the next one runs, because the dangerous ordering is
`sprites` (which CLEARS the bank) followed by a training launch on a half-built dataset.
#>
param(
    [string]$Root  = "c:\Users\benpe\ClashBot\icebow",
    [int]   $Synth = 3000,
    [int]   $Seed  = 0,
    [switch]$NoWatchdog
)

Set-Location $Root
$py  = Join-Path $Root ".venv\Scripts\python.exe"
$log = Join-Path $Root "data\chain_board23.log"

function Say($m) {
    $s = "{0}  {1}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $m
    Write-Host $s
    $s | Out-File -FilePath $log -Append -Encoding utf8
}

function Bank() {
    # class dirs only -- _verify holds montages, not bank sprites
    Get-ChildItem (Join-Path $Root "data\detect\sprites") -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notlike '_*' } |
        ForEach-Object { Get-ChildItem $_.FullName -Filter *.png -ErrorAction SilentlyContinue }
}

Say "===== chain START (synth=$Synth seed=$Seed) ====="

# ---- 1. wait for the in-flight detector training (board-22) --------------------------------------
$p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
     Where-Object { $_.CommandLine -like '*detect*train.py*' } | Select-Object -First 1
if ($p) {
    Say "waiting on detector training PID $($p.ProcessId) (board-22)"
    try { Wait-Process -Id $p.ProcessId -ErrorAction Stop } catch { Say "wait ended: $_" }
    Say "training process exited"
} else {
    Say "no detector training running -- proceeding immediately"
}

# ---- 2. verify board-22 actually produced weights ------------------------------------------------
$b22 = Join-Path $Root "runs\detect\board-22\weights\best.pt"
if (-not (Test-Path $b22)) { Say "ABORT: $b22 missing -- board-22 produced no weights; bank left untouched"; exit 1 }
$csv = Join-Path $Root "runs\detect\board-22\results.csv"
$rows = if (Test-Path $csv) { (Import-Csv $csv).Count } else { 0 }
Say "board-22 OK: $rows epoch(s), best.pt present"

# ---- 3. rebuild the sprite bank (this is what applies the _w tagging) ----------------------------
$before = (Bank | Measure-Object).Count
Say "rebuilding sprite bank (was $before sprite(s)) -- this CLEARS and re-cuts every class dir"
& $py run.py sprites 2>&1 | Tee-Object -FilePath $log -Append
$all    = Bank
$total  = ($all | Measure-Object).Count
$tagged = ($all | Where-Object { $_.BaseName -match '_w\d+$' } | Measure-Object).Count
Say "bank rebuilt: $total sprite(s), $tagged carrying a _w tag"
if ($total -lt 1000)   { Say "ABORT: bank only $total sprite(s) -- rebuild failed"; exit 1 }
if ($tagged -ne $total) { Say "ABORT: $tagged of $total tagged -- the scaling fix did not apply, board-23 would test nothing"; exit 1 }

# ---- 4. regenerate synth at the SAME count (coverage must not change) ----------------------------
Say "regenerating synth ($Synth images, unchanged count so coverage matches board-21/22)"
& $py run.py sprites --synth $Synth 2>&1 | Tee-Object -FilePath $log -Append
$sy = (Get-ChildItem (Join-Path $Root "data\detect\synth\images") -Filter *.jpg -ErrorAction SilentlyContinue | Measure-Object).Count
Say "synth: $sy image(s)"
if ($sy -lt [int]($Synth * 0.9)) { Say "ABORT: synth produced $sy of $Synth -- not launching training"; exit 1 }

# ---- 5. battery watchdog (best effort -- never blocks the run) -----------------------------------
if (-not $NoWatchdog) {
    try {
        $wd = Join-Path $Root "tools\battery_watchdog.ps1"
        if (Test-Path $wd) {
            Start-Process powershell -ArgumentList @("-NoProfile","-ExecutionPolicy","Bypass","-File",$wd,"-Run","board-23") -WindowStyle Hidden
            Say "battery watchdog started for board-23"
        }
    } catch { Say "watchdog failed to start (non-fatal): $_" }
}

# ---- 6. launch board-23 --------------------------------------------------------------------------
Say "launching board-23: yolo11s.pt batch 8 imgsz 960 epochs 120 patience 30 seed $Seed"
& $py tools\detect\train.py --model yolo11s.pt --batch 8 --imgsz 960 --epochs 120 --patience 30 --seed $Seed 2>&1 |
    Tee-Object -FilePath $log -Append
Say "===== board-23 finished ====="
