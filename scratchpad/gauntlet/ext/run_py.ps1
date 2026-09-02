param([string]$Cmd = "")
$ErrorActionPreference = "Continue"
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox
. .\runtime.env.ps1
"=== start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Cmd"
$argv = $Cmd -split ' '
& .\.venv\Scripts\python.exe -u @argv
"exit=$LASTEXITCODE"
"=== end $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
