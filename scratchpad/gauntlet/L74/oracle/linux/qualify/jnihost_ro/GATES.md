# Gates: ORACLE v6 loader kit

Scope: build and offline verification only. No target execution; Android qualification remains unmeasured.

- [x] G1: Loader inputs, optional preload, one-attempt launch and load-only reviews pass positive and negative fixtures
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/test_jnihost_ro.py
  EXPECT: JNIHOST_RO_TESTS_OK
  EVIDENCE: VERIFICATION.json checks[0]; 37 tests passed, exit 0 and expected marker matched; output SHA-256 ee51ecff1d07f4aec0ce888799be41206e154553b84d2dbdcff8e316cd3dad67.

- [x] G2: Public sources contain no private offsets and the host has no client lifecycle calls
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/verify.py
  EXPECT: JNIHOST_RO_PRIVACY_OK
  EVIDENCE: VERIFICATION.json checks[1]; exit 0 and expected marker matched; output SHA-256 e99a0ea81411e7e06ca7fbf360dc3dbe6c28bf5696c89b031aed1657fb849078.

- [x] G3: Separate host and child DEX artifacts and read-only observer compile offline
  EVIDENCE: VERIFICATION.json compile; javac, D8, Android observer compilation passed; DEX ownership, JNI export/import audit, javap loadLibrary/no static initializer and final hashes verified.

- [x] G4: README and source review cover exact touched classes, native initialization risks, default-off fallback and stop boundary
  EVIDENCE: VERIFICATION.json manual_review and README.md; load-only boundary, exact direct classes, indirect side effects, opt-in preloads and refusal STOP reviewed. Linux Bash blocked locally; worker check documented.
