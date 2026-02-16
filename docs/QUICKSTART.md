# Quick Start Guide

Get your Polymarket AI trading bot up and running in under 30 minutes!

## Prerequisites Checklist

Before starting, make sure you have:

- [ ] Raspberry Pi 4 (8GB) with Raspberry Pi OS installed
- [ ] Internet connection
- [ ] ~$150 available:
  - $100 for trading capital
  - $5-10 for MATIC (gas fees)
  - $20-40 for RPC/API services (optional)

## Step-by-Step Setup

### 1. Prepare Raspberry Pi (5 minutes)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3 python3-pip python3-venv git -y

# Create directory
mkdir ~/polymarket-ai-bot
cd ~/polymarket-ai-bot
```

### 2. Clone Repository (1 minute)

If you have the code on GitHub:
```bash
git clone YOUR_REPO_URL .
```

Or if files are local:
```bash
# Copy project files to ~/polymarket-ai-bot/
```

### 3. Set Up Python Environment (3 minutes)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

This will take a few minutes on Raspberry Pi.

### 4. Create Crypto Wallet (10 minutes)

**Follow the detailed guide**: [WALLET_SETUP.md](WALLET_SETUP.md)

**Quick version**:
1. Install MetaMask browser extension
2. Create new wallet (save seed phrase!)
3. Add Polygon network
4. Get wallet address and private key

### 5. Fund Your Wallet (5 minutes)

You need:
- **$100-500 USDC** on Polygon network (for trading)
- **$5-10 MATIC** on Polygon network (for gas fees)

**Easiest method**:
1. Buy USDC on Coinbase/Binance
2. Withdraw to your wallet address
3. **IMPORTANT**: Select "Polygon" network, NOT Ethereum!

**Verify funds arrived**:
1. Open MetaMask
2. Switch to Polygon network
3. Check balance shows USDC and MATIC

### 6. Get Polymarket API Keys (5 minutes)

1. Go to https://polymarket.com
2. Connect your wallet
3. Navigate to Settings → API
4. Click "Create API Key"
5. Save:
   - API Key
   - API Secret
   - Passphrase

### 7. Get Anthropic API Key (3 minutes)

1. Go to https://console.anthropic.com
2. Sign up / Log in
3. Go to API Keys
4. Create new key
5. Copy and save it

**Cost**: ~$5-20/month depending on trading frequency

### 8. Create Telegram Bot (5 minutes)

1. Open Telegram
2. Search for `@BotFather`
3. Send `/newbot`
4. Follow instructions
5. Save the Bot Token

**Get Chat ID**:
1. Message your bot
2. Visit: `https://api.telegram.org/botYOUR_TOKEN/getUpdates`
3. Find your chat ID in the response

### 9. Configure Environment (5 minutes)

```bash
cd ~/polymarket-ai-bot

# Copy example configuration
cp .env.example .env

# Edit configuration
nano .env
```

**Fill in ALL fields**:

```bash
# Polymarket (from Step 6)
POLYMARKET_API_KEY=your_api_key
POLYMARKET_API_SECRET=your_api_secret
POLYMARKET_API_PASSPHRASE=your_passphrase

# Wallet (from Step 4)
WALLET_PRIVATE_KEY=your_private_key
WALLET_ADDRESS=your_wallet_address

# Anthropic (from Step 7)
ANTHROPIC_API_KEY=your_anthropic_key

# Telegram (from Step 8)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Settings
INITIAL_BALANCE=100.0
MAX_POSITION_SIZE=10.0
DAILY_LOSS_LIMIT=20.0
RISK_PER_TRADE=2.0

# IMPORTANT: Start with paper trading!
PAPER_TRADING=true
LOG_LEVEL=INFO
```

**Save**: Ctrl+O, Enter, Ctrl+X

### 10. Test Run (2 minutes)

```bash
# Activate venv if not already
source venv/bin/activate

# Run the bot
python src/main.py
```

**Expected output**:
```
🚀 Polymarket AI Trading Bot
==================================================
2026-02-16 15:30:00 | INFO | Starting Polymarket AI Trading Bot...
2026-02-16 15:30:01 | INFO | Mode: PAPER TRADING
2026-02-16 15:30:02 | INFO | Polymarket client initialized successfully
2026-02-16 15:30:03 | INFO | AI Trading Agent initialized
2026-02-16 15:30:04 | INFO | ✅ All components initialized
2026-02-16 15:30:05 | INFO | ✅ Telegram bot started
2026-02-16 15:30:06 | INFO | ✅ Starting trading engine...
```

**You should receive a Telegram message**: "🤖 Bot Started"

**Press Ctrl+C to stop** after verifying it works.

### 11. Set Up 24/7 Operation (3 minutes)

```bash
# Copy systemd service file
sudo cp config/polymarket-bot.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start
sudo systemctl enable polymarket-bot

# Start the service
sudo systemctl start polymarket-bot

# Check status
sudo systemctl status polymarket-bot
```

**Should show**: `Active: active (running)`

### 12. Monitor & Verify (Ongoing)

**Via Telegram**:
```
/status   # Check bot is running
/balance  # Verify balance
/strategies  # See active strategies
```

