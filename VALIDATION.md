# Validation record

Release **1.00**, validated on 2026-10-29 UTC. All six full-history campaigns and final browser checks completed.

## Follow-up: dark mode and CUDA price trajectories

Validated on 2026-10-30. CUDA hardware: NVIDIA GeForce RTX 5070 with 12,227 MiB, driver 621.01, CuPy 14.2.0 and CUDA runtime 13.2. The CPU has 24 physical / 32 logical cores; RAM is 64 GiB.

- Dark mode now covers the guided workspace, original FreqUI, charts and sandboxed QuantStats HTML. Downloaded HTML remains original. Historical failures retain their status and now show the specific cause and remediation; later successful runs are identified. The ten earlier failures comprised four missing-data attempts, four unsupported market/metadata attempts and two excessive compounded stakes.
- GBM checks cover reproducible seeds, positive OHLC, initial price after warmup, the zero-volatility analytic limit and terminal log-return moments. Real CUDA tests run on this GPU. A 12-path / 7-day integration test completed all 48 native strategy evaluations without errors, paused/resumed without duplicates, preserved stored rows and proved independence from previous paths and worker assignment.
- Native CLI parity on the same synthetic candles matches trades, final balance and drawdown for all four strategies. A separate full-year CUDA validation completed three 365-day paths / 12 evaluations without errors, using frozen strategy files and hashes.
- Backend tests cover parameter bounds, path traversal, failure accounting, zero-trade outcomes and automatic publication refusing unrelated changes. Publication commits only its own generated result directory and never force-pushes. Final result pushes remain conditional on unchanged branch/remote, clean unrelated files and working Git credentials.
- All 29 backend tests and 56 frontend tests pass. TypeScript and the production build pass. Edge checks verify the CUDA dashboard's annual results, all three regimes, charts, native metrics, dark/mobile layout and API bounds, alongside the existing guided and native UI checks. Snapshot exports preserve counts, portable Git paths and SHA-256 checksums; result files disable Git newline conversion so Windows checkouts preserve their bytes.
- These short validations do not claim the million-path production experiment is complete. Its committed `results/monte-carlo/<run-id>/progress.json` records actual completed/target counts; the local UI shows live progress. One-minute price generation runs on CUDA; unchanged Freqtrade backtests run on CPU. Full paths are evaluated, while candle files are reused and per-path outcomes are retained.
- Production run `4f03f4f4fe2e40978d71fa25f585a3a1` reached 64 annual paths / 256 evaluations with zero failures before its first export. All 16 workers completed their in-flight paths for a consistent checkpoint. The measured first batch used about 138 MiB of reusable candle files and left over 30 GiB RAM available. Initial throughput projects several weeks; this is an estimate, not a completion claim.

The simulator keeps Windows awake while its process runs without changing global power settings. Browser or backend closure does not terminate the supervisor. Pause/resume was exercised; a real power-loss/reboot recovery and a fresh CUDA installation on another machine were not tested.

## Follow-up: native UI, Telegram and published results

Validated on 2026-10-30. The original 1.00 tag remains unchanged; these improvements are subsequent commits on main.

- Full FreqUI restores the upstream navbar, bot controls, refresh, themes, layouts and mobile footer. The chosen view persists; a top bar connects the research/trading engines and returns to guided workflows or QuantStats. Guided CSS is scoped to its own workspace.
- A browser regression check connects both native engines, verifies research navigation, opens the trading dashboard, persists the dark theme across reload, checks mobile overflow and returns to reports. It also verifies Telegram status. A discovered upstream dashboard issue is corrected in the frontend: research webservers are excluded from trading-period requests and portfolio comparison rows. Freqtrade engine code is unchanged.
- Telegram previously advertised OpenClaw commands while the local Freqtrade engine was offline. The dedicated bot now advertises 39 commands verified against the installed native handlers. The user confirmed `/help` and `/show_config` respond from Freqtrade. Tests distinguish saved credentials from a running process with matching credentials; neither a menu nor an outbound test is described as proof of reception.
- The six published campaigns contain 81,835 simulated trades. Exports include native result JSON compressed with gzip, complete QuantStats HTML, metrics/provenance and daily/monthly/yearly CSVs. Counts and final balances reconcile with source archives; gzip round trips and published SHA-256 checksums pass. Private settings are scanned in plaintext and decompressed exports. Original configs, candles, trading databases and strategy source remain local.
- 19 backend tests and 56 frontend tests pass, along with TypeScript and the production build. Guided desktop/mobile/report checks and the new native UI check pass. No backtest calculation or trading rule changed; full-history campaigns were exported, not rerun. No live orders were tested.

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
