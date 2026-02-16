# Wallet Setup Guide

This guide will help you create and configure a cryptocurrency wallet for use with Polymarket.

## Prerequisites

- Basic understanding of cryptocurrency
- Secure computer/device
- Strong password manager

## Step 1: Install MetaMask

1. Go to https://metamask.io
2. Download and install MetaMask for your browser
3. Click "Create a Wallet"
4. **CRITICAL**: Write down your Secret Recovery Phrase (12-24 words)
   - Store it in a safe place (NOT on your computer)
   - Never share it with anyone
   - You'll need it to recover your wallet

## Step 2: Add Polygon Network

MetaMask starts on Ethereum mainnet. We need to add Polygon:

1. Click the network dropdown (top of MetaMask)
2. Click "Add Network"
3. Click "Add Network Manually"
4. Enter these details:

```
Network Name: Polygon Mainnet
RPC URL: https://polygon-rpc.com
Chain ID: 137
Currency Symbol: MATIC
Block Explorer: https://polygonscan.com
```

5. Click "Save"
6. Switch to Polygon network

## Step 3: Get Your Wallet Address

1. Click your account name at the top of MetaMask
2. Your address will be shown (starts with 0x...)
3. Click to copy it
4. Save this address - you'll need it for the bot configuration

## Step 4: Get Your Private Key

⚠️ **WARNING**: Your private key gives FULL access to your funds. Keep it absolutely secure!

1. In MetaMask, click the three dots menu
2. Click "Account Details"
3. Click "Show Private Key"
4. Enter your MetaMask password
5. **Copy the private key and store it securely**
6. You'll add this to the bot's `.env` file

## Step 5: Fund Your Wallet with USDC

Polymarket uses USDC (a stablecoin) on the Polygon network.

### Option A: Bridge from Ethereum

1. Go to https://wallet.polygon.technology/
2. Connect your MetaMask
3. Bridge USDC from Ethereum to Polygon
4. Fees: ~$5-20 depending on Ethereum gas prices

### Option B: Buy Directly on Polygon

1. Use a CEX (Centralized Exchange) like:
   - Binance
   - Coinbase
   - Kraken
2. Buy USDC
3. Withdraw to your Polygon address
   - **Make sure to select Polygon network, not Ethereum!**
4. Fees: Usually $1-5

### Option C: Crypto On-Ramp (Fiat → USDC)

1. Use services like:
   - Transak
   - MoonPay
   - Ramp Network
2. Buy USDC directly to Polygon
3. Fees: 3-5% typically

### Recommended Starting Amount

- Testing: $10-20
- Conservative: $50-100
- Your budget: $100-500

**Start small!** You can always add more later.

## Step 6: Get MATIC for Gas Fees

Transactions on Polygon require MATIC for gas fees (very cheap, usually $0.01-0.10 per transaction).

1. Buy a small amount of MATIC (~$5 worth)
2. Send to your Polygon wallet address
3. This will last for hundreds of transactions

## Step 7: Connect to Polymarket

1. Go to https://polymarket.com
2. Click "Connect Wallet"
3. Select MetaMask
4. Approve the connection
5. You're now connected!

## Step 8: Get Polymarket API Credentials

To trade programmatically, you need API credentials:

1. Log into Polymarket
2. Go to Settings → API
3. Click "Create API Key"
4. Save these securely:
   - API Key
   - API Secret
   - Passphrase
5. You'll add these to the bot's `.env` file

## Step 9: Configure the Bot

Edit your `.env` file:

```bash
# Polymarket Configuration
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_API_SECRET=your_api_secret_here
POLYMARKET_API_PASSPHRASE=your_passphrase_here

# Wallet Configuration
WALLET_PRIVATE_KEY=your_private_key_here
WALLET_ADDRESS=your_wallet_address_here
```

## Security Best Practices

### DO:
- ✅ Keep your seed phrase offline in a safe place
- ✅ Use a hardware wallet for large amounts (Ledger, Trezor)
- ✅ Enable 2FA on all exchange accounts
- ✅ Use strong, unique passwords
- ✅ Regularly backup your wallet
- ✅ Start with small amounts for testing

### DON'T:
- ❌ Share your private key with anyone
- ❌ Store private keys in cloud storage
- ❌ Take screenshots of seed phrases
- ❌ Use public WiFi when accessing wallet
- ❌ Click suspicious links
- ❌ Enter seed phrase on websites

## Troubleshooting

### "Insufficient funds" error
- Make sure you have USDC on Polygon (not Ethereum!)
- Check you have MATIC for gas fees

### "Wrong network" error
- Switch MetaMask to Polygon Mainnet
- Refresh the page

### Transaction failed
- Increase gas limit slightly
- Check you have enough MATIC
- Wait a few minutes and try again

### Can't see my USDC
- Click "Import tokens" in MetaMask
- Enter USDC contract address: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- It should appear

## Next Steps

Once your wallet is set up and funded:

1. Test with paper trading first (`PAPER_TRADING=true`)
2. Make a small manual trade on Polymarket to verify everything works
3. Start the bot with a small balance
4. Monitor closely for the first 24 hours
5. Gradually increase position sizes as you gain confidence

## Resources

- MetaMask Guide: https://metamask.io/faqs/
- Polygon Documentation: https://docs.polygon.technology/
- Polymarket Help: https://polymarket.com/help
- USDC on Polygon: https://www.circle.com/en/usdc

---

⚠️ **Remember**: Only invest what you can afford to lose!
