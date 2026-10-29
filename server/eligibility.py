"""Read current exchange metadata through Freqtrade; never fabricate delisted markets."""
from freqtrade.enums import RunMode
from freqtrade.resolvers import ExchangeResolver
from server.catalog import USER_DATA, DATA, make_config, available_pairs


def classify_pairs(pairs, markets, tiers, market):
    allowed, excluded = [], []
    for pair in pairs:
        reason = ''
        if pair not in markets:
            reason = 'Exchange no longer returns market metadata.'
        elif market == 'futures' and pair not in tiers:
            reason = 'Exchange has no leverage tiers for this contract.'
        if reason:
            excluded.append(dict(pair=pair, reason=reason))
        else:
            allowed.append(pair)
    return dict(pairs=allowed, excluded=excluded, total=len(pairs))


def check(exchange, market):
    name = 'dip_catcher' if market == 'futures' else 'NASOSv4_SMA'
    config = make_config(name, exchange)
    config.update(runmode=RunMode.BACKTEST, user_data_dir=USER_DATA, datadir=DATA / exchange)
    config['exchange']['pair_whitelist'] = []
    engine = ExchangeResolver.load_exchange(config, validate=True, load_leverage_tiers=market == 'futures')
    try:
        return classify_pairs(available_pairs(exchange, market), engine.markets, engine._leverage_tiers, market)
    finally:
        engine.close()
