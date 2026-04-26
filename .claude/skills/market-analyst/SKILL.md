---
name: market-analyst
description: Multi-agent market analysis that debates findings between a Technical Analyst, Momentum/Sentiment Analyst, and Risk Manager using live TradingView data, then outputs a STRONG BUY / BUY / HOLD / SELL / STRONG SELL verdict with confidence score. Use when the user asks to analyse a symbol, get a signal, or wants a market opinion. Triggers on "analyse", "analyze", "signal", "what do you think about", "should I buy/sell", or any symbol with analysis intent.
---

# Market Analyst — Multi-Agent Debate System

Uses live TradingView MCP data to run a three-agent debate and produce a final trading verdict.

## Step 1: Gather Live Data

Before running any analysis, pull data using the TradingView MCP tools:

```
mcp__tradingview__data_get_ohlcv        — last 100 bars (or as many as available)
mcp__tradingview__data_get_study_values — RSI, MACD, Bollinger Bands, Volume MA
mcp__tradingview__quote_get             — current price, % change, volume
mcp__tradingview__data_get_strategy_results — if a strategy is active on chart
mcp__tradingview__chart_get_state       — current symbol, timeframe, indicators loaded
```

If the user specifies a symbol other than the active chart, use `mcp__tradingview__chart_set_symbol` first, wait, then pull data.

## Step 2: Run the Three Agents

Run each agent independently using only the data gathered. Each agent must state their case and give a directional bias with a confidence score (0–100).

---

### Agent 1: Technical Analyst

Focus areas:
- Trend: Is price above/below key MAs (20, 50, 200)? Higher highs/lows or lower highs/lows?
- Momentum: RSI level and direction. Overbought (>70) or oversold (<30)?
- MACD: Signal line cross, histogram expanding or contracting?
- Bollinger Bands: Price near upper/lower band? Squeeze forming?
- Support/Resistance: Recent swing highs/lows, round numbers
- Candlestick patterns on the last 3–5 bars

Output format:
```
TECHNICAL ANALYST
Bias: BULLISH / BEARISH / NEUTRAL
Confidence: 0–100
Key findings:
- [finding 1]
- [finding 2]
- [finding 3]
```

---

### Agent 2: Momentum & Sentiment Analyst

Focus areas:
- Volume: Is volume confirming price moves? Above or below average?
- Momentum: Rate of change over 10 and 20 bars
- Trend strength: ADX if available, otherwise slope of price
- Relative performance: How has this asset moved vs recent sessions?
- Market structure: Are we in a range or trending environment?
- Timeframe confluence: Does the signal align across higher timeframes (if data allows)?

Output format:
```
MOMENTUM & SENTIMENT ANALYST
Bias: BULLISH / BEARISH / NEUTRAL
Confidence: 0–100
Key findings:
- [finding 1]
- [finding 2]
- [finding 3]
```

---

### Agent 3: Risk Manager

Focus areas:
- Volatility: ATR as % of price. Is it elevated or compressed?
- Drawdown risk: How far is price from recent swing high/low?
- Reward:Risk: Identify nearest logical stop and target. Is R:R >= 2:1?
- Position sizing: For 4x leverage (Hyperliquid), what is the max safe position size?
- Invalidation level: At what price is the thesis wrong?
- Timing risk: Is this a good entry point or are we chasing?

Output format:
```
RISK MANAGER
Bias: PROCEED / CAUTION / AVOID
Confidence: 0–100
Key findings:
- Stop level: [price]
- Target level: [price]
- R:R ratio: [x:1]
- Invalidation: [price/condition]
- [other finding]
```

---

## Step 3: Debate & Reconcile

After all three agents have spoken, run a brief debate:
- If all three agree → high conviction verdict
- If two agree and one dissents → note the dissent, moderate confidence
- If all three disagree → HOLD, low confidence, explain the conflict

Debate format:
```
DEBATE
[Agent with strongest view states their case in 1–2 sentences]
[Dissenting agent counters in 1–2 sentences]
[Resolution: which argument wins and why]
```

---

## Step 4: Final Verdict

Output a single, clear verdict:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VERDICT: [STRONG BUY / BUY / HOLD / SELL / STRONG SELL]
Confidence: [0–100]%
Timeframe: [chart timeframe]
Symbol: [EXCHANGE:SYMBOL]
Price: [current price]

Entry zone:    [price range]
Stop loss:     [price]
Take profit:   [price]
R:R:           [x:1]
Invalidation:  [price or condition]

Summary: [2–3 sentences explaining the verdict]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Verdict Thresholds

| Verdict | Condition |
|---|---|
| STRONG BUY | All 3 agents bullish, confidence avg > 75 |
| BUY | 2–3 agents bullish, confidence avg 55–75 |
| HOLD | Mixed signals or confidence avg < 55 |
| SELL | 2–3 agents bearish, confidence avg 55–75 |
| STRONG SELL | All 3 agents bearish, confidence avg > 75 |

## Usage

User can trigger with:
- `/market-analyst` — analyse current chart symbol
- `/market-analyst BTCUSD` — analyse specific symbol
- `/market-analyst SOLUSDT 4h` — analyse symbol on specific timeframe

## Important Notes

- Always use live TradingView MCP data — never make up prices or indicator values
- If MCP data is unavailable, say so explicitly rather than guessing
- This is analysis, not financial advice — always note this in the output
- For Hyperliquid 4x leverage context: flag if volatility makes the trade particularly high risk
