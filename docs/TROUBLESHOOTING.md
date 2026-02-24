# Troubleshooting Guide

Common issues and solutions for the stock trading bot.

## Installation Issues

### yfinance Import Error (Python 3.8)

**Error:**
```
TypeError: 'type' object is not subscriptable
```

**Solution:**
```bash
pip install "multitasking<0.0.12"
```
This is a Python 3.8 compatibility issue with the multitasking library.

### Pip Install Fails

**Solution:**
```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## Configuration Issues

### Pydantic Validation Error

**Error:**
```
pydantic_core._pydantic_core.ValidationError: Extra inputs are not permitted
```

**Solution:** The `config/settings.py` has `extra = "ignore"` in the Config class. If you see this error, make sure your `settings.py` includes:
```python
class Config:
    extra = "ignore"
```

### Missing .env File

**Solution:**
```bash
cp .env.example .env
# Edit .env with your API keys
```

## Runtime Issues

### "Market closed" Message

This is normal behavior. The bot only trades during US market hours:
- **Market hours**: 9:30 AM - 4:00 PM Eastern Time
- **Weekdays only** (no weekends/holidays)

The bot will automatically resume when the market opens.

### RuntimeError: no current event loop in thread

**Error:**
```
RuntimeError: There is no current event loop in thread 'Thread-1'
```

**Solution:** This is fixed in the codebase. The Telegram bot creates its own event loop:
```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
```

### Bot Not Finding Opportunities

**Checks:**
1. Is the market open? Check `/status`
2. Are strategies enabled? Check `/strategies`
3. Is confidence threshold too high? Default is 55%
4. Are there any error logs? Check `logs/errors.log`

### AI Scanner Not Working

**Checks:**
1. Is OpenAI API key valid? Check `.env`
2. Do you have OpenAI credits? Check https://platform.openai.com
3. Is Yahoo Finance accessible? The bot handles failures gracefully

### Alpaca Connection Issues

**Error:** `Failed to initialize Alpaca client`

**Solutions:**
1. Verify API keys are correct
2. Make sure you're using the right URL:
   - Paper: `https://paper-api.alpaca.markets`
   - Live: `https://api.alpaca.markets`
3. Don't mix paper keys with live URL

### Telegram Bot Not Responding

**Checks:**
1. Verify bot token: `curl https://api.telegram.org/botYOUR_TOKEN/getMe`
2. Verify chat ID is correct
3. Check bot is running: look for "Telegram bot started" in logs
4. Restart the bot

## Trading Issues

### PDT Warning

If your account is under $25,000:
- Limited to 3 day trades per 5 business days
- Bot tracks this automatically
- Check with `/risk` command
- Paper trading accounts ($100k) are not affected

### Positions Not Closing

- Bracket orders have automatic SL/TP built in via Alpaca
- Trailing stops are checked every trading cycle (60s)
- Use `/closeall` for emergency close
- Check Alpaca dashboard for order status

### High OpenAI Costs

**Solutions:**
1. Increase scan interval in `.env`: `SCAN_INTERVAL=120`
2. The AI scanner runs every 15 minutes (configurable in `stock_scanner.py`)
3. Consider using `gpt-4o-mini` for lower costs:
   ```
   OPENAI_MODEL=gpt-4o-mini
   ```

## Logs

Check logs for debugging:

```bash
# All activity
tail -50 logs/trading.log

# Errors only
tail -20 logs/errors.log

# Trade history
tail -20 logs/trades.log
```

## Getting Help

1. Check logs for specific error messages
2. Enable debug logging: `LOG_LEVEL=DEBUG` in `.env`
3. Review the documentation in `docs/` folder
4. Check Alpaca status: https://status.alpaca.markets
