# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI-powered autonomous stock trading bot** for US equities with:
- **Alpaca Markets** broker API for execution
- **Polygon.io Massive API** for technical indicators (RSI, SMA, MACD)
- **OpenAI GPT-4o** for AI analysis (analysis only - never decides trades)
- **Yahoo Finance** for market data and stock discovery
- **Telegram bot** for remote control and monitoring
- **Strict risk management** with multiple safety layers
- **Raspberry Pi optimization** (memory limits, CPU constraints, rate limiting)

**CRITICAL:** This bot handles real money. All changes must preserve the strict risk management architecture.

## Running the Bot

```bash
# Development (paper trading)
python src/main.py

# Test Polygon.io API integration
python test_polygon.py

# Test resource monitoring (Raspberry Pi)
python scripts/monitor_resources.py

# Install dependencies
pip install -r requirements.txt
```

**Note:** No traditional test suite exists - testing is done via paper trading mode with real market data.

## Critical Architecture Concepts

### 1. **Trade Execution Flow: Three Mandatory Gates**

Every trade MUST pass through three sequential approval gates. This is non-negotiable:

```
Phase 1: Strategies (src/trading/strategies.py)
  ↓ Technical signals only (price, volume, indicators)
  ↓ Outputs: {action, confidence, reasoning}

Phase 2: AI Analysis (src/agents/ai_agent.py)
  ↓ ANALYSIS ONLY - AI never decides to trade
  ↓ Scores: setup_score (1-10), risk_score (1-10)
  ↓ Critical: AI can reject with risk_score > 8

Phase 3: Risk Manager (src/trading/risk_manager.py)
  ↓ MANDATORY GATE: risk_approve() must return True
  ↓ Enforces: position sizing, daily limits, drawdown, PDT rules
  ↓ If rejected, trade is BLOCKED - no exceptions

Engine executes ONLY if all 3 gates approve
```

**Never bypass `risk_approve()` - it's the final safety gate protecting user funds.**

### 2. **AI Role: Analysis Only, Never Execution**

The AI agent (`src/agents/ai_agent.py`) provides scores and analysis but **NEVER** triggers trades:

- ✅ `analyze_stock()` → returns `{setup_score, risk_score, reasoning}`
- ✅ AI can reject trades by returning `risk_score > 8`
- ❌ AI does NOT call `place_trade()` or trigger execution
- ❌ AI does NOT have access to `RiskManager` or `AlpacaClient`

**Design pattern:** AI = read-only analyst. Risk Manager = gatekeeper. Engine = executor.

### 3. **Polygon.io Rate Limiting (< 100 req/hour)**

The Polygon client (`src/trading/polygon_client.py`) has intelligent caching to stay within rate limits:

- **Cache TTL:** 5 minutes per indicator per symbol
- **Max requests:** 90/hour (safety buffer below 100 limit)
- **Request tracking:** Resets hourly, logged to monitor usage
- **Graceful degradation:** Strategies work without indicators if Polygon unavailable

**Pattern:** Always call `get_indicators_bundle()` - it handles caching, rate limiting, and fallback.

### 4. **Security Architecture (Multi-Layer Defense)**

Security was recently hardened - all new code must maintain these protections:

**Telegram Bot (`src/telegram_bot/bot.py`):**
- `@require_authorization` decorator on EVERY command handler
- Rate limiting per command (e.g., `/scan` = 1 per 5min, `/closeall` = 1 per min)
- Critical operations require confirmation (`/closeall CONFIRM`)
- All unauthorized attempts logged to `logs/security.log`

**Logging (`src/monitoring/logger.py`):**
- `SensitiveDataFilter` automatically redacts API keys, tokens, passwords
- Applied to ALL log handlers (console, files)
- Patterns include: Alpaca keys (PK*/SK*), OpenAI keys (sk-*), Telegram tokens

**Security Logger (`src/monitoring/security_logger.py`):**
- Separate `logs/security.log` for security events (90-day retention)
- Tracks: unauthorized access, rate limits, critical operations, credential usage
- Always use `get_security_logger()` for security events

### 5. **Raspberry Pi Optimizations**

This bot is designed to run 24/7 on Raspberry Pi 4 with limited resources:

**Memory Management (`src/trading/engine.py`):**
- Explicit `gc.collect()` every 10 trading loop iterations
- Trade history capped at 100 entries (`max_trades_history`)
- Polygon client caches limited to recent symbols

**API Call Limits:**
- Polygon: 90 req/hour (< 100 limit)
- OpenAI: 3 AI analyses per cycle (reduced from 5)
- Yahoo Finance: Cached 15 minutes per scan

