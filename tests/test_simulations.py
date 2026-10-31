import json
import math

import numpy as np
import pytest
from pydantic import ValidationError

from server.app import SimulationInput
from server import simulations
from server.catalog import write_json


def config(**changes):
    return dict(seed=42, days=2, warmup_days=14, substeps=5, drifts=[-0.3, 0, 0.3],
                volatility=0.5, volume=100, calibration={'initial_price': 100}, **changes)


def test_gbm_starts_at_initial_price_after_warmup_and_preserves_ohlc():
    params = config()
    frame, regime, asset, daily = simulations.candles(params, 1)
    active = frame[frame.date >= '2025-01-01']
    assert len(active) == 2 * 288
    assert active.iloc[0]['open'] == pytest.approx(100)
    assert regime == 'neutral'
    assert len(daily) == 3
    assert (frame.high >= frame[['open', 'close']].max(axis=1)).all()
    assert (frame.low <= frame[['open', 'close']].min(axis=1)).all()
    assert (frame.low > 0).all()
    assert asset['final'] == frame.iloc[-1]['close']
    again = simulations.candles(params, 1)[0]
    assert frame.equals(again)
    assert not frame.equals(simulations.candles(params, 4)[0])


def test_zero_volatility_matches_analytic_gbm_limit():
    params = config()
    params['volatility'] = 0
    frame, _, asset, _ = simulations.candles(params, 2)
    assert asset['final'] == pytest.approx(100 * math.exp(0.3 * 2 / 365))
    assert asset['drawdown'] == 0


def test_terminal_log_returns_match_gbm_analytic_moments():
    params = config()
    params.update(days=30, warmup_days=0, substeps=1, drifts=[0, 0, 0])
    returns = np.array([math.log(simulations.candles(params, i)[2]['final'] / 100) for i in range(512)])
    variance = params['volatility']**2 * 30 / 365
    assert abs(returns.mean() + variance / 2) < 5 * math.sqrt(variance / len(returns))
    assert returns.var(ddof=1) == pytest.approx(variance, rel=0.2)


def test_cuda_gbm_is_positive_and_reproducible_when_available():
    cp = pytest.importorskip('cupy')
    if cp.cuda.runtime.getDeviceCount() == 0:
        pytest.skip('No CUDA device')
    params = config(backend='cuda')
    first = simulations.candles(params, 2)
    second = simulations.candles(params, 2)
    assert first[0].equals(second[0])
    assert first[2] == second[2]
    assert np.isfinite(first[0].close).all()
    params['volatility'] = 0
    assert simulations.candles(params, 2)[2]['final'] == pytest.approx(100 * math.exp(0.3 * 2 / 365))


def test_simulation_limits_prevent_invalid_numeric_models():
    assert SimulationInput().paths == 1000000
    assert SimulationInput().days == 365
    for values in ({'paths': 1000001}, {'workers': 33}, {'drifts': [0.3, 0, -0.3]},
                   {'drifts': [0, float('nan'), 1]}, {'stake_amount': -1}, {'volatility': 0}):
        with pytest.raises(ValidationError):
            SimulationInput(**values)


def test_summary_counts_failed_and_zero_trade_outcomes_separately(monkeypatch, tmp_path):
    monkeypatch.setattr(simulations, 'BASE', tmp_path)
    run_id = 'a' * 32
    path = tmp_path / run_id
    write_json(path / 'config.json', {'paths': 10, 'capital': 1000})
    with simulations.connect_db(path) as db:
        for index, result in enumerate([
            {'final_balance': 900, 'drawdown': 0.1, 'trades': 2},
            {'final_balance': 1000, 'drawdown': 0, 'trades': 0}, {'error': 'Native failure'},
        ]):
            row = dict(regime='neutral', asset={'final': 100}, daily=[100, 100], strategies={'Strategy': result})
            db.execute('INSERT INTO paths VALUES (?, ?, ?)', (index, json.dumps(row), int('error' in result)))
        db.commit()
    summary = simulations.summarize(run_id)
    result = summary['strategies'][0]
    assert summary['completed'] == 3
    assert result['valid'] == 2 and result['failed'] == 1
    assert result['probability_loss'] == 0.5
    assert result['probability_no_trades'] == 0.5
    assert summary['prices']['neutral']['chart_sample'] == 3
    with pytest.raises(ValueError):
        simulations.directory('../outside')


def test_automatic_publication_refuses_unrelated_changes_and_limits_commit_paths(monkeypatch):
    from types import SimpleNamespace
    relative = 'results/monte-carlo/' + 'a' * 32
    calls = []
    changes = ' M unrelated.py\n'
    def command(args, **kwargs):
        operation = args[3]
        calls.append(args[3:])
        output = {'branch': 'main\n', 'remote': 'https://github.com/Hibra999/freqmyass.git\n',
                  'status': changes, 'rev-parse': 'abc123\n'}.get(operation, '')
        return SimpleNamespace(returncode=0, stdout=output)
    monkeypatch.setattr(simulations.subprocess, 'run', command)
    assert simulations.publish_git(relative)['status'] == 'needs_attention'
    assert not any(row[0] in ('add', 'commit', 'push') for row in calls)
    changes = f' M {relative}/summary.json\n'
    calls.clear()
    assert simulations.publish_git(relative)['status'] == 'pushed'
    assert next(row for row in calls if row[0] == 'commit')[-2:] == ['--', relative]
    assert next(row for row in calls if row[0] == 'push') == ['push', 'origin', 'main']


def test_public_snapshot_preserves_counts_checksums_and_portable_git_path(monkeypatch, tmp_path):
    import csv
    import gzip
    import hashlib
    from server import catalog
    monkeypatch.setattr(simulations, 'ROOT', tmp_path)
    monkeypatch.setattr(simulations, 'BASE', tmp_path / 'private')
    monkeypatch.setattr(catalog, 'settings', lambda: {'api_password': 'private-test-secret'})
    run_id = 'b' * 32
    path = simulations.BASE / run_id
    write_json(path / 'config.json', {'paths': 1000000, 'capital': 1000})
    write_json(path / 'state.json', {'status': 'paused', 'completed': 1, 'target': 1000000})
    row = dict(regime='bear', asset=dict(final=90, minimum=80, maximum=110, drawdown=0.2),
               daily=[100, 90], strategies={'Strategy': dict(final_balance=950, trades=1, drawdown=0.05, wins=0)})
    with simulations.connect_db(path) as db:
        db.execute('INSERT INTO paths VALUES (?, ?, ?)', (0, json.dumps(row), 0))
        db.commit()
    result = simulations.export_public(run_id)
    assert result == dict(directory=f'results/monte-carlo/{run_id}', completed=1, target=1000000)
    output = tmp_path / result['directory']
    with gzip.open(output / 'outcomes-0000.csv.gz', 'rt') as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 1 and rows[0]['asset_minimum'] == '80' and rows[0]['final_balance'] == '950'
    for line in (output / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ')
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
