"""Enable nested virtualization on one existing GCE VM via the Compute REST API (owner-approved 2026-10-13).
GET instance -> set advancedMachineFeatures.enableNestedVirtualization -> PUT (restart allowed) -> wait on the operation.
The access token comes from gcloud and is never printed."""
import json, subprocess, sys, time, urllib.request

GCLOUD = r'C:\Users\benpe\tools\google-cloud-sdk\bin\gcloud.cmd'
URL = 'https://compute.googleapis.com/compute/v1/projects/clashbot-oracle/zones/us-east1-c/instances/clashbot-oracle-2'


def token():
    out = subprocess.run([GCLOUD, 'auth', 'print-access-token'], capture_output=True, text=True, check=True).stdout
    return [l for l in out.splitlines() if l.strip() and 'Python was not found' not in l][-1].strip()


def call(method, url, body=None):
    req = urllib.request.Request(url, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


inst = call('GET', URL)
amf = inst.setdefault('advancedMachineFeatures', {})
print('before:', json.dumps(amf), 'status', inst['status'])
if amf.get('enableNestedVirtualization'):
    print('already enabled'); sys.exit(0)
amf['enableNestedVirtualization'] = True
op = call('PUT', URL + '?mostDisruptiveAllowedAction=RESTART', inst)
print('operation:', op.get('name'), op.get('status'))
for _ in range(90):
    op = call('GET', op['selfLink'])
    if op.get('status') == 'DONE':
        break
    time.sleep(5)
print('op done:', op.get('status'), 'error:', json.dumps(op.get('error')) if op.get('error') else None)
after = call('GET', URL)
print('after:', json.dumps(after.get('advancedMachineFeatures')), 'status', after['status'])
