$ErrorActionPreference = "Continue"
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox
. .\runtime.env.ps1
for ($i = 1; $i -le 6; $i++) {
  "=== attempt $i start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
  & .\.venv\Scripts\python.exe -m native_core.worker start --workers 2 --base-port 37031 2> "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62\_boot_att$i.err"
  "exit=$LASTEXITCODE"
  if ($LASTEXITCODE -eq 0) { break }
}
"=== end $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
