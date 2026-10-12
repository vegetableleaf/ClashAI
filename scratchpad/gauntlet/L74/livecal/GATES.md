# Gates: LIVECAL

OWNS: scratchpad/gauntlet/L74/livecal/**

Scope: Offline live truth, reproducible five-pool SIM plan, scoring, pod driver, tests and transfer manifest. No deployment or SIM run on this laptop.

Split/merge ticket acceptance (2026-10-12; original verification below is historical):

- [x] S1: Pool subsets retain full-run seeds, checkpoint/fast identities and opponent assignments; defaults remain unchanged.
  CHECK: icebow/.venv/Scripts/python.exe -B -m pytest scratchpad/gauntlet/L74/livecal -q -p no:cacheprovider
  EXPECT: /[0-9]+ passed in [0-9.]+s/
  EVIDENCE: direct ticket-authorized test run; shell=PowerShell (Python subprocess capture); cwd=C:\Users\benpe\ClashBot; exit=0; match=true; 48 passed in 19.01s; output_sha256=3ac53bca9f40dc1eec9f3ba65a750f100a065e2e2ea232c09e52ce2478511e85; PATH_sha256=3d558a0928cb8b944d60d8fcf85d45aab913ff1021edbcc0bfb05799c372aee9; see SPLIT_VERIFICATION.json
- [x] S2: Merging synthetic split results equals full scoring, including bootstrap intervals; missing arms are explicitly reported without imputation.
  CHECK: icebow/.venv/Scripts/python.exe -B -m pytest scratchpad/gauntlet/L74/livecal -q -p no:cacheprovider
  EXPECT: /[0-9]+ passed in [0-9.]+s/
  EVIDENCE: direct ticket-authorized test run; shell=PowerShell (Python subprocess capture); cwd=C:\Users\benpe\ClashBot; exit=0; match=true; 48 passed in 19.01s; output_sha256=3ac53bca9f40dc1eec9f3ba65a750f100a065e2e2ea232c09e52ce2478511e85; PATH_sha256=3d558a0928cb8b944d60d8fcf85d45aab913ff1021edbcc0bfb05799c372aee9; see SPLIT_VERIFICATION.json
- [x] S3: Shell PART naming and pool passthrough are documented with exact two-pod and laptop commands and calculated ETAs; edits remain in livecal and uncommitted.
  EVIDENCE: reviewed shell PART/default/LIVECAL_OUT precedence and existing quoted argument passthrough; README provides exact A/C/merge commands. Current manifest scheduling measured A=14400 games/306.382979 minutes, C=9600 games/228.765957 minutes at 47*(workers/28). All writes confined to livecal; no git commit or network/SIM call. Shell execution remains unverified: bash -n blocked by CreateFileMapping Win32 error 5 (same environment limitation as G5).

- [x] G1: Synthetic log selection and grouping preserve the phase-stats rules and checkpoint identity.
  CHECK: icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/livecal -q -p no:cacheprovider
  EXPECT: /24 passed in [0-9.]+s/
  EVIDENCE: direct authorized test run; shell=PowerShell; cwd=C:\Users\benpe\ClashBot; exit=0; match=true; output_sha256=99cc050dd3792a21359a3da94d58c110b54925a535d2e6dd2f832ff9e5a11a1b; PATH_sha256=f662c29f785a15b745320aa4e7e4c8b58f7c58ce74f5f0462bb74ac89f961ec7; see VERIFICATION.json
- [x] G2: Scoring tests verify signs, tied ranks, offset MAE, paired bootstrap and incomplete-result rejection.
  CHECK: icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/livecal -q -p no:cacheprovider
  EXPECT: /24 passed in [0-9.]+s/
  EVIDENCE: direct authorized test run; shell=PowerShell; cwd=C:\Users\benpe\ClashBot; exit=0; match=true; output_sha256=99cc050dd3792a21359a3da94d58c110b54925a535d2e6dd2f832ff9e5a11a1b; PATH_sha256=f662c29f785a15b745320aa4e7e4c8b58f7c58ce74f5f0462bb74ac89f961ec7; see VERIFICATION.json
- [x] G3: Driver tests verify scheduling, live flags, optional P4, process cap and failure artifacts without SIM.
  CHECK: icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L74/livecal -q -p no:cacheprovider
  EXPECT: /24 passed in [0-9.]+s/
  EVIDENCE: direct authorized test run; shell=PowerShell; cwd=C:\Users\benpe\ClashBot; exit=0; match=true; output_sha256=99cc050dd3792a21359a3da94d58c110b54925a535d2e6dd2f832ff9e5a11a1b; PATH_sha256=f662c29f785a15b745320aa4e7e4c8b58f7c58ce74f5f0462bb74ac89f961ec7; see VERIFICATION.json
- [x] G4: Actual logs are measured; checkpoint sizes and hashes, exact commands and ETA are documented.
  EVIDENCE: manual artifact audit: 1042 receipts, 32 era groups, 10 arms, 13 matching checkpoint hashes/247479569 bytes; README launch and 47 games/min ETA; LIVECAL_ARTIFACTS_VERIFIED; POLICY_LOAD_OK 13 checkpoints/common lattice grid without SIM.
- [x] G5: New source files stay in livecal; policy inputs use the public path, anti-stall is disabled, and no deployment code exists.
  EVIDENCE: manual source review: plain-only worker; public counter; forced stall_elixir=None on both sides; no deployment paths; only livecal source files added. Git Bash could not run in this sandbox; Linux shell execution and SIM remain pod-side checks.
