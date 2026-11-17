"""Replay pinned reviewer records and the two fresh operator hash manifests."""
from pathlib import Path
import json,hashlib,os
from collections import Counter
R=Path(__file__).resolve().parent;D=Path(os.environ.get('RESULTS_DIR',str(R/'results')))
blob=lambda b:hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
p=json.loads((R/'source-provenance.json').read_text())
for f in p['files']:assert blob((R/'claude'/f['path']).read_bytes())==f['sha']
c=json.loads((R/'claude/tile_swap_and_operator_hash.json').read_text())
assert c['default_1_worker']==c['4_workers_with_1_worker_tiles']
assert c['default_4_workers']==c['1_worker_with_4_worker_tiles']
old=json.loads((R/'prior-partition.json').read_text());o={x['label']:x for x in old}
for key,label in [('default_1_worker','default1'),('default_4_workers','default4'),('1_worker_with_4_worker_tiles','workers1_tiles4'),('4_workers_with_1_worker_tiles','workers4_tiles1')]:assert c[key]==o[label]['exact_sha256']
a=json.loads((D/'operator-1.json').read_text());b=json.loads((D/'operator-4.json').read_text())
assert a['arrays']==b['arrays']
def tile_counts(rec):
 counts=Counter()
 for x in rec['tile_choices']:counts[(x['elements'],x['bytes_per_entry'],x['planned'],x['tile'])]+=x['calls']
 return counts
assert tile_counts(a)==tile_counts(b)
for rec in [a,b]:
 payload={e['path']:(e['shape'],e['dtype'],e['sha256']) for e in rec['arrays']}
 digest=hashlib.sha256(json.dumps(sorted(payload.items())).encode()).hexdigest()
 assert digest==rec['combined_sha256']==c['operator']['combined_sha256_1']==c['operator']['combined_sha256_4']
 assert len(rec['arrays'])==rec['array_count']==351
 assert sum(e['dtype'].startswith('complex') for e in rec['arrays'])==rec['complex_count']==141
 assert sum(e['nbytes'] for e in rec['arrays'] if e['owns_data'])==rec['directly_owned_bytes']==rec['operator_bytes']==rec['unique_numpy_owner_bytes']==311969440
 assert all(x['threads']==1 for x in rec['blas_pools'])
out=dict(pinned_files_verified=5,tile_swap_matches_prior_independent_evidence=True,fresh_operator_assemblies=2,new_solves=0,
         array_count=351,complex_arrays=141,retained_bytes=311969440,all_array_hashes_shapes_dtypes_strides_and_ownership_match=True,
         combined_sha256=a['combined_sha256'],matches_claude=True,actual_tile_size_counts_match=True,
         query_allocations={str(x['workers']):x['effective_query_workers'] for x in [a,b]},
         scope='Saved manifests permit hash comparison; full operator arrays were generated and hashed in this run, not archived. One Linux build, one geometry, workers 1 and 4.')
(R/'analysis.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
