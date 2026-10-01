"""Measure real parsing/chunking, not fake embedding or model performance."""
import json
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from email_rag.parsing import parse_email, chunks_for

root=Path(__file__).resolve().parents[1]
files=sorted((root/'sample_data').glob('*/*.eml'))
raw=[p.read_bytes() for p in files]
rounds=100
measurements=[]
for _ in range(rounds):
    start=perf_counter()
    records=[parse_email(b) for b in raw]
    chunks=[chunks_for(r) for r in records]
    measurements.append(perf_counter()-start)
report={'measurement':'actual offline MIME parsing and chunking only','python':platform.python_version(),
        'platform':platform.platform(),'rounds':rounds,'emails_per_round':len(raw),
        'chunks_per_round':sum(len(c) for c in chunks),'attachments_per_round':sum(n!='body' for r in records for n,_ in r.parts),
        'median_batch_ms':statistics.median(measurements)*1000,
        'p95_batch_ms':sorted(measurements)[94]*1000,
        'median_per_email_ms':statistics.median(measurements)*1000/len(raw),
        'embedding_s':None,'retrieval_s':None,'generation_s':None,
        'note':'No PostgreSQL or Ollama available in authoring environment. Null values are unmeasured, not zero.'}
(root/'reports/offline_benchmark.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
