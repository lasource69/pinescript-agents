# WunderTrading Signal Bot Setup (2026)

## Webhook URL
- **Main Endpoint**: `https://wtalerts.com/bot/trading_view_strategy`
- **Alternative**: Check your WunderTrading dashboard for a unique bot-specific URL.

## Standard JSON Format (For TradingView Strategies)
When using `strategy.entry(..., alert_message = ...)` use this structure:

```json
{
  "action": "{{strategy.order.action}}",
  "pair": "{{ticker}}",
  "leverage": 4,
  "type": "market",
  "secret": "PASTE_YOUR_BOT_SECRET_HERE"
}