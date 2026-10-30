#!/bin/bash
# boot_opp_pod.sh NEWPORT [SRCPORT] -- OPP-PUSH 10-30 (run on the laptop): give a fresh pod 33903's opponent-arm setup so
# launch_arm_prod.sh / launch_arm.sh / arm_d3.sh / arm_d3_card.sh work on it unchanged (same /workspace paths).
# Copies POD TO POD (never through the laptop: ~10 GB, and the laptop carries live play), with a one-off key: the new pod makes
# /workspace/oppboot/id, its public half goes into SRC's authorized_keys tagged "opp-push-boot-NEWPORT" and is REMOVED on exit
# (trap; precedent pilot/ops/loop_pod.sh). SRC (default 33903) is otherwise read-only.
# Copied (checkpoints and run dirs excluded):
#   /workspace/venvf16          python 3.12 venv = pilot/ops/requirements.txt + jpype1, pyarrow, royalesim 0.1.36, royalegym 0.1.23
#   /workspace/oplm/cb2         the arm tree (code, icebow/data minus bench, pilot/loop + jbuild_fe364ceb facade build)
#   /workspace/oplm/{tables/16.635.3, opp_ft_s0_R_sim.pt (ftR init), strip_ckpt.py}, /workspace/opp/cbs/opp_ckpt (cb2/opp_ckpt ->)
#   /workspace/crforge_main     crforge fe364ceb (training) + 5e8089a4 (D3) builds;  /workspace/cfspeed
#   /workspace/opp/cb -> /workspace/oplm/cbe (D3 eval code: arm_d3.sh's evcb for any pod but 33903) + /workspace/icebow_data
#   (cbe's icebow/data symlink target);  /workspace/oplm/d3/ck/oplc_ftR_l0003_s1_u0040.pt (the eval exactness check, PUSH.md)
# Then: JDK 17 + rsync (apt) if missing, python3.12 if missing (apt, else uv + venv symlink), a CUDA matmul per GPU in the venv,
# and a sha256 digest of every copied tree on BOTH pods (must match; a mismatch on opp/cb can be the lead's D3 block writing
# there: re-run). Idempotent: re-running re-copies and re-verifies. Output: /workspace/oppboot/BOOT.txt on the new pod.
set -euo pipefail
NP=$1; SP=${2:-33903}; H=root@157.157.221.29; TAG=opp-push-boot-$NP
K="-o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=30 -i $HOME/.ssh/runpod_clashbot"
N="ssh $K -p $NP $H"; S="ssh $K -p $SP $H"
X="--exclude=workspace/oplm/cb2/icebow/data/bench/rl_royale/* --exclude=workspace/oplm/cb2/scratchpad/gauntlet/L68/rl/*"
X="$X --exclude=workspace/oplm/cb2/hs_err_pid* --exclude=workspace/icebow_data/bench/rl_royale/* --exclude=*/remote_actors.token"
X="$X --exclude=*/__pycache__"
P="workspace/venvf16 workspace/oplm/cb2 workspace/oplm/tables workspace/oplm/opp_ft_s0_R_sim.pt workspace/oplm/strip_ckpt.py"
P="$P workspace/opp/cbs/opp_ckpt workspace/crforge_main workspace/cfspeed workspace/opp/cb workspace/icebow_data"
P="$P workspace/oplm/d3/ck/oplc_ftR_l0003_s1_u0040.pt"
# digest of one tree, same exclusions as the tar (relative paths, so /workspace/opp/cb on SRC = /workspace/oplm/cbe on NEW)
DIG='dig() { (cd "$1" && find . -type f | grep -v -E "^\./(icebow/data/)?bench/rl_royale/|^\./scratchpad/gauntlet/L68/rl/|^\./hs_err_pid|remote_actors\.token$|/__pycache__/" | LC_ALL=C sort | xargs -d "\n" sha256sum | sha256sum | cut -c1-16); }'
TREES_S="/workspace/venvf16 /workspace/oplm/cb2 /workspace/opp/cb /workspace/icebow_data /workspace/crforge_main /workspace/oplm/tables /workspace/opp/cbs/opp_ckpt"
TREES_N="/workspace/venvf16 /workspace/oplm/cb2 /workspace/oplm/cbe /workspace/icebow_data /workspace/crforge_main /workspace/oplm/tables /workspace/opp/cbs/opp_ckpt"

