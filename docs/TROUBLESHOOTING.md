# Troubleshooting Guide

Common issues and their solutions.

## Installation Issues

### Python Version Error

**Error**:
```
Python 3.9.10 or higher is required
```

**Solution**:
```bash
# Check current version
python3 --version

# Update Python (Raspberry Pi)
sudo apt update
sudo apt install python3.11 python3.11-venv -y

# Create venv with new version
python3.11 -m venv venv
source venv/bin/activate
```

---

### Pip Install Fails

**Error**:
```
ERROR: Could not build wheels for...
```

**Solution**:
```bash
# Install build dependencies
sudo apt install python3-dev build-essential libssl-dev libffi-dev -y

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Try again
pip install -r requirements.txt
```

---

### py-clob-client Installation Fails

**Error**:
```
Failed building wheel for py-clob-client
```

**Solution**:
```bash
# Install specific version
pip install py-clob-client==0.32.0 --no-cache-dir

# Or try alternative
pip install git+https://github.com/Polymarket/py-clob-client.git
```

---

## Configuration Issues

### .env File Not Found

**Error**:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Settings
```

**Solution**:
```bash
# Make sure .env exists
ls -la .env

# If not, create from example
cp .env.example .env

# Edit with your credentials
nano .env
```

---

### Invalid API Credentials

**Error**:
```
Failed to initialize Polymarket client: Invalid API key
```

**Solution**:
1. Verify credentials in Polymarket dashboard
2. Make sure no extra spaces in `.env` file
3. Regenerate API key if needed
4. Check API key has trading permissions

```bash
# Check .env format
cat .env | grep POLYMARKET_API_KEY

# Should be:
POLYMARKET_API_KEY=your_key_here
# NOT:
POLYMARKET_API_KEY = your_key_here  # ❌ Extra spaces
```

---

### Wrong Network

**Error**:
```
web3.exceptions.InvalidAddress: Wrong chain ID
```

**Solution**:
- Make sure wallet is on Polygon (Chain ID: 137), not Ethereum
- Check `POLYGON_RPC_URL` in `.env`
- Verify wallet address is valid

```bash
# Valid Polygon RPC URLs:
POLYGON_RPC_URL=https://polygon-rpc.com
# or
POLYGON_RPC_URL=https://rpc-mainnet.maticvigil.com
```

---

## Runtime Issues

### Bot Starts Then Crashes

**Error**:
```
Error in trading loop: ...
```

**Solution**:
1. Check logs for specific error:
   ```bash
   tail -100 logs/errors.log
   ```

2. Common causes:
   - No internet connection
   - API rate limit exceeded
   - Insufficient balance
   - Invalid market data

3. Restart with more logging:
   ```bash
   LOG_LEVEL=DEBUG python src/main.py
   ```

---

### No Markets Found

**Error**:
```
Scanned 0 markets
```

**Solution**:
1. Check internet connection:
   ```bash
   ping polymarket.com
   ```

2. Verify Polymarket API is accessible:
   ```bash
   curl https://clob.polymarket.com/markets
   ```

3. Check rate limits - wait 5 minutes and retry

4. Try different RPC endpoint

---

### Cannot Place Orders

**Error**:
```
Error placing order: Insufficient funds
```

**Solutions**:

**Check Balance**:
```python
# In Python shell
from src.trading.polymarket_client import PolymarketClient
client = PolymarketClient()
print(client.get_balance())
```

**Ensure Sufficient USDC**:
- Need USDC for trades
- Need MATIC for gas fees (~$0.01 per transaction)

**Check Approval**:
- Polymarket needs token approval
- Do one manual trade on Polymarket website first
- This sets up necessary approvals

---

### Telegram Bot Not Working

**Error**: Bot doesn't respond to commands

**Solutions**:

1. **Verify Token**:
   ```bash
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe
   ```
   Should return bot info

2. **Check Chat ID**:
   ```bash
   # Send a message to your bot, then:
   curl https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
   Look for your chat ID

3. **Firewall Issues**:
   ```bash
   # Allow outbound HTTPS
   sudo ufw allow out 443/tcp
   ```

4. **Test Separately**:
   ```python
   # test_telegram.py
   from telegram import Bot
   import asyncio

   async def test():
       bot = Bot(token="YOUR_TOKEN")
       await bot.send_message(chat_id="YOUR_CHAT_ID", text="Test")

   asyncio.run(test())
   ```

