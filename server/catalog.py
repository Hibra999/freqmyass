"""Local configuration; the Freqtrade engine and upstream strategies remain external."""
from pathlib import Path
import json
import os
import secrets

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
DATA = RUNTIME / 'dataset'
USER_DATA = RUNTIME / 'user_data'
STRATEGIES = USER_DATA / 'strategies'
RESULTS = USER_DATA / 'backtest_results'
STRATEGY_INFO = [
    dict(name='NASOSv4_SMA', market='spot', exchange='binance', informative=['1h'],
         description='SMA offsets with informative trend filters.',
         warning='Official V2-to-V3 interface migration; signals preserved. Original custom stoploss is disabled.',
         repo='remiotore/ccxt-freqtrade', branch='main', path='strategies/NASOSv4_SMA.py'),
    dict(name='NotAnotherSMAOffsetStrategyHO', market='spot', exchange='binance', informative=[],
         description='Optimized moving-average offset entries and trailing exits.',
         warning='Original stoploss is -35%. EWO is sensitive to warmup (200 original candles). Official V3 migration; archived source.',
         repo='davidzr/freqtrade-strategies', branch='main', path='strategies/NotAnotherSMAOffsetStrategyHO/NotAnotherSMAOffsetStrategyHO.py'),
    dict(name='dip_catcher', market='futures', exchange='binance', informative=[],
         description='Long and short entries using Hull averages and Ichimoku.',
         warning='Original warmup is 30 candles; cloud calculation needs more history. Run recursive analysis.',
         repo='viktors1982/trading', branch='main', path='freqtrade/strategies/dip_catcher.py'),
    dict(name='SingleB_FixedRR', market='futures', exchange='binance', informative=[],
         description='Momentum entries with fixed 1.5% stoploss and profit target.',
         warning='Weekday/hour filter uses candle timestamps. Source experiment used OKX, not Binance.',
         repo='ly5586/backtest-autopsy', branch='master', path='strategy/SingleB_FixedRR.py'),
]


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(temp, path)


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def initialize():
    for path in [RUNTIME / 'jobs', RUNTIME / 'reports', STRATEGIES, RESULTS]:
        path.mkdir(parents=True, exist_ok=True)
    path = RUNTIME / 'settings.json'
    if not path.exists():
        write_json(path, dict(capital=1000, max_open_trades=3, exchange='binance',
                             telegram_token='', telegram_chat_id='', exchange_key='',
                             exchange_secret='', exchange_password='', credential_exchange='binance',
                             api_password=secrets.token_urlsafe(32), jwt_secret=secrets.token_hex(32)))


def settings():
    initialize()
    return read_json(RUNTIME / 'settings.json')


def strategy(name):
    for item in STRATEGY_INFO:
        if item['name'] == name:
            return item
    raise ValueError('Select a known strategy.')


def data_directory(exchange, market):
    # Freqtrade automatically appends /futures for futures candle types.
    return DATA / exchange


def available_pairs(exchange, market):
    directory = data_directory(exchange, market)
    if market == 'futures':
        directory = directory / 'futures'
    suffix = '-5m-futures.feather' if market == 'futures' else '-5m.feather'
    pairs = []
    for path in sorted(directory.glob('*' + suffix)):
        parts = path.name.removesuffix(suffix).split('_')
        if market == 'futures' and len(parts) == 3:
            pairs.append(f'{parts[0]}/{parts[1]}:{parts[2]}')
        elif market == 'spot' and len(parts) == 2:
            pairs.append('/'.join(parts))
    return pairs


def make_config(name='NASOSv4_SMA', exchange='binance', capital=1000, max_open_trades=3,
                pairs=None, trading=False, live=False, port=8081):
    info = strategy(name)
    market = info['market']
    if exchange not in ('binance', 'kucoin') or (market == 'futures' and exchange != 'binance'):
        raise ValueError('This dataset has Binance spot/futures and KuCoin spot only.')
    choices = available_pairs(exchange, market)
    if pairs is not None and (not pairs or any(p not in choices for p in pairs)):
        raise ValueError('Selected pairs are absent from this dataset and market.')
    selected = choices if pairs is None else pairs
    if not selected:
        raise ValueError('No 5m candles available. Import the dataset first.')
    s = settings()
    if live and s.get('credential_exchange', 'binance') != exchange:
        raise ValueError('The saved exchange credentials belong to a different exchange.')
    config = {
        '$schema': 'https://schema.freqtrade.io/schema.json',
        'bot_name': 'FreqMyAss' + (' Live' if live else ' Simulation'),
        'strategy': name, 'timeframe': '5m', 'dry_run': not live,
        'dry_run_wallet': capital, 'max_open_trades': max_open_trades,
        'stake_currency': 'USDT', 'stake_amount': 'unlimited',
        'tradable_balance_ratio': 0.99, 'fiat_display_currency': 'USD',
        'trading_mode': market, 'margin_mode': 'isolated' if market == 'futures' else '',
        'cancel_open_orders_on_exit': False,
        'unfilledtimeout': {'entry': 10, 'exit': 10, 'unit': 'minutes'},
        'entry_pricing': {'price_side': 'same', 'use_order_book': True, 'order_book_top': 1,
                          'price_last_balance': 0.0, 'check_depth_of_market': {'enabled': False, 'bids_to_ask_delta': 1}},
        'exit_pricing': {'price_side': 'same', 'use_order_book': True, 'order_book_top': 1},
        'exchange': {'name': exchange, 'key': s['exchange_key'] if live else '',
                     'secret': s['exchange_secret'] if live else '',
                     'password': s.get('exchange_password', '') if live else '',
                     'ccxt_config': {}, 'ccxt_async_config': {},
                     'pair_whitelist': selected, 'pair_blacklist': []},
        'pairlists': [{'method': 'StaticPairList', 'allow_inactive': not trading}],
        'telegram': {'enabled': bool(trading and s['telegram_token']),
                     'token': s['telegram_token'] if trading else '',
                     'chat_id': s['telegram_chat_id'] if trading else ''},
        'api_server': {'enabled': True, 'listen_ip_address': '127.0.0.1', 'listen_port': port,
                       'verbosity': 'error', 'enable_openapi': True, 'username': 'freqmyass',
                       'password': s['api_password'], 'jwt_secret_key': s['jwt_secret'],
                       'ws_token': s['jwt_secret'],
                       'CORS_origins': ['http://127.0.0.1:8765', 'http://localhost:8765', 'http://127.0.0.1:3000']},
        'initial_state': 'stopped' if trading else 'running',
        'force_entry_enable': True,
        'internals': {'process_throttle_secs': 5},
        'user_data_dir': str(USER_DATA),
        'datadir': str(data_directory(exchange, market)),
        'dataformat_ohlcv': 'feather',
    }
    return config
