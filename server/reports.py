"""QuantStats reports from Freqtrade's exported portfolio wallet."""
import hashlib
import json
import os
from pathlib import Path
from zipfile import ZipFile
import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

from server.catalog import RESULTS, RUNTIME, DATA, read_json, write_json, available_pairs

SUMMARY_CACHE = {}


def result_path(file):
    path = (RESULTS / file).resolve()
    if not path.is_relative_to(RESULTS.resolve()) or path.suffix != '.zip' or not path.is_file():
        raise ValueError('Unknown backtest archive.')
    return path


def publish_to_engine_history(path):
    """Expose the same archive to the official explorer without copying large wallet data."""
    if path.parent == RESULTS:
        return
    for original in (path, path.with_suffix('.meta.json')):
        destination = RESULTS / original.name
        if original.exists() and not destination.exists():
            os.link(original, destination)


def wallet_returns(wallet, initial, start, end):
    if initial <= 0:
        raise ValueError('Initial capital must be positive.')
    wallet = wallet.copy()
    wallet['date'] = pd.to_datetime(wallet['date'], utc=True)
    wallet['quote'] = wallet['rate'] * wallet['balance']
    values = wallet.groupby('date')['quote'].sum().sort_index()
    first = pd.Timestamp(start)
    first = first.tz_localize('UTC') if first.tzinfo is None else first.tz_convert('UTC')
    last = pd.Timestamp(end)
    last = last.tz_localize('UTC') if last.tzinfo is None else last.tz_convert('UTC')
    days = pd.date_range(first.normalize(), last.normalize(), freq='D')
    daily = values.resample('D').last().reindex(days).ffill().fillna(initial)
    baseline = pd.Series([initial], index=[days[0] - pd.Timedelta(days=1)])
    equity = pd.concat([baseline, daily])
    if (equity <= 0).any() or not np.isfinite(equity).all():
        raise ValueError('Invalid wallet values; cannot calculate reliable portfolio returns.')
    returns = equity.pct_change().iloc[1:]
    returns.index = returns.index.tz_localize(None)
    return daily, returns


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value


def reconcile_wallet(wallet, stats):
    wallet = wallet.copy()
    final_rows = wallet[pd.to_datetime(wallet['date'], utc=True) == pd.to_datetime(wallet['date'], utc=True).max()]
    last_value = float((final_rows['rate'] * final_rows['balance']).sum())
    delta = stats['final_balance'] - last_value
    if np.isclose(delta, 0, rtol=1e-5, atol=0.01):
        return wallet
    adjustment = 0.0
    for trade in stats['trades']:
        if trade['exit_reason'] != 'force_exit' or trade['close_timestamp'] != stats['backtest_end_ts']:
            continue
        adjustment += trade['profit_abs']
        if stats.get('trading_mode', 'spot') == 'spot':
            coin = trade['pair'].split('/')[0]
            row = final_rows[final_rows['currency'] == coin]
            if len(row) != 1:
                raise ValueError('Cannot reconcile a final spot position without its wallet rate.')
            # Spot wallet values the coin before liquidation and before finalizing both fees.
            adjustment += trade['stake_amount'] - trade['amount'] * float(row.iloc[0]['rate'])
    if not np.isclose(delta, adjustment, rtol=1e-5, atol=0.01):
        raise ValueError('Wallet discrepancy is not explained by final position liquidation and fees.')
    final_time = pd.to_datetime(wallet['date'], utc=True).max() + pd.Timedelta(microseconds=1)
    return pd.concat([wallet, pd.DataFrame([dict(date=final_time, rate=1, balance=stats['final_balance'])])], ignore_index=True)