---

### AI Agent Errors

**Error**:
```
Error in market analysis: Invalid API key
```

**Solution**:
1. Check Anthropic API key:
   ```bash
   cat .env | grep ANTHROPIC_API_KEY
   ```

2. Verify key at https://console.anthropic.com

3. Check API credits/billing

4. Test API directly:
   ```python
   from anthropic import Anthropic
   client = Anthropic(api_key="your_key")
   message = client.messages.create(
       model="claude-sonnet-4-5-20250929",
       max_tokens=100,
       messages=[{"role": "user", "content": "Hello"}]
   )
   print(message.content)
   ```

---

## Performance Issues

### Bot Running Slow

**Symptoms**: Long delays between market scans

**Solutions**:

1. **Reduce Market Scan Size**:
   ```python
   # In src/trading/engine.py
   markets = self.polymarket.get_markets(limit=20)  # Was 50
   ```

2. **Increase Scan Interval**:
   ```python
   # In src/trading/engine.py
   time.sleep(600)  # Was 300 (10 minutes instead of 5)
   ```

3. **Disable Heavy Strategies**:
   ```
   /disable value  # Value strategy uses most AI calls
   ```

4. **Check Raspberry Pi Load**:
   ```bash
   htop
   ```
   If CPU > 80%, reduce concurrent operations

---

### High API Costs

**Symptom**: Anthropic API bill too high

**Solutions**:

1. **Reduce AI Calls**:
   - Only analyze top markets
   - Cache AI responses
   - Increase confidence threshold (fewer trades = fewer analyses)

2. **Use Haiku Model** (cheaper):
   ```python
   # In src/agents/ai_agent.py
   self.model = "claude-haiku-4-5-20251001"  # Much cheaper
   ```

3. **Limit Analysis Frequency**:
   ```python
   # Only analyze if strategy signals first
   if strategy_signals:
       ai_analysis = self.ai_agent.analyze_market(market_data)
   ```

---

### Memory Issues on Raspberry Pi

**Error**:
```
MemoryError
```

**Solutions**:

1. **Add Swap Space**:
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile
   # Set: CONF_SWAPSIZE=2048
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```

2. **Reduce Concurrent Operations**:
   - Analyze fewer markets at once
   - Reduce log retention
   - Clear old data

3. **Check Memory Usage**:
   ```bash
   free -h
   ```

---

## Trading Issues

### Losing Money Consistently

**Analysis Steps**:

1. **Check Win Rate**:
   ```
   /stats
   ```
   Should be >60%. If <50%, something is wrong.

2. **Review Strategy Performance**:
   ```bash
   grep "TRADE" logs/trades.log | tail -50
   ```
   Which strategies are losing?

3. **Check AI Reasoning**:
   ```bash
   grep "reasoning" logs/trading.log | tail -20
   ```
   Is the AI making sense?

**Common Causes**:

- **Too Aggressive**: Reduce position sizes
- **Wrong Strategies**: Disable losing strategies
- **Bad Timing**: Market conditions changed
- **AI Hallucination**: Lower confidence threshold

**Solutions**:

```bash
# Switch to more conservative settings
MAX_POSITION_SIZE=5.0
RISK_PER_TRADE=1.0
DAILY_LOSS_LIMIT=10.0

# Enable only arbitrage
/disable value
/disable high_frequency
/disable liquidity
```

---

### Positions Not Closing

**Symptom**: Positions held too long

**Causes**:
1. Stop loss not triggering
2. Take profit too high
3. Market illiquid

**Solutions**:

1. **Manual Close**:
   - Log into Polymarket
   - Close position manually

2. **Adjust Exit Thresholds**:
   ```python
   # In src/trading/risk_manager.py
   stop_loss_pct = -10.0  # Was -15.0 (tighter)
   ```

3. **Check Position Management**:
   ```bash
   grep "manage_positions" logs/trading.log
   ```

---

### Not Finding Opportunities

**Symptom**: No trades executed

**Checks**:

1. **Are Markets Available?**:
   ```bash
   grep "Scanned.*markets" logs/trading.log | tail -5
   ```

2. **Are Strategies Enabled?**:
   ```
   /strategies
   ```

3. **Is Confidence Threshold Too High?**:
   ```python
   # In src/trading/engine.py
   if ai_analysis.get('confidence', 0) < 50:  # Was 70
   ```

4. **Check Risk Limits**:
   ```
   /risk
   ```
   Maybe daily limit reached?

---

## System Issues

### Systemd Service Won't Start

**Error**:
```
Failed to start polymarket-bot.service
```

**Solution**:

1. **Check Status**:
   ```bash
   sudo systemctl status polymarket-bot
   ```

2. **View Logs**:
   ```bash
   sudo journalctl -u polymarket-bot -n 50
   ```

3. **Common Issues**:
   - Wrong path in service file
   - Wrong user (should be 'pi')
   - Permissions issue
   - .env file not found

4. **Fix Service File**:
   ```bash
   sudo nano /etc/systemd/system/polymarket-bot.service
   ```

   Ensure paths are correct:
   ```ini
   WorkingDirectory=/home/pi/polymarket-ai-bot
   ExecStart=/home/pi/polymarket-ai-bot/venv/bin/python src/main.py
   ```

5. **Reload**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart polymarket-bot
   ```

