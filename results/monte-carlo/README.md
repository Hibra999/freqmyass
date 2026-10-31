# CUDA price-path experiments

This directory contains exported synthetic experiments, separate from the six historical backtests in the parent directory. Inspect each run's `progress.json`: a partial snapshot is not a completed million-path experiment. Live progress is available in the local application's **Monte Carlo** page.

[Production run 4f03f4f4 · target 1,000,000 annual paths](4f03f4f4fe2e40978d71fa25f585a3a1/). Its first published checkpoint contains 64 paths / 256 native strategy evaluations with zero failures. The same directory will receive the complete export when processing finishes.

The requested production run contains **1,000,000 complete BTC/USDT paths**, **365 days each**, with **105,120 five-minute trading candles per path**, plus 14 synthetic warmup days. CUDA generates geometric Brownian motion prices at one-minute steps and aggregates OHLC candles. Native Freqtrade 2026.8 evaluates the four original strategies on every path: **4,000,000 strategy evaluations**. CUDA accelerates generation; the unchanged backtester uses CPU.

Paths are split across assumed annual drifts of -30%, 0% and +30%. Annual volatility and initial price come from the recorded NFI BTC/USDT history. Volume is fixed at 100 BTC per candle, funding is zero and futures mark prices equal synthetic spot. Strategy capital starts at 1,000 USDT, with automatic allocation and three maximum positions; native single-pair rules limit concurrent BTC positions to one. Failed evaluations and valid zero-trade outcomes are counted separately.

GBM omits jumps, changing volatility, realistic volume, spreads and market impact. One-minute samples miss extrema between those samples. Loss probabilities and percentiles describe this model only; they do not predict real BTC or establish live profitability. Strategy drawdown uses Freqtrade's closed-trade equity calculation.

Each run contains:

- `summary.json`: model parameters, engine/CUDA versions, pinned strategy references and runnable hashes, completed/target counts, per-regime price and strategy statistics. Fractions such as drawdown and loss probability multiply by 100 for percent.
- `progress.json`: snapshot status, actual completed paths, failed strategy evaluations and measured runtime.
- `outcomes-*.csv.gz`: one row per path and strategy, including asset final/minimum/maximum prices and asset drawdown, native final balance, trades, wins, strategy drawdown and any error. Each compressed shard covers at most 10,000 path IDs.
- `SHA256SUMS`: checksums of the exported files.

Terminal statistics use every completed path. Chart bands are pointwise P5/P50/P95 from at most 256 reproducibly selected paths per regime; they are not individual trajectories. Full candles are generated and evaluated for every path, then worker files are reused to avoid storing terabytes. Per-path outcomes remain in local SQLite. Seeds and frozen strategies allow regeneration on the recorded software stack; full individual trade archives are not retained for the million-path experiment.

The background worker saves each completed path, supports pause/resume, and exports/pushes the complete run automatically when Git is ready. A PC restart requires reopening the app and resuming. The earlier six historical campaigns retain their full trade/order results and QuantStats reports.
