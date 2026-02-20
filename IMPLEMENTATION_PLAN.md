# Implementation Plan - Aggressive US Stock Trading Bot

## Overview

Replaced the Polymarket prediction market bot with an aggressive US stock trading bot connected to Alpaca Markets API, with AI-powered stock discovery via Yahoo Finance and GPT-4o.

## Architecture

```
┌──────────────────┐    ┌──────────────┐    ┌──────────────┐
│  Yahoo Finance   │    │   Alpaca     │    │  Telegram    │
│  + Web News      │    │  Broker API  │    │  (Control)   │
└──────┬───────────┘    └──────┬───────┘    └──────┬───────┘
       │                       │                   │
       └───────────┬───────────┘───────────────────┘
                   │
           ┌───────▼───────┐
           │  GPT-4o AI    │
           │  (Analysis +  │
           │   Scanning)   │
           └───────┬───────┘
                   │
           ┌───────▼───────┐
           │ Trading Engine │
           ├───────────────┤
           │ - Momentum    │
           │ - Mean Revert │
           │ - Breakout    │
           │ - Gap Trading │
           ├───────────────┤
           │ Risk Manager  │
           │ (Aggressive)  │
           └───────────────┘
```

## Components Built

### 1. Configuration (`config/settings.py`)
- Alpaca API keys + OpenAI API key
- Aggressive trading parameters
- Watchlist, position sizing, risk limits

### 2. Alpaca Client (`src/trading/alpaca_client.py`)
- Account info, positions, market data
- Market orders, bracket orders (with TP/SL)
- Market movers scanning (500+ stocks)
- Market hours check

### 3. AI Stock Scanner (`src/agents/stock_scanner.py`)
- Yahoo Finance trending, gainers, losers, most active
- Market news headlines (general + sector)
- Sector ETF performance tracking
- Stock enrichment via yfinance (price, volume, market cap, news)
- GPT-4o selects top 15 stocks every 15 minutes

### 4. AI Trading Agent (`src/agents/ai_agent.py`)
- Individual stock analysis with OHLCV data
- Batch watchlist scanning
- Exit position analysis
- Aggressive prompts emphasizing momentum and catalysts

### 5. Trading Strategies (`src/trading/strategies.py`)
- Momentum: >2% move + 1.5x volume
- Mean Reversion: RSI < 30, down >3%
- Breakout: 20-bar high break with 2x volume
- Gap Trading: >2% gap with continuation/fade logic

### 6. Risk Manager (`src/trading/risk_manager.py`)
- Confidence-based position sizing (5-25%)
- Trailing stops (+5% activation, 3% trail)
- PDT rule tracking
- Daily loss limits (30%)

### 7. Trading Engine (`src/trading/engine.py`)
- 60-second trading cycles during market hours
- Dynamic stock scanning (AI + fixed watchlist)
- Combined strategy + AI signal analysis
- Up to 3 trades per cycle, 5 concurrent positions

### 8. Telegram Bot (`src/telegram_bot/bot.py`)
- 15 commands for monitoring and control
- /scan for manual AI market scan
- Trade execution alerts
- Position and P&L tracking

## Setup Steps

1. Create free Alpaca account at https://alpaca.markets
2. Generate Paper Trading API keys
3. Get OpenAI API key
4. Create Telegram bot via @BotFather
5. Configure `.env` with all keys
6. `pip install -r requirements.txt`
7. `python src/main.py`
8. Paper trade for at least 1 week before going live
