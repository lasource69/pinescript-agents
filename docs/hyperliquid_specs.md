# Hyperliquid Perpetual Specifications (2026)

## Core Precision Rules
Hyperliquid enforces two strict rules for all perpetual orders. If an order violates either, it will be rejected.

1. **Max Significant Figures**: Prices are limited to **5 significant figures** (e.g., 123.45 is valid, 123.456 is not).
   - *Exception*: Integer prices (e.g., 123456) are always valid regardless of significant figures.
2. **Decimal Precision**: The maximum number of decimals allowed for a price is calculated as:  
   `MAX_PRICE_DECIMALS = 6 - szDecimals`

---

## Asset-Specific Metadata (Perpetuals)

| Asset | szDecimals (Lot Size) | Max Price Decimals | Min Order Size |
| :--- | :--- | :--- | :--- |
| **BTC** | 5 | 1 | 0.00001 BTC |
| **SOL** | 2 | 4 | 0.01 SOL |
| **SUI** | 1 | 5 | 0.1 SUI |
| **ETH** | 4 | 2 | 0.0001 ETH |
| **HYPE** | 2 | 4 | 0.01 HYPE |

---

## Pine Script v6 Rounding Helper
Use this function in your scripts to ensure compatibility with Hyperliquid's engine.

```pinescript
// @function Rounds a price to Hyperliquid's 5-significant-figure rule
// @param price The raw price from your strategy
// @returns Valid price for Hyperliquid execution
f_hp_round(float price) =>
    float p = price
    if p >= 10000
        math.round(p, 1)
    else if p >= 1000
        math.round(p, 1)
    else if p >= 100
        math.round(p, 2)
    else if p >= 10
        math.round(p, 3)
    else
        math.round(p, 4)