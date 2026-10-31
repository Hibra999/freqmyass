"""GBM candle paths evaluated by the unmodified Freqtrade backtesting engine."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import copy
import csv
import gzip
import hashlib
import importlib.metadata
from functools import lru_cache
import gc
import json
import logging
import math
from multiprocessing.util import Finalize
import os
from pathlib import Path
import re
import sqlite3
import shutil
import subprocess
import sys
import time
import uuid

import numpy as np
import pandas as pd
import psutil
from filelock import FileLock

from server.catalog import ROOT, RUNTIME, DATA, STRATEGIES, read_json, write_json, make_config

BASE = RUNTIME / 'simulations'
REGIMES = ('bear', 'neutral', 'bull')
GROUPS = (('spot', ('NASOSv4_SMA', 'NotAnotherSMAOffsetStrategyHO')),
          ('futures', ('dip_catcher', 'SingleB_FixedRR')))
CONTEXT = {}
os.environ.setdefault('CUPY_CACHE_DIR', str(RUNTIME / 'cupy-cache'))


@lru_cache(maxsize=1)
def gpu_info():
    import cupy as cp
    if cp.cuda.runtime.getDeviceCount() < 1:
        raise ValueError('CUDA requires an NVIDIA GPU and a working driver.')
    return dict(name=cp.cuda.runtime.getDeviceProperties(0)['name'].decode(), cupy=cp.__version__,
                cuda_runtime=cp.cuda.runtime.runtimeGetVersion())


def directory(run_id):
    if not re.fullmatch(r'[a-f0-9]{32}', run_id) or not (BASE / run_id / 'config.json').exists():
        raise ValueError('Unknown simulation.')
    return BASE / run_id


def calibration():
    path = DATA / 'binance' / 'BTC_USDT-5m.feather'
    data = pd.read_feather(path)
    changes = np.log(data['close']).diff()[data['date'].diff().eq(pd.Timedelta(minutes=5))].dropna()
    sigma = float(changes.std(ddof=1) * np.sqrt(365 * 288))
    return dict(asset='BTC/USDT', initial_price=float(data['close'].iloc[-1]), volatility=sigma,
                historical_drift=float(changes.mean() * 365 * 288 + sigma**2 / 2),
                observations=len(changes), start=str(data['date'].min()), end=str(data['date'].max()),
                dataset_revision=read_json(RUNTIME / 'inventory.json', {}).get('revision'))


def state(run_id):
    path = directory(run_id)
    value = read_json(path / 'state.json')
    owner = value.get('owner', {})
    alive = False
    try:
        process = psutil.Process(owner['pid'])
        alive = process.create_time() == owner['created'] and Path(process.exe()).resolve() == Path(sys.executable).resolve()
    except (KeyError, psutil.Error):
        pass
    active = ('running', 'pausing', 'starting', 'finalizing', 'publishing')
    value['running'] = alive and value['status'] in active
    if not value['running'] and value['status'] in active:
        value['status'] = 'interrupted'
    return value


def list_runs():
    if not BASE.exists():
        return []
    return sorted([state(p.name) for p in BASE.iterdir() if (p / 'config.json').exists()],
                  key=lambda row: row['created'], reverse=True)


def launch(run_id):
    path = directory(run_id)
    if any(row['running'] for row in list_runs()):
        raise ValueError('Pause the active simulation before starting another.')
    write_json(path / 'control.json', {'action': 'run'})
    with (path / 'worker.log').open('a', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-m', 'server.simulations', run_id], cwd=ROOT,
            stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8',
                 'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'NUMEXPR_MAX_THREADS': '1'})
    value = read_json(path / 'state.json')
    value.update(status='starting', owner=dict(pid=process.pid, created=psutil.Process(process.pid).create_time()))
    write_json(path / 'state.json', value)
    return value


def create(payload):
    if any(row['running'] for row in list_runs()):
        raise ValueError('A simulation is already running.')
    gpu = gpu_info()
    source = calibration()
    run_id = uuid.uuid4().hex
    path = BASE / run_id
    strategy_path = path / 'strategies'
    strategy_path.mkdir(parents=True)
    strategy_hashes = {}
    for _, names in GROUPS:
        for name in names:
            for suffix in ('.py', '.json'):
                source_file = STRATEGIES / f'{name}{suffix}'
                if source_file.exists():
                    frozen = strategy_path / source_file.name
                    shutil.copy2(source_file, frozen)
                    strategy_hashes[frozen.name] = hashlib.sha256(frozen.read_bytes()).hexdigest()
    config = {**payload, 'calibration': source, 'volatility': payload.get('volatility') or source['volatility'],
              'asset': 'BTC/USDT', 'warmup_days': 14, 'substeps': 5, 'volume': 100,
              'funding_rate': 0, 'mark_price': 'synthetic spot price', 'engine_version': '2026.8',
              'backend': 'cuda', 'gpu': gpu}
    config.update(strategy_sources=read_json(ROOT / 'strategies.lock.json'), runnable_strategy_hashes=strategy_hashes)
    write_json(path / 'config.json', config)
    write_json(path / 'state.json', dict(id=run_id, created=time.time(), status='starting', completed=0,
        target=config['paths'], strategy_evaluations=0, failures=0, workers=config['workers'],
        horizon_days=config['days'], elapsed_seconds=0, message='Preparing native engines.'))
    return launch(run_id)


def control(run_id, action):
    path = directory(run_id)
    current = state(run_id)
    if action == 'resume':
        if current['completed'] >= current['target']:
            raise ValueError('This simulation is already complete.')
        return launch(run_id)
    write_json(path / 'control.json', {'action': 'pause'})
    return {'requested': 'pause', 'message': 'In-flight paths finish before pausing. Completed results are retained.'}


def candles(config, index):
    """Exact GBM increments at one minute, aggregated into five-minute OHLC."""
    seed = np.random.SeedSequence([config['seed'], index])
    if config.get('backend') == 'cuda':
        import cupy as xp
        rng = xp.random.RandomState(int(seed.generate_state(1, dtype=np.uint64)[0]))
    else:
        xp = np
        rng = np.random.default_rng(seed)
    regime = index % 3
    mu = config['drifts'][regime]
    sigma = config['volatility']
    bars = (config['days'] + config['warmup_days']) * 288
    substeps = config['substeps']
    dt = 1 / (365 * 288 * substeps)
    increments = (mu - sigma**2 / 2) * dt + sigma * math.sqrt(dt) * rng.standard_normal(bars * substeps)
    logs = xp.concatenate((xp.zeros(1), xp.cumsum(increments)))
    warmup = config['warmup_days'] * 288 * substeps
    prices = config['calibration']['initial_price'] * xp.exp(logs - logs[warmup])
    if config.get('backend') == 'cuda':
        prices = xp.asnumpy(prices)
    if not np.isfinite(prices).all() or np.any(prices <= 0):
        raise ValueError('GBM prices exceeded finite positive numeric bounds.')
    blocks = prices[1:].reshape(bars, substeps)
    opens = prices[:-1:substeps]
    start = pd.Timestamp('2025-01-01', tz='UTC') - pd.Timedelta(days=config['warmup_days'])
    frame = pd.DataFrame(dict(date=pd.date_range(start, periods=bars, freq='5min'), open=opens,
        high=np.maximum(opens, blocks.max(axis=1)), low=np.minimum(opens, blocks.min(axis=1)),
        close=blocks[:, -1], volume=float(config['volume'])))
    active = prices[warmup:]
    asset = dict(final=float(active[-1]), minimum=float(active.min()), maximum=float(active.max()),
                 drawdown=float(np.max(1 - active / np.maximum.accumulate(active))))
    daily = active[::288 * substeps].tolist() if index < 768 else None
    return frame, REGIMES[regime], asset, daily


def initialize_worker(run_id):
    logging.disable(logging.CRITICAL)
    path = directory(run_id)
    CONTEXT.update(config=read_json(path / 'config.json'), path=path / 'workers' / str(os.getpid()),
                   engines={}, configs={})
    CONTEXT['path'].mkdir(parents=True, exist_ok=True)
    Finalize(None, cleanup_worker, exitpriority=10)
    if importlib.metadata.version('freqtrade') != CONTEXT['config']['engine_version'] or gpu_info()['cupy'] != CONTEXT['config']['gpu']['cupy']:
        raise RuntimeError('Engine or CUDA library version changed. Restore the recorded versions before resuming.')
    for name, digest in CONTEXT['config']['runnable_strategy_hashes'].items():
        if hashlib.sha256((path / 'strategies' / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('A frozen strategy changed. Restore its recorded contents before resuming.')


def cleanup_worker():
    engines = CONTEXT.pop('engines', {})
    for name in list(engines):
        engines.pop(name).close()
    gc.collect()


def evaluate(index):
    from freqtrade.commands.optimize_commands import setup_optimize_configuration
    from freqtrade.enums import RunMode
    from freqtrade.optimize.backtesting import Backtesting
    from freqtrade.data.metrics import calculate_max_drawdown
    from server.jobs import redact

    config, path = CONTEXT['config'], CONTEXT['path']
    frame, regime, asset, daily = candles(config, index)
    hourly = frame.set_index('date').resample('1h').agg(dict(open='first', high='max', low='min', close='last', volume='sum')).reset_index()
    frame.to_feather(path / 'BTC_USDT-5m.feather')
    hourly.to_feather(path / 'BTC_USDT-1h.feather')
    futures = path / 'futures'
    futures.mkdir(exist_ok=True)
    frame.to_feather(futures / 'BTC_USDT_USDT-5m-futures.feather')
    hourly.to_feather(futures / 'BTC_USDT_USDT-1h-mark.feather')
    funding = hourly.copy()
    funding[['open', 'high', 'low', 'close', 'volume']] = 0.
    funding.to_feather(futures / 'BTC_USDT_USDT-1h-funding_rate.feather')
    results = {}
    for market, names in GROUPS:
        if market not in CONTEXT['configs']:
            native = make_config(names[0], capital=config['capital'], max_open_trades=config['max_open_trades'],
                pairs=['BTC/USDT' if market == 'spot' else 'BTC/USDT:USDT'])
            native['stake_amount'] = config['stake_amount']
            native['api_server']['enabled'] = False
            native_path = path / f'{market}.json'
            write_json(native_path, native)
            end = pd.Timestamp('2025-01-01') + pd.Timedelta(days=config['days'])
            args = dict(config=[str(native_path)], datadir=str(path), strategy_list=list(names),
                        strategy_path=str(path.parent.parent / 'strategies'),
                        timerange=f'20250101-{end:%Y%m%d}', enable_protections=True,
                        export='none', backtest_cache='none')
            CONTEXT['configs'][market] = setup_optimize_configuration(args, RunMode.BACKTEST)
        # A fresh native backtester clears data-provider, strategy and trade state for each path.
        bt = Backtesting(copy.deepcopy(CONTEXT['configs'][market]), exchange=CONTEXT['engines'].get(market),
                         progress_callback=lambda _: None)
        CONTEXT['engines'][market] = bt.exchange
        data, timerange = bt.load_bt_data()
        for strategy in bt.strategylist:
            name = strategy.get_strategy_name()
            try:
                bt.backtest_one_strategy(strategy, data, timerange)
                value = bt.all_bt_content[name]
                trades = value['results']
                drawdown = 0.
                if len(trades):
                    try:
                        drawdown = calculate_max_drawdown(trades, starting_balance=config['capital'], relative=True).relative_account_drawdown
                    except ValueError:
                        pass  # No negative trade-equity excursion.
                results[name] = dict(final_balance=float(value['final_balance']), trades=len(trades),
                    drawdown=float(drawdown), wins=int((trades['profit_abs'] > 0).sum()) if len(trades) else 0)
            except Exception as exc:
                results[name] = {'error': redact(f'{type(exc).__name__}: {exc}')[:1200]}
    return dict(index=index, regime=regime, asset=asset, daily=daily, strategies=results)


def connect_db(path):
    db = sqlite3.connect(path / 'outcomes.sqlite', timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS paths (id INTEGER PRIMARY KEY, result TEXT NOT NULL, failures INTEGER NOT NULL)')
    db.commit()
    return db


def summarize(run_id):
    path = directory(run_id)
    config = read_json(path / 'config.json')
    groups, price_groups, curves = {}, {r: [] for r in REGIMES}, {r: [] for r in REGIMES}
    count = 0
    with connect_db(path) as db:
        for raw, in db.execute('SELECT result FROM paths ORDER BY id'):
            row = json.loads(raw)
            count += 1
            regime = row['regime']
            price_groups[regime].append(row['asset']['final'])
            if row['daily']:
                curves[regime].append(row['daily'])
            for name, result in row['strategies'].items():
                group = groups.setdefault((regime, name), dict(final=[], drawdown=[], trades=[], failed=0))
                if 'error' in result:
                    group['failed'] += 1
                else:
                    for key in ('drawdown', 'trades'):
                        group[key].append(result[key])
                    group['final'].append(result['final_balance'])
    rows = []
    for (regime, name), values in groups.items():
        final = np.asarray(values['final'])
        rows.append(dict(regime=regime, strategy=name, valid=len(final), failed=values['failed'],
            probability_loss=float(np.mean(final < config['capital'])) if len(final) else None,
            probability_no_trades=float(np.mean(np.asarray(values['trades']) == 0)) if len(final) else None,
            final_percentiles=np.percentile(final, [5, 50, 95]).tolist() if len(final) else [],
            drawdown_percentiles=np.percentile(values['drawdown'], [5, 50, 95]).tolist() if len(final) else [],
            average_trades=float(np.mean(values['trades'])) if len(final) else None))
    prices = {r: dict(count=len(values), final_percentiles=np.percentile(values, [5, 50, 95]).tolist() if values else [],
        chart_sample=len(curves[r]), daily_percentiles=np.percentile(curves[r], [5, 50, 95], axis=0).tolist() if curves[r] else [])
        for r, values in price_groups.items()}
    result = dict(id=run_id, completed=count, target=config['paths'], config=config, prices=prices, strategies=rows,
        assumptions=['GBM with constant drift and volatility; no jumps or volatility clustering.',
            'One-minute GBM samples form five-minute OHLC; unsampled intraminute extrema are omitted.',
            'Synthetic constant volume, zero funding and mark price equal to synthetic spot.',
            'Original Freqtrade entries, exits, fees, precision and protections; no synthetic live orders.',
            'Drawdown uses native closed-trade equity. Price chart bands use at most 256 paths per regime; terminal statistics use every completed path.',
            'The single BTC pair permits one position at a time under native position rules.',
            'Probabilities are conditional on this synthetic model, not forecasts of real BTC.'])
    write_json(path / 'summary.json', result)
    return result


def run(run_id):
    path = directory(run_id)
    with FileLock(str(path / 'supervisor.lock'), timeout=0):
        if os.name == 'nt':
            import ctypes
            # Windows releases this process-owned sleep request when the worker exits.
            if not ctypes.windll.kernel32.SetThreadExecutionState(0x80000001):
                raise OSError('Unable to keep Windows awake during simulation.')
        config = read_json(path / 'config.json')
        current = read_json(path / 'state.json')
        current.update(status='running', owner=dict(pid=os.getpid(), created=psutil.Process().create_time()))
        started = time.monotonic()
        elapsed = current.get('elapsed_seconds', 0)
        db = connect_db(path)
        finished = {row[0] for row in db.execute('SELECT id FROM paths')}
        pending_ids = (i for i in range(config['paths']) if i not in finished)
        completed_before = len(finished)
        current['completed'] = len(finished)
        current['strategy_evaluations'] = len(finished) * 4
        current['failures'] = db.execute('SELECT COALESCE(SUM(failures), 0) FROM paths').fetchone()[0]
        try:
            with ProcessPoolExecutor(max_workers=config['workers'], initializer=initialize_worker, initargs=(run_id,)) as pool:
                pending = {}
                pausing = False
                while True:
                    pausing = read_json(path / 'control.json', {}).get('action') == 'pause'
                    while not pausing and len(pending) < config['workers']:
                        index = next(pending_ids, None)
                        if index is None:
                            break
                        pending[pool.submit(evaluate, index)] = index
                    if not pending:
                        break
                    done, _ = wait(pending, timeout=1, return_when=FIRST_COMPLETED)
                    for future in done:
                        pending.pop(future)
                        row = future.result()
                        errors = sum('error' in value for value in row['strategies'].values())
                        db.execute('INSERT OR IGNORE INTO paths VALUES (?, ?, ?)', (row['index'], json.dumps(row, allow_nan=False), errors))
                        db.commit()
                        current['completed'] += 1
                        current['strategy_evaluations'] = current['completed'] * 4
                        current['failures'] += errors
                        if all('error' in value for value in row['strategies'].values()):
                            raise RuntimeError('All four strategies failed on a path. Inspect the recorded errors before resuming.')
                        if current['completed'] & (current['completed'] - 1) == 0:
                            summarize(run_id)
                    duration = time.monotonic() - started
                    rate = (current['completed'] - completed_before) / duration if duration else 0
                    current.update(status='pausing' if pausing else 'running', elapsed_seconds=elapsed + duration,
                        paths_per_hour=rate * 3600, eta_seconds=(config['paths'] - current['completed']) / rate if rate else None,
                        message='Finishing in-flight paths.' if pausing else 'Native Freqtrade evaluates every generated path.')
                    write_json(path / 'state.json', current)
            current['status'] = 'completed' if current['completed'] == config['paths'] else 'paused'
            current['message'] = 'All paths evaluated.' if current['status'] == 'completed' else 'Paused. Resume keeps completed paths.'
        except Exception as exc:
            from server.jobs import redact
            current.update(status='failed', message=redact(f'{type(exc).__name__}: {exc}'))
        finally:
            db.close()
            current['elapsed_seconds'] = elapsed + time.monotonic() - started
            write_json(path / 'state.json', {**current, 'status': 'finalizing'})
            summarize(run_id)
            if current['status'] == 'completed' and config.get('publish_on_complete'):
                write_json(path / 'state.json', {**current, 'status': 'publishing'})
                try:
                    exported = _export_public(run_id)
                    current['publication'] = publish_git(exported['directory'])
                except Exception as exc:
                    from server.jobs import redact
                    current['publication'] = {'status': 'needs_attention', 'message': redact(str(exc))}
            write_json(path / 'state.json', current)


def export_public(run_id):
    path = directory(run_id)
    if state(run_id)['running']:
        raise ValueError('Pause the simulation and wait for active paths before saving a consistent repository snapshot.')
    with FileLock(str(path / 'supervisor.lock'), timeout=0):
        return _export_public(run_id)


def _export_public(run_id):
    import hashlib
    from scripts.export_results import public_bytes
    from server.catalog import settings
    path = directory(run_id)
    summary = summarize(run_id)
    output = ROOT / 'results' / 'monte-carlo' / run_id
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'summary.json', summary)
    progress = {k: v for k, v in state(run_id).items() if k not in ('owner', 'running')}
    if summary['completed'] == summary['target']:
        progress.update(status='completed', message='All paths evaluated.')
    write_json(output / 'progress.json', progress)
    with connect_db(path) as db:
        output_file, writer, part = None, None, -1
        try:
            for index, raw in db.execute('SELECT id, result FROM paths ORDER BY id'):
                if index // 10000 != part:
                    if output_file:
                        output_file.close()
                    part = index // 10000
                    output_file = gzip.open(output / f'outcomes-{part:04d}.csv.gz', 'wt', encoding='utf-8', newline='')
                    writer = csv.writer(output_file)
                    writer.writerow(['path', 'regime', 'asset_final', 'asset_minimum', 'asset_maximum', 'asset_drawdown', 'strategy', 'final_balance', 'trades', 'drawdown', 'wins', 'error'])
                row = json.loads(raw)
                for name, values in row['strategies'].items():
                    writer.writerow([index, row['regime'], *[row['asset'][k] for k in ('final', 'minimum', 'maximum', 'drawdown')], name,
                        *[values.get(k, '') for k in ('final_balance', 'trades', 'drawdown', 'wins')],
                        values.get('error', '').replace(str(ROOT), '<workspace>')])
        finally:
            if output_file:
                output_file.close()
    secrets = [str(value) for key, value in settings().items() if value and any(
        word in key for word in ('token', 'secret', 'password', 'chat_id', 'exchange_key'))]
    files = sorted(p for p in output.iterdir() if p.name != 'SHA256SUMS')
    for file in files:
        content = gzip.decompress(file.read_bytes()) if file.suffix == '.gz' else file.read_bytes()
        public_bytes(content.decode('utf-8'), secrets)
    (output / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files))
    return {'directory': output.relative_to(ROOT).as_posix(), 'completed': summary['completed'], 'target': summary['target']}


def publish_git(relative):
    """Publish only this run's generated files; never include unrelated working changes."""
    prefix = ['git', '-c', f'safe.directory={ROOT.as_posix()}']
    def git(*args):
        result = subprocess.run([*prefix, *args], cwd=ROOT, capture_output=True, text=True,
            timeout=180, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            env={**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'})
        if result.returncode:
            raise RuntimeError(f'Git {args[0]} failed. Results remain in {relative}; inspect Git authentication or remote changes before retrying.')
        return result.stdout.rstrip('\r\n')
    if git('branch', '--show-current') != 'main' or git('remote', 'get-url', 'origin') != 'https://github.com/Hibra999/freqmyass.git':
        return {'status': 'needs_attention', 'message': 'Results saved. Automatic push requires the expected main branch and repository.'}
    changes = git('status', '--porcelain', '--untracked-files=all')
    if any(not line[3:].replace('\\', '/').startswith(relative + '/') for line in changes.splitlines()):
        return {'status': 'needs_attention', 'message': 'Results saved. Unrelated working changes prevent automatic commit.'}
    if changes:
        git('add', '--', relative)
        git('commit', '--only', '-m', f'data: publish complete GBM run {Path(relative).name[:8]}', '--', relative)
    git('push', 'origin', 'main')
    return {'status': 'pushed', 'directory': relative, 'commit': git('rev-parse', 'HEAD')}


if __name__ == '__main__':
    run(sys.argv[1])
