"""Prove the official V3 migration preserves previously exported smoke-test trades."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import math
import subprocess
from freqtrade.data.btanalysis import load_backtest_stats
from server.catalog import RESULTS, RUNTIME, make_config, read_json, write_json

evidence = []
for name in ['NASOSv4_SMA', 'NotAnotherSMAOffsetStrategyHO']:
    originals = []
    for path in (RUNTIME / 'jobs').glob('*.json'):
        if len(path.stem) != 32:
            continue
        job = read_json(path)
        if (job['kind'] == 'backtesting' and job['status'] == 'completed'
                and job['payload']['strategies'] == [name]
                and job['payload']['timerange'] == '20250101-20250301'):
            originals.append(job)
    baseline = sorted(originals, key=lambda j: j['created'])[0]
    before = load_backtest_stats(RESULTS / baseline['results'][0])['strategy'][name]
    config = make_config(name, pairs=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
    config_path = RUNTIME / 'validation' / f'{name}-migration.config.json'
    write_json(config_path, config)
    output = RUNTIME / 'validation' / f'{name}-migration'
    output.mkdir(exist_ok=True)
    with (output / 'backtest.log').open('w', encoding='utf-8') as log:
        subprocess.run([sys.executable, '-m', 'freqtrade', 'backtesting', '--config', str(config_path),
            '--datadir', config['datadir'], '--timerange', '20250101-20250301', '--export', 'trades',
            '--export-directory', str(output), '--cache', 'none', '--enable-protections'],
            check=True, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
    archive = max(output.glob('*.zip'), key=lambda p: p.stat().st_mtime)
    after = load_backtest_stats(archive)['strategy'][name]
    assert before['total_trades'] == after['total_trades']
    assert math.isclose(before['final_balance'], after['final_balance'], abs_tol=1e-8)
    for left, right in zip(before['trades'], after['trades'], strict=True):
        # V3 restores descriptive entry tags that the V2 adapter dropped; economics must match.
        for field in ['pair', 'open_timestamp', 'close_timestamp', 'exit_reason']:
            assert left[field] == right[field], (name, field)
        for field in ['profit_abs', 'amount', 'stake_amount', 'open_rate', 'close_rate']:
            assert math.isclose(left[field], right[field], rel_tol=1e-10, abs_tol=1e-8), (name, field)
    evidence.append(dict(strategy=name, matched_trades=after['total_trades'], matched_final_balance=True))
    print(name, 'trade-for-trade parity passed', flush=True)
write_json(RUNTIME / 'validation' / 'migration-parity.json', evidence)
