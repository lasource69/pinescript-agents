"""
================================================================================
HYPERLIQUID EMA-RSI PERP STRATEGY — Backtest  v2
================================================================================
Exchange  : Hyperliquid (data fetched via ccxt)
Framework : backtesting.py + pure pandas indicators
Author    : lasource69

Changes v2:
  - SL/TP now ATR-based (matches Pine Script exactly)
  - fetch() paginates to support 6-12 months of data
  - Optimizer grid uses sl_atr / tp_atr multipliers

Run:
    python projects/hyperliquid-ema-rsi-backtest.py
    python projects/hyperliquid-ema-rsi-backtest.py optimize
================================================================================
"""

import ccxt, sys, time
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from datetime import datetime

VERSION = "v2"

# ── chart helpers ─────────────────────────────────────────────────────────────

def chart_title(symbol, timeframe, mode="backtest", pf=None, best=None):
    pair  = symbol.split("/")[0]
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M")
    label = "OPTIMIZED" if mode == "optimized" else "BACKTEST"
    pf_str = f"  PF {pf:.2f}" if pf is not None else ""
    if best:
        params = (f"EMA {best['ema_fast']}/{best['ema_mid']}/{best['ema_slow']}  "
                  f"RSI OB{best['rsi_ob']}/OS{best['rsi_os']}  "
                  f"SL{best['sl_atr']}xATR TP{best['tp_atr']}xATR")
    else:
        params = "EMA 34/100/200  RSI OB60/OS30  SL1.5xATR TP3xATR"
    return f"HL EMA-RSI {VERSION} | {pair} {timeframe.upper()} | {label} | {params}{pf_str} | {ts}"

def chart_filename(symbol, timeframe, mode="backtest", pf=None):
    pair   = symbol.split("/")[0]
    ts     = datetime.now().strftime("%Y%m%d_%H%M")
    pf_str = f"_PF{pf:.2f}".replace(".", "_") if pf is not None else ""
    return f"projects/{mode}_{pair}_{timeframe}_{VERSION}{pf_str}_{ts}.html"

def inject_title(filepath, title):
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()
    banner = (
        f'<div style="background:#1a1a2e;color:#00d4ff;font-family:monospace;'
        f'font-size:13px;padding:8px 16px;border-bottom:1px solid #00d4ff;">'
        f'{title}</div>'
    )
    html = html.replace("<body>", f"<body>{banner}", 1)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

def save_chart(bt, filepath, title, open_browser=True):
    bt.plot(filename=filepath, open_browser=False)
    inject_title(filepath, title)
    if open_browser:
        import subprocess, os
        subprocess.Popen(["cmd", "/c", "start", "", os.path.abspath(filepath)])

# ── indicators ────────────────────────────────────────────────────────────────

def ema(series: pd.Series, period: int) -> np.ndarray:
    return series.ewm(span=period, adjust=False).mean().values

def rsi(series: pd.Series, period: int) -> np.ndarray:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).values

def sma(series: pd.Series, period: int) -> np.ndarray:
    return series.rolling(period).mean().values

def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> np.ndarray:
    """Average True Range — matches Pine Script ta.atr()"""
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean().values

# ── fetch with pagination ─────────────────────────────────────────────────────

def fetch(symbol, timeframe="1h", months=6):
    """
    Fetch OHLCV from Hyperliquid, paginating to cover `months` of history.
    HL returns max ~2000 candles per request, so we walk backwards in time.
    """
    tf_minutes = {"1m":1,"5m":5,"15m":15,"30m":30,"1h":60,"4h":240,"1d":1440}
    mins_per_candle = tf_minutes.get(timeframe, 60)
    candles_needed  = int(months * 30 * 24 * 60 / mins_per_candle)
    since_ms        = int((time.time() - months * 30 * 24 * 3600) * 1000)

    ex       = ccxt.hyperliquid({"enableRateLimit": True})
    all_rows = []
    current  = since_ms

    print(f"  Fetching ~{candles_needed} candles ({months}mo) for {symbol} [{timeframe}]...")

    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=current, limit=2000)
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < 2000:
            break
        current = batch[-1][0] + 1   # next ms after last candle

    df = pd.DataFrame(all_rows, columns=["Date","Open","High","Low","Close","Volume"])
    df["Date"] = pd.to_datetime(df["Date"], unit="ms", utc=True)
    df.set_index("Date", inplace=True)
    df = df[~df.index.duplicated(keep="first")].sort_index()

    print(f"  Got {len(df)} candles — {df.index[0].date()} to {df.index[-1].date()}")
    return df

