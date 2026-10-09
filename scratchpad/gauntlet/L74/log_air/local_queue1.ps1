# Candidate games from the VM-backup base results (cands.py): retarget then block, 4 worker processes at a time.
$S = 'C:\Users\benpe\ClashBot\.claude\worktrees\agent-a93fc9a12f7a33091\scratchpad\gauntlet\L74\log_air\local_run.ps1'
foreach ($arm in 'retarget', 'block') {
  $jobs = @(@('air', '15,24', 2), @('evo', '22', 1), @('lad', '19', 1))
  $ps = foreach ($j in $jobs) {
    Start-Process powershell -PassThru -WindowStyle Hidden -ArgumentList '-NoProfile', '-File', $S, '-Name', "${arm}_$($j[0])_b1", '-Census', $j[0], '-Seeds', $j[1], '-LogAir', $arm, '-Workers', $j[2]
  }
  $ps | Wait-Process
}
