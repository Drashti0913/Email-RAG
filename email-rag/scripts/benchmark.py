"""Live local-model benchmark. Persist raw evidence, timings, and model digests.

Run AFTER sample ingestion. Keyword coverage is a diagnostic, not factual accuracy.
Use a fresh sample-only database to make expected-source recall meaningful.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import sys
from time import perf_counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from email_rag.models import Ollama
from email_rag.parsing import parse_email
from email_rag.pipeline import ask, model_identity, summarize_all
from email_rag.store import Store

CASES = [
    ('What did Sarah say about the Q4 budget?',{},['a01-budget'],['120,000','70,000','50,000']),
    ('Show me emails discussing the API integration project',{},['a02-api'],['October 8']),
    ('What is the API retry policy?',{},['a02-api'],['5','429','503']),
    ('When did I last hear from the marketing team?',{'sender':'marketing@example.test','latest':True},['a06-marketing-latest'],['2026-09-30']),
    ('Summarize all conversations about the product launch',{'all':True,'subject':'product launch'},['a04-launch','a05-launch-update'],['October 15','October 22']),
]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--alice-token',type=Path,required=True)
    parser.add_argument('--bob-token',type=Path,required=True)
    parser.add_argument('--out',type=Path,default=Path('reports/local_benchmark.json'))
    parser.add_argument('--runs',type=int,default=3)
    args=parser.parse_args()
    if args.runs < 1:parser.error('--runs must be positive')
    models=Ollama();alice=Store(args.alice_token.read_text());bob=Store(args.bob_token.read_text())
    try:
        identity=model_identity(models);alice.ensure_model(identity);bob.ensure_model(identity)
        sample=Path(__file__).resolve().parents[1]/'sample_data/alice'
        ids={p.stem:parse_email(p.read_bytes()).email_id for p in sample.glob('*.eml')}
        # Measure actual model throughput separately, without altering indexed data.
        texts=[t for p in sample.glob('*.eml') for _,t in parse_email(p.read_bytes()).parts]
        start=perf_counter();models.embed(texts);embedding_s=perf_counter()-start
        results=[]
        for run in range(args.runs):
            for question,options,expected,terms in CASES:
                result=(summarize_all(alice,models,question,options['subject']) if options.get('all')
                        else ask(alice,models,question,**options))
                retrieved={s['email_id'] for s in result['sources']}
                results.append({'run':run,'question':question,'result':result,
                                'expected_source_recall':sum(ids[k] in retrieved for k in expected)/len(expected),
                                'keyword_coverage_proxy':sum(t.casefold() in result['answer'].casefold() for t in terms)/len(terms)})
        cross=ask(alice,models,'What is the private Orion acquisition code COBALT-731?')
        own=ask(bob,models,'What is the private Orion acquisition code?')
        # Inspect sources, not echoed query text: a model might repeat the input string.
        bob_ids=set()
        for p in (sample.parent/'bob').glob('*.eml'):bob_ids.add(parse_email(p.read_bytes()).email_id)
        cross_leaks=[s for s in cross['sources'] if s['email_id'] in bob_ids]
        security={'alice_bob_source_leaks':len(cross_leaks),
                  'bob_own_secret_retrieved':any('COBALT-731' in s['excerpt'] for s in own['sources']),
                  'alice_result':cross,'bob_result':own}
        metrics={}
        for key in ['query_embedding_s','retrieval_s','generation_s','total_s']:
            values=sorted(x['result']['metrics'][key] for x in results)
            metrics[key]={'median':statistics.median(values),'max':max(values),
                          'p95_nearest_rank':values[max(0,__import__('math').ceil(.95*len(values))-1)]}
        report={'status':'live measured results','python':platform.python_version(),'platform':platform.platform(),
                'processor':platform.processor(),'models':models.identities(),'runs':args.runs,
                'embedding_batch':{'texts':len(texts),'seconds':embedding_s,'texts_per_second':len(texts)/embedding_s},
                'timings':metrics,'results':results,'isolation':security,
                'interpretation':'Run 0 includes model warm-up. Keyword matches are not a factual-accuracy score. Manually check citations and contradictions.'}
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(report,indent=2,default=str))
        print(f'Wrote {args.out}')
        if cross_leaks:raise SystemExit('FAIL: cross-user source leakage')
    finally:
        alice.close();bob.close()


if __name__=='__main__':main()
