$ErrorActionPreference = 'Stop'
$taskProcesses = @(Get-CimInstance Win32_Process)
$taskRoots = @($taskProcesses | Where-Object { $_.Name -eq 'bash.exe' -and $_.CommandLine -match 'api_worker\.sh' -and $_.CommandLine -match '(stepd|r7_closer)' })
$taskRootIds = @($taskRoots.ProcessId)
$taskRoots = @($taskRoots | Where-Object {
    $taskParent = $_.ParentProcessId
    $taskNested = $false
    for ($taskDepth=0; $taskDepth -lt 30 -and $taskParent; $taskDepth++) {
        if ($taskParent -in $taskRootIds) { $taskNested=$true; break }
        $taskAncestor = $taskProcesses | Where-Object { $_.ProcessId -eq $taskParent } | Select-Object -First 1
        if ($null -eq $taskAncestor -or $taskAncestor.ParentProcessId -eq $taskParent) { break }
        $taskParent = $taskAncestor.ParentProcessId
    }
    -not $taskNested
})
$taskWorkers = @()
foreach ($taskRoot in $taskRoots) {
    $taskIds = [System.Collections.Generic.HashSet[uint32]]::new()
    [void]$taskIds.Add($taskRoot.ProcessId)
    do {
        $taskAdded = $false
        foreach ($taskProcess in $taskProcesses) {
            if ($taskIds.Contains($taskProcess.ParentProcessId) -and $taskIds.Add($taskProcess.ProcessId)) { $taskAdded = $true }
        }
    } while ($taskAdded)
    $taskKind = if ($taskRoot.CommandLine -match 'stepd') { 'step-d executor' } else { 'round-7 closer' }
    $taskWorkers += [pscustomobject]@{kind=$taskKind; root_pid=$taskRoot.ProcessId; processes=@($taskProcesses | Where-Object { $taskIds.Contains($_.ProcessId) } | Select-Object ProcessId,ParentProcessId,Name,CreationDate)}
}
$taskOld = @(10448,26708,41080 | ForEach-Object {
    $taskRecordedId = $_
    $taskCurrent = $taskProcesses | Where-Object { $_.ProcessId -eq $taskRecordedId } | Select-Object -First 1
    [pscustomobject]@{pid=$taskRecordedId;pid_present=($null -ne $taskCurrent);name=$taskCurrent.Name;created=$taskCurrent.CreationDate;note='Original worker failure established from logs and earlier absence; a reused PID is not worker recovery.'}
})
$taskFiles = @('scratchpad/gauntlet/L74/stepd/executor.log','scratchpad/gauntlet/L74/stepd/STATUS.md','scratchpad/gauntlet/L74/parity/diag_night/r7_closer.log','scratchpad/gauntlet/L74/parity/diag_night/R7_STATUS.md','scratchpad/gauntlet/L74/parity/diag_night/R7_SUMMARY.md')
$taskMeta = @($taskFiles | ForEach-Object { $taskFile=Get-Item -LiteralPath $_ -ErrorAction SilentlyContinue; [pscustomobject]@{path=$_;exists=($null -ne $taskFile);bytes=$taskFile.Length;modified_utc=$taskFile.LastWriteTimeUtc} })
$taskDoc = [pscustomobject]@{checked_utc=(Get-Date).ToUniversalTime().ToString('o');original_pids=$taskOld;workers=$taskWorkers;files=$taskMeta}
$taskDoc | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 scratchpad/gauntlet/L74/codex1018/local_workers_current.json
$taskOld | ConvertTo-Json -Compress
$taskWorkers | Select-Object kind,root_pid,@{Name='process_count';Expression={$_.processes.Count}} | ConvertTo-Json -Compress