**View Logs**:
```bash
# Live logs
sudo journalctl -u polymarket-bot -f

# Recent errors
tail -50 logs/errors.log

# Recent trades
tail -50 logs/trades.log
```

## First 24 Hours Checklist

### Hour 1: Initial Monitoring
- [ ] Verify bot is scanning markets (check logs)
- [ ] Check Telegram notifications are working
- [ ] Send `/status` every 15 minutes

### Hours 2-6: Verification
- [ ] Bot should identify some opportunities
- [ ] If paper trading, verify simulated trades
- [ ] Check AI reasoning makes sense (in logs)
- [ ] Monitor for errors

### Hours 6-24: Observation
- [ ] Check `/stats` every few hours
- [ ] Verify win rate is reasonable (>60%)
- [ ] No crashes or restarts
- [ ] Telegram alerts working

## Going Live (After 1 Week Paper Trading)

**ONLY proceed if**:
- ✅ Bot ran for 7+ days without issues
- ✅ Paper trading shows profit (or small loss <10%)
- ✅ You understand how the bot makes decisions
- ✅ All strategies are working as expected

**To go live**:

```bash
# Stop the bot
sudo systemctl stop polymarket-bot

# Edit config
nano .env

# Change this line:
PAPER_TRADING=false  # Was true

# Save and restart
sudo systemctl start polymarket-bot
```

**You'll receive a warning**:
```
⚠️  WARNING: LIVE TRADING MODE - REAL MONEY AT RISK!
⚠️  Press Ctrl+C within 10 seconds to abort...
```

**Start with small positions**:
```bash
INITIAL_BALANCE=100.0  # Start small
MAX_POSITION_SIZE=5.0  # $5 max per trade
DAILY_LOSS_LIMIT=10.0  # Stop if lose $10
```

## Recommended Settings for Beginners

### Conservative (Recommended)
```bash
INITIAL_BALANCE=100.0
MAX_POSITION_SIZE=5.0
DAILY_LOSS_LIMIT=10.0
RISK_PER_TRADE=1.0

# Strategies:
/disable high_frequency
/disable value
# Keep: arbitrage, liquidity
```

**Expected**: 5-10% monthly return, low risk

### Balanced
```bash
INITIAL_BALANCE=200.0
MAX_POSITION_SIZE=10.0
DAILY_LOSS_LIMIT=20.0
RISK_PER_TRADE=2.0

# All strategies enabled
```

**Expected**: 15-25% monthly return, medium risk

### Aggressive (NOT for beginners)
```bash
INITIAL_BALANCE=500.0
MAX_POSITION_SIZE=25.0
DAILY_LOSS_LIMIT=50.0
RISK_PER_TRADE=3.0

# All strategies enabled
```

**Expected**: 30-50% monthly return, HIGH risk

## Common First-Time Issues

### "No markets found"
- Check internet connection
- Verify Polymarket API is working: https://polymarket.com
- Wait 5 minutes, bot scans periodically

### "Invalid API key"
- Double-check credentials in `.env`
- No spaces around `=` sign
- Regenerate keys if needed

### "Insufficient funds"
- Make sure USDC is on **Polygon**, not Ethereum
- Check you have MATIC for gas
- Verify wallet address is correct

### Telegram bot not responding
- Check bot token is correct
- Verify chat ID
- Send `/start` to your bot manually

### Bot keeps restarting
- Check logs: `sudo journalctl -u polymarket-bot -n 100`
- Look for error message
- See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Daily Routine

### Morning (5 minutes)
```
/status   # Check overnight performance
/positions  # Review open trades
/risk     # Verify limits OK
```

### Evening (5 minutes)
```
/stats    # Daily performance
/trades   # Review today's trades
```

### Weekly (15 minutes)
- Review full statistics
- Analyze which strategies perform best
- Adjust settings if needed
- Check API costs (Anthropic)
- Verify no missed notifications

## Resources

- **Full Documentation**: [README.md](../README.md)
- **Wallet Setup**: [WALLET_SETUP.md](WALLET_SETUP.md)
- **Trading Strategies**: [STRATEGIES.md](STRATEGIES.md)
- **Telegram Commands**: [TELEGRAM.md](TELEGRAM.md)
- **Troubleshooting**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Safety Reminders

1. **Never share your private keys**
2. **Start with paper trading**
3. **Use only money you can afford to lose**
4. **Monitor the bot daily**
5. **Start with small positions**
6. **Set conservative limits**
7. **Understand the risks**

## Next Steps

Once comfortable with basic operation:

1. **Learn the Strategies** - Read [STRATEGIES.md](STRATEGIES.md)
2. **Optimize Settings** - Adjust based on performance
3. **Advanced Features** - Explore custom strategies
4. **Join Community** - Share experiences (when available)

---

## Quick Reference Card

**Stop the bot**:
```bash
sudo systemctl stop polymarket-bot
```

**Start the bot**:
```bash
sudo systemctl start polymarket-bot
```

**View logs**:
```bash
sudo journalctl -u polymarket-bot -f
```

**Edit config**:
```bash
nano .env
sudo systemctl restart polymarket-bot
```

**Check status**:
```
/status (via Telegram)
```

---

**Good luck and trade responsibly! 🚀**

*Remember: The goal is to learn and grow, not to get rich quick. Start small, be patient, and let the AI work for you.*
