"""
Multi-pair scanner — EMA 34/100/200 + RSI OB60/OS30 on Hyperliquid 1H
Runs the optimized BTC strategy across all major HL perp pairs and ranks by Sharpe.
"""

import ccxt
import pandas as pd
import numpy as np
import subprocess, os
from backtesting import Backtest, Strategy
from datetime import datetime

VERSION = "v1"

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
    ema_fast = 34;  ema_mid = 100;  ema_slow = 200
    rsi_period = 14;  rsi_ob = 60;  rsi_os = 30
    vol_mult = 1.1;  sl_pct = 1.0;  tp_pct = 3.0
    trade_longs = True;  trade_shorts = True

    def init(self):
        c = pd.Series(self.data.Close)
        v = pd.Series(self.data.Volume)
        self.ef     = self.I(ema, c, self.ema_fast,   name="EMA_F")
        self.em     = self.I(ema, c, self.ema_mid,    name="EMA_M")
        self.es     = self.I(ema, c, self.ema_slow,   name="EMA_S")
        self.rsi_i  = self.I(rsi, c, self.rsi_period, name="RSI")
        self.vol_ma = self.I(sma, v, 20,              name="VolMA")

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
        up   = rsi_prev < 50 <= rsi_now
        down = rsi_prev > 50 >= rsi_now

        sl_l = price * (1 - self.sl_pct / 100)
        tp_l = price * (1 + self.tp_pct / 100)
        sl_s = price * (1 + self.sl_pct / 100)
        tp_s = price * (1 - self.tp_pct / 100)

        if self.trade_longs  and not self.position.is_long  and bull and up   and rsi_now < self.rsi_ob and vol_ok:
            self.buy(sl=sl_l,  tp=tp_l,  size=0.99)
        if self.trade_shorts and not self.position.is_short and bear and down and rsi_now > self.rsi_os and vol_ok:
            self.sell(sl=sl_s, tp=tp_s,  size=0.99)

# ── helpers ───────────────────────────────────────────────────────────────────

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

def fetch(symbol, timeframe="1h", limit=2000):
    ex   = ccxt.hyperliquid({"enableRateLimit": True})
    data = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df   = pd.DataFrame(data, columns=["Date","Open","High","Low","Close","Volume"])
    df["Date"] = pd.to_datetime(df["Date"], unit="ms", utc=True)
    df.set_index("Date", inplace=True)
    return df

def run_pair(symbol, timeframe="1h", limit=2000):
    pair = symbol.split("/")[0]
    print(f"  {pair:<8}", end=" ", flush=True)
    try:
        df    = fetch(symbol, timeframe, limit)
        bt    = Backtest(df, EmaRsiStrategy, cash=1_000_000,
                         commission=0.0005, exclusive_orders=True, trade_on_close=True)
        stats = bt.run()

        pf      = stats.get("Profit Factor", 0) or 0
        sharpe  = stats.get("Sharpe Ratio",  0) or 0
        ret     = stats.get("Return [%]",    0) or 0
        bh      = stats.get("Buy & Hold Return [%]", 0) or 0
        dd      = stats.get("Max. Drawdown [%]", 0) or 0
        wr      = stats.get("Win Rate [%]",  0) or 0
        trades  = stats.get("# Trades",      0) or 0

        # save chart
        ts      = datetime.now().strftime("%Y%m%d_%H%M")
        pf_str  = f"_PF{pf:.2f}".replace(".", "_")
        chart   = f"projects/scan_{pair}_{timeframe}_{VERSION}{pf_str}_{ts}.html"
        title   = (f"HL EMA-RSI | {pair} {timeframe.upper()} | SCAN | "
                   f"EMA 34/100/200  RSI OB60/OS30  SL1% TP3%  PF {pf:.2f} | "
                   f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
        bt.plot(filename=chart, open_browser=False)
        inject_title(chart, title)

        flag = "**" if sharpe >= 2.0 else ("~" if sharpe >= 1.0 else " ")
        print(f"{trades:>7} {wr:>6.1f}% {ret:>8.2f}% {bh:>8.2f}% {dd:>8.2f}% {sharpe:>7.2f}{flag} {pf:>6.2f}  {chart}")

        return {
            "pair": pair, "trades": trades, "win_rate": wr,
            "return": ret, "bh": bh, "drawdown": dd,
            "sharpe": sharpe, "pf": pf, "chart": chart,
            "period": f"{df.index[0].date()} / {df.index[-1].date()}",
        }

    except Exception as e:
        print(f"  ERROR: {e}")
        return None

# ── pairs to scan ─────────────────────────────────────────────────────────────

PAIRS = [
    "BTC/USDC:USDC",
    "ETH/USDC:USDC",
    "SOL/USDC:USDC",
    "XRP/USDC:USDC",
    "DOGE/USDC:USDC",
    "AVAX/USDC:USDC",
    "LINK/USDC:USDC",
    "ARB/USDC:USDC",
    "WIF/USDC:USDC",
    "SUI/USDC:USDC",
    "TIA/USDC:USDC",
    "INJ/USDC:USDC",
]

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    TF    = "1h"
    LIMIT = 2000

    print("=" * 100)
    print(f"  HYPERLIQUID MULTI-PAIR SCAN  |  EMA 34/100/200 + RSI OB60/OS30  |  {TF.upper()}  |  {len(PAIRS)} pairs")
    print("=" * 100)
    print(f"  {'PAIR':<8} {'Trades':>7} {'Win%':>7} {'Return%':>9} {'B&H%':>9} {'MaxDD%':>9} {'Sharpe':>8} {'PF':>6}  Chart")
    print("  " + "-" * 96)

    results = []
    for symbol in PAIRS:
        r = run_pair(symbol, TF, LIMIT)
        if r:
            results.append(r)

    # rank by Sharpe
    results.sort(key=lambda x: x["sharpe"], reverse=True)

    print("\n" + "=" * 100)
    print("  RANKED BY SHARPE  (** = Sharpe >= 2.0,  ~ = Sharpe >= 1.0)")
    print("=" * 100)
    print(f"  {'#':<3} {'PAIR':<8} {'Sharpe':>8} {'PF':>6} {'Return%':>9} {'B&H%':>9} {'MaxDD%':>9} {'Win%':>7} {'Trades':>7}")
    print("  " + "-" * 72)
    for i, r in enumerate(results, 1):
        flag = "**" if r["sharpe"] >= 2.0 else ("~" if r["sharpe"] >= 1.0 else " ")
        print(f"  {i:<3} {r['pair']:<8} {r['sharpe']:>7.2f}{flag} {r['pf']:>6.2f} {r['return']:>9.2f}% {r['bh']:>9.2f}% {r['drawdown']:>9.2f}% {r['win_rate']:>7.1f}% {r['trades']:>7}")
    print("=" * 100)

    # open top 3 charts
    top3 = [r for r in results if r["sharpe"] >= 1.0][:3]
    if top3:
        print(f"\n  Opening top {len(top3)} charts (Sharpe >= 1.0)...")
        for r in top3:
            subprocess.Popen(["cmd", "/c", "start", "", os.path.abspath(r["chart"])])
