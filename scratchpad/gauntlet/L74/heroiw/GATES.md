# Gates: HEROIW

OWNS: pipeline/royale_runtime.py, pipeline/royale_heroiw.py, pipeline/royale_env.py, pipeline/reader_identity_aliases.py, pipeline/obs_contract.py, pipeline/public_observation.py, pipeline/own_ability.py, pipeline/tests/test_heroiw.py, scratchpad/gauntlet/L74/heroiw/**

Scope: Default-off Hero Ice Wizard adapter, source-reviewed pins, offline tests and an isolated pod validation job. No deployment or live configuration edits.

- [x] G1: Old selection is unchanged; new versions and table resolve without importing SIM.
  CHECK: research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/heroiw/verify_offline.py
  EXPECT: HEROIW_OFFLINE_OK
  EVIDENCE: 2026-10-12; PowerShell; cwd C:/Users/benpe/ClashBot; exit 0; EXPECT matched; 70 pytest cases passed in 13.37 seconds; no engine modules imported. See VERIFICATION.json.
- [x] G2: Hero deck, controller and public body/cube mappings have offline regression coverage.
  EVIDENCE: G1 covers production methods with a fake protocol, public reducers, aliases, selected own ability spec and existing live identity tests. Default selection independently compared against HEAD source.
- [x] G3: Pod job implements isolated install, CPU locking, bounded concurrency, paired drift, LIVECAL and failure receipts.
  EVIDENCE: Static review of run_heroiw.sh and validate.py; schedule tests count 480 drift pairs and 14400 LIVECAL games per runtime, verify selected pools and matching opponent configuration. Paired-score negative controls reject missing, duplicate and different-deck pairs. Bash execution remains unverified (Windows CreateFileMapping access denied); actual execution is G5.
- [x] G4: Release changes and unconfirmed wheel/behavior checks are documented with source references.
  EVIDENCE: README.md, build_manifest.json (17 Gym Python source hashes), calibration_changes.json (170 changed/new default-value fields), and fetched release tags equal origin/HEAD. 6bb7b62 is an ancestor of the pinned Sim tag. No fetch or install was run.
- [ ] G5: Pod smoke, drift and LIVECAL results are measured.
  EVIDENCE: pending; execution belongs to the pod, which installs the wheels. No sandbox network or SIM execution authorized.

ABANDON: G5 Pod execution is handed off via run_heroiw.sh as requested; no wheel installation/network/SIM was run in this sandbox. Numerical smoke, drift and ordering results remain unmeasured. Four local gates met, one execution gate handed off; no claim of runtime acceptance.
