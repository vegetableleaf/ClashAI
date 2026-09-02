$ErrorActionPreference = "Continue"
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox
. .\runtime.env.ps1
"=== start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
& .\.venv\Scripts\python.exe -m native_core.worker start --workers 1 --base-port 37031
"exit=$LASTEXITCODE"
"=== end $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
