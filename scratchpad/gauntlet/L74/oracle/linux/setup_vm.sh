#!/usr/bin/env bash
# Online host provisioning; does not start an emulator or install a game.
# shellcheck source=common.sh
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
log_start setup
linux_host
instances "${1:-1}"
lock_state
[[ -e /dev/kvm ]] || fail '/dev/kvm missing: provision nested virtualization first'
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk-headless python3 python3-venv unzip zip \
    ca-certificates iproute2 util-linux cpu-checker libgl1 libpulse0 \
    libnss3 libx11-6 libxcb1 libxcomposite1 libxcursor1 libxi6 libxtst6 shellcheck
sudo usermod -aG kvm "$ORACLE_USER"
[[ -x $SDKMANAGER ]] || fail 'Install official Linux Command-line Tools in $ANDROID_SDK_ROOT/cmdline-tools/latest first (PORT.md)'
[[ -x $AVDMANAGER ]] || fail 'avdmanager missing'
mkdir -p "$ANDROID_AVD_HOME"
# A finite input avoids yes|sdkmanager triggering SIGPIPE under pipefail.
printf 'y\n%.0s' {1..64} | "$SDKMANAGER" --sdk_root="$ANDROID_SDK_ROOT" --licenses
"$SDKMANAGER" --sdk_root="$ANDROID_SDK_ROOT" \
    'platform-tools' 'emulator' 'platforms;android-35' \
    'build-tools;35.0.0' 'ndk;27.3.13750724' "$SYSTEM_IMAGE"
for ((i=0; i<N; i++)); do
    avd="oracle_160402012_api31_$i"
    if [[ ! -f $ANDROID_AVD_HOME/$avd.ini ]]; then
        printf 'no\n' | "$AVDMANAGER" create avd -n "$avd" -k "$SYSTEM_IMAGE" -d pixel_2
    fi
    # Never overwrite another image or change an active AVD.
    config="$ANDROID_AVD_HOME/$avd.avd/config.ini"
    python3 - "$config" <<'PY'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
text = p.read_text()
values = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
if values.get('image.sysdir.1', '').replace('\\', '/').rstrip('/') != 'system-images/android-31/default/x86_64':
    raise SystemExit('Existing AVD image mismatch; refusing to replace it')
updates = {'hw.cpu.ncore': '4', 'hw.ramSize': '4096', 'disk.dataPartition.size': '10G'}
if all(values.get(k) == v for k, v in updates.items()):
    sys.exit(0)
if list(p.parent.glob('*.lock')):
    raise SystemExit('AVD has lock files; refusing to reconfigure')
lines = [line for line in text.splitlines() if line.split('=', 1)[0] not in updates]
output = '\n'.join(lines + [f'{k}={v}' for k, v in updates.items()]) + '\n'
p.write_text(output)
PY
done
"$EMULATOR" -version
"$ADB" version
"$SDKMANAGER" --sdk_root="$ANDROID_SDK_ROOT" --list_installed > "$ORACLE_STATE/logs/sdk-installed.txt"
printf '%s\n' 'PREPARED_ONLY: log out/in if kvm group membership changed; then run boot.sh.'
printf '%s\n' 'Native bindings need Python >=3.11; Ubuntu 22.04 system Python is not sufficient. No native package was installed.'
