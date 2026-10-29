"""Bounded native analysis checks. These are diagnostics, not proof of strategy profitability."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.catalog import RUNTIME, STRATEGY_INFO, make_config, write_json
import subprocess
from datetime import datetime

output = RUNTIME / 'validation' / ('analysis-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
output.mkdir(parents=True, exist_ok=True)
results = []
for strategy in STRATEGY_INFO:
    name = strategy['name']
    futures = strategy['market'] == 'futures'
    pairs = [f'{coin}/USDT:USDT' if futures else f'{coin}/USDT' for coin in ['BTC','ETH','SOL']]
    config = make_config(name, pairs=pairs)
    config_path = output / f'{name}.config.json'
    write_json(config_path, config)
    for kind in ['recursive-analysis', 'lookahead-analysis']:
        if kind == 'lookahead-analysis':
            config['entry_pricing']['price_side'] = 'other'
            config['exit_pricing']['price_side'] = 'other'
            write_json(config_path, config)
        command = [sys.executable, '-m', 'freqtrade', kind, '--config', str(config_path),
                   '--datadir', config['datadir'], '--timerange', '20240101-20260101']
        if kind == 'recursive-analysis':
            command += ['--startup-candle', '30', '100', '248', '500', '1000']
        else:
            command += ['--minimum-trade-amount', '5', '--targeted-trade-amount', '10',
                        '--lookahead-analysis-exportfilename', str(output / f'{name}-lookahead.csv')]
        with (output / f'{name}-{kind}.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)
        verified = result.returncode == 0 and (kind != 'lookahead-analysis' or (output / f'{name}-lookahead.csv').exists())
        results.append(dict(strategy=name, kind=kind, exit_code=result.returncode, verified=verified))
        print(name, kind, result.returncode, flush=True)
write_json(RUNTIME / 'validation' / 'analysis-summary.json', dict(directory=str(output), results=results))
sys.exit(0 if all(item['verified'] for item in results) else 1)
