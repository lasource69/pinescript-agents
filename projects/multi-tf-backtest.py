"""
Multi-timeframe backtest runner — BTC/USDC:USDC
Tests 15m, 30m, 4h with optimized BTC params and prints comparison table.
"""

import ccxt
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from datetime import datetime

VERSION = "v1"

def chart_title(symbol, timeframe, pf=None):
    pair   = symbol.split("/")[0]
    ts     = datetime.now().strftime("%Y-%m-%d %H:%M")
    pf_str = f"  PF {pf:.2f}" if pf is not None else ""
    return f"HL EMA-RSI | {pair} {timeframe.upper()} | BACKTEST | EMA 34/100/200  RSI OB60/OS30  SL1% TP3%{pf_str} | {ts}"

def chart_filename(symbol, timeframe, pf=None):
    pair   = symbol.split("/")[0]
    ts     = datetime.now().strftime("%Y%m%d_%H%M")
    pf_str = f"_PF{pf:.2f}".replace(".", "_") if pf is not None else ""
    return f"projects/backtest_{pair}_{timeframe}_{VERSION}{pf_str}_{ts}.html"

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

# ── indicators ────────────────────────────────────────────────────────────────

def ema(series, period):
    return series.ewm(span=period, adjust=False).mean().values

def rsi(series, period):
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).values

def sma(series, period):
    return series.rolling(period).mean().values

# ── strategy ──────────────────────────────────────────────────────────────────

class EmaRsiStrategy(Strategy):
    ema_fast    = 34
    ema_mid     = 100
    ema_slow    = 200
    rsi_period  = 14
    rsi_ob      = 60
    rsi_os      = 30
    vol_mult    = 1.1
    sl_pct      = 1.0
    tp_pct      = 3.0
    trade_longs  = True
    trade_shorts = True

    def init(self):
        c = pd.Series(self.data.Close)
        v = pd.Series(self.data.Volume)
        self.ef     = self.I(ema, c, self.ema_fast,  name="EMA_F")
        self.em     = self.I(ema, c, self.ema_mid,   name="EMA_M")
        self.es     = self.I(ema, c, self.ema_slow,  name="EMA_S")
        self.rsi_i  = self.I(rsi, c, self.rsi_period,name="RSI")
        self.vol_ma = self.I(sma, v, 20,             name="VolMA")

    def next(self):
        import math
        ef, em, es   = self.ef[-1], self.em[-1], self.es[-1]
        rsi_now      = self.rsi_i[-1]
        rsi_prev     = self.rsi_i[-2]
        price        = self.data.Close[-1]
        vol_ok       = self.data.Volume[-1] > self.vol_ma[-1] * self.vol_mult

        if any(math.isnan(x) for x in [ef, em, es, rsi_now, rsi_prev, self.vol_ma[-1]]):
            return

        bull = ef > em and em > es and price > ef
        bear = ef < em and em < es and price < ef
        rsi_up   = rsi_prev < 50 <= rsi_now
        rsi_down = rsi_prev > 50 >= rsi_now

        sl_l = price * (1 - self.sl_pct / 100)
        tp_l = price * (1 + self.tp_pct / 100)
        sl_s = price * (1 + self.sl_pct / 100)
        tp_s = price * (1 - self.tp_pct / 100)

        if self.trade_longs and not self.position.is_long and bull and rsi_up and rsi_now < self.rsi_ob and vol_ok:
            self.buy(sl=sl_l, tp=tp_l, size=0.99)

        if self.trade_shorts and not self.position.is_short and bear and rsi_down and rsi_now > self.rsi_os and vol_ok:
            self.sell(sl=sl_s, tp=tp_s, size=0.99)

# ── fetch ─────────────────────────────────────────────────────────────────────

def fetch(symbol, timeframe, limit):
    ex   = ccxt.hyperliquid({"enableRateLimit": True})
    data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df   = pd.DataFrame(data, columns=["Date","Open","High","Low","Close","Volume"])
    df["Date"] = pd.to_datetime(df["Date"], unit="ms", utc=True)
    df.set_index("Date", inplace=True)
    return df

# ── run one tf ────────────────────────────────────────────────────────────────

def run_tf(symbol, timeframe, limit):
    print(f"  [{timeframe}] fetching {limit} candles...", flush=True)
    df = fetch(symbol, timeframe, limit)
    print(f"  [{timeframe}] {df.index[0].date()} / {df.index[-1].date()}")

    bt    = Backtest(df, EmaRsiStrategy, cash=1_000_000,
                     commission=0.0005, exclusive_orders=True, trade_on_close=True)
    stats = bt.run()

    # save chart silently
    pf    = stats.get("Profit Factor", None)
    chart = chart_filename(symbol, timeframe, pf)
    bt.plot(filename=chart, open_browser=False)
    inject_title(chart, chart_title(symbol, timeframe, pf))

    return {
        "TF"          : timeframe,
        "Candles"     : len(df),
        "Period"      : f"{df.index[0].date()} / {df.index[-1].date()}",
        "Trades"      : stats["# Trades"],
        "Win %"       : round(stats["Win Rate [%]"], 1),
        "Return %"    : round(stats["Return [%]"], 2),
        "B&H %"       : round(stats["Buy & Hold Return [%]"], 2),
        "Max DD %"    : round(stats["Max. Drawdown [%]"], 2),
        "Sharpe"      : round(stats["Sharpe Ratio"], 2),
        "PF"          : round(stats["Profit Factor"], 2),
        "Avg Trade %"  : round(stats["Avg. Trade [%]"], 3),
        "Chart"       : chart,
    }

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    SYMBOL = "BTC/USDC:USDC"

    # candle limits per timeframe (aim for ~3 months of data each)
    timeframes = [
        ("15m", 5000),
        ("30m", 3000),
        ("4h",  1000),
    ]

    print("=" * 65)
    print("  BTC MULTI-TIMEFRAME BACKTEST  |  EMA 34/100/200 + RSI 60/30")
    print("=" * 65)

    results = []
    for tf, limit in timeframes:
        try:
            results.append(run_tf(SYMBOL, tf, limit))
        except Exception as e:
            print(f"  [{tf}] ERROR: {e}")

    # ── comparison table ──────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("  COMPARISON TABLE")
    print("=" * 65)
    print(f"  {'TF':<6} {'Trades':>7} {'Win%':>6} {'Return%':>9} {'B&H%':>8} {'MaxDD%':>8} {'Sharpe':>8} {'PF':>6}")
    print("  " + "-" * 62)
    for r in results:
        sharpe_flag = "★" if r["Sharpe"] >= 2.0 else " "
        print(f"  {r['TF']:<6} {r['Trades']:>7} {r['Win %']:>6} {r['Return %']:>9} {r['B&H %']:>8} {r['Max DD %']:>8} {r['Sharpe']:>7}{sharpe_flag} {r['PF']:>6}")
    print("=" * 65)

    print("\n  Charts saved (open manually):")
    for r in results:
        print(f"    {r['TF']} to {r['Chart']}")

    # open best Sharpe chart
    best = max(results, key=lambda x: x["Sharpe"] if not (x["Sharpe"] != x["Sharpe"]) else -99)
    print(f"\n  Opening best chart: {best['TF']} (Sharpe {best['Sharpe']})")
    import subprocess, os
    subprocess.Popen(["cmd", "/c", "start", "", os.path.abspath(best["Chart"])])
