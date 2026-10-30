import json, sys, zipfile
import numpy as np
z = np.load(sys.argv[1], allow_pickle=False)
m = json.loads(str(z['meta']))
print({k: m[k] for k in ('replays', 'tables', 'events', 'rows', 'rows_with_table', 'E_MAX', 'built')})
print(z.files)
