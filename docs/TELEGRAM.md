# Telegram Bot Commands

Control and monitor your trading bot from anywhere using Telegram.

## Setup

### 1. Create Your Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Start a chat and send `/newbot`
3. Choose a name for your bot (e.g., "My Polymarket Bot")
4. Choose a username (must end in 'bot', e.g., "mypolymarket_bot")
5. BotFather will give you a **Bot Token** - save this!

Example:
```
Done! Congratulations on your new bot.
Token: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2. Get Your Chat ID

1. Start a chat with your new bot
2. Send any message (e.g., "hello")
3. Open this URL in your browser (replace YOUR_BOT_TOKEN):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
4. Look for `"chat":{"id":123456789`
5. That number is your **Chat ID**

### 3. Configure the Bot

Add to your `.env` file:
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

### 4. Test Connection

Start your bot:
```bash
python src/main.py
```

You should receive a message in Telegram: "🤖 Bot Started"

## Available Commands

### Basic Commands

#### `/start`
**Description**: Start interaction with the bot and see welcome message

**Response**: Welcome message with all available commands

**Usage**:
```
/start
```

---

#### `/help`
**Description**: Display help message with all commands

**Response**: Same as /start

**Usage**:
```
/help
```

---

### Monitoring Commands

#### `/status`
**Description**: Get current bot status and overview

**Response**:
```
📊 Bot Status

🔹 Status: Running
💰 Balance: $98.50
📈 Daily P&L: +$2.30
🎯 Open Positions: 2
📊 Trades Today: 5
⚡ Mode: PAPER TRADING

Last Update: 2026-02-16T14:30:15
```

**Usage**:
```
/status
```

---

#### `/balance`
**Description**: Check detailed account balance

**Response**:
```
💰 Account Balance

💵 USDC: $98.50
📊 In Positions: $20.00
💎 Available: $78.50
📈 Total Value: $118.50

🎯 Initial: $100.00
📊 P&L: +$18.50 (+18.50%)
```

**Usage**:
```
/balance
```

---

#### `/positions`
**Description**: View all open positions with P&L

**Response**:
```
📊 Open Positions

1. Will Bitcoin reach $100K by 2026?
   Side: BUY
   Entry: $0.4500
   Current: $0.4750
   Size: $10.00
   P&L: +$0.55 (+5.56%)
   Age: 3.5h

2. Will Democrats win Senate?
   Side: SELL
   Entry: $0.6200
   Current: $0.6000
   Size: $10.00
   P&L: +$0.32 (+3.23%)
   Age: 1.2h
```

**Usage**:
```
/positions
```

---

#### `/trades`
**Description**: View recent trade history (last 10 trades)

**Response**:
```
📜 Recent Trades

✅ 1. Will Bitcoin reach $100K?
   BUY @ $0.4500
   Size: $10.00
   P&L: +$2.50
   Time: 14:20

❌ 2. Election outcome market
   SELL @ $0.7200
   Size: $8.00
   P&L: -$1.20
   Time: 12:15
```

**Usage**:
```
/trades
```

---

#### `/stats`
**Description**: View detailed trading statistics

**Response**:
```
📈 Trading Statistics

📊 Performance
   Total Trades: 47
   Winning Trades: 35
   Losing Trades: 12
   Win Rate: 74.5%

💰 Profit & Loss
   Total P&L: +$18.50
   Avg Win: $2.10
   Avg Loss: -$1.50
   Best Trade: +$5.25
   Worst Trade: -$3.10

📊 Today
   Trades: 5
   P&L: +$2.30
   Win Rate: 80.0%
```

**Usage**:
```
/stats
```

---

### Control Commands

#### `/pause`
**Description**: Pause trading (stops taking new positions, keeps existing ones)

**Response**:
```
⏸️ Trading paused. Use /resume to continue.
```

**Usage**:
```
/pause
```

**Use Cases**:
- Temporary market uncertainty
- Need to review bot behavior
- Taking a break from trading

---

#### `/resume`
**Description**: Resume trading after pause

**Response**:
```
▶️ Trading resumed.
```

**Usage**:
```
/resume
```

---

### Strategy Commands

#### `/strategies`
**Description**: View all available strategies and their status

**Response**:
```
🎯 Trading Strategies

• arbitrage: ✅ Enabled
• high_frequency: ✅ Enabled
• liquidity: ❌ Disabled
• value: ✅ Enabled

Use /enable <strategy> or /disable <strategy>
```

**Usage**:
```
/strategies
```

---

#### `/enable <strategy>`
**Description**: Enable a specific trading strategy

**Parameters**:
- `strategy`: Name of strategy (arbitrage, high_frequency, liquidity, value)

**Response**:
```
✅ Enabled liquidity strategy
```

**Usage**:
```
/enable liquidity
/enable arbitrage
```

---

#### `/disable <strategy>`
**Description**: Disable a specific trading strategy

**Parameters**:
- `strategy`: Name of strategy

**Response**:
```
❌ Disabled high_frequency strategy
```

**Usage**:
```
/disable high_frequency
/disable value
```

---

### Risk Management Commands

#### `/risk`
**Description**: View current risk metrics and limits

**Response**:
```
🛡️ Risk Metrics

📊 Daily Limits
   Loss: $5.20 / $20.00
   Usage: 26.0%
   Trades: 5 / 50

⚙️ Position Limits
   Max Size: $10.00
   Risk/Trade: 2.0%

✅ Status
   Can Trade: Yes ✅
```

**Usage**:
```
/risk
```

---

## Automatic Notifications

The bot automatically sends you notifications for important events:

### Trade Execution

```
🟢 Trade Executed

Market: Will Bitcoin reach $100K by end of 2026?
Action: BUY
Price: $0.4500
Size: $10.00
Strategy: value
Confidence: 85%

Reasoning: Market underpricing likelihood given historical trends
and current momentum. 10 months is sufficient time.
```

### Stop Loss Triggered

```
🛑 Stop Loss Triggered

Market: Election outcome market
Entry: $0.7200
Exit: $0.6120
Loss: -$1.50 (-15.0%)
Reason: Stop Loss

Position closed automatically.
```

### Take Profit Reached

```
✅ Take Profit Reached

Market: Weather prediction
Entry: $0.5000
Exit: $0.6000
Profit: +$2.00 (+20.0%)
Reason: Take Profit

Position closed automatically.
```

### Daily Loss Limit

```
⚠️ Daily Loss Limit Reached

Total loss today: $20.00
Trading paused for the rest of the day.
Will resume tomorrow at midnight.

This is a safety measure to protect your capital.
```

### Bot Errors

```
❌ Error Occurred

Error: Failed to fetch market data
Time: 14:30:15
Action: Retrying in 60 seconds

If this persists, check logs or restart bot.
```

### Bot Started

```
🤖 Bot Started

Mode: PAPER TRADING
Balance: $100.00
Max Position: $10.00
Daily Loss Limit: $20.00

Bot is now monitoring markets 24/7!
```

### Bot Stopped

```
🛑 Bot Stopped

Total Runtime: 15h 32m
Trades: 12
P&L: +$8.50

Bot has been shut down.
```

## Tips for Using Telegram Bot

### Best Practices

1. **Enable Notifications**
   - Make sure Telegram notifications are ON
   - You'll be alerted to every trade
   - Critical for monitoring

2. **Check Status Regularly**
   - Use `/status` 2-3 times per day
   - Monitor P&L trends
   - Verify bot is running

3. **Review Positions Before Bed**
   - Use `/positions` to check open trades
   - Ensure you're comfortable with exposure
   - Consider manual exits if concerned

4. **Monitor Risk Metrics**
   - Use `/risk` to check limit usage
   - Stay well under daily loss limit
   - Adjust if needed

5. **Analyze Performance Weekly**
   - Use `/stats` to review win rate
   - Identify which strategies work best
   - Adjust strategy mix accordingly

### Security Tips

1. **Keep Bot Token Private**
   - Never share your bot token
   - If compromised, create new bot via @BotFather

2. **Secure Your Chat**
   - Only send commands from your registered Chat ID
   - Bot ignores other users

3. **Don't Share Trading Data**
   - Screenshots of `/balance` or `/stats` reveal your capital
   - Keep your trading performance private

### Troubleshooting

#### Bot not responding to commands

1. Check bot is running:
   ```bash
   sudo systemctl status polymarket-bot
   ```

2. Check Telegram token in `.env`

3. Restart bot:
   ```bash
   sudo systemctl restart polymarket-bot
   ```

#### Not receiving notifications

1. Verify Chat ID is correct in `.env`

2. Send `/start` to your bot manually

3. Check bot logs:
   ```bash
   tail -f logs/trading.log | grep Telegram
   ```

#### Wrong data in responses

1. Bot might be caching old data
2. Restart bot to refresh

3. Check Polymarket API connectivity

## Advanced: Custom Commands

You can add custom commands by editing `src/telegram/bot.py`:

```python
async def custom_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom command"""
    # Your logic here
    await update.message.reply_text("Custom response")

# Add handler in start() method
self.application.add_handler(CommandHandler("custom", self.custom_command))
```

Example custom commands you could add:
- `/exitall` - Close all positions immediately
- `/report` - Generate daily PDF report
- `/graph` - Generate P&L chart
- `/markets` - List top markets by volume

---

**Pro Tip**: Add your bot to a private group chat and have multiple people monitor it collaboratively!
