"""Loopback-only workbench. Trading decisions stay inside Freqtrade."""
from contextlib import asynccontextmanager
from datetime import datetime
import importlib.metadata
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from server.catalog import ROOT, RUNTIME, DATA, STRATEGIES, STRATEGY_INFO, USER_DATA, RESULTS, initialize, settings, read_json, write_json, make_config, strategy, available_pairs
from server import jobs, reports, simulations
from server.telegram_menu import COMMANDS

initialize()
SESSION = secrets.token_urlsafe(40)
ENGINES = {}
ENGINE_LOCK = threading.RLock()


@asynccontextmanager
async def lifespan(app):
    jobs.recover_jobs()
    yield
    # Do not orphan processes on a graceful shutdown. Freqtrade persists trades in its own database.
    for engine in ENGINES.values():
        if engine['process'].poll() is None:
            engine['process'].terminate()
            try:
                engine['process'].wait(timeout=15)
            except subprocess.TimeoutExpired:
                engine['process'].kill()


app = FastAPI(title='FreqMyAss Workbench', lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])


@app.middleware('http')
async def protect_local_session(request: Request, call_next):
    if request.url.path.startswith('/workbench'):
        if not secrets.compare_digest(request.cookies.get('fma_session', ''), SESSION):
            return JSONResponse({'detail': 'Open the application first to establish a local session.'}, status_code=401)
        origin = request.headers.get('origin')
        if origin and origin not in ('http://127.0.0.1:8765', 'http://localhost:8765', 'http://127.0.0.1:3000'):
            return JSONResponse({'detail': 'Cross-origin requests are not allowed.'}, status_code=403)
        if request.method not in ('GET', 'HEAD') and request.headers.get('x-fma-request') != '1':
            return JSONResponse({'detail': 'Missing request protection header.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.path.startswith('/workbench'):
        response.headers['Cache-Control'] = 'no-store'
    return response


class Research(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['backtesting', 'hyperopt', 'lookahead-analysis', 'recursive-analysis'] = 'backtesting'
    strategies: list[str] = Field(default=['NASOSv4_SMA'], min_length=1, max_length=4)
    exchange: Literal['binance', 'kucoin'] = 'binance'
    capital: float = Field(default=1000, gt=0, le=1e9, allow_inf_nan=False)
    max_open_trades: int = Field(default=3, ge=1, le=100)
    stake_amount: float | Literal['unlimited'] = 'unlimited'
    timerange: str = ''
    pairs: list[str] | None = Field(default=None, max_length=1000)
    epochs: int = Field(default=100, ge=1, le=10000)
    workers: int = Field(default=1, ge=1, le=8)
    loss: Literal['SharpeHyperOptLossDaily', 'SortinoHyperOptLossDaily', 'CalmarHyperOptLoss', 'ProfitDrawDownHyperOptLoss'] = 'SharpeHyperOptLossDaily'
    spaces: list[Literal['buy', 'sell', 'roi', 'stoploss', 'trailing', 'protection']] = ['buy', 'sell']
    freqai_model: str | None = None
    freqai_config: dict | None = None

    @field_validator('stake_amount')
    @classmethod
    def valid_stake(cls, value):
        if value != 'unlimited' and (not math.isfinite(value) or value <= 0):
            raise ValueError('Fixed stake must be a positive finite USDT amount.')
        return value

    @field_validator('timerange')
    @classmethod
    def valid_range(cls, value):
        if value:
            if not re.fullmatch(r'\d{8}-\d{8}', value):
                raise ValueError('Use YYYYMMDD-YYYYMMDD or leave blank for all available history.')
            start, end = [datetime.strptime(x, '%Y%m%d') for x in value.split('-')]
            if start >= end:
                raise ValueError('End date must be after start date.')
        return value

    @field_validator('strategies')
    @classmethod
    def known_strategies(cls, names):
        for name in names:
            strategy(name)
        if len(set(names)) != len(names):
            raise ValueError('Duplicate strategy.')
        return names

    @model_validator(mode='after')
    def validate_profile(self):
        markets = {strategy(name)['market'] for name in self.strategies}
        if len(markets) != 1:
            raise ValueError('Run spot and futures as separate campaigns.')
        if self.exchange == 'kucoin' and 'futures' in markets:
            raise ValueError('No KuCoin futures candles exist in this dataset.')
        if self.freqai_model and (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,100}', self.freqai_model) or not self.freqai_config):
            raise ValueError('FreqAI needs a model name and complete FreqAI configuration.')
        return self


class Trading(Research):
    live: bool = False
    confirmation: str = ''


class SettingsInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    capital: float = Field(default=1000, gt=0, le=1e9, allow_inf_nan=False)
    max_open_trades: int = Field(default=3, ge=1, le=100)
    telegram_token: str | None = Field(default=None, max_length=200)
    telegram_chat_id: str | None = Field(default=None, max_length=50)
    exchange_key: str | None = Field(default=None, max_length=500)
    exchange_secret: str | None = Field(default=None, max_length=500)
    exchange_password: str | None = Field(default=None, max_length=500)
    credential_exchange: Literal['binance', 'kucoin'] = 'binance'


def engine_state():
    return {key: {'running': value['process'].poll() is None, 'pid': value['process'].pid,
                  'mode': value['mode'], 'strategy': value['strategy'], 'port': value['port']}
            for key, value in ENGINES.items()}


@app.get('/workbench/status')
def status():
    s = settings()
    engines = engine_state()
    telegram = read_json(RUNTIME / 'trading.json', {}).get('telegram', {})
    version_file = ROOT / 'VERSION'
    return dict(app_version=version_file.read_text(encoding='utf-8').strip() if version_file.exists() else 'development',
                engine_version=importlib.metadata.version('freqtrade'),
                quantstats_version=importlib.metadata.version('quantstats'), engines=engines,
                strategies=[{**item, 'installed': (STRATEGIES / f"{item['name']}.py").exists()}
                            for item in STRATEGY_INFO],
                data_ready=bool(available_pairs('binance', 'spot')),
                datasets=[dict(exchange=e, market=m, pairs=len(available_pairs(e, m)))
                          for e, m in [('binance', 'spot'), ('binance', 'futures'), ('kucoin', 'spot')]],
                capital=s['capital'], max_open_trades=s['max_open_trades'],
                telegram_ready=bool(s['telegram_token'] and s['telegram_chat_id']),
                telegram_engine_running=bool(engines.get('trading', {}).get('running')
                    and telegram.get('enabled') and telegram.get('token') == s['telegram_token']
                    and str(telegram.get('chat_id')) == str(s['telegram_chat_id'])),
                exchange_ready=bool(s['exchange_key'] and s['exchange_secret']),
                credential_exchange=s.get('credential_exchange', 'binance'),
                jobs=jobs.list_jobs(), reports=reports.summaries())


@app.post('/workbench/settings')
def save_settings(body: SettingsInput):
    s = settings()
    s.update(body.model_dump(exclude_none=True))
    write_json(RUNTIME / 'settings.json', s)
    return {'saved': True}


@app.get('/workbench/data')
def data_inventory():
    return read_json(RUNTIME / 'inventory.json', {'files': [], 'count': 0, 'bytes': 0})


class SimulationInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paths: int = Field(default=1000000, ge=1, le=1000000)
    days: int = Field(default=365, ge=1, le=365)
    workers: int = Field(default=16, ge=1, le=16)
    seed: int = Field(default=20261030, ge=0, le=2**32 - 1)
    capital: float = Field(default=1000, gt=0, le=1e9, allow_inf_nan=False)
    max_open_trades: int = Field(default=3, ge=1, le=100)
    stake_amount: float | Literal['unlimited'] = 'unlimited'
    volatility: float | None = Field(default=None, gt=0, le=3, allow_inf_nan=False)
    drifts: list[float] = Field(default=[-0.3, 0.0, 0.3], min_length=3, max_length=3)
    publish_on_complete: bool = True

    @field_validator('stake_amount')
    @classmethod
    def valid_stake(cls, value):
        if value != 'unlimited' and (not math.isfinite(value) or value <= 0):
            raise ValueError('Stake must be positive and finite.')
        return value

    @field_validator('drifts')
    @classmethod
    def valid_drifts(cls, values):
        if any(not math.isfinite(value) or abs(value) > 2 for value in values) or values != sorted(values):
            raise ValueError('Use three ordered finite drifts between -2 and 2.')
        return values


@app.get('/workbench/simulations')
def simulation_list():
    return simulations.list_runs()


@app.get('/workbench/simulations/calibration')
def simulation_calibration():
    try:
        return {**simulations.calibration(), 'gpu': simulations.gpu_info()}
    except Exception as exc:
        raise HTTPException(422, jobs.redact(str(exc)))


@app.post('/workbench/simulations')
def create_simulation(body: SimulationInput):
    try:
        with ENGINE_LOCK:
            return simulations.create(body.model_dump())
    except Exception as exc:
        raise HTTPException(422, jobs.redact(str(exc)))


@app.get('/workbench/simulations/{run_id}')
def simulation_result(run_id: str):
    try:
        path = simulations.directory(run_id)
        return dict(state=simulations.state(run_id), config=read_json(path / 'config.json'),
                    summary=read_json(path / 'summary.json'))
    except ValueError as exc:
        raise HTTPException(404, str(exc))


@app.post('/workbench/simulations/{run_id}/{action}')
def simulation_control(run_id: str, action: Literal['pause', 'resume', 'export']):
    try:
        simulations.directory(run_id)
        if action == 'export':
            return jobs.submit('simulation-export', {'simulation_id': run_id})
        with ENGINE_LOCK:
            return simulations.control(run_id, action)
    except ValueError as exc:
        raise HTTPException(422, str(exc))


@app.get('/workbench/pairs/{exchange}/{market}')
def pairs(exchange: Literal['binance', 'kucoin'], market: Literal['spot', 'futures']):
    return available_pairs(exchange, market)


@app.get('/workbench/compatibility/{exchange}/{market}')
def compatibility(exchange: Literal['binance', 'kucoin'], market: Literal['spot', 'futures']):
    from server.eligibility import check
    try:
        return check(exchange, market)
    except Exception as exc:
        raise HTTPException(422, jobs.redact(str(exc)))


@app.post('/workbench/data/{action}')
def import_data(action: Literal['import', 'scan']):
    if any(j['kind'] in ('import', 'scan') and j['status'] in ('queued', 'running') for j in jobs.list_jobs()):
        raise HTTPException(409, 'A data operation is already pending.')
    return jobs.submit(action, {})


@app.post('/workbench/jobs')
def new_job(body: Research):
    try:
        for name in body.strategies:
            make_config(name, body.exchange, body.capital, body.max_open_trades, body.pairs)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return jobs.submit(body.kind, body.model_dump())


def valid_job(job_id):
    if not re.fullmatch(r'[a-f0-9]{32}', job_id) or not (RUNTIME / 'jobs' / f'{job_id}.json').exists():
        raise HTTPException(404, 'Job not found.')


@app.get('/workbench/jobs/{job_id}/log')
def job_log(job_id: str):
    valid_job(job_id)
    path = RUNTIME / 'jobs' / f'{job_id}.log'
    if not path.exists():
        return {'text': 'Waiting for output…'}
    with path.open('rb') as file:
        file.seek(max(0, path.stat().st_size - 18000))
        text = file.read().decode('utf-8', errors='replace')
    return {'text': jobs.redact(text)}


@app.post('/workbench/jobs/{job_id}/cancel')
def cancel_job(job_id: str):
    valid_job(job_id)
    return jobs.cancel(job_id)


@app.post('/workbench/engines/{mode}')
def start_engine(mode: Literal['research', 'trading'], body: Trading):
    with ENGINE_LOCK:
        return launch_engine(mode, body)


def launch_engine(mode, body):
    previous = ENGINES.get(mode)
    if previous and previous['process'].poll() is None:
        current = read_json(RUNTIME / f'{mode}.json')
        if (body.live != (not current['dry_run']) or body.strategies != [current['strategy']]
                or body.exchange != current['exchange']['name']
                or body.capital != current['dry_run_wallet'] or body.max_open_trades != current['max_open_trades']
                or body.stake_amount != current['stake_amount']
                or (body.pairs is not None and body.pairs != current['exchange']['pair_whitelist'])):
            raise HTTPException(409, 'This engine already runs a different profile. Close it from Settings before switching.')
        return {'started': True, 'existing': True, **engine_state()[mode]}
    if len(body.strategies) != 1:
        raise HTTPException(422, 'Select exactly one strategy for a running bot.')
    if body.live and mode != 'trading':
        raise HTTPException(422, 'Research mode never enables live trading.')
    if body.live and (body.confirmation != 'ENABLE LIVE TRADING' or not settings()['exchange_key'] or not settings()['exchange_secret']):
        raise HTTPException(422, 'Live trading needs exchange credentials and the exact activation phrase.')
    port = 8081 if mode == 'research' else 8082
    try:
        config = make_config(body.strategies[0], body.exchange, body.capital, body.max_open_trades,
                             body.pairs, trading=mode == 'trading', live=body.live, port=port)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    if mode == 'trading':
        db = USER_DATA / f"trades-{'live' if body.live else 'dry'}-{body.exchange}-{config['trading_mode']}.sqlite"
        config['db_url'] = f'sqlite:///{db.as_posix()}'
    config['stake_amount'] = body.stake_amount
    if mode == 'research':
        # Native lookahead analysis forces market orders and requires the opposite quote side.
        config['entry_pricing']['price_side'] = 'other'
        config['exit_pricing']['price_side'] = 'other'
    path = RUNTIME / f'{mode}.json'
    write_json(path, config)
    log = (RUNTIME / f'{mode}.log').open('a', encoding='utf-8')
    command = [sys.executable, '-m', 'freqtrade', 'webserver' if mode == 'research' else 'trade',
               '--config', str(path), '--datadir', config['datadir']]
    try:
        process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=jobs.HIDDEN,
                                   env={**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONIOENCODING': 'utf-8'})
    finally:
        log.close()
    ENGINES[mode] = dict(process=process, mode='live' if body.live else mode,
                         strategy=body.strategies[0], port=port)
    return {'started': True, **engine_state()[mode]}


@app.get('/workbench/engines/{mode}/connection')
def connection(mode: Literal['research', 'trading']):
    state = engine_state().get(mode)
    if not state or not state['running']:
        raise HTTPException(409, 'Start this engine first.')
    return dict(botName='Research Lab' if mode == 'research' else 'Trading Bot',
                url=f"http://127.0.0.1:{state['port']}", username='freqmyass', password=settings()['api_password'])


@app.get('/workbench/engines/{mode}/log')
def engine_log(mode: Literal['research', 'trading']):
    path = RUNTIME / f'{mode}.log'
    text = path.read_text(encoding='utf-8', errors='replace')[-18000:] if path.exists() else 'No output yet.'
    return {'text': jobs.redact(text)}


@app.post('/workbench/engines/research/close')
def close_research():
    value = ENGINES.get('research')
    if value and value['process'].poll() is None:
        value['process'].terminate()
        value['process'].wait(timeout=15)
    return {'closed': True}


@app.post('/workbench/engines/trading/close')
async def close_trading():
    value = ENGINES.get('trading')
    if not value or value['process'].poll() is not None:
        return {'closed': True}
    try:
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{value['port']}/api/v1", timeout=15) as client:
            auth = await client.post('/token/login', auth=('freqmyass', settings()['api_password']))
            auth.raise_for_status()
            headers = {'Authorization': f"Bearer {auth.json()['access_token']}"}
            paused = await client.post('/stopbuy', headers=headers)
            paused.raise_for_status()
            opened = await client.get('/status', headers=headers)
            opened.raise_for_status()
            if opened.json():
                raise HTTPException(409, 'Open trades still need management. Close them in the trading desk before closing the engine.')
            response = await client.post('/stop', headers=headers)
            response.raise_for_status()
    except httpx.HTTPError:
        raise HTTPException(409, 'Cannot verify open positions. Keep the engine running and inspect its log.')
    value['process'].terminate()
    value['process'].wait(timeout=15)
    return {'closed': True}


async def telegram_request(method, payload):
    s = settings()
    if not s['telegram_token'] or not s['telegram_chat_id']:
        raise HTTPException(422, 'Save your Telegram token and chat ID first.')
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(f"https://api.telegram.org/bot{s['telegram_token']}/{method}", json=payload)
        if not response.is_success or not response.json().get('ok'):
            raise ValueError(response.json().get('description', 'Telegram rejected the request.'))
    except Exception as exc:
        raise HTTPException(502, jobs.redact(str(exc)))
    return response.json().get('result')


@app.post('/workbench/telegram/test')
async def telegram_test():
    await telegram_request('sendMessage', {'chat_id': settings()['telegram_chat_id'],
        'text': 'FreqMyAss outbound connection test. This confirms sending only. Keep the Freqtrade trading engine open, then send /help or /show_config here to verify native commands. No trading was started by this test.'})
    return {'sent': True}


@app.post('/workbench/telegram/commands')
async def telegram_commands():
    commands = [{'command': name, 'description': description} for name, description in COMMANDS.items()]
    chat_id = settings()['telegram_chat_id']
    # A chat-specific menu also takes precedence over an older default menu.
    for scope in ({'type': 'default'}, {'type': 'chat', 'chat_id': chat_id}):
        await telegram_request('setMyCommands', {'commands': commands, 'scope': scope})
    if str(chat_id).isdigit():
        await telegram_request('setChatMenuButton', {'chat_id': chat_id, 'menu_button': {'type': 'commands'}})
    return {'installed': True, 'commands': len(commands)}


@app.get('/workbench/reports/{report_id}')
def report(report_id: str):
    if not re.fullmatch(r'[a-f0-9]{24}', report_id):
        raise HTTPException(404, 'Report not found.')
    result = read_json(RUNTIME / 'reports' / f'{report_id}.json')
    if not result:
        raise HTTPException(404, 'Report not found.')
    return result


class ReportInput(BaseModel):
    file: str = Field(max_length=300)
    strategy: str = Field(pattern=r'^[A-Za-z_][A-Za-z0-9_]{0,100}$')


@app.post('/workbench/reports/create')
def create_report(body: ReportInput):
    try:
        reports.result_path(body.file)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    return jobs.submit('report', body.model_dump())


@app.get('/workbench/reports/{report_id}/html')
def report_html(report_id: str, download: bool = False, theme: Literal['light', 'dark'] = 'light'):
    record = report(report_id)
    if not record['html_ready']:
        raise HTTPException(422, 'At least two daily returns and a nonzero return are required for the HTML tear sheet.')
    path = RUNTIME / 'reports' / f'{report_id}.html'
    headers = {'Content-Security-Policy': "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline';"}
    if theme == 'dark' and not download:
        css = '''<style>
body { background: #17252a !important; color: #dce9e9 !important; }
h1,h2,h3,h4,p,td,th,a,dt,dd { color: #dce9e9 !important; }
aside,thead,tr:nth-child(even) { background: #203238 !important; }
table,td,th { border-color: #3a5158 !important; }
svg [id='patch_1'] path { fill: #17252a !important; }
svg g[id^='text_'],svg g[id^='text_'] g,svg g[id^='text_'] use { fill: #dce9e9 !important; }
</style>'''
        return HTMLResponse(path.read_text(encoding='utf-8').replace('</head>', css + '</head>'), headers=headers)
    return FileResponse(path, media_type='text/html',
                        filename=f"{record['strategy']}-quantstats.html" if download else None,
                        headers=headers)


@app.get('/workbench/results')
def results():
    items, seen = [], set()
    # Prefer the original directory over its hard link in native engine history.
    for path in sorted(RESULTS.rglob('*.zip'), key=lambda p: len(p.parts), reverse=True):
        identity = (path.stat().st_dev, path.stat().st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        metadata = read_json(path.with_suffix('.meta.json'), {})
        items.append(dict(file=str(path.relative_to(RESULTS)).replace('\\', '/'), bytes=path.stat().st_size,
                          strategies=list(metadata)))
    return items


@app.get('/workbench/results/download')
def result_download(file: str):
    try:
        path = reports.result_path(file)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    return FileResponse(path, filename=path.name)


@app.get('/{path:path}')
def frontend(path: str):
    dist = ROOT / 'frontend' / 'dist'
    target = (dist / path).resolve()
    if not target.is_relative_to(dist.resolve()):
        raise HTTPException(404)
    if not target.is_file():
        target = dist / 'index.html'
    if not target.exists():
        return JSONResponse({'detail': 'Build the frontend with pnpm build first.'}, status_code=503)
    response = FileResponse(target)
    if target.name == 'index.html':
        response.set_cookie('fma_session', SESSION, httponly=True, samesite='strict')
        response.headers['Cache-Control'] = 'no-store'
    return response
