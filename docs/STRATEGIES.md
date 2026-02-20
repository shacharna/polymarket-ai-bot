# Trading Strategies

This bot implements 4 aggressive stock trading strategies plus AI-powered analysis via GPT-4o.

## Strategy Overview

The bot uses a multi-layer approach:
1. Strategies analyze price action and volume data
2. AI (GPT-4o) validates and selects signals
3. Best opportunities are executed with bracket orders (TP/SL)
4. Combined signals (strategy + AI agree) get highest priority

## Available Strategies

### 1. Momentum Strategy (High Risk)

**How it Works:**
- Detects stocks with strong directional movement + volume confirmation
- Entry: Price up >2% intraday with volume 1.5x above average
- Checks recent bar trend for confirmation (3+ bars in same direction)

**Position Size:** 8-9/10 for confirmed momentum

**Best For:** Trending markets, stocks with news catalysts

### 2. Mean Reversion Strategy (Medium-High Risk)

**How it Works:**
- Catches oversold bounces using RSI calculation (14-period)
- BUY: RSI < 30 AND stock down >3% intraday
- SELL: RSI > 75 AND stock up >5% intraday

**Position Size:** 7/10

**Best For:** Stocks that dropped sharply without fundamental reason

### 3. Breakout Strategy (High Risk)

**How it Works:**
- Detects price breaking above/below recent highs/lows
- Entry: Price breaks 20-bar high (15-min chart) with 2x average volume
- Works for both long breakouts and short breakdowns

**Position Size:** 8/10

**Best For:** Stocks consolidating then exploding with volume

### 4. Gap Strategy (High Risk)

**How it Works:**
- Trades stocks that gap up or down at market open
- Entry: Stock gaps >2% from previous close
- Gap continuation: Strong gap with same direction momentum
- Gap fade: Overextended gap showing reversal signs

**Position Size:** 7/10

**Best For:** First 30 minutes of trading, earnings reactions

## AI Analysis Layer

On top of strategies, GPT-4o provides:

- **Individual Stock Analysis**: Deep analysis of OHLCV data + snapshot
- **Watchlist Scanning**: Batch analysis of all stocks in one AI call
- **Exit Analysis**: When to close existing positions
- **Dynamic Stock Discovery**: Scans Yahoo Finance to find new opportunities

### Signal Types

| Source | Description | Priority |
|--------|------------|----------|
| Combined | Strategy + AI agree | Highest |
| AI-only | AI finds opportunity strategies missed | High |
| Strategy-only | Strategy signal, AI neutral | Medium |

## Risk Management Per Strategy

Every trade includes:

- **Stop Loss**: -8% (configurable)
- **Take Profit**: +15% (configurable)
- **Trailing Stop**: Activates at +5%, trails 3% below peak
- **Position Size**: Based on confidence level (5-25% of equity)

## Configuration

Strategies can be enabled/disabled via Telegram:
```
/strategies    # View status
```

Or adjust parameters in `src/trading/strategies.py`.

## AI Stock Scanner

Beyond strategies, the AI scanner runs every 15 minutes:

1. Fetches Yahoo Finance trending, gainers, losers, most active
2. Pulls market news headlines
3. Checks sector ETF performance
4. Enriches stocks with price, volume, market cap data
5. GPT-4o selects top 15 stocks ranked by conviction

Use `/scan` in Telegram to trigger a manual scan.
