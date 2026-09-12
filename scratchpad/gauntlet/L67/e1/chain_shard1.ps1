# E1 option B, single-slot chain (L67ak): wait for baseline shard 0/2 on door 38031 to exit, then run shard 1/2 on the
# SAME door into baseline_k0\slot1. One engine client at a time (free RAM ~1.3-1.8 GB with one eval process, 2026-09-12).
$Repo = 'C:\Users\benpe\ClashBot'
Set-Location $Repo
$Py   = "$Repo\icebow\.venv\Scripts\python.exe"
$E1   = "$Repo\scratchpad\gauntlet\L67\e1"
$Ckpt = 'icebow\data\pipeline\s1_icebow_v6lat_s0.pt'
$Log  = "$E1\chain.log"

function Note([string]$m) { "$(Get-Date -Format s) $m" | Add-Content $Log }

$line = (Get-Content "$E1\pids.txt" | Select-String 'baseline port=38031 shard=0/2' | Select-Object -Last 1).Line
$p0 = [int]([regex]::Match($line, 'pid=(\d+)').Groups[1].Value)
Note "chain start; waiting for shard 0/2 launcher pid $p0"
try { Wait-Process -Id $p0 -ErrorAction Stop } catch { Note "pid $p0 already gone" }
$n0 = if (Test-Path "$E1\baseline_k0\slot0\matches.jsonl") { (Get-Content "$E1\baseline_k0\slot0\matches.jsonl").Count } else { 0 }
Note "shard 0/2 exited; matches=$n0"
if (Test-Path "$E1\baseline_k0\slot0\errors.jsonl") { Note "shard 0/2 wrote errors.jsonl -- NOT starting shard 1/2"; exit 3 }

$Out = "$E1\baseline_k0\slot1"
if ((Test-Path $Out) -and (Get-ChildItem $Out -ErrorAction SilentlyContinue)) { Note "slot1 output not empty -- stop"; exit 4 }
$argv = @('-m','pipeline.e1_eval','--mode','eval','--policy','live','--ckpt',$Ckpt,'--port','38031','--shard','1/2',
          '--split','heldout','--entries','0:293','--seeds','0','--out',$Out)
$p1 = Start-Process -FilePath $Py -ArgumentList $argv -WorkingDirectory $Repo -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput "$Out.stdout.log" -RedirectStandardError "$Out.stderr.log"
"$(Get-Date -Format s) pid=$($p1.Id) baseline port=38031 shard=1/2 out=$Out" | Add-Content "$E1\pids.txt"
Note "shard 1/2 launched pid $($p1.Id)"
Wait-Process -Id $p1.Id
$n1 = if (Test-Path "$Out\matches.jsonl") { (Get-Content "$Out\matches.jsonl").Count } else { 0 }
Note "shard 1/2 exited; matches=$n1"
Note "CHAIN DONE"
