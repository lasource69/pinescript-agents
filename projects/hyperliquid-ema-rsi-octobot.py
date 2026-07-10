"""
================================================================================
HYPERLIQUID EMA-RSI PERP STRATEGY — OctoBot Script
================================================================================
Exchange  : Hyperliquid (native OctoBot support)
Framework : OctoBot-Script (backtesting + live)
Author    : lasource69

Install:
    pip install octobot-script

Run backtest:
    python hyperliquid-ema-rsi-octobot.py

Docs: https://www.octobot.cloud/en/guides/octobot-script-docs/strategies
================================================================================
"""

import asyncio
import tulipy
import numpy as np
import octobot_script as op

# ============================================================================
# STRATEGY CONFIGURATION
# ============================================================================

config = {
    # EMAs
    "ema_fast":         21,
    "ema_mid":          50,
    "ema_slow":         200,

    # RSI
    "rsi_period":       14,
    "rsi_midline":      50,
    "rsi_overbought":   65,    # avoid longs above this
    "rsi_oversold":     35,    # avoid shorts below this

    # Volume filter
    "vol_filter":       True,
    "vol_period":       20,
    "vol_multiplier":   1.1,   # volume must be X times the average

    # Risk management (% offset from entry price)
    "stop_loss":        "-1.5%",   # SL below entry for longs (above for shorts)
    "take_profit":      "3.0%",    # TP above entry for longs (below for shorts)
    "position_size":    "10%",     # % of equity per trade

    # Trade direction: "long", "short", "both"
    "trade_direction":  "both",

    # Symbol info (for display only)
    "symbol":           "BTC/USDT:USDT",
    "exchange":         "Hyperliquid",
}

# ============================================================================
# HELPER: safe indicator — returns None if not enough data
# ============================================================================

def safe_ema(data: np.ndarray, period: int):
    if len(data) <= period:
        return None
    return tulipy.ema(data, period=period)

def safe_rsi(data: np.ndarray, period: int):
    if len(data) <= period:
        return None
    return tulipy.rsi(data, period=period)

def safe_sma(data: np.ndarray, period: int):
    if len(data) <= period:
        return None
    return tulipy.sma(data, period=period)

# ============================================================================
# STRATEGY (iterative — works for backtesting AND live trading)
# ============================================================================