# ── strategy ──────────────────────────────────────────────────────────────────

class EmaRsiStrategy(Strategy):
    """
    EMA Trend + RSI Entry + Volume + ATR-based SL/TP
    Matches Pine Script hyperliquid-ema-rsi-strategy.pine exactly.
    """
    ema_fast   = 34
    ema_mid    = 100
    ema_slow   = 200
    rsi_period = 14
    rsi_ob     = 60
    rsi_os     = 30
    vol_mult   = 1.1
    atr_period = 14
    sl_atr     = 1.5    # SL = entry ± ATR × sl_atr
    tp_atr     = 3.0    # TP = entry ± ATR × tp_atr
    trade_longs  = True
    trade_shorts = True

    def init(self):
        c = pd.Series(self.data.Close)
        h = pd.Series(self.data.High)
        l = pd.Series(self.data.Low)
        v = pd.Series(self.data.Volume)

        self.ef     = self.I(ema, c, self.ema_fast,   name="EMA_F")
        self.em     = self.I(ema, c, self.ema_mid,    name="EMA_M")
        self.es     = self.I(ema, c, self.ema_slow,   name="EMA_S")
        self.rsi_i  = self.I(rsi, c, self.rsi_period, name="RSI")
        self.vol_ma = self.I(sma, v, 20,              name="VolMA")
        self.atr_i  = self.I(atr, h, l, c, self.atr_period, name="ATR")

    def next(self):
        import math
        ef, em, es  = self.ef[-1], self.em[-1], self.es[-1]
        rsi_now     = self.rsi_i[-1]
        rsi_prev    = self.rsi_i[-2]
        price       = self.data.Close[-1]
        atr_val     = self.atr_i[-1]
        vol_ok      = self.data.Volume[-1] > self.vol_ma[-1] * self.vol_mult

        if any(math.isnan(x) for x in [ef, em, es, rsi_now, rsi_prev, self.vol_ma[-1], atr_val]):
            return

        bull = ef > em and em > es and price > ef
        bear = ef < em and em < es and price < ef
        rsi_cross_up   = rsi_prev < 50 <= rsi_now
        rsi_cross_down = rsi_prev > 50 >= rsi_now

        sl_long  = price - atr_val * self.sl_atr
        tp_long  = price + atr_val * self.tp_atr
        sl_short = price + atr_val * self.sl_atr
        tp_short = price - atr_val * self.tp_atr

        if self.trade_longs and not self.position.is_long and bull and rsi_cross_up and rsi_now < self.rsi_ob and vol_ok:
            self.buy(sl=sl_long, tp=tp_long, size=0.99)

        if self.trade_shorts and not self.position.is_short and bear and rsi_cross_down and rsi_now > self.rsi_os and vol_ok:
            self.sell(sl=sl_short, tp=tp_short, size=0.99)

# ── backtest ──────────────────────────────────────────────────────────────────

def run_backtest(symbol="BTC/USDC:USDC", timeframe="1h", months=6):
    print("=" * 65)
    print(f"  HYPERLIQUID EMA-RSI BACKTEST {VERSION}")
    print(f"  Symbol    : {symbol}")
    print(f"  Timeframe : {timeframe}")
    print(f"  History   : {months} months")
    print("=" * 65)

    df = fetch(symbol, timeframe, months)
    bt = Backtest(df, EmaRsiStrategy, cash=1_000_000,
                  commission=0.0005, exclusive_orders=True, trade_on_close=True)
    stats = bt.run()

    print("\n" + "=" * 65)
    print("  RESULTS")
    print("=" * 65)
    for k in ["Start","End","# Trades","Win Rate [%]","Return [%]",
              "Buy & Hold Return [%]","Max. Drawdown [%]",
              "Sharpe Ratio","Profit Factor","Avg. Trade [%]"]:
        if k in stats:
            print(f"  {k:<28}: {stats[k]}")
    print("=" * 65)

    pf         = stats.get("Profit Factor", None)
    chart_file = chart_filename(symbol, timeframe, "backtest", pf)
    save_chart(bt, chart_file, chart_title(symbol, timeframe, "backtest", pf))
    print(f"\n  Chart saved: {chart_file}")
    return stats, bt

