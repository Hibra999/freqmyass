# Published backtest results

Six completed full-history campaigns from release **1.00**. These are simulated historical results, not live trading records or forecasts. All begin with **1,000 USDT**, use **5m candles** and allow **three open positions**. Dates are UTC.

| Campaign / files | Pairs | Trades | Allocation | Final USDT | Return | Native max drawdown |
| --- | ---: | ---: | --- | ---: | ---: | ---: |
| [binance spot · NASOSv4_SMA](./binance-spot-NASOSv4_SMA/) | 147/147 | 5,696 | Automatic | 12,182,289.29 | 1,218,128.93% | 13.28% |
| [binance spot · NotAnotherSMAOffsetStrategyHO](./binance-spot-NotAnotherSMAOffsetStrategyHO/) | 147/147 | 3,470 | Automatic | 157,693.09 | 15,669.31% | 47.39% |
| [kucoin spot · NASOSv4_SMA](./kucoin-spot-NASOSv4_SMA/) | 53/64 | 2,990 | Automatic | 831,160.47 | 83,016.05% | 23.85% |
| [kucoin spot · NotAnotherSMAOffsetStrategyHO](./kucoin-spot-NotAnotherSMAOffsetStrategyHO/) | 53/64 | 1,343 | Automatic | 26,694.11 | 2,569.41% | 27.02% |
| [binance futures · dip_catcher](./binance-futures-dip_catcher/) | 326/328 | 15,663 | 330 USDT fixed | 46,004.57 | 4,500.46% | 5.21% |
| [binance futures · SingleB_FixedRR](./binance-futures-SingleB_FixedRR/) | 326/328 | 52,673 | 330 USDT fixed | 24,852.39 | 2,385.24% | 28.44% |

## Open the results

Each campaign contains:

- `quantstats.html`: complete QuantStats HTML with monthly heatmaps, annual returns, risk metrics, equity, drawdown and a BTC benchmark. Download the file and open it in a browser; GitHub displays HTML source.
- `summary.json`: metrics, warnings, allocation, strategy pins, the data revision and the exact selected pairs. Ratios such as profit, win rate and drawdown are fractions: multiply by 100 for percent.
- `equity.csv`, `monthly.csv`, `yearly.csv`: chart values for further analysis. Monthly and yearly `value` fields are compounded return fractions. Equity `value` is USDT.
- `freqtrade-result.json.gz`: the complete native strategy-result object, including every simulated trade and order, pair metrics, entry/exit statistics, parameters and native period breakdowns. Extract with gzip/7-Zip or Python `gzip.open(path, 'rt')` and `json.load`. This is a standalone result object, not a native import ZIP.

The original archive SHA-256 is recorded for provenance. Original archives stay local because they also contain private engine configurations and downloaded third-party strategy source. No credentials, databases, raw candles or strategy source are published here.

## Conditions and limitations

Spot histories run from 2024-01-01 16:40 through 2026-10-02 03:00. Futures end at 2026-09-01 17:25; strategy warmup determines the exact start. Individual pairs can cover shorter periods.

All dataset files were retained locally. Current exchange metadata excluded two Binance futures contracts (AERGO and SXP) and eleven KuCoin spot pairs (AMPL, DEGO, EOS, MKR, NWC, PLU, SXP, USDJ, VIDT, VRA and XEM). The published runs use the supported subset; selection is recorded in each summary.

Automatic compounding exceeded exchange stake limits in the initial futures attempts. The completed futures campaigns explicitly use fixed 330 USDT allocation. Compare strategies only with equivalent allocation and market assumptions.

The Binance NotAnotherSMAOffsetStrategyHO run contains a POND history gap before final settlement. The HTML and summary retain that warning. Curves come from Freqtrade's exported wallet with verified final liquidation; they are not an independent mark-to-market reconstruction. Incomplete prices can affect daily risk metrics.

Large compounded historical returns do not establish realistic liquidity, slippage or live profitability. The original short warmup in dip_catcher and recursive sensitivity in NotAnotherSMAOffsetStrategyHO remain documented in [VALIDATION.md](../VALIDATION.md).

Regenerate this snapshot locally with `.runtime\env\python.exe scripts\export_results.py` after the six recorded campaigns exist. The exporter checks trade counts, final balances, compressed-data round trips and private settings before writing. Development smoke tests and failed attempts remain in local activity history.
