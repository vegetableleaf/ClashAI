"""Static delivery/privacy check. This does not execute Bash or Android."""
from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIVATE = ROOT / "scratchpad/gauntlet/L70/reader/oracle_160402012"


def main():
    required = ["PORT.md", "ACCEPTANCE.md", "GATES.md", "GATES_V2.md", "V2_REPORT.md", ".gitignore",
                "linux/common.sh", "linux/setup_vm.sh", "linux/boot.sh",
                "linux/deploy.sh", "linux/health.sh"]
    files = {name: (HERE/name).read_text(encoding="utf-8") for name in required}
    for name, content in files.items():
        assert content.strip(), name
        assert not re.search(r"\b0x[0-9a-fA-F]+\b", content), f"Address literal in public file: {name}"
        if name.endswith(".sh"):
            assert (HERE/name).read_bytes().startswith(b"#!/usr/bin/env bash\n"), name
            assert b"\r" not in (HERE/name).read_bytes(), name
    assert not re.search(r"\b(?:adb|app_process|clang\+\+|javac)\s", files["linux/deploy.sh"])
    assert files["linux/deploy.sh"].strip().endswith("blocked")
    assert files["linux/health.sh"].strip().endswith("blocked")
    assert "exit 78" in files["linux/common.sh"]
    # Positive control: prove the public literal checker rejects a sample address.
    assert re.search(r"\b0x[0-9a-fA-F]+\b", "private pointer 0" + "x1234")
    artifacts = [PRIVATE/name for name in ("derive.py", "README.md", "inventory.json",
                 "artifact_manifest.json", "candidate_values.json", "derivation_receipt.json")]
    ignored = []
    for path in artifacts + [HERE/".local/logs/test.log"]:
        result = subprocess.run(["git", "check-ignore", "-v", str(path)], cwd=ROOT,
                                capture_output=True, text=True, check=True)
        ignored.append(result.stdout.strip())
    # Opposite control: tracked top-level documentation must not look ignored.
    result = subprocess.run(["git", "check-ignore", "-q", "README.md"], cwd=ROOT)
    assert result.returncode == 1
    for path in (PRIVATE/"derive.py", Path(__file__)):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    receipt = json.loads((PRIVATE/"derivation_receipt.json").read_text())
    inventory = json.loads((PRIVATE/"inventory.json").read_text())
    assert receipt["source_constants"] == len(inventory["constants"])
    assert receipt["numeric_source_sites"] == len(inventory["numeric_sites"])
    # Detect source drift since the derivation, including the pre-existing dirty bridge.
    for item in inventory["source_files"]:
        path = ROOT/"research/ext/cr-native-sandbox"/item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"], str(path)
    checks = dict(deliverables_present=True, public_address_literal_check=True,
                  negative_controls=True, private_artifacts_git_ignored=True,
                  source_hashes_unchanged=True, python_ast=True, bash_files_lf=True,
                  deploy_and_health_fail_closed_source_check=True)
    report = dict(status="STATIC_CHECKS_ONLY_NATIVE_BLOCKED", checks=checks,
                  check_evidence=dict(cwd=str(ROOT), shell="PowerShell", python_ast_only=True,
                      success_token="ORACLE_STATIC_CHECKS_PASS",
                      expected_stdout_sha256=hashlib.sha256(
                          b"ORACLE_STATIC_CHECKS_PASS; BASH_AND_NATIVE_NOT_TESTED\n").hexdigest()),
                  measured_counts={key:receipt[key] for key in (
                      "functions", "selected_decompilations", "source_constants",
                      "numeric_source_sites", "apks", "native_libraries", "apk_asset_files")},
                  not_executed=["bash -n", "shellcheck", "VM connection", "KVM boot",
                                "Android SDK install", "probe build", "APK install",
                                "native service", "native acceptance", "determinism test"],
                  bash_blocker="Git Bash CreateFileMapping failed with Win32 error 5 before any script ran",
                  native_blocker="V2 literal port writes a mixed native tick/presentation gate; presentation-only proof and target binding are unqualified",
                  files={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in required})
    (HERE/"VERIFICATION.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (PRIVATE/"privacy_receipt.json").write_text(json.dumps(ignored, indent=2) + "\n", encoding="utf-8")
    print("ORACLE_STATIC_CHECKS_PASS; BASH_AND_NATIVE_NOT_TESTED")


if __name__ == "__main__":
    main()
