param([string]$Extra = "", [string]$Log = "tp.log")
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox
. .\runtime.env.ps1
$py = "C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox\.venv\Scripts\python.exe"
Start-Process -FilePath $py -ArgumentList "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L61/throughput.py $Extra" -NoNewWindow -Wait -RedirectStandardOutput "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L61\$Log" -RedirectStandardError "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L61\$Log.err"
