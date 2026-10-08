# Run python at BelowNormal priority (the owner may be playing live): lowprio.ps1 -Out <file> -PyArgs "<python args>"
param([string]$Out, [string]$PyArgs)
$py = 'C:\Users\benpe\ClashBot\icebow\.venv\Scripts\python.exe'
$wd = 'C:\Users\benpe\ClashBot\.claude\worktrees\agent-a1f8484f32eef598e'
$env:CUDA_VISIBLE_DEVICES = ''
$p = Start-Process -FilePath $py -ArgumentList $PyArgs -WorkingDirectory $wd -NoNewWindow -PassThru -RedirectStandardOutput $Out -RedirectStandardError "$Out.err"
try { $p.PriorityClass = 'BelowNormal' } catch {}
$p.WaitForExit()
"exit $($p.ExitCode)"
