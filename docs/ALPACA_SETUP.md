# Alpaca Markets Setup Guide

How to set up your Alpaca Markets account for the stock trading bot.

## What is Alpaca?

Alpaca Markets is a commission-free stock trading API. It provides:
- Free paper trading (demo account with $100,000 fake money)
- Commission-free US stock trading
- REST API for automated trading
- Real-time market data

## Step 1: Create Account

1. Go to https://alpaca.markets
2. Click "Sign Up"
3. Complete registration with email
4. Verify your email

## Step 2: Paper Trading Keys (Start Here)

Paper trading lets you test the bot risk-free.

1. Log into https://app.alpaca.markets
2. Switch to "Paper Trading" mode (toggle at top)
3. Go to API Keys section
4. Click "Generate New Keys"
5. Save both:
   - **API Key ID** (e.g., `PKXXXXXXXXXXXXXXXXXX`)
   - **Secret Key** (shown once - save immediately!)

### Configure in `.env`:
```
ALPACA_API_KEY=your_api_key_id
ALPACA_SECRET_KEY=your_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets
PAPER_TRADING=true
```

## Step 3: Verify Connection

```bash
python -c "
from alpaca_trade_api import REST
api = REST('YOUR_KEY', 'YOUR_SECRET', 'https://paper-api.alpaca.markets')
account = api.get_account()
print(f'Connected! Equity: \${float(account.equity):,.2f}')
"
```

Should show: `Connected! Equity: $100,000.00`

## Step 4: Going Live (After Paper Trading)

Only after successful paper trading:

1. Complete KYC verification on Alpaca (requires ID + SSN)
2. Fund your account (bank transfer, wire, etc.)
3. Generate LIVE API keys
4. Update `.env`:
   ```
   ALPACA_API_KEY=your_live_key
   ALPACA_SECRET_KEY=your_live_secret
   ALPACA_BASE_URL=https://api.alpaca.markets
   PAPER_TRADING=false
   ```

## Important Notes

### PDT Rule (Pattern Day Trader)
- If account equity < $25,000, you're limited to 3 day trades per 5 business days
- A day trade = buying and selling the same stock on the same day
- The bot tracks this automatically via `/risk` command
- Paper trading accounts start with $100,000 so PDT doesn't apply there

### Market Hours
- US stock market: 9:30 AM - 4:00 PM Eastern Time
- The bot only trades during market hours by default
- Pre-market (4:00 AM - 9:30 AM ET) and after-hours (4:00 PM - 8:00 PM ET) are not supported

### Commission-Free
- Alpaca charges $0 commission on US stock trades
- No minimum account balance for paper trading
- $0 minimum for live trading (but PDT rule applies under $25k)

## Troubleshooting

### "Invalid API key"
- Make sure you're using Paper keys with paper URL, or Live keys with live URL
- Don't mix paper keys with `https://api.alpaca.markets` (live URL)
- Regenerate keys if needed

### "Account not found"
- Verify account status at https://app.alpaca.markets
- Complete any pending verification steps

### "Insufficient buying power"
- Check account balance: `/balance` in Telegram
- Paper accounts reset to $100k if you create new keys