echo "== 1. new pod $NP facts"
$N 'echo "cpus $(nproc) cgroup cpu.max $(cat /sys/fs/cgroup/cpu.max 2>/dev/null) mem.max $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"
 free -g | sed -n 2p; nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader; df -BG /workspace | tail -1
 head -1 /etc/os-release; lscpu | grep "Model name"; ls /usr/bin/python3.12 2>&1; java -version 2>&1 | head -1'
FREE=$($N "df -BG --output=avail /workspace | tail -1 | tr -dc 0-9")
[ "$FREE" -ge 30 ] || { echo "ABORT: /workspace has ${FREE} GB free (need >= 30: ~10 copy + ~5.5 per 400-update arm + D3 rows)"; exit 1; }

echo "== 2. system packages + python3.12"
$N 'command -v javac >/dev/null && command -v rsync >/dev/null || { apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq openjdk-17-jdk-headless rsync >/dev/null; }
 [ -x /usr/bin/python3.12 ] || { apt-get update -qq; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12 >/dev/null 2>&1 || true; }
 java -version 2>&1 | head -1; ls /usr/bin/python3.12 2>&1 || echo "python3.12 not from apt: uv fallback after the copy"'

echo "== 3. copy $SP -> $NP (pod to pod)"
$N "mkdir -p /workspace/oppboot /workspace/oplm/d3/ck /workspace/oplm/d3/rows /workspace/oplm/logs && { [ -f /workspace/oppboot/id ] || ssh-keygen -q -t ed25519 -N '' -f /workspace/oppboot/id -C $TAG; }"
PUB=$($N "cat /workspace/oppboot/id.pub")
trap '$S "sed -i \"/ $TAG\$/d\" ~/.ssh/authorized_keys" && echo "key $TAG removed from $SP"' EXIT
$S "mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && { grep -qF '$PUB' ~/.ssh/authorized_keys || echo '$PUB' >> ~/.ssh/authorized_keys; }"
T0=$(date +%s)
$N "ssh -i /workspace/oppboot/id -o StrictHostKeyChecking=no -o UserKnownHostsFile=/workspace/oppboot/kh -o BatchMode=yes -p $SP $H \
 'cd / && tar cf - $X $P' | tar xf - -C / --transform='s,^workspace/opp/cb/,workspace/oplm/cbe/,'"
echo "copied in $(( $(date +%s) - T0 )) s; $($N 'du -sh /workspace/venvf16 /workspace/oplm /workspace/icebow_data | tr "\n" " "')"

echo "== 4. python + GPU check"
$N 'V=/workspace/venvf16
 if [ ! -x /usr/bin/python3.12 ]; then
   python3 -m pip install -q uv 2>/dev/null || python3 -m pip install -q --break-system-packages uv
   python3 -m uv python install 3.12 >/dev/null; PY=$(python3 -m uv python find 3.12)
   ln -sf "$PY" $V/bin/python3.12; sed -i "s#^home = .*#home = $(dirname $PY)#" $V/pyvenv.cfg; echo "venv python -> $PY (uv)"
 fi
 $V/bin/python -c "
import torch, jpype, royalesim, sys
n = torch.cuda.device_count(); assert n > 0, \"no GPU\"
for i in range(n):
    x = torch.ones(256, 256, device=f\"cuda:{i}\"); assert (x @ x).sum().item() == 256 ** 3
print(\"venv OK python\", sys.version.split()[0], \"torch\", torch.__version__, \"GPUs\", n, torch.cuda.get_device_name(0))"'

echo "== 5. digests (SRC vs NEW)"
DS=$($S "$DIG; for t in $TREES_S; do echo \$(dig \$t); done" | tr '\n' ' ')
DN=$($N "$DIG; for t in $TREES_N; do echo \$(dig \$t); done" | tr '\n' ' ')
echo "src $DS"; echo "new $DN"
{ date -u +%FT%TZ; echo "source $SP; trees: $TREES_N"; echo "src $DS"; echo "new $DN"; } | $N "cat > /workspace/oppboot/BOOT.txt"
[ "$DS" = "$DN" ] && echo "BOOT OK: every tree identical ($NP)" || { echo "BOOT DIGEST MISMATCH (re-run once; opp/cb can change while a D3 block runs on $SP)"; exit 2; }