async def strategy(ctx):
    """
    EMA Trend + RSI Entry + Volume Confirmation
    ------------------------------------------
    LONG  : EMA21 > EMA50 > EMA200, price > EMA21, RSI crosses 50 upward, vol ok
    SHORT : EMA21 < EMA50 < EMA200, price < EMA21, RSI crosses 50 downward, vol ok
    EXIT  : ATR-based SL/TP set at entry via stop_loss / take_profit offsets
    """

    c = config

    # --- Price + Volume data ---
    closes  = await op.Close(ctx)
    volumes = await op.Volume(ctx)

    min_bars = c["ema_slow"] + c["rsi_period"] + 5
    if len(closes) < min_bars:
        return  # not enough history yet

    closes_np  = np.array(closes,  dtype=np.float64)
    volumes_np = np.array(volumes, dtype=np.float64)

    # --- EMAs ---
    ema_fast = safe_ema(closes_np, c["ema_fast"])
    ema_mid  = safe_ema(closes_np, c["ema_mid"])
    ema_slow = safe_ema(closes_np, c["ema_slow"])

    if ema_fast is None or ema_mid is None or ema_slow is None:
        return

    # Latest values
    ef  = ema_fast[-1]
    em  = ema_mid[-1]
    es  = ema_slow[-1]
    price = closes_np[-1]

    # --- RSI ---
    rsi_vals = safe_rsi(closes_np, c["rsi_period"])
    if rsi_vals is None or len(rsi_vals) < 2:
        return

    rsi_now  = rsi_vals[-1]
    rsi_prev = rsi_vals[-2]

    # RSI cross: current candle RSI crossed the midline
    rsi_cross_up   = rsi_prev < c["rsi_midline"] and rsi_now >= c["rsi_midline"]
    rsi_cross_down = rsi_prev > c["rsi_midline"] and rsi_now <= c["rsi_midline"]

    # --- Volume filter ---
    vol_ok = True
    if c["vol_filter"]:
        vol_ma = safe_sma(volumes_np, c["vol_period"])
        if vol_ma is not None:
            vol_ok = volumes_np[-1] > vol_ma[-1] * c["vol_multiplier"]

    # --- Trend conditions ---
    bull_trend = ef > em and em > es and price > ef
    bear_trend = ef < em and em < es and price < ef

    # --- Entry signals ---
    long_signal  = (bull_trend and
                    rsi_cross_up and
                    rsi_now < c["rsi_overbought"] and
                    vol_ok and
                    c["trade_direction"] in ("long", "both"))

    short_signal = (bear_trend and
                    rsi_cross_down and
                    rsi_now > c["rsi_oversold"] and
                    vol_ok and
                    c["trade_direction"] in ("short", "both"))

    # --- Execute orders ---
    if long_signal:
        await op.market(
            ctx,
            "buy",
            amount=c["position_size"],
            stop_loss_offset=c["stop_loss"],
            take_profit_offset=c["take_profit"],
        )

    if short_signal:
        await op.market(
            ctx,
            "sell",
            amount=c["position_size"],
            stop_loss_offset=c["stop_loss"],   # OctoBot flips SL/TP for shorts
            take_profit_offset=c["take_profit"],
        )

    # --- Plot indicators for backtest report ---
    times = await op.Time(ctx, use_close_time=True)
    times_np = np.array(times)

    # Align lengths (EMA arrays are shorter due to period offset)
    fast_delta = len(closes_np) - len(ema_fast)
    mid_delta  = len(closes_np) - len(ema_mid)
    slow_delta = len(closes_np) - len(ema_slow)
    rsi_delta  = len(closes_np) - len(rsi_vals)

    await op.plot_indicator(ctx, "EMA 21",  times_np[fast_delta:], ema_fast)
    await op.plot_indicator(ctx, "EMA 50",  times_np[mid_delta:],  ema_mid)
    await op.plot_indicator(ctx, "EMA 200", times_np[slow_delta:], ema_slow)
    await op.plot_indicator(ctx, "RSI",     times_np[rsi_delta:],  rsi_vals)


# ============================================================================
# BACKTEST RUNNER
# ============================================================================

async def run_backtest():
    """
    Fetch historical data from Hyperliquid and run the backtest.

    Data options:
      - op.get_data(exchange, symbol, timeframe, start, end)
      - timeframe: "1m" "5m" "15m" "1h" "4h" "1d"
      - exchange:  "hyperliquid" (native support)
    """

    print("=" * 60)
    print("  HYPERLIQUID EMA-RSI BACKTEST")
    print(f"  Symbol    : {config['symbol']}")
    print(f"  Exchange  : {config['exchange']}")
    print(f"  Direction : {config['trade_direction'].upper()}")
    print(f"  SL / TP   : {config['stop_loss']} / {config['take_profit']}")
    print("=" * 60)

    # Fetch 2 years of 1H candles from Hyperliquid
    data = await op.get_data(
        exchange="hyperliquid",
        symbol=config["symbol"],
        time_frame="1h",
        start_timestamp=op.timestamp_util.get_timestamp("2024-01-01"),
        end_timestamp=op.timestamp_util.get_timestamp("2026-01-01"),
    )

    # Run backtest
    result = await op.run(data, strategy, config)

    # Print results
    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Total trades    : {result.get('total_trades', 'N/A')}")
    print(f"  Win rate        : {result.get('win_rate', 'N/A')}")
    print(f"  Profit factor   : {result.get('profit_factor', 'N/A')}")
    print(f"  Net profit      : {result.get('net_profit', 'N/A')}")
    print(f"  Max drawdown    : {result.get('max_drawdown', 'N/A')}")
    print(f"  Sharpe ratio    : {result.get('sharpe_ratio', 'N/A')}")
    print("=" * 60)

    return result


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    asyncio.run(run_backtest())