**CPU Constraints:**
- Scan interval: 120 seconds (2 minutes) to reduce CPU load
- Max concurrent positions: 3 (reduced from 5)
- Token limits: 400 max for AI prompts (increased slightly for indicator context)

### 6. **Configuration: Environment Variables vs Settings**

**`.env` file (NEVER commit!):**
- API credentials (Alpaca, OpenAI, Telegram, Polygon)
- Checked into `.gitignore` - credentials are rotated regularly
- Permissions: `chmod 600 .env` on Unix systems

**`config/settings.py`:**
- Uses Pydantic BaseSettings for type-safe configuration
- Loads from environment variables with validation
- Singleton pattern via `get_settings()`
- Defaults optimized for Raspberry Pi deployment

**Pattern:** API keys in `.env`, behavior config can be either `.env` or hardcoded defaults in `settings.py`.

### 7. **Data Flow: Strategy → AI → Risk → Execute**

```
1. TradingEngine.run_trading_loop() (every 120s)
   ↓
2. _get_trading_symbols()
   - Fixed watchlist + AI scanner discoveries
   ↓
3. _find_strategy_signals()
   - Strategies analyze price/volume/indicators
   - Call polygon.get_indicators_bundle() for RSI/SMA/MACD
   - Return signals with confidence ≥ threshold
   ↓
4. _score_with_ai()
   - Pass indicators to AI for context
   - AI returns setup_score + risk_score
   - Reject if risk_score > 8
   ↓
5. _execute_approved_trades()
   - Sort by setup_score (best first)
   - For each signal: risk_approve() MUST return True
   - Only then: _place_trade()
   ↓
6. manage_positions()
   - Update trailing stops
   - Check SL/TP via Alpaca bracket orders
```

### 8. **Supabase Database: Async Trade History Storage**

The bot uses Supabase (PostgreSQL) to store trade history for analytics while keeping it as a non-critical dependency:

**Architecture Pattern:**
- **Async writes:** Trade data is queued and written in a background thread
- **Non-blocking:** If Supabase fails, bot continues trading and logs the error
- **Analytics only:** Database is for historical analysis, NOT for trade decisions

**Database Client (`src/database/supabase_client.py`):**
- Queue-based async writer with background thread
- Graceful failure handling (continues trading if DB unavailable)
- Connection pooling for efficiency
- Automatic reconnection on network failures

**Trade History Storage:**
```
After successful trade execution:
  ↓
Engine calls: supabase_client.log_trade(trade_data)
  ↓
Trade queued in memory (non-blocking)
  ↓
Background thread writes to Supabase
  ↓
If write fails: log error, continue trading
```

**Analytics (`src/database/analytics.py`):**
- Query utilities for win rate, P&L trends, strategy performance
- Aggregations by strategy, symbol, time period
- Used by Telegram `/analytics` command

**CRITICAL:** The database is for analytics only. Never query Supabase during trade execution - it would add latency and create a dependency on external service availability.

### 9. **Type Hints: Python 2.7 Style Comments**

All type hints use comment style for Python 2.7 compatibility:

```python
def analyze_stock(self, symbol, snapshot, bars=None, indicators=None):
    # type: (str, Dict[str, Any], List[Dict[str, Any]], Optional[Dict]) -> Dict[str, Any]
```

**Never use modern type hints** like `def foo(x: int) -> str:` - use comment style.

## Common Gotchas

### SSL Certificate Issue (Non-ASCII Paths)

The `main.py` entry point includes a workaround for SSL certificate issues on Windows with non-ASCII paths (Hebrew, Unicode chars). This code block is critical:

```python
# Lines 18-34 in main.py
# If user's path has Hebrew/Unicode, copy cacert.pem to safe location
```

**Don't remove this** - it's required for users with non-Latin Windows usernames.

### Alpaca Paper Trading URL Detection

The code detects paper vs live trading by checking if "paper" is in the URL:

```python
paper = "paper" in self.settings.alpaca_base_url
```

**Pattern used everywhere** - don't change this check or paper/live detection breaks.

### Strategy Manager: Polygon Client Injection

Strategies need the Polygon client passed at initialization:

```python
# In engine.py __init__:
self.polygon = PolygonIndicatorClient()
self.strategy_manager = StrategyManager(polygon_client=self.polygon)

# In strategies.py:
class MomentumStrategy(BaseStrategy):
    def __init__(self, polygon_client=None):
        self.polygon = polygon_client
```

