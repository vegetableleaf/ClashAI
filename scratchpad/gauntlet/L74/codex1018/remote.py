"""Run an inspected Python script remotely without stdin or shell interpolation."""
import base64
from pathlib import Path
import subprocess
import sys

def run(host,port,code):
    encoded=base64.b64encode(code.encode()).decode()
    command='python3 -c "import base64;exec(base64.b64decode(\''+encoded+'\'))"'
    result=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=15','-o','ServerAliveInterval=30','-i',str(Path.home()/'.ssh/runpod_clashbot'),'-p',str(port),'root@'+host,command])
    if result.returncode:raise SystemExit(result.returncode)
    return result

if __name__=='__main__':run(sys.argv[1],sys.argv[2],Path(sys.argv[3]).read_text())
