---
name: hl-backtester
description: Runs local backtests and parameter optimization on Hyperliquid perpetual pairs using real OHLCV data. Use when the user wants to backtest a strategy, optimize parameters, test a pair, compare results, or run the backtesting engine. Triggers on "backtest", "optimize", "test", "run backtest", "how did it perform", "best params", or any mention of a Hyperliquid pair with performance testing intent.
---

# Hyperliquid Local Backtester

Specialized in running, interpreting, and improving backtests on Hyperliquid perpetual pairs using the local Python engine at `projects/hyperliquid-ema-rsi-backtest.py`.

## Setup Check

Before running anything, verify dependencies are installed:
```powershell
python -m pip install backtesting ccxt pandas numpy bokeh cryptography cffi requests aiohttp certifi charset-normalizer idna urllib3 python-dateutil tzdata tqdm colorama 2>&1 | tail -5
```

If any import errors appear, install the missing module with `python -m pip install <module>`.

## Available Commands

### Normal Backtest
```powershell
cd "C:\Users\mcgra\OneDrive\Claude\.claude\worktrees\thirsty-borg\pinescript-agents"
python projects/hyperliquid-ema-rsi-backtest.py
```
Runs with default parameters. Opens interactive HTML chart in browser.

### Parameter Optimizer
```powershell
cd "C:\Users\mcgra\OneDrive\Claude\.claude\worktrees\thirsty-borg\pinescript-agents"
python projects/hyperliquid-ema-rsi-backtest.py optimize
```
Tests 432 parameter combinations. Finds best EMA lengths, RSI thresholds, SL/TP. Takes 1-3 minutes.

## Changing the Pair

Open `projects/hyperliquid-ema-rsi-backtest.py` and edit the bottom section:
```python
SYMBOL    = "BTC/USDC:USDC"   # change this
TIMEFRAME = "1h"               # 5m 15m 1h 4h 1d
LIMIT     = 2000               # number of candles
```

### Supported Hyperliquid Pairs
Any perp listed on Hyperliquid. Common ones:
- `BTC/USDC:USDC`
- `ETH/USDC:USDC`
- `SOL/USDC:USDC`
- `WIF/USDC:USDC`
- `HYPE/USDC:USDC`
- `ARB/USDC:USDC`

## Output Files

All saved to `projects/`:
| File | Contents |
|------|----------|
| `backtest_results_<PAIR>_<TF>.html` | Interactive chart — default params |
| `optimized_<PAIR>_<TF>.html` | Interactive chart — best params |
| `heatmap_<PAIR>_<TF>.html` | Parameter sensitivity heatmap |

## Interpreting Results

When showing results to the user, explain these key metrics:

| Metric | Good | Acceptable | Poor |
|--------|------|------------|------|
| Sharpe Ratio | >2.0 | 1.0–2.0 | <1.0 |
| Profit Factor | >1.8 | 1.2–1.8 | <1.2 |
| Win Rate | >55% | 45–55% | <45% |
| Max Drawdown | <10% | 10–20% | >20% |
| Return vs B&H | Beat by >10% | Beat | Underperform |

**Important:** Always compare Return vs Buy & Hold. A strategy that returns +5% when BTC gained +40% is actually bad.

## Workflow

### When user says "backtest [PAIR]"
1. Edit `SYMBOL` in the script to the requested pair
2. Run: `python projects/hyperliquid-ema-rsi-backtest.py`
3. Show results table
4. Explain key metrics
5. Offer to optimize

### When user says "optimize [PAIR]"
1. Edit `SYMBOL` in the script
2. Run: `python projects/hyperliquid-ema-rsi-backtest.py optimize`
3. Show best parameters found
4. Compare optimized vs default results
5. Offer to update Pine Script with new params

### When user says "update Pine Script with optimized params"
1. Open `projects/hyperliquid-ema-rsi-strategy.pine`
2. Update the default values in the input section to match optimized params
3. Remind user to re-paste into TradingView

## Current Best Known Parameters

All optimized on 1H, 2000 candles, Apr 2026.

### BTC 1H (baseline)
```
ema_fast  = 34
ema_mid   = 100
ema_slow  = 200
rsi_ob    = 60
rsi_os    = 30
sl_pct    = 1.0%
tp_pct    = 3.0%

Result: Sharpe 2.26, PF 1.98, Return +12.88% vs B&H -17.08%
```

### SUI 1H  ** BEST **
```
ema_fast  = 34      (same as BTC)
ema_mid   = 100     (same as BTC)
ema_slow  = 200
rsi_ob    = 60
rsi_os    = 30
sl_pct    = 1.5%    (slightly wider than BTC)
tp_pct    = 3.0%

Result: Sharpe 2.90, PF 2.85, Return +22.19% vs B&H -37.17%, Max DD -4.46%
```

### SOL 1H
```
ema_fast  = 21      (shorter — SOL is more volatile)
ema_mid   = 50
ema_slow  = 200
rsi_ob    = 60
rsi_os    = 40      (tighter OS filter)
sl_pct    = 2.0%
tp_pct    = 4.0%

Result: Sharpe 2.26, PF 2.32, Return +11.10% vs B&H -35.27%, Max DD -4.89%
Note: Only 9 trades — use with caution, may be over-fit on small sample.
```

### Multi-pair scan results (fixed BTC params, Apr 2026)
| Pair | Sharpe | PF | Return% |
|------|--------|----|---------|
| BTC  |  2.26  | 1.98 | +12.88% |
| SUI  |  2.00  | 2.31 | +16.3%  |
| SOL  |  1.44  | 1.67 | +8.2%   |
| INJ  |  1.18  | 1.45 | +5.1%   |
| ARB  |  1.04  | 1.31 | +3.8%   |

## Adding a New Strategy

To backtest a different strategy:
1. Create a new class inheriting from `Strategy` in the script
2. Implement `init()` for indicators and `next()` for logic
3. Change `EmaRsiStrategy` to your new class name in `run_backtest()` and `run_optimizer()`
4. Run normally

## Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError` | `python -m pip install <module>` |
| `0 trades` | Increase `cash=` value or use `size=0.99` in buy/sell |
| `ExchangeError` on pair | Check exact symbol name on Hyperliquid |
| Chart doesn't open | Find the `.html` file in `projects/` and open manually |