**Always pass `polygon_client` to StrategyManager** - strategies gracefully degrade without it but won't have indicator confirmations.

### Telegram Bot: Threading + Async Mix

The Telegram bot runs in a separate thread with async handlers:

```python
# main.py starts Telegram in daemon thread
telegram_thread = Thread(target=self.telegram_bot.start, daemon=True)

# bot.py uses async/await for command handlers
async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
```

**Don't change to full async** - the trading engine uses blocking calls and can't be easily converted.

## File Organization Logic

```
src/
├── agents/              # AI components (read-only - provide analysis)
│   ├── ai_agent.py      # GPT-4o stock analysis
│   └── stock_scanner.py # AI market scanner (Yahoo Finance scraping)
│
├── trading/             # Trading execution (read-write - execute trades)
│   ├── engine.py        # Main orchestrator - coordinates all components
│   ├── strategies.py    # Technical strategies with indicator confirmations
│   ├── risk_manager.py  # CRITICAL: Final approval gate for all trades
│   ├── alpaca_client.py # Broker API - order execution
│   └── polygon_client.py # Technical indicators with caching
│
├── database/            # Trade history storage (non-critical dependency)
│   ├── supabase_client.py # Async writer with queue + graceful failure
│   ├── analytics.py     # Query utilities for performance analysis
│   └── schema.sql       # Database schema for trades table
│
├── telegram_bot/        # Remote control (external interface)
│   └── bot.py           # Command handlers with auth + rate limiting
│
├── monitoring/          # Observability
│   ├── logger.py        # Logging with sensitive data filtering
│   └── security_logger.py # Security event logging (separate file)
│
└── main.py              # Entry point + SSL workaround
```

## Security Requirements (Recently Added)

When adding new Telegram commands:
1. Apply `@require_authorization` decorator
2. Add to rate limits dict if expensive/critical
3. Require confirmation if destructive (like `/closeall`)
4. Log critical operations to `security_logger`

When adding new API clients:
1. Implement request timeouts (10s default)
2. Add retry logic with exponential backoff
3. Rate limiting if API has limits
4. Credential usage logging for security audit

When modifying logging:
1. Ensure `SensitiveDataFilter` is applied
2. Test that API keys are redacted in output
3. Don't log raw request/response bodies that may contain credentials

## Integration Points

**Adding a new trading strategy:**
1. Extend `BaseStrategy` in `strategies.py`
2. Accept `polygon_client` in `__init__`
3. Call `polygon.get_indicators_bundle()` for RSI/SMA/MACD
4. Return signal with `confidence` (0-100) and `reasoning`
5. Register in `StrategyManager.__init__`

**Adding a new Telegram command:**
1. Add command method with `@require_authorization`
2. Add to `rate_limits` dict if needed
3. Register in `start()` method handler list
4. Update `/help` command text

**Adding a new API integration:**
1. Create client in `src/trading/` or `src/agents/`
2. Use singleton pattern like Polygon client if stateful
3. Implement caching if API has rate limits
4. Add to `TradingEngine.__init__` for access in strategies

## Risk Management Rules (DO NOT MODIFY)

These risk rules are hardcoded for user safety - changes require explicit approval:

- **Per-trade risk:** 0.5-1% of equity (`risk_per_trade_pct`)
- **Daily loss limit:** 2% of equity (`daily_loss_limit_pct`)
- **Max drawdown:** 10% from peak (`max_drawdown_pct`) → bot pauses
- **Consecutive loss pause:** 3 losses → manual `/resume` required
- **Position limits:** Max 3 concurrent, max 2% equity per position
- **PDT enforcement:** Tracks day trades, blocks if approaching limit

**These are not suggestions - they're guardrails protecting user funds.**

## Documentation

- [SECURITY_GUIDE.md](SECURITY_GUIDE.md) - Security setup, credential rotation, Pi hardening
- [README.md](README.md) - Quick start, feature overview
- Plan file: `C:\Users\shach\.claude\plans\fancy-rolling-gray.md` - Security hardening implementation details

## Notes for Claude Code

- This bot manages real financial assets - be extra cautious with risk management changes
- The user runs this on Raspberry Pi 4 - optimize for limited resources
- Security was recently hardened - maintain auth, rate limiting, and logging
- Type hints use Python 2.7 comment style (`# type:`) - don't modernize
- Paper trading mode is default (`ALPACA_BASE_URL=https://paper-api.alpaca.markets`)
- SSL certificate workaround in main.py is required for non-ASCII Windows paths
