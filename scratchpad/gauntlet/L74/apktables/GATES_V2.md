# Gates: APKTABLES v2

Scope: Device CSV/TOML precedence with explicit APK fallback; device rarity scaling; offline comparisons; read-only pull helper. All writes confined to apktables; no commits, network or live-script edits.

- [x] V1: Synthetic tests prove device precedence, absent-only fallback, failure preservation and integer level scaling.
  CHECK: python scratchpad/gauntlet/L74/apktables/verify.py
  EXPECT: APKTABLES_SYNTHETIC_PASS
  EVIDENCE: out/test_receipt.json; PowerShell at repository root, Python 3.13, exit 0, APKTABLES_SYNTHETIC_PASS matched; 41 tests, zero failures/errors/skips. Output SHA256 e7b94b2fc7a23791e0486df680a56c027c6fa3d400f3d0b9af91c749f1188123. CLI fixture proves device-over-APK and corrupt-update baseline preservation; X-Bow Common L11 is 61.

- [x] V2: Local device audit covers icebow and top 60 against both requested SIM tables, with owner and opponent level stats and X-Bow L11 calibration.
  CHECK: python scratchpad/gauntlet/L74/apktables/verify_device.py
  EXPECT: APKTABLES_DEVICE_PASS
  EVIDENCE: PowerShell at repository root, Python 3.13, exit 0, APKTABLES_DEVICE_PASS matched. out/device_audit.json verifies final out/device_builds/20261012T221627332682Z-50188 run: 73 device tables, 351 APK fallbacks, 63 main cards plus 36 observed forms, 69 owner/opponent level rows, X-Bow L11=61. Old main equal/mismatch/missing=42/20/1; selected main=63/0/0; selected all=99/0/0. Raw rarities, decoded tables, update inputs, APKs, SIM reference bytes, parser and tool hashes verified. Repeated real build has zero changed files/cards. rarities.csv is explicitly APK fallback.

- [ ] V3: Pull helper uses the existing adb wrapper read-only, with ignored output and shell syntax verified.
  EVIDENCE: Source reviewed: only adb operation is pull through unchanged L68 wrapper; MSYS_NO_PATHCONV=1, explicit cygpath local destination, unique output under ignored out/. No device call performed. Shell syntax check could not execute: Git Bash CreateFileMapping Win32 error 5; WSL CreateInstance E_ACCESSDENIED. This validation remains unmet due to sandbox permissions. Helper SHA256 e8614ce15691d0479180020728fdea8feb947a69ce9057aabb0c724cc5bb9f80.

- [x] V4: Final diff contains only intended source/docs/tests; private outputs ignored and input hashes unchanged.
  EVIDENCE: Scoped git status contains only the eight intended v2 source/docs/test files; git diff --check exits 0; scoped staged diff empty. No staging/commit, network or live-script changes. Device audit verifies source hashes and ignored output with a nonignored source-file positive control. All task writes stayed in apktables/; existing unrelated worktree changes untouched.
