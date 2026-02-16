# Polymarket AI Trading Bot 🤖

An autonomous AI-powered trading bot for Polymarket prediction markets, running 24/7 on Raspberry Pi 4.

## ⚠️ Important Disclaimer

**Trading involves significant financial risk. This bot is for educational purposes. Only invest money you can afford to lose.**

- Only 7.6% of Polymarket traders are profitable
- Start with paper trading mode before using real money
- Never invest more than you can afford to lose
- Past performance does not guarantee future results

## 🎯 Features

- **AI-Powered Decision Making**: Uses Claude AI (Anthropic) for market analysis
- **24/7 Autonomous Trading**: Runs continuously on Raspberry Pi
- **Multiple Trading Strategies**:
  - Arbitrage detection
  - News-based trading
  - Liquidity provision
  - Market inefficiency exploitation
- **Risk Management**:
  - Daily loss limits
  - Position size limits
  - Stop-loss automation
  - Paper trading mode
- **Telegram Control**: Monitor and control the bot remotely
- **Real-time Monitoring**: Comprehensive logging and alerts

## 🛠️ Technology Stack

- Python 3.9+
- Anthropic Claude API
- Polymarket CLOB API (py-clob-client)
- Web3.py for Polygon blockchain
- Python Telegram Bot
- SQLAlchemy for data storage
- Loguru for logging

## 📋 Prerequisites

### Hardware
- Raspberry Pi 4 (8GB RAM recommended)
- MicroSD card (32GB+ recommended)
- Stable internet connection
- Power supply

### Software
- Raspberry Pi OS (64-bit)
- Python 3.9.10 or higher

### Accounts & Keys
1. **Polymarket Account**
   - Create account at https://polymarket.com
   - Generate API credentials

2. **Polygon Wallet**
   - MetaMask or similar wallet
   - Fund with USDC on Polygon network

3. **Anthropic API Key**
   - Sign up at https://console.anthropic.com
   - Generate API key

4. **Telegram Bot**
   - Create bot via @BotFather on Telegram
   - Get bot token and your chat ID

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd polymarket-ai-bot
```

### 2. Set Up Python Environment

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
sudo apt install python3-pip python3-venv -y

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

Fill in all required credentials in the `.env` file.

### 4. Create Polygon Wallet (If you don't have one)

See [WALLET_SETUP.md](docs/WALLET_SETUP.md) for detailed instructions.

## 🎮 Usage

### Paper Trading (Recommended First)

```bash
# Make sure PAPER_TRADING=true in .env
python src/main.py
```

### Live Trading

```bash
# Set PAPER_TRADING=false in .env
# WARNING: Uses real money!
python src/main.py
```

### Telegram Commands

Once the bot is running, you can control it via Telegram:

- `/start` - Start the bot
- `/stop` - Stop trading (bot keeps running)
- `/status` - Get current status and balance
- `/positions` - View open positions
- `/balance` - Check account balance
- `/stats` - Trading statistics
- `/strategy <name>` - Change trading strategy
- `/pause` - Pause trading temporarily
- `/resume` - Resume trading

## 🔧 Configuration

Edit `config/settings.py` or `.env` file to customize:

- **Initial Balance**: Starting capital
- **Max Position Size**: Maximum per trade
- **Daily Loss Limit**: Stop trading if exceeded
- **Risk Per Trade**: Percentage of balance to risk
- **Trading Strategies**: Enable/disable specific strategies

## 📊 Trading Strategies

### 1. Arbitrage Strategy (Low Risk)
- Detects price discrepancies across markets
- Executes simultaneous buy/sell orders
- Target: 1-5% per trade

### 2. News-Based Trading (Medium Risk)
- Monitors news feeds and social media
- Uses AI to assess impact on markets
- Quick entry/exit based on events

### 3. Liquidity Provision (Medium Risk)
- Provides liquidity to new markets
- Earns from spreads
- Target: 80-200% APY

### 4. High-Frequency Trading (High Risk)
- Exploits short-term price movements
- Focuses on markets near resolution (95c+)
- Requires quick execution

## 🛡️ Security Best Practices

1. **Never share your private keys or API keys**
2. **Use hardware wallet for large amounts**
3. **Start with small amounts ($10-20) for testing**
4. **Enable 2FA on all accounts**
5. **Regularly backup your wallet**
6. **Monitor bot activity daily**
7. **Set conservative risk limits initially**

## 📈 Monitoring

Logs are stored in `logs/` directory:
- `trading.log` - All trading activity
- `errors.log` - Error tracking
- `performance.log` - Performance metrics

View real-time logs:
```bash
tail -f logs/trading.log
```

## 🔄 Running 24/7 on Raspberry Pi

### Set Up Systemd Service

```bash
sudo cp config/polymarket-bot.service /etc/systemd/system/
sudo systemctl enable polymarket-bot
sudo systemctl start polymarket-bot
```

Check status:
```bash
sudo systemctl status polymarket-bot
```

View logs:
```bash
sudo journalctl -u polymarket-bot -f
```

## 📚 Documentation

- [Wallet Setup Guide](docs/WALLET_SETUP.md)
- [Trading Strategies Explained](docs/STRATEGIES.md)
- [Telegram Bot Commands](docs/TELEGRAM.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [API Reference](docs/API.md)

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## ⚠️ Risk Warning

**IMPORTANT**: This software is provided "as is" without warranty of any kind. Trading cryptocurrencies and prediction markets involves substantial risk of loss. The developers are not responsible for any financial losses incurred while using this software.

- Start with paper trading
- Only invest what you can afford to lose
- Understand the strategies before enabling them
- Monitor the bot regularly
- Be prepared for losses

## 📞 Support

- GitHub Issues: [Report bugs or request features]
- Telegram Community: [Coming soon]
- Documentation: See `docs/` folder

## 🙏 Acknowledgments

- Polymarket for the prediction market platform
- Anthropic for Claude AI
- The open-source community

---

**Built with ❤️ for autonomous trading**

*Remember: Past performance is not indicative of future results. Trade responsibly.*
