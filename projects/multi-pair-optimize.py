"""
Multi-pair optimizer v2 — ATR-based SL/TP, 6-month history, grid search per pair.
"""

import ccxt, sys, os, time, subprocess
import pandas as pd
import numpy as np
from backtesting import Backtest, Strategy
from backtesting.lib import plot_heatmaps
from datetime import datetime

VERSION = "v2"

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

def atr(high, low, close, period):
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean().values

# ── strategy ──────────────────────────────────────────────────────────────────

class EmaRsiStrategy(Strategy):
    ema_fast = 34;  ema_mid = 100;  ema_slow = 200
    rsi_period = 14;  rsi_ob = 60;  rsi_os = 30
    vol_mult = 1.1;  atr_period = 14
    sl_atr = 1.5;  tp_atr = 3.0          # ATR multipliers — matches Pine Script
    trade_longs = True;  trade_shorts = True

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
        ef, em, es = self.ef[-1], self.em[-1], self.es[-1]
        rsi_now    = self.rsi_i[-1]
        rsi_prev   = self.rsi_i[-2]
        price      = self.data.Close[-1]
        atr_val    = self.atr_i[-1]
        vol_ok     = self.data.Volume[-1] > self.vol_ma[-1] * self.vol_mult

        if any(math.isnan(x) for x in [ef, em, es, rsi_now, rsi_prev, self.vol_ma[-1], atr_val]):
            return

        bull = ef > em and em > es and price > ef
        bear = ef < em and em < es and price < ef
        up   = rsi_prev < 50 <= rsi_now
        down = rsi_prev > 50 >= rsi_now

        sl_l = price - atr_val * self.sl_atr
        tp_l = price + atr_val * self.tp_atr
        sl_s = price + atr_val * self.sl_atr
        tp_s = price - atr_val * self.tp_atr

        if self.trade_longs  and not self.position.is_long  and bull and up   and rsi_now < self.rsi_ob and vol_ok:
            self.buy(sl=sl_l, tp=tp_l, size=0.99)
        if self.trade_shorts and not self.position.is_short and bear and down and rsi_now > self.rsi_os and vol_ok:
            self.sell(sl=sl_s, tp=tp_s, size=0.99)

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

def fetch(symbol, timeframe="1h", months=6):
    tf_minutes = {"1m":1,"5m":5,"15m":15,"30m":30,"1h":60,"4h":240,"1d":1440}
    since_ms   = int((time.time() - months * 30 * 24 * 3600) * 1000)
    ex         = ccxt.hyperliquid({"enableRateLimit": True})
    all_rows   = []
    current    = since_ms

    while True:
        batch = ex.fetch_ohlcv(symbol, timeframe=timeframe, since=current, limit=2000)
        if not batch:
            break
        all_rows.extend(batch)
        if len(batch) < 2000:
            break
        current = batch[-1][0] + 1

    df = pd.DataFrame(all_rows, columns=["Date","Open","High","Low","Close","Volume"])
    df["Date"] = pd.to_datetime(df["Date"], unit="ms", utc=True)
    df.set_index("Date", inplace=True)
    return df[~df.index.duplicated(keep="first")].sort_index()

# ── optimizer ─────────────────────────────────────────────────────────────────

PARAM_KEYS = ["ema_fast","ema_mid","ema_slow","rsi_ob","rsi_os","sl_atr","tp_atr"]

