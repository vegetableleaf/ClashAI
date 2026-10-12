# Gates: drills XL2

OWNS: scratchpad/gauntlet/L74/drills/build_pros.py, scratchpad/gauntlet/L74/drills/pro_when.py, scratchpad/gauntlet/L74/drills/xl2_selectors.py, scratchpad/gauntlet/L74/weekend/**, scratchpad/gauntlet/L74/mechanic_fork/mech_fork.py

Scope: Add public-only conditioned drill forks, honest DEV/TEST search, chained training/evaluation, tests and pod handoff without running SIM or changing legacy behavior.

For checker execution from the repository root, pass `--root . --cwd .` with this ledger path; omit `--cwd` for read-only `--status`. CHECK commands below were authored and executed directly in the repository cwd.

- [x] G1: Synthetic selectors, arms, fit/predict and search bookkeeping pass locally without a simulator.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/weekend/tests/check_xl2.py --tests
  EXPECT: ^XL2 unit checks passed$
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/cb_drills2; exit=0; EXPECT=matched; 39 passed in 1.59s; output-sha256=48af0b5d8a02e0cd5fe464f407a7facf2362b35193b0428d017267e32d409cbe. Ran the authored CHECK directly; no inherited gate commands executed.

- [x] G2: New Python modules import without engine runtime and compile; legacy definitions remain unchanged.
  CHECK: C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/weekend/tests/check_xl2.py
  EXPECT: XL2 static checks passed
  EVIDENCE: PowerShell; cwd=C:/Users/benpe/cb_drills2; exit=0; EXPECT=matched; output-sha256=11d78243f2197447163a025efd6c95b0bb0ade376a60b9c25472996399ab3fe0. Static checker imports all five new/shared modules, compiles Python, compares original functions and stage text against base commit 9489fb0e99dc7eacb640259241b1fe731af9b7a6. Also rerun within the final G1 check.

- [x] G3: Public features, isolated DEV/TEST selection, training label provenance, failure sentinels, lock order and deployer commands match the ticket.
  EVIDENCE: Reviewed pro_when explicit feature whitelist and shared visible-body estimator; pro replay sides grouped before holdout; DEV winner persisted before one TEST call; identical DEV opportunity hashes; TEST-only training sources with NPZ variant checks; binary win CI label vs own A; 960-pair completeness guard and archetype output; shell prerequisite poll then CPU / GPU-before-CPU locks; failure DONE and final ICEBOW_DONE traps. XL2.md records drift lead, approximate elixir estimate, sample shortfalls and pod commands. No SIM/network/live/data changes performed.

- [ ] G4: Changes committed on l74-drills-xl2 with no unrelated tracked changes.
  EVIDENCE: git branch was l74-drills-xl2; git add returned exit 1 with fatal index.lock Permission denied. No commit created or staged changes.

- [ ] G5: Both shell entry points pass bash syntax validation.
  EVIDENCE: bash -n and dash -n both failed to start with CreateFileMapping Win32 error 5. Explicit --shell preflight remains in XL2.md; it is not reported as passed.

ABANDON: G4 git add cannot create C:/Users/benpe/ClashBot/.git/worktrees/cb_drills2/index.lock (Permission denied); linked Git metadata is outside the writable sandbox. Owner must stage and commit the listed ticket files.
ABANDON: G5 Git Bash and Dash cannot start in this Windows sandbox (CreateFileMapping Win32 error 5). Shell source was reviewed; deployer must run check_xl2.py --shell on the pod before launch.