# ── optimizer ─────────────────────────────────────────────────────────────────

PARAM_KEYS = ["ema_fast","ema_mid","ema_slow","rsi_ob","rsi_os","sl_atr","tp_atr"]

def run_optimizer(symbol="BTC/USDC:USDC", timeframe="1h", months=6):
    print("=" * 65)
    print(f"  HYPERLIQUID EMA-RSI OPTIMIZER {VERSION}")
    print(f"  Symbol    : {symbol}")
    print(f"  Timeframe : {timeframe}")
    print(f"  History   : {months} months")
    print(f"  Metric    : Sharpe Ratio")
    print("=" * 65)

    df = fetch(symbol, timeframe, months)
    bt = Backtest(df, EmaRsiStrategy, cash=1_000_000,
                  commission=0.0005, exclusive_orders=True, trade_on_close=True)

    print("\n  Running grid search (432 combos)...\n")

    stats, heatmap = bt.optimize(
        ema_fast = [14, 21, 34],
        ema_mid  = [50, 100],
        ema_slow = [200],
        rsi_ob   = [60, 65, 70],
        rsi_os   = [30, 35, 40],
        sl_atr   = [1.0, 1.5, 2.0],
        tp_atr   = [2.0, 3.0, 4.0],
        constraint = lambda p: (
            p.ema_fast < p.ema_mid and
            p.ema_mid  < p.ema_slow and
            p.tp_atr   > p.sl_atr   and
            p.rsi_ob   > p.rsi_os
        ),
        maximize       = "Sharpe Ratio",
        return_heatmap = True,
    )

    best = {k: stats._strategy.__dict__[k] for k in PARAM_KEYS}
    pf     = stats.get("Profit Factor", 0) or 0
    sharpe = stats.get("Sharpe Ratio",  0) or 0
    ret    = stats.get("Return [%]",    0) or 0
    bh     = stats.get("Buy & Hold Return [%]", 0) or 0
    dd     = stats.get("Max. Drawdown [%]", 0) or 0
    wr     = stats.get("Win Rate [%]",  0) or 0
    trades = stats.get("# Trades",      0) or 0

    print("\n" + "=" * 65)
    print("  BEST PARAMETERS")
    print("=" * 65)
    for k, v in best.items():
        print(f"  {k:<12}: {v}")
    print(f"\n  Trades     : {trades}")
    print(f"  Win Rate   : {wr:.1f}%")
    print(f"  Return     : {ret:.2f}%")
    print(f"  B&H        : {bh:.2f}%")
    print(f"  Max DD     : {dd:.2f}%")
    print(f"  Sharpe     : {sharpe:.2f}")
    print(f"  PF         : {pf:.2f}")
    print("=" * 65)

    bt.run(**best)
    chart_file = chart_filename(symbol, timeframe, "optimized", pf)
    save_chart(bt, chart_file, chart_title(symbol, timeframe, "optimized", pf, best))
    print(f"\n  Chart: {chart_file}")

    try:
        from backtesting.lib import plot_heatmaps
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        pair = symbol.split("/")[0]
        hm = f"projects/heatmap_{pair}_{timeframe}_{VERSION}_{ts}.html"
        plot_heatmaps(heatmap, agg="mean", filename=hm, open_browser=False)
        print(f"  Heatmap: {hm}")
    except Exception:
        pass

    return stats, heatmap

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SYMBOL    = "BTC/USDC:USDC"
    TIMEFRAME = "1h"
    MONTHS    = 6       # 6 months of history (~4380 candles on 1H)

    mode = sys.argv[1] if len(sys.argv) > 1 else "backtest"

    if mode == "optimize":
        run_optimizer(symbol=SYMBOL, timeframe=TIMEFRAME, months=MONTHS)
    else:
        run_backtest(symbol=SYMBOL, timeframe=TIMEFRAME, months=MONTHS)
