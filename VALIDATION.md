# Validation record

Release **1.00**, validated on 2026-10-29 UTC. All six full-history campaigns and final browser checks completed.

## Environment and application

- Windows, isolated Conda environment: Python 3.13.15, Freqtrade 2026.8, QuantStats 0.0.81. Freqtrade engine files are unchanged.
- Setup.ps1 completed against the project environment. Python dependencies are constrained to the tested dependency closure; pip check passes. An entirely new Windows installation has not been tested.
- 56 inherited frontend unit tests and 16 backend tests pass. Production build and TypeScript checks pass.
- All three browser checks pass: desktop and mobile navigation, real reports and sandboxed QuantStats HTML, research authentication, native backtest tools, the stopped simulation desk, report generation from saved archives and visible market exclusions.
- Native Telegram connection test delivered successfully. The trading process exposes native Telegram commands and remains in simulation, stopped. No real-money orders were placed.
- Empty trading-engine shutdown was exercised through the API. A separate test verifies that open positions prevent shutdown and that entries are paused first.
- Live activation, profile mismatch, origin/session protection, path traversal, invalid money/date/market input, cancellation and worker recovery have focused tests.
- A two-epoch native Hyperopt run completed with NotAnotherSMAOffsetStrategyHO, one worker, fixed random seed, January–February 2025 and BTC/ETH/SOL. Parameter export was disabled. This verifies execution, not optimization quality.

## Data and full-history campaigns

NostalgiaForInfinityData revision: `0e7e78c85e3815584a2accc5528fe9161e45e433`.

The complete snapshot contains 3,971 files, including 3,951 Feather files. Every Feather file was scanned without read errors. The inventory records actual coverage, duplicates and gaps. It contains 147 Binance spot pairs, 328 Binance futures pairs and 64 KuCoin spot pairs; there is no KuCoin futures dataset.

All runs below start with 1,000 USDT, allow three open positions, use 5m candles and preserve the strategy's risk parameters. NASOS receives 1h informative candles. Dates are UTC; individual pairs may cover less history.

| Exchange / market | Strategy | Processed pairs | Trades | Allocation | Outcome |
| --- | --- | ---: | ---: | --- | --- |
| Binance spot | NASOSv4_SMA | 147 | 5,696 | Automatic | Complete; HTML reconciled |
| Binance spot | NotAnotherSMAOffsetStrategyHO | 147 | 3,470 | Automatic | Complete; HTML reconciled; POND coverage warning |
| KuCoin spot | NASOSv4_SMA | 53 | 2,990 | Automatic | Complete; HTML reconciled |
| KuCoin spot | NotAnotherSMAOffsetStrategyHO | 53 | 1,343 | Automatic | Complete; HTML reconciled |
| Binance futures | dip_catcher | 326 | 15,663 | 330 USDT fixed | Complete; HTML reconciled |
| Binance futures | SingleB_FixedRR | 326 | 52,673 | 330 USDT fixed | Complete; HTML reconciled |

Spot campaigns cover 2024-01-01 16:40 through 2026-10-02 03:00. Futures campaigns start on 2024-01-01 (02:30 for dip_catcher, 04:10 for SingleB) and end on 2026-09-01 17:25.

The initial attempts requested every downloaded pair. Binance rejected AERGO and SXP contracts because current metadata/leverage tiers were unavailable. KuCoin no longer returned AMPL, DEGO, EOS, MKR, NWC, PLU, SXP, USDJ, VIDT, VRA and XEM. All source files remain present. Subsequent campaigns explicitly selected the supported subset.

Automatic compounding in both full-history futures attempts exceeded exchange contract stake limits. Those failures remain recorded. Fixed allocation is a separate, explicitly labeled experiment; it does not replace the application's automatic default. Comparisons must use matching allocation modes.

## Strategy compatibility and diagnostics

The two V2 SMA strategies use Freqtrade's official StrategyUpdater. Originals retain their pinned checksums. A January–February 2025 comparison against the originals matched all eight NASOS trades and both SMA Offset trades: pair, timing, prices, amounts, exits and final balance. V3 restores descriptive entry tags previously dropped by the V2 adapter. The unused pandas_ta import is removed from dip_catcher; indicator expressions are unchanged.

Native lookahead analysis completed for all four strategies with ten targeted trades each over BTC/ETH/SOL and a 2024–2025 period. No biased signals were found in that limited sample. This is not proof that the strategies are bias-free.

Native recursive analysis tested startup counts 30, 100, 248, 500 and 1,000 plus each strategy's original value. NotAnotherSMAOffsetStrategyHO showed substantial EWO sensitivity at its original 200 candles (58.206% in that diagnostic). dip_catcher declares 30 startup candles although its cloud calculation needs more history. The original startup values remain unchanged and the interface flags the issue.

## Report accounting and limits

Reports reconcile against the native final balance, including verified forced liquidation and spot fees. Midnight snapshots close the preceding UTC day, preventing an artificial extra month. A BTC price benchmark uses 5m candles available by the end of the run. Tests cover initial capital, idle days, exclusive end dates, benchmark timing and forced exits with early candle endings.

The Binance SMA Offset campaign includes POND history ending before the campaign ends. Freqtrade's exported wallet can omit that unpriced holding until final settlement. The interface and downloadable HTML carry a coverage warning. These are native wallet curves, not an independent mark-to-market reconstruction; daily risk statistics can be affected by incomplete prices.

These checks establish software behavior and accounting consistency. They do not establish profitability, liquidity, slippage realism or fitness for live trading. Live exchange credentials, real orders, FreqAI training and access beyond localhost were not tested.
