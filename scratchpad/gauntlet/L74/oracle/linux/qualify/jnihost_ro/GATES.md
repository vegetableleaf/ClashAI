# Gates: ORACLE v5 worker kit

OWNS: scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/**

Scope: prepare and offline-test the isolated, no-patch JniHost worker kit. Android runtime outcomes are worker evidence, not a local acceptance claim.

- [x] G1: Offline tests reject unsafe inputs and distinguish progress, refusal, rendering and unknown failures
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/test_jnihost_ro.py
  EXPECT: JNIHOST_RO_TESTS_OK
  EVIDENCE: VERIFICATION.json checks[0]; exit 0, expected marker matched; output SHA-256 bd0516b58a4141a867d36170220ddbd83836976c0fc273cfb4bfb30cba21f87f.

- [x] G2: Public source is offset-free and private generated inputs are ignored and untracked
  CHECK: python scratchpad/gauntlet/L74/oracle/linux/qualify/jnihost_ro/verify.py
  EXPECT: JNIHOST_RO_PRIVACY_OK
  EVIDENCE: VERIFICATION.json checks[1]; exit 0, expected marker matched; output SHA-256 e99a0ea81411e7e06ca7fbf360dc3dbe6c28bf5696c89b031aed1657fb849078.

- [x] G3: Java and observer compile offline in a private upstream copy without the upstream bridge
  EVIDENCE: VERIFICATION.json compile; JDK 17 Java/DEX and Android x86_64 observer built offline. One JNI read export, only system dependencies, artifact/source/upstream hashes rechecked. Runtime unrun.

- [x] G4: Worker order and source review cover isolation, stop boundaries, all eleven presentation sites and unrun runtime risks
  EVIDENCE: VERIFICATION.json manual_review and README.md; all eleven sites mapped, truthful adapters, unknown failures kept unknown, no target execution. Linux Bash check handed to worker after local Win32 startup failure.
