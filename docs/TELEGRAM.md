# Telegram Bot Commands

Control and monitor your stock trading bot from anywhere using Telegram.

## Setup

### 1. Create Your Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name (e.g., "My Stock Trading Bot")
4. Choose a username (must end in `bot`)
5. Save the **Bot Token**

### 2. Get Your Chat ID

1. Start a chat with your new bot
2. Send any message
3. Open: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
4. Find `"chat":{"id":123456789}`
5. Save the Chat ID

### 3. Configure

Add to `.env`:
```
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Available Commands

### Monitoring

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with all commands |
| `/help` | Same as /start |
| `/status` | Bot status, equity, buying power, P&L, market status |
| `/balance` | Detailed account balance from Alpaca |
| `/positions` | Open stock positions with unrealized P&L |
| `/trades` | Last 10 trade executions |
| `/stats` | Win rate, total P&L, best/worst trades |

### AI Scanner

| Command | Description |
|---------|-------------|
| `/scan` | Trigger AI market scan (Yahoo Finance + Alpaca + GPT-4o). Shows top picks with conviction scores |
| `/watchlist` | Fixed watchlist + AI-selected stocks |

### Strategy & Risk

| Command | Description |
|---------|-------------|
| `/strategies` | View enabled/disabled strategies |
| `/risk` | Risk metrics, PDT status, daily limits |
| `/mode` | Current trading parameters (position sizing, stops, etc.) |

### Control

| Command | Description |
|---------|-------------|
| `/pause` | Pause trading (keeps existing positions) |
| `/resume` | Resume trading |
| `/closeall` | Emergency close ALL positions |

## Automatic Notifications

The bot sends alerts for:

- **Trade Executed**: Symbol, qty, price, strategy, confidence, SL/TP levels
- **Bot Started**: Mode, watchlist, scan interval
- **Bot Stopped**: Confirmation message

## Example Responses

### /status
```
Bot Status

Status: Running
Market: OPEN
Mode: PAPER - AGGRESSIVE
Equity: $523.45
Buying Power: $412.30
Daily P&L: +$12.50
Open Positions: 2
Trades Today: 5
Day Trades: 1/3
```

### /scan
```
AI Market Scan Results

Scanned at: 10:45:23
Stocks selected: 12

1. NVDA - BUY (momentum)
   Conviction: 9/10
   Strong momentum with AI chip demand news

2. TSLA - SELL (reversal)
   Conviction: 7/10
   Overbought RSI after 8% run, likely pullback
...
```

### /positions
```
Open Positions

AAPL (long)
  Qty: 3 @ $185.20
  Now: $187.50
  P&L: +$6.90 (+1.2%)

NVDA (long)
  Qty: 1 @ $890.00
  Now: $895.30
  P&L: +$5.30 (+0.6%)

Total Unrealized P&L: +$12.20
```

## Tips

- Check `/status` 2-3 times during market hours
- Use `/scan` when you want fresh AI stock picks
- Use `/risk` to monitor PDT day trade count
- Use `/pause` during high-volatility news events
- `/closeall` is for emergencies only - it market-sells everything
