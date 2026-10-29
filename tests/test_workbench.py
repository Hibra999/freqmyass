import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from server.app import Research, app, SESSION
from server.catalog import make_config, settings
from server.reports import wallet_returns, result_path


def test_daily_returns_include_initial_capital_and_idle_days():
    wallet = pd.DataFrame({'date': ['2025-01-01T12:00:00Z', '2025-01-03T12:00:00Z'],
                           'rate': [1, 1], 'balance': [1100, 990]})
    equity, returns = wallet_returns(wallet, 1000, '2025-01-01', '2025-01-03')
    assert list(equity) == [1100, 1100, 990]
    assert returns.tolist() == pytest.approx([0.1, 0, -0.1])
    assert (1 + returns).prod() - 1 == pytest.approx(-0.01)


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


def test_default_config_is_simulated_and_preserves_strategy():
    config = make_config('dip_catcher', pairs=['BTC/USDT:USDT'])
    assert config['dry_run'] is True
    assert config['dry_run_wallet'] == 1000
    assert config['max_open_trades'] == 3
    assert config['trading_mode'] == 'futures'
    assert config['exchange']['key'] == ''
    assert config['telegram']['enabled'] is False
    assert 'stoploss' not in config
    assert 'startup_candle_count' not in config
