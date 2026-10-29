"""Persistent, serialized research jobs using the official Freqtrade CLI."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import uuid

from server.catalog import RUNTIME, ROOT, DATA, RESULTS, STRATEGIES, USER_DATA, make_config, read_json, write_json, settings

POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='research')
LOCK = threading.RLock()
PROCESSES = {}
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def now():
    return datetime.now(timezone.utc).isoformat()


def redact(text):
    for key, value in settings().items():
        if any(word in key for word in ('token', 'secret', 'password', 'key')) and value:
            text = text.replace(str(value), '[REDACTED]')
    return re.sub(r'\b\d{6,12}:[A-Za-z0-9_-]{30,}\b', '[REDACTED]', text)


def update(job_id, **changes):
    with LOCK:
        path = RUNTIME / 'jobs' / f'{job_id}.json'
        job = read_json(path)
        job.update(changes, updated=now())
        write_json(path, job)
        return job


def list_jobs():
    return sorted([read_json(p) for p in (RUNTIME / 'jobs').glob('*.json')
                   if re.fullmatch(r'[a-f0-9]{32}', p.stem)],
                  key=lambda item: item['created'], reverse=True)


def recover_jobs():
    for job in list_jobs():
        if job['status'] in ('running', 'queued', 'cancelling'):
            update(job['id'], status='interrupted', message='Application restarted. Review log and run again.')


def run_command(job_id, command):
    with (RUNTIME / 'jobs' / f'{job_id}.log').open('a', encoding='utf-8') as output:
        env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'MPLBACKEND': 'Agg', 'PYTHONIOENCODING': 'utf-8'}
        with LOCK:
            if read_json(RUNTIME / 'jobs' / f'{job_id}.json')['status'] in ('cancelled', 'cancelling'):
                raise InterruptedError('Cancelled by user.')
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       creationflags=HIDDEN)
            PROCESSES[job_id] = process
        code = process.wait()
        with LOCK:
            PROCESSES.pop(job_id, None)
        if read_json(RUNTIME / 'jobs' / f'{job_id}.json')['status'] in ('cancelled', 'cancelling'):
            raise InterruptedError('Cancelled by user.')
        if code:
            raise RuntimeError(f'Process exited with code {code}. See the job log for details.')


def submit(kind, payload):
    job_id = uuid.uuid4().hex
    record = dict(id=job_id, kind=kind, payload=payload, status='queued', created=now(), updated=now(),
                  message='Waiting for the research worker.', results=[])
    write_json(RUNTIME / 'jobs' / f'{job_id}.json', record)
    POOL.submit(execute, job_id)
    return record


def execute(job_id):
    job = read_json(RUNTIME / 'jobs' / f'{job_id}.json')
    if job['status'] == 'cancelled':
        return
    update(job_id, status='running', message='Starting…')
    try:
        kind, p = job['kind'], job['payload']
        if kind == 'import':
            if not (DATA / '.git').exists():
                if DATA.exists() and any(DATA.iterdir()):
                    raise ValueError('An incomplete dataset directory exists. Review it before retrying import.')
                run_command(job_id, ['git', 'clone', '--depth', '1',
                                    'https://github.com/iterativv/NostalgiaForInfinityData.git', str(DATA)])
            run_command(job_id, [sys.executable, str(ROOT / 'scripts' / 'import_strategies.py')])
            scan_data(job_id)
        elif kind == 'scan':
            scan_data(job_id)
        elif kind == 'report':
            from server.reports import generate
            result = generate(p['file'], p['strategy'])
            update(job_id, results=[result['id']])
        else:
            names = p['strategies']
            outputs = []
            warnings = []
            for index, name in enumerate(names):
                update(job_id, message=f'{index + 1}/{len(names)} · {name}')
                config = make_config(name, p['exchange'], p['capital'], p['max_open_trades'], p.get('pairs'))
                if kind == 'lookahead-analysis':
                    # The native analysis forces market orders to avoid limit-order false positives.
                    config['entry_pricing']['price_side'] = 'other'
                    config['exit_pricing']['price_side'] = 'other'
                if p.get('freqai_model'):
                    config['freqai'] = p['freqai_config']
                path = RUNTIME / 'jobs' / f'{job_id}-{name}.config.json'
                write_json(path, config)
                command = [sys.executable, '-m', 'freqtrade', kind, '--config', str(path),
                           '--strategy', name, '--userdir', str(USER_DATA), '--datadir', config['datadir']]
                if p.get('timerange'):
                    command += ['--timerange', p['timerange']]
                if p.get('freqai_model'):
                    command += ['--freqaimodel', p['freqai_model']]
                if kind == 'backtesting':
                    directory = RESULTS / job_id / name
                    directory.mkdir(parents=True, exist_ok=True)
                    command += ['--export', 'trades', '--export-directory', str(directory), '--cache', 'none',
                                '--enable-protections', '--breakdown', 'month', 'year']
                elif kind == 'hyperopt':
                    command += ['--epochs', str(p['epochs']), '--job-workers', str(p['workers']),
                                '--hyperopt-loss', p['loss'], '--spaces', *p['spaces'], '--disable-param-export']
                elif kind == 'lookahead-analysis':
                    command += ['--lookahead-analysis-exportfilename', str(RUNTIME / 'jobs' / f'{job_id}-{name}.csv')]
                elif kind == 'recursive-analysis':
                    command += ['--startup-candle', '30', '100', '248', '500', '1000']
                run_command(job_id, command)
                if kind == 'lookahead-analysis' and not (RUNTIME / 'jobs' / f'{job_id}-{name}.csv').exists():
                    raise RuntimeError('Analysis did not produce verified results. The native command can exit successfully with insufficient trades or configuration errors; inspect its log.')
                if kind == 'backtesting':
                    from server.reports import generate
                    for result in directory.glob('*.zip'):
                        file = str(result.relative_to(RESULTS)).replace('\\', '/')
                        outputs.append(file)
                        try:
                            generate(file, name)
                        except Exception as exc:
                            warnings.append(f'{name}: {redact(str(exc))}')
                            with (RUNTIME / 'jobs' / f'{job_id}.log').open('a', encoding='utf-8') as log:
                                log.write(f'\nReport could not be generated: {redact(str(exc))}\n')
                    update(job_id, results=outputs)
            if kind == 'backtesting' and not outputs:
                raise RuntimeError('Freqtrade completed but did not produce a backtest archive.')
            if warnings:
                update(job_id, report_warnings=warnings)
        if read_json(RUNTIME / 'jobs' / f'{job_id}.json')['status'] in ('cancelled', 'cancelling'):
            raise InterruptedError()
        warnings = read_json(RUNTIME / 'jobs' / f'{job_id}.json').get('report_warnings', [])
        update(job_id, status='completed', message='Engine completed. Report needs attention: ' + '; '.join(warnings) if warnings else 'Completed.', finished=now())
    except InterruptedError:
        update(job_id, status='cancelled', message='Cancelled. Partial files are kept for inspection.', finished=now())
    except Exception as exc:
        update(job_id, status='failed', message=redact(str(exc)), finished=now())


def cancel(job_id):
    with LOCK:
        record = read_json(RUNTIME / 'jobs' / f'{job_id}.json')
        if not record:
            raise ValueError('Job not found.')
        if record['status'] not in ('queued', 'running'):
            return record
        process = PROCESSES.get(job_id)
        update(job_id, status='cancelling' if process else 'cancelled', message='Cancellation requested.')
        if process and process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=HIDDEN)
            else:
                process.terminate()
        return read_json(RUNTIME / 'jobs' / f'{job_id}.json')


def scan_data(job_id):
    import pandas as pd
    import pyarrow.feather as feather
    files = sorted(DATA.rglob('*.feather'))
    rows = []
    for index, path in enumerate(files):
        if index % 50 == 0:
            if read_json(RUNTIME / 'jobs' / f'{job_id}.json')['status'] in ('cancelled', 'cancelling'):
                raise InterruptedError()
            update(job_id, message=f'Inspecting candles · {index}/{len(files)} files')
        row = dict(file=str(path.relative_to(DATA)).replace('\\', '/'), bytes=path.stat().st_size)
        try:
            dates = feather.read_table(path, columns=['date']).column('date').to_pandas()
            dates = pd.to_datetime(dates, utc=True)
            match = re.search(r'-(\d+)([mhd])(?:-|\.)', path.name)
            seconds = int(match[1]) * {'m': 60, 'h': 3600, 'd': 86400}[match[2]] if match else None
            differences = dates.sort_values().diff().dt.total_seconds()
            row.update(rows=len(dates), start=dates.min().isoformat(), end=dates.max().isoformat(),
                       duplicates=int(dates.duplicated().sum()),
                       gaps=int((differences > seconds).sum()) if seconds else None)
        except Exception as exc:
            row['error'] = str(exc)
        rows.append(row)
    revision = subprocess.run(['git', '-c', f'safe.directory={DATA.as_posix()}', '-C', str(DATA),
                               'rev-parse', 'HEAD'], capture_output=True, text=True, creationflags=HIDDEN)
    write_json(RUNTIME / 'inventory.json', dict(scanned=now(), revision=revision.stdout.strip(),
               files=rows, count=len(rows), bytes=sum(row['bytes'] for row in rows)))
