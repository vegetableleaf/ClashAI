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
# Ubuntu 22.04 has JDK 17; Debian 13 (GCP clashbot-oracle-2) only 21. The SDK tools and D8 accept either.
jdk=openjdk-17-jdk-headless
apt-cache show "$jdk" >/dev/null 2>&1 || jdk=openjdk-21-jdk-headless
sudo apt-get install -y "$jdk" python3 python3-venv unzip zip \
    ca-certificates iproute2 util-linux cpu-checker libgl1 libpulse0 \
    libnss3 libx11-6 libxcb1 libxcomposite1 libxcursor1 libxi6 libxtst6 shellcheck curl \
    libxkbfile1 libsm6 libice6 git python3-jsonschema
java_bin=$(readlink -f "$(command -v java)")
export JAVA_HOME=${java_bin%/bin/java} PATH="${java_bin%/java}:$PATH"
sudo usermod -aG kvm "$ORACLE_USER"
if [[ ! -x $SDKMANAGER ]]; then
    # Official stable cmdline-tools;latest from Google's SDK manifest, checked against the manifest's size and SHA-1.
    read -r url sum size < <(curl -fsS https://dl.google.com/android/repository/repository2-3.xml | python3 -c '
import sys, xml.etree.ElementTree as E
for p in E.parse(sys.stdin).getroot().iter("remotePackage"):
    if p.get("path") == "cmdline-tools;latest":
        for a in p.iter("archive"):
            if a.findtext("host-os") == "linux":
                c = a.find("complete"); print(c.findtext("url"), c.findtext("checksum"), c.findtext("size"))') || true
    [[ -n ${url:-} ]] || fail 'cmdline-tools;latest (linux) not found in the SDK manifest'
    zip="$ORACLE_STATE/$url"
    curl -fsS -o "$zip" "https://dl.google.com/android/repository/$url"
    [[ $(stat -c %s "$zip") == "$size" && $(sha1sum "$zip" | cut -d' ' -f1) == "$sum" ]] || fail "$url size/SHA-1 mismatch"
    rm -rf "$ORACLE_STATE/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
    mkdir -p "$ANDROID_SDK_ROOT/cmdline-tools"
    unzip -q "$zip" -d "$ORACLE_STATE"
    mv "$ORACLE_STATE/cmdline-tools" "$ANDROID_SDK_ROOT/cmdline-tools/latest"
    printf '%s size=%s sha1=%s\n' "$url" "$size" "$sum" >> "$ORACLE_STATE/logs/cmdline-tools.txt"
fi
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
if values.get('image.sysdir.1', '').replace('\\', '/').rstrip('/') != 'system-images/android-32/default/x86_64':
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
