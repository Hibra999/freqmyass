import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from server.app import Research, app, SESSION
from server.catalog import make_config, settings
from server.reports import wallet_returns, result_path, reconcile_wallet, benchmark_returns


def test_daily_returns_include_initial_capital_and_idle_days():
    wallet = pd.DataFrame({'date': ['2025-01-01T12:00:00Z', '2025-01-03T12:00:00Z'],
                           'rate': [1, 1], 'balance': [1100, 990]})
    equity, returns = wallet_returns(wallet, 1000, '2025-01-01', '2025-01-03')
    assert list(equity) == [1100, 1100, 990]
    assert returns.tolist() == pytest.approx([0.1, 0, -0.1])
    assert (1 + returns).prod() - 1 == pytest.approx(-0.01)


def test_final_spot_liquidation_accounts_for_marked_coins_and_fees():
    wallet = pd.DataFrame({'date': ['2025-01-03T12:00:00Z'] * 2, 'currency': ['USDT', 'COIN'],
                           'rate': [1, 110], 'balance': [500, 5]})
    stats = dict(final_balance=1048.95, trading_mode='spot', backtest_end_ts=1,
                 trades=[dict(exit_reason='force_exit', close_timestamp=1, profit_abs=48.95,
                              stake_amount=500, amount=5, pair='COIN/USDT')])
    assert reconcile_wallet(wallet, stats).iloc[-1]['balance'] == 1048.95
    stats['final_balance'] = 999
    with pytest.raises(ValueError, match='not explained'):
        reconcile_wallet(wallet, stats)


def test_benchmark_does_not_use_prices_after_backtest_end():
    candles = pd.DataFrame({'date': ['2025-01-01T23:55:00Z', '2025-01-02T12:00:00Z', '2025-01-02T23:55:00Z'],
                            'close': [100, 110, 999]})
    returns = benchmark_returns(candles, '2025-01-02T00:00:00Z', '2025-01-02T12:00:00Z', pd.DatetimeIndex(['2025-01-02']))
    assert returns.iloc[0] == pytest.approx(0.1)


def test_final_futures_liquidation_only_adds_net_profit():
    wallet = pd.DataFrame({'date': ['2025-01-03T12:00:00Z'], 'currency': ['USDT'], 'rate': [1], 'balance': [1000]})
    stats = dict(final_balance=1048.95, trading_mode='futures', backtest_end_ts=1,
                 trades=[dict(exit_reason='force_exit', close_timestamp=1, profit_abs=48.95)])
    assert reconcile_wallet(wallet, stats).iloc[-1]['balance'] == 1048.95


def test_markets_and_dates_rejected_before_process_launch():
    with pytest.raises(ValidationError):
        Research(strategies=['NASOSv4_SMA', 'dip_catcher'])
    with pytest.raises(ValidationError):
        Research(strategies=['dip_catcher'], exchange='kucoin')
    with pytest.raises(ValidationError):
        Research(timerange='20250230-20250301')
    with pytest.raises(ValidationError):
        Research(capital=float('nan'))
    with pytest.raises(ValidationError):
        Research(strategies=['../../untrusted'])


def test_result_download_cannot_escape_results():
    with pytest.raises(ValueError):
        result_path('../../settings.json')


def test_market_compatibility_reports_every_exclusion():
    from server.eligibility import classify_pairs
    result = classify_pairs(['A', 'B', 'C'], {'A': {}, 'B': {}}, {'A': {}}, 'futures')
    assert result['pairs'] == ['A']
    assert [item['pair'] for item in result['excluded']] == ['B', 'C']
    assert result['total'] == 3


def test_existing_live_engine_cannot_masquerade_as_simulation(monkeypatch):
    from types import SimpleNamespace
    from server import app as module
    monkeypatch.setattr(module, 'ENGINES', {'trading': {'process': SimpleNamespace(poll=lambda: None)}})
    monkeypatch.setattr(module, 'read_json', lambda _: {'dry_run': False})
    client = TestClient(app)
    client.cookies.set('fma_session', SESSION)
    response = client.post('/workbench/engines/trading', json={'live': False}, headers={'X-FMA-Request': '1'})
    assert response.status_code == 409


def test_close_engine_pauses_entries_and_refuses_unmanaged_positions(monkeypatch):
    from types import SimpleNamespace
    from server import app as module
    calls = []
    process = SimpleNamespace(poll=lambda: None, terminate=lambda: calls.append('terminate'))
    monkeypatch.setattr(module, 'ENGINES', {'trading': {'process': process, 'port': 8082}})

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, path, **kwargs):
            calls.append(path)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'access_token': 'test'})

        async def get(self, path, **kwargs):
            calls.append(path)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: [{'trade_id': 1}])

    monkeypatch.setattr(module.httpx, 'AsyncClient', Client)
    client = TestClient(app)
    client.cookies.set('fma_session', SESSION)
    response = client.post('/workbench/engines/trading/close', json={}, headers={'X-FMA-Request': '1'})
    assert response.status_code == 409
    assert calls == ['/token/login', '/stopbuy', '/status']


def test_cancelling_queued_job_never_launches_it(monkeypatch, tmp_path):
    from server import jobs
    from server.catalog import write_json
    monkeypatch.setattr(jobs, 'RUNTIME', tmp_path)
    path = tmp_path / 'jobs' / 'test.json'
    write_json(path, {'status': 'queued'})
    assert jobs.cancel('test')['status'] == 'cancelled'
    jobs.execute('test')
    assert jobs.read_json(path)['status'] == 'cancelled'


def test_local_api_requires_cookie_and_protection_header():
    client = TestClient(app)
    assert client.get('/workbench/status').status_code == 401
    client.cookies.set('fma_session', SESSION)
    assert client.post('/workbench/settings', json={'capital': 2000}).status_code == 403
    assert client.get('/workbench/status', headers={'Origin': 'https://evil.example'}).status_code == 403
    response = client.get('/workbench/status')
    assert response.status_code == 200
    assert settings()['api_password'] not in response.text
    assert 'telegram_token' not in response.text


def test_live_mode_requires_explicit_phrase_and_credentials():
    client = TestClient(app)
    client.cookies.set('fma_session', SESSION)
    response = client.post('/workbench/engines/trading', json={'live': True}, headers={'X-FMA-Request': '1'})
    assert response.status_code == 422
    assert 'activation phrase' in response.text


def test_default_config_is_simulated_and_preserves_strategy(monkeypatch):
    monkeypatch.setattr('server.catalog.available_pairs', lambda *args: ['BTC/USDT:USDT'])
    config = make_config('dip_catcher', pairs=['BTC/USDT:USDT'])
    assert config['dry_run'] is True
    assert config['dry_run_wallet'] == 1000
    assert config['max_open_trades'] == 3
    assert config['trading_mode'] == 'futures'
    assert config['exchange']['key'] == ''
    assert config['telegram']['enabled'] is False
    assert 'stoploss' not in config
    assert 'startup_candle_count' not in config
