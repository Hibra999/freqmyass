# FreqMyAss

A local, English trading workspace for Windows. Freqtrade performs all trading, backtesting and optimization. A redesigned Vue interface puts guided workflows first, with the official FreqUI engine tools available under Advanced.

## Run

Prerequisites: Windows, Miniconda, Git, Node.js and pnpm (the version is pinned in `frontend/package.json`).

1. Run `Setup.cmd`. It creates an isolated Conda environment in `.runtime/env`, installs Python dependencies constrained to `requirements-lock.txt`, verifies the four strategy sources and builds the frontend.
2. Run `Start.cmd`. The application opens at **http://127.0.0.1:8765**. Its server remains active when the browser closes.
3. Open **Market data → Import all** to download the complete current NostalgiaForInfinityData snapshot and scan its coverage. Existing snapshots are preserved.
4. Open **Backtesting**, choose spot or futures, strategies, capital and a period. Empty dates and pairs mean all available data for that exchange and market.
5. Reports appear automatically after completed runs. Inspect each job log when a run or report fails.

For retired markets, use **Advanced configuration → Check and select available markets** before submitting. Every excluded pair is listed. This consults Freqtrade's exchange metadata; it does not delete or fabricate historical candles. Reports distinguish selected, processed and total dataset pairs. A failed full-universe attempt remains in activity history.

The configured defaults are **1,000 USDT**, **3 open positions**, automatic stake sizing and **5m candles**. NASOS also receives its required 1h informative candles. These are comparison defaults, not claims about the authors' recommended risk settings.

Advanced configuration also offers fixed USDT per entry. This can be necessary for long futures campaigns: automatic compounding may exceed the exchange's maximum contract stake. Reports record the allocation mode and maximum positions so results with different sizing are not confused.

## What is included

- A guided research workflow, persistent queue, cancellation, job logs and stored configurations.
- The four requested strategies, fetched from pinned upstream revisions with SHA-256 verification. Originals remain alongside runnable copies. The two V2 SMA strategies use Freqtrade's official V3 migration; trading rules are preserved.
- Binance spot/futures and KuCoin spot data, with per-file start/end dates, duplicates and gap counts. KuCoin futures has no candles in the source snapshot.
- Native Freqtrade trading controls, portfolio dashboard, charts, orders, history, balances, pairlists, data collector, lookahead analysis and recursive analysis.
- Hyperopt jobs through the official CLI. Parameter export is disabled to avoid silently changing the original strategy settings.
- QuantStats HTML reports, daily wallet curves, monthly and yearly compounded returns, trade tables and downloadable engine archives. Saved native backtest archives can also be selected under Reports.
- Native Freqtrade Telegram. Configure credentials in Settings and test the connection; commands are owned by the running Freqtrade trading process.
- Multiple external engine connections through Settings. FreqAI requires a compatible strategy and its model dependencies; the four supplied strategies do not implement FreqAI features.

Complete 326-contract futures campaigns used approximately 51 GiB of RAM on the validation machine. The workbench serializes its research queue and Hyperopt defaults to one worker. Native tools and external engines run independently; avoid launching another large campaign alongside one already running.

## Data, money and credentials

All mutable state is under `.runtime/`, excluded from Git: credentials, the Conda environment, original strategies, market data, job logs, engine configurations, trading databases and reports. Never publish this directory. The Git repository contains the application and reproducible source references, not the dataset or credentials.

The application listens on loopback. Local workbench requests require an HTTP-only SameSite session cookie, and writes require a request protection header. The engine uses its own authenticated REST API on ports 8081 (research) and 8082 (trading). Do not expose these ports directly to the internet.

Trading starts in simulation and in the stopped state. Live activation requires credentials plus the explicit `ENABLE LIVE TRADING` phrase. Starting a process does not start entries; use the native Start control. Use exchange keys without withdrawal permission. One native Telegram bot token must belong to one running trading process.

Reports use Freqtrade's exported wallet, sampled daily in UTC with 365 periods per year. Final forced exits are reconciled from their exported net PnL; spot reconciliation also accounts for the marked coins and fees before liquidation. The final balance must match the engine. Wallet equity is not an independently reconstructed mark-to-market series. Native Freqtrade drawdown and Sharpe metrics are labeled separately from QuantStats. The BTC price benchmark uses 5m candles truncated at the backtest end, with no assumed future prices or trading fees.

Backtests depend on coverage, exchange metadata and Freqtrade's execution assumptions. Delisted or unsupported pairs can be rejected by the engine; logs must be reviewed. No missing markets are silently substituted. Backtest results do not guarantee live results.

When a final position's candles end before the campaign, Freqtrade uses its last available candle for forced settlement. The exported wallet may omit the unpriced holding during the remaining period. Such reports carry an explicit coverage warning in both the interface and downloaded HTML; their daily risk statistics need particular caution.

## Verification

```powershell
.runtime\env\python.exe -m pytest tests -q
.runtime\env\python.exe scripts\validate_engine.py
.runtime\env\python.exe scripts\validate_analysis.py
cd frontend
pnpm typecheck
pnpm build
node check-workspace.mjs
node check-engines.mjs
node check-local-actions.mjs
```

The engine smoke test runs the four strategies against BTC, ETH and SOL from January through February 2025. The browser checks need the app running and Microsoft Edge installed; `check-engines.mjs` additionally expects a stopped simulation engine. Full-universe tests are separate from smoke tests. Analysis checks target ten trades per strategy and do not prove the absence of bias. Each execution writes a new diagnostic directory to preserve earlier evidence.

The first completed release is **1.00**. Development commits are pushed to `main` without development version tags. See `VALIDATION.md` for the verification record and known limits.

## Credits and licensing

This application incorporates FreqUI, distributed under GPL-3.0; its existing notices remain in `frontend/`. Freqtrade is an external, unmodified dependency. QuantStats is Apache-2.0. The strategy importer preserves source provenance in `strategies.lock.json`; downloaded third-party strategies are not republished here. See `THIRD_PARTY.md`.
