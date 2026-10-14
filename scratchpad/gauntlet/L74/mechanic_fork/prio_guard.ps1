# usage: powershell -File prio_guard.ps1 ROOTPID
# Every 10 s: ROOTPID's process tree runs at Idle while a live_play.py python process exists, else Normal.
# (BelowNormal/Idle alone gave 0.00 CPU-s per 30 s on the saturated laptop, measured 2026-10-10.)
param($Root)
while ($true) {
  $all = Get-CimInstance Win32_Process
  if (-not ($all | ? { $_.ProcessId -eq [int]$Root })) { break }
  $live = [bool]($all | ? { $_.Name -eq 'python.exe' -and $_.CommandLine -match 'live_play\.py' })
  $tree = @([int]$Root)
  do { $n = $tree.Count; $tree = @($tree + ($all | ? { $tree -contains [int]$_.ParentProcessId } | % { [int]$_.ProcessId }) | sort -Unique) } while ($tree.Count -ne $n)
  $cls = if ($live) { 'Idle' } else { 'Normal' }
  foreach ($i in $tree) { try { (Get-Process -Id $i -ErrorAction Stop).PriorityClass = $cls } catch {} }
  Start-Sleep 10
}
