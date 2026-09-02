# GAUNTLET L2 — detector architecture screen (cheap, per owner ruling 4).
# Two arms, IDENTICAL in everything but --model, run sequentially on the free GPU.
# fraction 0.35 / 30 epochs keeps imgsz 960 (small-object ranking preserved) while cutting the
# 23.9 h full-run cost to ~2 h per arm. These numbers are NOT comparable to board-26's 0.860 —
# only to each other. That is the whole point of carrying the yolo11s control arm.
Set-Location C:\Users\benpe\ClashBot\icebow
$py  = ".\.venv\Scripts\python.exe"
$out = "C:\Users\benpe\ClashBot\scratchpad\gauntlet\L2"
New-Item -ItemType Directory -Force $out | Out-Null

$arms = @(
    @{ name = "screen-y11s"; model = "yolo11s.pt" },   # control: same family as board-26
    @{ name = "screen-y26s"; model = "yolo26s.pt" }    # candidate
)

foreach ($a in $arms) {
    $log = "$out\$($a.name).log"
    "=== $($a.name) [$($a.model)] start $(Get-Date -Format 'HH:mm:ss') ===" | Tee-Object -Append "$out\screen.progress"
    $t0 = Get-Date
    & $py tools\detect\train.py --model $a.model --epochs 30 --fraction 0.35 `
         --batch 4 --imgsz 960 --workers 4 --seed 0 --patience 30 --name $a.name `
         *> $log
    $mins = [int]((Get-Date) - $t0).TotalMinutes
    "=== $($a.name) done exit=$LASTEXITCODE in $mins min ===" | Tee-Object -Append "$out\screen.progress"
}
"ALL SCREEN ARMS DONE $(Get-Date -Format 'HH:mm:ss')" | Tee-Object -Append "$out\screen.progress"
