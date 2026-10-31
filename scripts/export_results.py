"""Publish the six validated campaigns without engine configs or strategy source."""
import csv
import gzip
import hashlib
import importlib.metadata
import io
import json
import math
from pathlib import Path
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
OUTPUT = ROOT / 'results'
CAMPAIGNS = (
    'b88ade95322347a28946830cfb82a686',
    '1fdbb07d09d849888cfe71b1512a8965',
    'fc403e362d5340159309ebd8c262636b',
    '68c89f456f5b4015be8958a90625d3b2',
    '878e825915b74d92babeb123cd8ff000',
    '76a0d9276e2248cd86275a0dbb9ca571',
)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def public_bytes(content, secrets):
    encoded = content.encode('utf-8')
    if any(value.encode('utf-8') in encoded for value in secrets):
        raise ValueError('Export contains a private setting.')
    if re.search(r'\b\d{8,12}:[A-Za-z0-9_-]{30,}|[A-Z]:[\\/]+Users[\\/]', content, re.I):
        raise ValueError('Export contains a token or a personal filesystem path.')
    return encoded


def export():
    settings = read(RUNTIME / 'settings.json')
    secrets = [str(value) for key, value in settings.items() if value and any(
        word in key for word in ('token', 'secret', 'password', 'chat_id', 'exchange_key'))]
    locks = read(ROOT / 'strategies.lock.json')
    revision = read(RUNTIME / 'inventory.json')['revision']
    reports = {read(path)['file'].split('/')[0]: read(path)
               for path in (RUNTIME / 'reports').glob('*.json')}
    rows = []
    OUTPUT.mkdir(exist_ok=True)
    for campaign in CAMPAIGNS:
        report = reports[campaign]
        job = read(RUNTIME / 'jobs' / f'{campaign}.json')
        assert job['status'] == 'completed', 'Only completed campaigns can be published.'
        assert len(report['trade_list']) == report['trades']
        assert math.isclose(report['initial'] + report['profit_abs'], report['final'], abs_tol=0.01)
        name = f"{report['exchange']}-{report['market']}-{report['strategy']}"
        directory = OUTPUT / name
        directory.mkdir(exist_ok=True)
        archive = RUNTIME / 'user_data' / 'backtest_results' / report['file']
        with ZipFile(archive) as z:
            result_name = archive.stem + '.json'
            native = json.loads(z.read(result_name))['strategy'][report['strategy']]
        assert native['total_trades'] == report['trades']
        assert math.isclose(native['final_balance'], report['final'], abs_tol=0.01)
        assert math.isclose(report['equity'][-1]['value'], report['final'], abs_tol=0.01)
        summary = {key: value for key, value in report.items()
                   if key not in ('id', 'file', 'equity', 'trade_list', 'pair_results')}
        summary['provenance'] = dict(
            campaign=campaign, dataset_repository='https://github.com/iterativv/NostalgiaForInfinityData',
            dataset_revision=revision, strategy_source=locks[report['strategy']],
            source_archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
            app_release='1.00', freqtrade_version='2026.8',
            quantstats_version=importlib.metadata.version('quantstats'),
            requested_pairs=job['payload']['pairs'],
            timeframe='5m', timestamp_timezone='UTC',
        )

        def write(filename, content, compress=False):
            data = public_bytes(content, secrets)
            (directory / filename).write_bytes(gzip.compress(data, mtime=0) if compress else data)

        write('summary.json', json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
        # The result member contains statistics and simulated trades, never the sibling config/source members.
        serialized = json.dumps(native, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        write('freqtrade-result.json.gz', serialized, compress=True)
        assert json.loads(gzip.decompress((directory / 'freqtrade-result.json.gz').read_bytes())) == native
        for key in ('equity', 'monthly', 'yearly'):
            buffer = io.StringIO(newline='')
            writer = csv.DictWriter(buffer, fieldnames=list(report[key][0]))
            writer.writeheader()
            writer.writerows(report[key])
            write(f'{key}.csv', buffer.getvalue())
        html = (RUNTIME / 'reports' / f"{report['id']}.html").read_text(encoding='utf-8')
        assert 'initial capital' in html and 'FreqMyAss' in html
        write('quantstats.html', html)
        rows.append({**summary, 'directory': name})

    text = '''# Published backtest results

Six completed full-history campaigns from release **1.00**. These are simulated historical results, not live trading records or forecasts. All begin with **1,000 USDT**, use **5m candles** and allow **three open positions**. Dates are UTC.

| Campaign / files | Pairs | Trades | Allocation | Final USDT | Return | Native max drawdown |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
'''
    for row in rows:
        allocation = 'Automatic' if row['stake_amount'] == 'unlimited' else f"{row['stake_amount']:g} USDT fixed"
        text += (f"| [{row['exchange']} {row['market']} · {row['strategy']}](./{row['directory']}/) "
                 f"| {row['processed_pairs']}/{row['dataset_pairs']} | {row['trades']:,} | {allocation} "
                 f"| {row['final']:,.2f} | {row['profit'] * 100:,.2f}% | {row['drawdown'] * 100:.2f}% |\n")
    text += '''
## Open the results

Synthetic CUDA experiments are published separately under [Monte Carlo](monte-carlo/README.md). Their completed counts and model assumptions are independent of these historical campaigns.

Each campaign contains:

- `quantstats.html`: complete QuantStats HTML with monthly heatmaps, annual returns, risk metrics, equity, drawdown and a BTC benchmark. Download the file and open it in a browser; GitHub displays HTML source.
- `summary.json`: metrics, warnings, allocation, strategy pins, the data revision and the exact selected pairs. Ratios such as profit, win rate and drawdown are fractions: multiply by 100 for percent.
- `equity.csv`, `monthly.csv`, `yearly.csv`: chart values for further analysis. Monthly and yearly `value` fields are compounded return fractions. Equity `value` is USDT.
- `freqtrade-result.json.gz`: the complete native strategy-result object, including every simulated trade and order, pair metrics, entry/exit statistics, parameters and native period breakdowns. Extract with gzip/7-Zip or Python `gzip.open(path, 'rt')` and `json.load`. This is a standalone result object, not a native import ZIP.

The original archive SHA-256 is recorded for provenance. Original archives stay local because they also contain private engine configurations and downloaded third-party strategy source. No credentials, databases, raw candles or strategy source are published here.

## Conditions and limitations

Spot histories run from 2024-01-01 16:40 through 2026-10-02 03:00. Futures end at 2026-09-01 17:25; strategy warmup determines the exact start. Individual pairs can cover shorter periods.

All dataset files were retained locally. Current exchange metadata excluded two Binance futures contracts (AERGO and SXP) and eleven KuCoin spot pairs (AMPL, DEGO, EOS, MKR, NWC, PLU, SXP, USDJ, VIDT, VRA and XEM). The published runs use the supported subset; selection is recorded in each summary.

Automatic compounding exceeded exchange stake limits in the initial futures attempts. The completed futures campaigns explicitly use fixed 330 USDT allocation. Compare strategies only with equivalent allocation and market assumptions.

The Binance NotAnotherSMAOffsetStrategyHO run contains a POND history gap before final settlement. The HTML and summary retain that warning. Curves come from Freqtrade's exported wallet with verified final liquidation; they are not an independent mark-to-market reconstruction. Incomplete prices can affect daily risk metrics.

Large compounded historical returns do not establish realistic liquidity, slippage or live profitability. The original short warmup in dip_catcher and recursive sensitivity in NotAnotherSMAOffsetStrategyHO remain documented in [VALIDATION.md](../VALIDATION.md).

Regenerate this snapshot locally with `.runtime\\env\\python.exe scripts\\export_results.py` after the six recorded campaigns exist. The exporter checks trade counts, final balances, compressed-data round trips and private settings before writing. Development smoke tests and failed attempts remain in local activity history.
'''
    (OUTPUT / 'README.md').write_bytes(public_bytes(text, secrets))
    files = sorted([OUTPUT / 'README.md', *[path for row in rows for path in (OUTPUT / row['directory']).iterdir() if path.is_file()]])
    manifest = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(OUTPUT).as_posix()}\n' for path in files)
    (OUTPUT / 'SHA256SUMS').write_text(manifest, encoding='utf-8')
    print(f'Published {len(rows)} campaigns, {sum(row["trades"] for row in rows):,} trades; {sum(p.stat().st_size for p in files) / 1024**2:.1f} MiB.')


if __name__ == '__main__':
    export()
