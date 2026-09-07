p = "scratchpad/gauntlet/L65/port/worker_linux.patch.py"
s = open(p, encoding="utf-8").read()
old = """    ('''        command = [
            _powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(PROJECT_ROOT / "scripts" / "start_direct_service.ps1"),
            "-Adb", str(self.config.adb), "-Serial", self.config.serial,
            "-Port", str(port), "-Slot", str(slot), "-DataRoot", str(self.config.data_root),''',
     '''        if os.name == "nt":
            command = [
                _powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(PROJECT_ROOT / "scripts" / "start_direct_service.ps1"),
                "-Adb", str(self.config.adb), "-Serial", self.config.serial,
                "-Port", str(port), "-Slot", str(slot), "-DataRoot", str(self.config.data_root),'''),"""
new = """    # The start block is replaced WHOLE, both branches, because a patch that opens `if os.name == "nt":`
    # around the existing list and stops there leaves `command` undefined on Linux -- caught by reading
    # the replacement back rather than by trusting that the anchor matched.
    ('''        command = [
            _powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(PROJECT_ROOT / "scripts" / "start_direct_service.ps1"),
            "-Adb", str(self.config.adb), "-Serial", self.config.serial,
            "-Port", str(port), "-Slot", str(slot), "-DataRoot", str(self.config.data_root),
            "-BootstrapReplayJson", str(PROJECT_ROOT / "examples" / "eight-card-bootstrap.json"),
        ]''',
     '''        _bootstrap = str(PROJECT_ROOT / "examples" / "eight-card-bootstrap.json")
        if os.name == "nt":
            command = [
                _powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                str(PROJECT_ROOT / "scripts" / "start_direct_service.ps1"),
                "-Adb", str(self.config.adb), "-Serial", self.config.serial,
                "-Port", str(port), "-Slot", str(slot), "-DataRoot", str(self.config.data_root),
                "-BootstrapReplayJson", _bootstrap,
            ]
        else:
            # CR_SANDBOX_* come from runtime.env.sh; the .sh takes --adb only via the env var, so the
            # config's adb path is exported rather than passed, keeping one source of truth.
            os.environ.setdefault("CR_SANDBOX_ADB", str(self.config.adb))
            command = [
                "bash", str(PROJECT_ROOT / "scripts" / "start_direct_service.sh"),
                "--serial", self.config.serial, "--port", str(port), "--slot", str(slot),
                "--bootstrap", _bootstrap,
            ]'''),"""
assert s.count(old) == 1
open(p, "w", encoding="utf-8", newline="\n").write(s.replace(old, new, 1))
print("ok")