def optimize_pair(symbol, timeframe="1h", months=6):
    pair = symbol.split("/")[0]
    print(f"\n{'='*65}")
    print(f"  OPTIMIZING {pair} {timeframe.upper()}  |  432 combinations  |  {months}mo history")
    print(f"{'='*65}")

    df = fetch(symbol, timeframe, months)
    print(f"  Data: {df.index[0].date()} / {df.index[-1].date()}  ({len(df)} candles)")

    bt = Backtest(df, EmaRsiStrategy, cash=1_000_000,
                  commission=0.0005, exclusive_orders=True, trade_on_close=True)

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

    best   = {k: stats._strategy.__dict__[k] for k in PARAM_KEYS}
    pf     = stats.get("Profit Factor", 0) or 0
    sharpe = stats.get("Sharpe Ratio",  0) or 0
    ret    = stats.get("Return [%]",    0) or 0
    bh     = stats.get("Buy & Hold Return [%]", 0) or 0
    dd     = stats.get("Max. Drawdown [%]", 0) or 0
    wr     = stats.get("Win Rate [%]",  0) or 0
    trades = stats.get("# Trades",      0) or 0

    ts        = datetime.now().strftime("%Y%m%d_%H%M")
    pf_str    = f"_PF{pf:.2f}".replace(".", "_")
    chart     = f"projects/optimized_{pair}_{timeframe}_{VERSION}{pf_str}_{ts}.html"
    title     = (f"HL EMA-RSI {VERSION} | {pair} {timeframe.upper()} | OPTIMIZED | "
                 f"EMA {best['ema_fast']}/{best['ema_mid']}/{best['ema_slow']}  "
                 f"RSI OB{best['rsi_ob']}/OS{best['rsi_os']}  "
                 f"SL{best['sl_atr']}xATR TP{best['tp_atr']}xATR  "
                 f"PF {pf:.2f} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    bt.run(**best)
    bt.plot(filename=chart, open_browser=False)
    inject_title(chart, title)

    heatmap_file = f"projects/heatmap_{pair}_{timeframe}_{VERSION}_{ts}.html"
    try:
        plot_heatmaps(heatmap, agg="mean", filename=heatmap_file, open_browser=False)
    except Exception:
        pass

    print(f"\n  BEST PARAMS:")
    for k, v in best.items():
        print(f"    {k:<12}: {v}")
    print(f"\n  RESULTS:")
    print(f"    Trades     : {trades}")
    print(f"    Win Rate   : {wr:.1f}%")
    print(f"    Return     : {ret:.2f}%")
    print(f"    B&H        : {bh:.2f}%")
    print(f"    Max DD     : {dd:.2f}%")
    print(f"    Sharpe     : {sharpe:.2f}")
    print(f"    PF         : {pf:.2f}")
    print(f"\n  Chart  : {chart}")
    print(f"  Heatmap: {heatmap_file}")

    subprocess.Popen(["cmd", "/c", "start", "", os.path.abspath(chart)])

    return {
        "pair": pair, "best": best,
        "sharpe": sharpe, "pf": pf, "return": ret,
        "bh": bh, "drawdown": dd, "win_rate": wr, "trades": trades,
        "chart": chart,
    }

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    PAIRS     = ["BTC/USDC:USDC", "SUI/USDC:USDC", "SOL/USDC:USDC"]
    TIMEFRAME = "1h"
    MONTHS    = 6

    print("=" * 65)
    print(f"  MULTI-PAIR OPTIMIZER {VERSION}  |  {' + '.join(p.split('/')[0] for p in PAIRS)}  |  {TIMEFRAME.upper()}  |  {MONTHS}mo")
    print("=" * 65)

    results = []
    for symbol in PAIRS:
        results.append(optimize_pair(symbol, TIMEFRAME, MONTHS))

    # ── comparison ────────────────────────────────────────────────────────────
    print(f"\n\n{'='*75}")
    print(f"  FINAL COMPARISON  ({MONTHS}mo ATR-based SL/TP)")
    print(f"{'='*75}")
    print(f"  {'PAIR':<6} {'EMA':<14} {'OB/OS':<8} {'SL/TP(ATR)':<12} {'Sharpe':>7} {'PF':>6} {'Ret%':>8} {'DD%':>7}")
    print("  " + "-" * 68)

    for r in results:
        b = r["best"]
        ema_str = f"{b['ema_fast']}/{b['ema_mid']}/{b['ema_slow']}"
        ob_str  = f"{b['rsi_ob']}/{b['rsi_os']}"
        sl_str  = f"{b['sl_atr']}/{b['tp_atr']}x"
        flag    = "  ** GOOD" if r["pf"] >= 1.5 else ("  ~ marginal" if r["pf"] >= 1.0 else "  !! FAIL")
        print(f"  {r['pair']:<6} {ema_str:<14} {ob_str:<8} {sl_str:<12} {r['sharpe']:>7.2f} {r['pf']:>6.2f} {r['return']:>8.2f} {r['drawdown']:>7.2f}{flag}")

    print("=" * 75)
    print(f"\n  PF >= 1.5 = good edge  |  PF 1.0-1.5 = marginal  |  PF < 1.0 = no edge")
