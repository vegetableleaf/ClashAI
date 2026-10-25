import json, sys, numpy as np
z = np.load('icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz', allow_pickle=False)
m = json.loads(str(z['meta']))
print({k: v for k, v in m.items() if k not in ('card_vocab', 'fields', 'summary_fields', 'card_fields', 'failed')})
print('failed', len(m['failed']), m['failed'][:3])
print(z.files)
