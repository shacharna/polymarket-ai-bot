# Aggressive US Stock Trading Bot

An AI-powered autonomous stock trading bot that trades US stocks via Alpaca Markets API with aggressive strategies, AI-driven stock discovery (Yahoo Finance + web scanning), and remote control via Telegram.

## Warning

**Trading involves significant financial risk. This bot uses aggressive strategies with high risk/high reward. Only invest money you can afford to lose.**

- Start with paper trading mode before using real money
- This bot tolerates up to 30% drawdowns by design
- Past performance does not guarantee future results

## Features

- **AI-Powered Stock Discovery**: GPT-4o scans Yahoo Finance, market news, and sector data to find the best opportunities
- **Dynamic Watchlist**: AI scanner discovers new stocks every 15 minutes instead of trading a fixed list
- **4 Aggressive Trading Strategies**: Momentum, Mean Reversion, Breakout, Gap Trading
- **Bracket Orders**: Automatic take-profit and stop-loss on every trade
- **Trailing Stops**: Locks in profits as stocks move in your favor
- **Risk Management**: PDT rule awareness, daily loss limits, position concentration limits
- **Telegram Remote Control**: Monitor and control the bot from your phone
- **Paper Trading**: Test everything risk-free with Alpaca's paper trading

## Technology Stack

- Python 3.8+
- OpenAI GPT-4o (AI analysis and stock scanning)
- Alpaca Markets API (broker - commission-free US stock trading)
- Yahoo Finance / yfinance (market data, news, sector performance)
- Python Telegram Bot (remote control)
- Pydantic Settings (configuration)
- Loguru (logging)

## Quick Start

### 1. Create Accounts

- **Alpaca Markets** (free): https://alpaca.markets - Generate Paper Trading API keys
- **OpenAI**: https://platform.openai.com - Get API key
- **Telegram**: Create bot via @BotFather

### 2. Install

```bash
git clone <your-repo-url>
cd polymarket-ai-bot
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
OPENAI_API_KEY=your_openai_key
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 4. Run

```bash
python src/main.py
```

## Project Structure

```
polymarket-ai-bot/
├── src/
│   ├── agents/
│   │   ├── ai_agent.py          # GPT-4o trading analysis
│   │   └── stock_scanner.py     # AI market scanner (Yahoo Finance + web)
│   ├── trading/
│   │   ├── alpaca_client.py     # Alpaca broker API
│   │   ├── engine.py            # Main trading engine
│   │   ├── risk_manager.py      # Aggressive risk management
│   │   └── strategies.py        # 4 trading strategies
│   ├── telegram_bot/
│   │   └── bot.py               # Telegram remote control
│   ├── monitoring/
│   │   └── logger.py            # Logging system
│   └── main.py                  # Entry point
├── config/
│   └── settings.py              # Configuration management
├── docs/                        # Documentation
├── requirements.txt             # Python dependencies
├── .env.example                 # Example configuration
└── .gitignore                   # Git ignore rules
```

## How It Works

### AI Stock Scanner
Every 15 minutes, the bot:
1. Fetches trending stocks from Yahoo Finance
2. Gets top gainers, losers, and most active stocks
3. Pulls market news headlines
4. Checks sector ETF performance (SPY, QQQ, XLK, etc.)
5. Scans Alpaca for biggest market movers
6. Sends all data to GPT-4o which selects the top 15 stocks to trade

### Trading Strategies

| Strategy | How It Works | Risk |
|----------|-------------|------|
| **Momentum** | Stocks up >2% with 1.5x volume | High |
| **Mean Reversion** | RSI < 30, stock down >3% | Medium-High |
| **Breakout** | Price breaks 20-bar high with 2x volume | High |
| **Gap Trading** | Stocks gapping >2% at open | High |

### Risk Management

- Position sizing based on confidence (5-25% of equity)
- Stop loss: -8% per trade
- Take profit: +15% per trade
- Trailing stop: activates at +5%, trails 3% below peak
- Daily loss limit: 30% of equity
- Max 5 concurrent positions
- PDT rule tracking (3 day trades per 5 days if < $25k)

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and command list |
| `/status` | Bot status, equity, P&L |
| `/balance` | Detailed account balance |
| `/positions` | Open stock positions with P&L |
| `/trades` | Recent trade history |
| `/stats` | Win rate, P&L statistics |
| `/scan` | Trigger AI market scan |
| `/watchlist` | Fixed + AI-selected stocks |
| `/strategies` | Active strategy status |
| `/risk` | Risk metrics and PDT status |
| `/mode` | Trading parameters |
| `/pause` | Pause trading |
| `/resume` | Resume trading |
| `/closeall` | Emergency close all positions |

## Configuration

Key settings in `.env`:

```bash
# Trading behavior
TRADING_MODE=aggressive
CONFIDENCE_THRESHOLD=55          # Min confidence to trade (%)
MAX_CONCURRENT_POSITIONS=5       # Max open positions
MAX_POSITION_PCT=0.25            # Max 25% equity per trade
SCAN_INTERVAL=60                 # Seconds between trading cycles

# Risk management
STOP_LOSS_PCT=-8.0               # Cut losers at -8%
TAKE_PROFIT_PCT=15.0             # Take profits at +15%
TRAILING_STOP_ENABLED=true       # Enable trailing stops
DAILY_LOSS_LIMIT_PCT=0.30        # Stop if down 30%

# Watchlist (base stocks, AI adds more dynamically)
WATCHLIST=AAPL,TSLA,NVDA,MSFT,AMZN,META,GOOGL,AMD,NFLX,SPY,QQQ
```

## Documentation

- [Quick Start Guide](docs/QUICKSTART.md)
- [Alpaca Setup](docs/ALPACA_SETUP.md)
- [Trading Strategies](docs/STRATEGIES.md)
- [Telegram Commands](docs/TELEGRAM.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)

## Risk Warning

**IMPORTANT**: This software is provided "as is" without warranty. Trading stocks involves substantial risk of loss. The developers are not responsible for any financial losses incurred while using this software.

- Always paper trade first
- Only invest what you can afford to lose
- Monitor the bot regularly
- Understand the strategies before going live