def generate(file, name):
    from freqtrade.data.btanalysis import get_backtest_wallet_change, load_backtest_stats
    import quantstats as qs
    path = result_path(file)
    stats = load_backtest_stats(path)['strategy'][name]
    wallet = get_backtest_wallet_change(path, name)
    if wallet is None or wallet.empty:
        raise ValueError('This archive has no wallet history. Re-run with Freqtrade 2026.8 or newer.')
    initial = stats['starting_balance']
    wallet = reconcile_wallet(wallet, stats)
    daily, returns = wallet_returns(wallet, initial, stats['backtest_start'], stats['backtest_end'])
    final = float(daily.iloc[-1])
    expected = stats['final_balance']
    if not np.isclose(final, expected, rtol=1e-5, atol=0.01):
        raise ValueError(f'Wallet reconciliation failed: {final:.6f} versus Freqtrade {expected:.6f}.')
    report_id = hashlib.sha256(f'{file}:{name}'.encode()).hexdigest()[:24]
    directory = RUNTIME / 'reports'
    output = directory / f'{report_id}.html'
    benchmark = None
    with ZipFile(path) as archive:
        config = json.loads(archive.read(f'{path.stem}_config.json'))
    exchange = config.get('exchange', {}).get('name', 'unknown')
    market = stats.get('trading_mode', 'spot')
    btc = DATA / exchange / ('futures/BTC_USDT_USDT-5m-futures.feather' if market == 'futures' else 'BTC_USDT-5m.feather')
    if btc.exists():
        candles = pd.read_feather(btc)
        benchmark = benchmark_returns(candles, stats['backtest_start'], stats['backtest_end'], returns.index)
    html_ready = len(returns) >= 2 and bool(returns.abs().sum())
    if html_ready:
        qs.reports.html(returns, benchmark=benchmark, output=str(output),
                        title=f'{name} · FreqMyAss', periods_per_year=365, download_filename=output.name)
    monthly = returns.resample('ME').apply(lambda s: (1 + s).prod() - 1)
    years = returns.resample('YE').apply(lambda s: (1 + s).prod() - 1)
    peak = pd.concat([pd.Series([initial]), daily.reset_index(drop=True)]).cummax().iloc[1:].to_numpy()
    record = clean(dict(id=report_id, file=file, strategy=name, initial=initial, final=final,
        start=stats['backtest_start'], end=stats['backtest_end'], exchange=exchange, market=market,
        profit=stats['profit_total'], profit_abs=stats['profit_total_abs'],
        trades=stats['total_trades'], winrate=stats.get('winrate'),
        drawdown=stats.get('max_drawdown_account'), sharpe=stats.get('sharpe'),
        sortino=stats.get('sortino'), profit_factor=stats.get('profit_factor'),
        html_ready=html_ready, benchmark='BTC price (no fees)' if benchmark is not None else None,
        basis='Freqtrade exported wallet plus verified final forced exits, daily UTC, 365 periods per year. Wallet equity, not a separate mark-to-market reconstruction.',
        equity=[dict(date=d.strftime('%Y-%m-%d'), value=float(v), drawdown=float(v / peak[i] - 1))
                for i, (d, v) in enumerate(daily.items())],
        monthly=[dict(year=d.year, month=d.month, value=v) for d, v in monthly.items()],
        yearly=[dict(year=d.year, value=v) for d, v in years.items()],
        requested_pairs=len(config.get('exchange', {}).get('pair_whitelist', [])),
        dataset_pairs=len(available_pairs(exchange, market)),
        processed_pairs=len(stats.get('pairlist', [])),
        skipped_pairs=sorted(set(config.get('exchange', {}).get('pair_whitelist', [])) - set(stats.get('pairlist', []))),
        trade_list=stats.get('trades', []), pair_results=stats.get('results_per_pair', [])))
    write_json(directory / f'{report_id}.json', record)
    publish_to_engine_history(path)
    return record


def summaries():
    result = []
    for path in sorted((RUNTIME / 'reports').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        modified = path.stat().st_mtime_ns
        if path not in SUMMARY_CACHE or SUMMARY_CACHE[path][0] != modified:
            SUMMARY_CACHE[path] = (modified, {k: v for k, v in read_json(path).items()
                if k not in ('equity', 'trade_list', 'pair_results')})
        result.append(SUMMARY_CACHE[path][1])
    return result


def benchmark_returns(candles, start, end, index):
    prices = candles.set_index(pd.to_datetime(candles['date'], utc=True))['close'].sort_index()
    first, last = pd.to_datetime(start, utc=True), pd.to_datetime(end, utc=True)
    previous = prices[prices.index < first]
    if previous.empty or prices.index.max() < last:
        return None
    # Truncate before daily resampling: a partial final day must not see later candles.
    daily = prices[(prices.index >= first) & (prices.index <= last)].resample('D').last()
    daily.index = daily.index.tz_localize(None)
    daily = daily.reindex(index)
    if daily.isna().any():
        return None
    values = pd.concat([pd.Series([previous.iloc[-1]], index=[index[0] - pd.Timedelta(days=1)]), daily])
    result = values.pct_change().iloc[1:]
    result.name = 'BTC price (no fees)'
    return result
