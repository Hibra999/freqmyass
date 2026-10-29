"""Real engine smoke tests, with no exchange keys and no orders."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.catalog import initialize, read_json, RUNTIME
from server.app import Research
from server.jobs import submit
from server.reports import summaries
import time

initialize()
records = []
for name in ['NASOSv4_SMA', 'NotAnotherSMAOffsetStrategyHO', 'dip_catcher', 'SingleB_FixedRR']:
    futures = name in ('dip_catcher', 'SingleB_FixedRR')
    pairs = [f'{coin}/USDT:USDT' if futures else f'{coin}/USDT' for coin in ['BTC', 'ETH', 'SOL']]
    payload = Research(strategies=[name], pairs=pairs, timerange='20250101-20250301').model_dump()
    job = submit('backtesting', payload)
    records.append(job['id'])
    print(name, job['id'], flush=True)
while True:
    items = [read_json(RUNTIME / 'jobs' / f'{job_id}.json') for job_id in records]
    if all(item['status'] in ('completed', 'failed', 'cancelled') for item in items):
        for item in items:
            print(item['payload']['strategies'], item['status'], item['message'], flush=True)
        reports = summaries()
        verified = all(item['status'] == 'completed' and not item.get('report_warnings')
                       and all(any(report['file'] == file and report['trades'] > 0 and report['html_ready']
                                   for report in reports) for file in item['results']) for item in items)
        sys.exit(0 if verified else 1)
    time.sleep(5)
