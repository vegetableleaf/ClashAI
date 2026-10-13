#!/usr/bin/env bash
# Offline build. Original upstream sources remain untouched.
set -Eeuo pipefail
umask 077
Q=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT=$(cd -- "$Q/../../../../../.." && pwd)
SDK=${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}
NDK="$SDK/ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin"
UPSTREAM="$ROOT/research/ext/cr-native-sandbox/android_probe"
BUILD="$ROOT/scratchpad/gauntlet/L74/oracle/.local/qualify-build"
[[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || exit 64
[[ -x $NDK/clang && -d $UPSTREAM ]] || exit 69
git -C "$ROOT" check-ignore -q "$BUILD/observer"
[[ ! -e $BUILD ]] || { echo 'Use an untouched build directory; existing build retained.'; exit 73; }
mkdir -p "$BUILD"
cp -a -- "$UPSTREAM" "$BUILD/android_probe"
cp -- "$Q/observer.c" "$BUILD/android_probe/native/oracle_readonly.c"
# This private build target cannot select the upstream mutating bridge.
cat > "$BUILD/android_probe/build_readonly.sh" <<'BUILD_SCRIPT'
#!/usr/bin/env bash
set -Eeuo pipefail
[[ ${ORACLE_READ_ONLY:-} == ON ]] || { echo 'READ_ONLY mode required'; exit 64; }
: "${ORACLE_CLANG:?}"
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
"$ORACLE_CLANG" --target=x86_64-linux-android31 -std=c11 -O2 -Wall -Wextra -Werror \
  -DORACLE_READ_ONLY=1 -fPIE -pie native/oracle_readonly.c -o ../observer
BUILD_SCRIPT
ORACLE_READ_ONLY=ON ORACLE_CLANG="$NDK/clang" bash "$BUILD/android_probe/build_readonly.sh"
"$NDK/llvm-nm" -u "$BUILD/observer" > "$BUILD/imports.txt"
if grep -E 'ptrace|process_vm_writev|mprotect|dlopen|pwrite|socket|connect' "$BUILD/imports.txt"; then
    echo 'Unexpected import: do not install'; exit 1
fi
sha256sum "$BUILD/observer" "$BUILD/android_probe/native/oracle_readonly.c" > "$BUILD/SHA256SUMS"
printf '%s\n' 'READ_ONLY_BUILD_READY (not Android/runtime tested)'
