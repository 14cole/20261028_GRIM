import json,os,platform,sys
from pathlib import Path
import numpy,scipy,psutil,threadpoolctl
P=Path(__file__).resolve().parent
record=dict(python=sys.version,platform=platform.platform(),numpy=numpy.__version__,scipy=scipy.__version__,
 cpu_affinity=psutil.Process().cpu_affinity(),host_memory_bytes=psutil.virtual_memory().total,
 cgroup={p:Path('/sys/fs/cgroup/'+p).read_text().strip() for p in ('memory.max','cpu.max')},
 threadpools=threadpoolctl.threadpool_info(),default_solve_reservation_gib=8,watchdog_process_tree_gib=10,
 desktop_forecast_assumption='32 GiB installed, 24 GiB one-solve reservation, adequate scratch; not executed on 32 GiB',
 lineage=dict(production_baseline='ae08d66dc309c393ce62cc76bacd510a150ebf33',audit_parent='bfcd255e76b12fc5ed13b44b1e276c4b7472a5ce',claude_head_observed='252e9d3ab1971c6fb8c2d21e839d31ab36e6a54a'))
(P/'ENVIRONMENT.json').write_text(json.dumps(record,indent=2)+'\n')
print(record['cgroup'])
