param([string]$Extra = "")
Set-Location C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox
. .\runtime.env.ps1
$py = "C:\Users\benpe\ClashBot\research\ext\cr-native-sandbox\.venv\Scripts\python.exe"
$args_ = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L61/replay_batch_rec.py --port 37031 $Extra"
Start-Process -FilePath $py -ArgumentList $args_ -NoNewWindow -Wait -RedirectStandardOutput C:\Users\benpe\ClashBot\scratchpad\gauntlet\L61\batch_rec.log -RedirectStandardError C:\Users\benpe\ClashBot\scratchpad\gauntlet\L61\batch_rec.err
