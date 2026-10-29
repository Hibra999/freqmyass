"""QuantStats reports from Freqtrade's exported portfolio wallet."""
import hashlib
from pathlib import Path
import matplotlib
matplotlib.use('Agg')

import numpy as np
import pandas as pd

from server.catalog import RESULTS, RUNTIME, DATA, read_json, write_json


def result_path(file):
    path = (RESULTS / file).resolve()
    if not path.is_relative_to(RESULTS.resolve()) or path.suffix != '.zip' or not path.is_file():
        raise ValueError('Unknown backtest archive.')
    return path


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


def generate(file, name):
    from freqtrade.data.btanalysis import get_backtest_wallet_change, load_backtest_stats
    import quantstats as qs
    path = result_path(file)
    stats = load_backtest_stats(path)['strategy'][name]
    wallet = get_backtest_wallet_change(path, name)
    if wallet is None or wallet.empty:
        raise ValueError('This archive has no wallet history. Re-run with Freqtrade 2026.8 or newer.')
    initial = stats['starting_balance']
    # The engine records the final candle before its forced liquidation pass.
    wallet_last = (wallet.assign(quote=wallet['rate'] * wallet['balance'])
                   .groupby('date')['quote'].sum().sort_index().iloc[-1])
    delta = stats['final_balance'] - wallet_last
    if not np.isclose(delta, 0, rtol=1e-5, atol=0.01):
        forced_pnl = sum(t['profit_abs'] for t in stats['trades']
                         if t['exit_reason'] == 'force_exit' and t['close_timestamp'] == stats['backtest_end_ts'])
        if not np.isclose(delta, forced_pnl, rtol=1e-5, atol=0.01):
            raise ValueError('Wallet discrepancy is not explained by final force exits.')
        final_time = pd.to_datetime(wallet['date'], utc=True).max() + pd.Timedelta(microseconds=1)
        wallet = pd.concat([wallet, pd.DataFrame([dict(date=final_time, rate=1, balance=stats['final_balance'])])], ignore_index=True)
    daily, returns = wallet_returns(wallet, initial, stats['backtest_start'], stats['backtest_end'])
    final = float(daily.iloc[-1])
    expected = stats['final_balance']
    if not np.isclose(final, expected, rtol=1e-5, atol=0.01):
        raise ValueError(f'Wallet reconciliation failed: {final:.6f} versus Freqtrade {expected:.6f}.')
    report_id = hashlib.sha256(f'{file}:{name}'.encode()).hexdigest()[:24]
    directory = RUNTIME / 'reports'
    output = directory / f'{report_id}.html'
    benchmark = None
    # Freqtrade stats omit the exchange; our persisted run configuration is authoritative.
    job_id = Path(file).parts[0]
    config = read_json(RUNTIME / 'jobs' / f'{job_id}-{name}.config.json', {})
    exchange = config.get('exchange', {}).get('name', 'unknown')
    market = stats.get('trading_mode', 'spot')
    btc = DATA / exchange / ('futures/BTC_USDT_USDT-1d-futures.feather' if market == 'futures' else 'BTC_USDT-1d.feather')
    if btc.exists():
        candles = pd.read_feather(btc)
        prices = candles.set_index(pd.to_datetime(candles['date'], utc=True))['close']
        benchmark = prices.resample('D').last().pct_change()
        benchmark.index = benchmark.index.tz_localize(None)
        benchmark = benchmark.reindex(returns.index)
        if benchmark.isna().any():
            benchmark = None
        else:
            benchmark.name = 'BTC buy & hold'
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
        html_ready=html_ready, benchmark='BTC buy & hold' if benchmark is not None else None,
        basis='Freqtrade exported wallet plus verified final forced exits, daily UTC, 365 periods per year. Wallet equity, not a separate mark-to-market reconstruction.',
        equity=[dict(date=d.strftime('%Y-%m-%d'), value=float(v), drawdown=float(v / peak[i] - 1))
                for i, (d, v) in enumerate(daily.items())],
        monthly=[dict(year=d.year, month=d.month, value=v) for d, v in monthly.items()],
        yearly=[dict(year=d.year, value=v) for d, v in years.items()],
        trade_list=stats.get('trades', []), pair_results=stats.get('results_per_pair', [])))
    write_json(directory / f'{report_id}.json', record)
    return record


def summaries():
    return [{k: v for k, v in read_json(path).items() if k not in ('equity', 'trade_list', 'pair_results')}
            for path in sorted((RUNTIME / 'reports').glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True)]
