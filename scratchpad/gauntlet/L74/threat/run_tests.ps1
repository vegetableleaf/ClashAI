# Single-process pytest at below-normal priority, CPU only (owner may be live on the laptop).
param([string]$Out, [string[]]$Tests)
$w = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))
$env:CUDA_VISIBLE_DEVICES = ''
$args2 = @('-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-x') + $Tests
$p = Start-Process -FilePath 'C:\Users\benpe\ClashBot\icebow\.venv\Scripts\python.exe' -ArgumentList $args2 `
    -WorkingDirectory $w -NoNewWindow -PassThru -RedirectStandardOutput $Out -RedirectStandardError "$Out.err"
try { $p.PriorityClass = 'BelowNormal' } catch {}
$p.WaitForExit()
Get-Content $Out -Tail 15