---

### Logs Not Writing

**Issue**: Log files empty or not updating

**Solution**:

1. **Check Permissions**:
   ```bash
   ls -la logs/
   # Should be writable
   ```

2. **Create Logs Directory**:
   ```bash
   mkdir -p logs
   chmod 755 logs
   ```

3. **Check Log Level**:
   ```bash
   # In .env
   LOG_LEVEL=INFO  # or DEBUG
   ```

4. **Manual Test**:
   ```python
   from loguru import logger
   logger.add("test.log")
   logger.info("Test message")
   ```

---

## Network Issues

### Connection Timeouts

**Error**:
```
requests.exceptions.ConnectTimeout
```

**Solutions**:

1. **Check Internet**:
   ```bash
   ping 8.8.8.8
   ping polymarket.com
   ```

2. **Check RPC**:
   ```bash
   curl https://polygon-rpc.com
   ```

3. **Try Different RPC**:
   ```bash
   # In .env
   POLYGON_RPC_URL=https://rpc-mainnet.matic.network
   ```

4. **Increase Timeout**:
   ```python
   # In py-clob-client initialization
   timeout=30  # seconds
   ```

---

### Rate Limit Exceeded

**Error**:
```
Rate limit exceeded: 429
```

**Solution**:

1. **Slow Down Requests**:
   ```python
   # In src/trading/engine.py
   time.sleep(600)  # 10 minutes between scans
   ```

2. **Use Different RPC**:
   - Infura
   - Alchemy
   - QuickNode

3. **Implement Backoff**:
   ```python
   import time

   def retry_with_backoff(func, max_retries=3):
       for i in range(max_retries):
           try:
               return func()
           except RateLimitError:
               time.sleep(2 ** i)  # Exponential backoff
       raise
   ```

---

## Getting Help

If you can't solve the issue:

### 1. Collect Debugging Info

```bash
# System info
uname -a
python --version

# Recent logs
tail -100 logs/errors.log > debug_errors.txt
tail -100 logs/trading.log > debug_trading.txt

# Current status
/status  # Via Telegram
```

### 2. Check Documentation

- README.md
- This file
- Code comments

### 3. Search Logs

```bash
# Find specific error
grep -r "error_message" logs/

# See all errors today
grep ERROR logs/trading.log | grep "$(date +%Y-%m-%d)"
```

### 4. Enable Debug Mode

```bash
# In .env
LOG_LEVEL=DEBUG

# Restart
sudo systemctl restart polymarket-bot

# Watch live
tail -f logs/trading.log
```

### 5. Create GitHub Issue

Include:
- Error message
- Relevant logs
- Steps to reproduce
- System info
- What you've tried

---

## Prevention Tips

1. **Start with Paper Trading**
   - Test for at least 1 week
   - Verify all features work
   - Only then go live

2. **Monitor Closely at First**
   - Check every hour first day
   - Review all trades
   - Adjust as needed

3. **Set Conservative Limits**
   - Low position sizes
   - Tight stop losses
   - Low daily loss limit

4. **Keep Software Updated**
   ```bash
   git pull
   pip install -r requirements.txt --upgrade
   ```

5. **Regular Backups**
   ```bash
   # Backup .env and database
   cp .env .env.backup
   cp data/*.db data/backup/
   ```

6. **Monitor Resources**
   ```bash
   # Check disk space
   df -h

   # Check memory
   free -h

   # Check CPU
   top
   ```

---

**Remember**: Most issues are configuration-related. Double-check your `.env` file!
