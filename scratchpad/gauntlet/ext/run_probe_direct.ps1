# Diagnostic: the author's own probe profiles (nativeLoadReplay -> [pump] -> waitForBattle -> nativeStep(100)
# -> nativeObserve) against the already-booted AVD. Unlike serve-direct they do NOT throw when the tick stays
# at 0, so probe_result carries the full ready/step/state JSON for the tick-0 stall seen 23:07 (§5aw).
# Args: -Profile probe-direct|probe-no-surface|probe-baseline|... ; -ReplayJson <path> for another bootstrap doc.
param([string]$Profile = "probe-direct", [string]$ReplayJson = "")
$ErrorActionPreference = "Continue"
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox
. .\runtime.env.ps1
"=== $Profile start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') replay=$ReplayJson"
try {
    if ($ReplayJson) {
        & .\scripts\run_probe.ps1 -Profile $Profile -Quiet -ReplayJson $ReplayJson
    } else {
        & .\scripts\run_probe.ps1 -Profile $Profile -Quiet
    }
    "probe exit=$LASTEXITCODE"
} catch {
    "probe THREW: $($_.Exception.Message)"
    $_.ScriptStackTrace
}
"=== $Profile end $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
