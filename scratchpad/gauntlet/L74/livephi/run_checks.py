"""Run explicit, author-reviewed verification commands and retain their receipts."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]


def main():
    env=dict(os.environ,ROYALE_RUNTIME="20261006",OMP_NUM_THREADS="1",CUDA_VISIBLE_DEVICES="-1")
    tests=["pipeline/tests/test_live_phi.py","pipeline/tests/test_reward_shaping.py","pipeline/tests/test_value_phi.py::TestMath",
           "scratchpad/gauntlet/L74/livephi/test_data.py"]
    commands=[("G1",[sys.executable,str(HERE/"verify.py"),"dataset"],"DATASET VERIFIED"),
              ("G2",[sys.executable,str(HERE/"verify.py"),"evaluation"],"EVALUATION VERIFIED"),
              ("G3",[sys.executable,"-m","pytest",*tests,"-q","-p","no:cacheprovider"],"passed")]
    receipts={}
    for gate,cmd,token in commands:
        start=time.monotonic();p=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
        output=p.stdout.decode("utf8",errors="replace");(HERE/(gate+".log")).write_text(output,encoding="utf8")
        assert p.returncode==0 and token in output,(gate,p.returncode,output)
        if gate=="G3": assert not re.search(r"\d+ (failed|error|skipped)",output)
        receipts[gate]={"command":cmd,"cwd":str(ROOT),"shell":"direct executable (shell=False), launched from PowerShell",
                        "exit_code":p.returncode,"expected":token,"matched":True,"output_sha256":hashlib.sha256(p.stdout).hexdigest(),
                        "seconds":time.monotonic()-start,"output":output}
        print(gate,"VERIFIED",flush=True)
    receipts["sources"]={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [ROOT/"pipeline/live_phi.py",ROOT/"pipeline/rl_royale.py",ROOT/"pipeline/tests/test_live_phi.py",HERE/"phi_live.pt",HERE/"results.json",HERE/"REPORT.md"]}
    (HERE/"VERIFICATION.json").write_text(json.dumps(receipts,indent=2))
    gates=(HERE/"GATES.md").read_text()
    for gate,r in receipts.items():
        if gate=="sources":continue
        gates=gates.replace(f"- [ ] {gate}:",f"- [x] {gate}:")
        pattern=rf"(- \[x\] {gate}:.*?  EVIDENCE: )[^\n]*"
        evidence=f"exit=0; matched=true; cwd={ROOT}; shell=direct Python via PowerShell; output_sha256={r['output_sha256']}; receipt=VERIFICATION.json"
        gates=re.sub(pattern,lambda m:m.group(1)+evidence,gates,flags=re.S)
    (HERE/"GATES.md").write_text(gates)
    print("ALL LIVEPHI GATES VERIFIED",flush=True)


if __name__=="__main__":main()
