# Third-party components

- [FreqUI](https://github.com/freqtrade/frequi): GPL-3.0. The frontend retains its API clients, stores, engine controls and advanced analysis components. The application shell, guided workspace, research queue and QuantStats integration are new. Original license: `frontend/LICENSE`.
- [Freqtrade](https://github.com/freqtrade/freqtrade): GPL-3.0. Installed as a pinned dependency; its engine source is not modified.
- [QuantStats](https://github.com/ranaroussi/quantstats): Apache-2.0. Installed as a dependency.
- [NostalgiaForInfinityData](https://github.com/iterativv/NostalgiaForInfinityData): GPL-3.0. Downloaded locally as a complete shallow snapshot; not redistributed in this repository.
- [NASOSv4_SMA](https://github.com/remiotore/ccxt-freqtrade/blob/main/strategies/NASOSv4_SMA.py): fetched locally from the pinned source. No root license identified during initial inspection.
- [NotAnotherSMAOffsetStrategyHO](https://github.com/davidzr/freqtrade-strategies/blob/main/strategies/NotAnotherSMAOffsetStrategyHO/NotAnotherSMAOffsetStrategyHO.py): source repository GPL-3.0, archived.
- [dip_catcher](https://github.com/viktors1982/trading/blob/main/freqtrade/strategies/dip_catcher.py): fetched locally from the pinned source. No root license identified during initial inspection. Only its unused `pandas_ta` import is removed in the runnable copy.
- [SingleB_FixedRR](https://github.com/ly5586/backtest-autopsy/blob/master/strategy/SingleB_FixedRR.py): MIT source repository; corresponds to the requested [Freqle entry](https://freqle.org/strategy/6fae0c352e8e44fb).

Strategy signals, ROI tables, stoploss, trailing configuration and startup counts are retained. The UI explicitly flags the original short warmup in dip_catcher. No unsupported author recommendations are invented.
