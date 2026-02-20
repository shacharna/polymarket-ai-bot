# Quick Start Guide

Get your stock trading bot running in under 15 minutes.

## Prerequisites

- Python 3.8+
- Internet connection
- API keys (see below)

## Step 1: Create Accounts (10 minutes)

### Alpaca Markets (Free broker)
1. Go to https://alpaca.markets
2. Sign up for free account
3. Go to Paper Trading section
4. Generate API keys (Key + Secret)
5. Note: Paper trading = demo account with fake money

### OpenAI
1. Go to https://platform.openai.com
2. Sign up and add payment method
3. Generate API key
4. Cost: ~$5-15/day for GPT-4o calls

### Telegram Bot
1. Open Telegram, search for `@BotFather`
2. Send `/newbot`, follow instructions
3. Save Bot Token
4. Send a message to your bot
5. Visit `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
6. Find your Chat ID

## Step 2: Install (3 minutes)

```bash
git clone <your-repo-url>
cd polymarket-ai-bot

# Create virtual environment
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 3: Configure (2 minutes)

Create `.env` file in project root:

```bash
# Alpaca Markets API
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# OpenAI API
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Watchlist
WATCHLIST=AAPL,TSLA,NVDA,MSFT,AMZN,META,GOOGL,AMD,NFLX,SPY,QQQ,SOFI,PLTR,COIN,MARA

# Trading Mode
TRADING_MODE=aggressive
PAPER_TRADING=true
LOG_LEVEL=DEBUG

# Position Sizing
MAX_POSITION_PCT=0.25
MAX_CONCURRENT_POSITIONS=5
CONFIDENCE_THRESHOLD=55

# Risk Limits
DAILY_LOSS_LIMIT_PCT=0.30
STOP_LOSS_PCT=-8.0
TAKE_PROFIT_PCT=15.0

# Trailing Stop
TRAILING_STOP_ENABLED=true
TRAILING_STOP_ACTIVATION=0.05
TRAILING_STOP_DISTANCE=0.03

# Scanning
SCAN_INTERVAL=60
MARKET_HOURS_ONLY=true
ALLOW_AI_ONLY_TRADES=true
ALLOW_STRATEGY_ONLY_TRADES=true
```

## Step 4: Run (1 minute)

```bash
python src/main.py
```

Expected output:
```
Aggressive Stock Trading Bot
==================================================
Starting Aggressive Stock Trading Bot...
Mode: PAPER TRADING | Strategy: AGGRESSIVE
Alpaca client initialized | Equity: $100,000.00
Stock Scanner Agent initialized (Yahoo Finance + Web + AI)
Trading Engine initialized | AI Scanner: ENABLED
Starting trading engine...
```

You should receive a Telegram message confirming startup.

## What Happens Next

1. **Market closed?** Bot waits for US market hours (9:30 AM - 4:00 PM ET)
2. **Market open?** Bot starts scanning:
   - Every 60 seconds: runs strategies on watchlist
   - Every 15 minutes: AI scans Yahoo Finance for new stocks
   - Executes up to 3 trades per cycle
   - Manages positions with trailing stops

## Telegram Commands

Once running, control via Telegram:
- `/status` - Check bot health
- `/scan` - Trigger AI market scan
- `/positions` - View open trades
- `/stats` - Trading statistics
- `/pause` / `/resume` - Control trading

## Important Notes

- **Paper trading first**: Always test with paper (demo) money
- **Market hours**: Bot only trades 9:30 AM - 4:00 PM Eastern Time
- **PDT rule**: If paper account is under $25k, limited to 3 day trades per 5 days
- **AI costs**: GPT-4o calls cost ~$5-15/day depending on scan frequency
- **Never share your `.env` file** - it contains API keys

## Going Live

After at least 1 week of successful paper trading:

1. Generate LIVE API keys from Alpaca
2. Change in `.env`:
   ```
   ALPACA_BASE_URL=https://api.alpaca.markets
   PAPER_TRADING=false
   ```
3. Fund your Alpaca account
4. Start with conservative settings first

See [ALPACA_SETUP.md](ALPACA_SETUP.md) for detailed broker setup.
