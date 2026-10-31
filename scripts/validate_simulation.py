"""Exercise CUDA, native strategies, pause/resume and duplicate-free checkpoints."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.app import SimulationInput
from server import simulations


def wait_for(run_id, predicate, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = simulations.state(run_id)
        if state['status'] in ('failed', 'interrupted'):
            raise AssertionError(state['message'])
        if predicate(state):
            return state
        time.sleep(1)
    raise TimeoutError('Simulation verification exceeded its time budget; inspect its saved state.')


def main():
    payload = SimulationInput(paths=12, days=7, workers=2, publish_on_complete=False).model_dump()
    payload['purpose'] = 'validation'
    run_id = simulations.create(payload)['id']
    print(f'CUDA/native validation run {run_id}', flush=True)
    wait_for(run_id, lambda s: s['completed'] >= 2)
    simulations.control(run_id, 'pause')
    paused = wait_for(run_id, lambda s: s['status'] in ('paused', 'completed'))
    assert paused['completed'] < 12, 'Pause should stop dispatching new paths.'
    with sqlite3.connect(simulations.directory(run_id) / 'outcomes.sqlite') as db:
        before = dict(db.execute('SELECT id, result FROM paths'))
    simulations.control(run_id, 'resume')
    done = wait_for(run_id, lambda s: s['status'] == 'completed')
    assert done['completed'] == 12 and done['strategy_evaluations'] == 48
    assert done['failures'] == 0
    with sqlite3.connect(simulations.directory(run_id) / 'outcomes.sqlite') as db:
        after = dict(db.execute('SELECT id, result FROM paths'))
    assert set(after) == set(range(12))
    assert all(after[key] == value for key, value in before.items())
    summary = json.loads((simulations.directory(run_id) / 'summary.json').read_text())
    assert all(p['count'] == 4 for p in summary['prices'].values())
    assert len(summary['strategies']) == 12
    assert sum(row['valid'] for row in summary['strategies']) == 48
    assert any(row['average_trades'] > 0 for row in summary['strategies'])
    simulations.initialize_worker(run_id)
    first = simulations.evaluate(0)
    simulations.evaluate(1)
    repeated = simulations.evaluate(0)
    assert first == repeated == json.loads(after[0]), 'Path results must not depend on worker or prior path state.'
    worker = simulations.CONTEXT['path']
    for market, names in simulations.GROUPS:
        target = simulations.directory(run_id) / f'cli-parity-{market}'
        target.mkdir(exist_ok=True)
        command = [sys.executable, '-m', 'freqtrade', 'backtesting', '--config', str(worker / f'{market}.json'),
            '--datadir', str(worker), '--strategy-list', *names, '--timerange', '20250101-20250108',
            '--strategy-path', str(simulations.directory(run_id) / 'strategies'),
            '--enable-protections', '--cache', 'none', '--export', 'trades', '--export-directory', str(target)]
        with (target / 'validation.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        archives = list(target.glob('*.zip'))
        assert archives, 'Native CLI must produce an archive, not only exit successfully.'
        with ZipFile(archives[-1]) as archive:
            native = json.loads(archive.read(archives[-1].stem + '.json'))['strategy']
        for name in names:
            expected = first['strategies'][name]
            assert native[name]['total_trades'] == expected['trades']
            assert abs(native[name]['final_balance'] - expected['final_balance']) < 1e-6
            assert abs(native[name]['max_drawdown_account'] - expected['drawdown']) < 1e-9
    print('CUDA + 48 native evaluations + pause/resume + independent paths + CLI parity passed.', flush=True)


if __name__ == '__main__':
    main()
