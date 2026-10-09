"""MEASUREMENT ONLY, VM tree ~/tau_threat/repo: hook pipeline/tau_tel.metrics into BehaviourTelemetry.result as out['tau'].
    ~/venv/bin/python vm_tel_patch.py ~/tau_threat/repo/pipeline"""
import pathlib, sys

P = pathlib.Path(sys.argv[1]) / 'behaviour_telemetry.py'
t = P.read_text()
OLD = "        out['push']=push_metrics(self.frames,self.plays,side)\n        return out"
NEW = """        out['push']=push_metrics(self.frames,self.plays,side)
        from .tau_tel import metrics as _tau_metrics
        out['tau']=_tau_metrics(self.frames,self.plays,side)
        return out"""
if NEW not in t:
    assert t.count(OLD) == 1, 'unexpected behaviour_telemetry.py'
    P.write_text(t.replace(OLD, NEW))
print('patched', P)
