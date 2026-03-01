# Supabase Setup Guide for Trade History Analytics

## Overview

Your trading bot now supports storing trade history in Supabase (PostgreSQL) for powerful performance analytics. This is **completely optional** - the bot works fine without it, but with Supabase you get:

- ✅ Unlimited trade history storage
- ✅ Performance analytics by strategy, symbol, time period
- ✅ Win rate tracking and P&L trends
- ✅ Telegram commands: `/analytics` and `/history`
- ✅ Non-blocking async writes (doesn't slow down trading)
- ✅ Graceful failure handling (bot continues trading if DB fails)

## Step 1: Create Supabase Account

1. Go to https://supabase.com
2. Click "Start your project"
3. Sign up with GitHub (free tier includes 500MB database + 2GB bandwidth/month)

## Step 2: Create a New Project

1. Click "New Project"
2. Choose organization or create one
3. Set project details:
   - **Name:** `trading-bot-history` (or any name you prefer)
   - **Database Password:** Generate a strong password (save it!)
   - **Region:** Choose closest to your Raspberry Pi location
   - **Plan:** Free (plenty for personal trading bot)
4. Click "Create new project"
5. Wait 2-3 minutes for provisioning

## Step 3: Get Your API Credentials

1. In your project dashboard, click **Settings** (gear icon) in left sidebar
2. Click **API** tab
3. Copy these two values:
   - **Project URL** (looks like `https://xxxxx.supabase.co`)
   - **anon/public key** (long string starting with `eyJ...`)

## Step 4: Run the Database Schema

1. In Supabase dashboard, click **SQL Editor** (left sidebar)
2. Click "New query"
3. Open the schema file: `src/database/schema.sql`
4. Copy the **entire contents** of that file
5. Paste into Supabase SQL Editor
6. Click "Run" (or press Ctrl+Enter)
7. You should see "Success. No rows returned"

This creates:
- `trades` table with all trade details
- Indexes for fast queries
- `trade_performance` view for analytics
- Auto-update trigger for `updated_at` column

## Step 5: Add Credentials to .env File

1. Open your `.env` file
2. Add these two lines at the end:

```bash
# Supabase (optional - for trade history analytics)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_KEY=eyJxxxxx...your-anon-key...
```

3. Save the file

## Step 6: Install Supabase Python Library

```bash
# Activate your virtual environment first
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install supabase (and psutil if not already installed)
pip install supabase>=2.3.0 psutil>=5.9.0
```

**Or** just reinstall all requirements:
```bash
pip install -r requirements.txt
```

## Step 7: Test the Integration

### Test 1: Start the Bot

```bash
python src/main.py
```

Look for this log message:
```
Trade history logging to Supabase enabled
```

If you see this, Supabase is connected! ✅

If you see an error, check:
- `SUPABASE_URL` and `SUPABASE_KEY` are correct in `.env`
- You ran the schema SQL script
- Your internet connection is working

### Test 2: Execute a Trade (Paper Trading)

Let the bot run and execute a trade (or force one if you know how). After the trade executes, check:

1. Go to Supabase dashboard
2. Click **Table Editor** (left sidebar)
3. Click `trades` table
4. You should see your trade entry! 🎉

### Test 3: Telegram Commands

Open Telegram and try these new commands:

```
/analytics
```
Shows performance summary for last 30 days:
- Win rate, total P&L, best/worst trades
- Average return percentage
- Average hold time

```
/analytics 7
```
Shows last 7 days only

```
/history
```
Shows last 10 trades across all symbols

```
/history AAPL
```
Shows all trades for AAPL specifically

## Database Structure

Your `trades` table stores:

**Entry Details:**
- Symbol, side (buy/sell), price, quantity, timestamp
- Alpaca order ID for reference

**Exit Details** (filled when trade closes):
- Exit price, exit time, exit reason
- Profit/loss ($ and %)
- Hold duration (minutes)

**Strategy & AI:**
- Strategy name (momentum, breakout, etc.)
- Confidence score (0-100)
- AI setup score (1-10) and risk score (1-10)
- AI reasoning text

**Technical Indicators** (at entry):
- RSI, SMA (20/50), MACD, volume

**Metadata:**
- Paper trading flag
- Bot version for tracking changes

## Monitoring Your Database

### Check Database Usage

1. Go to Supabase dashboard
2. Click **Settings** → **Usage**
3. Monitor:
   - Database size (free tier = 500MB)
   - Bandwidth (free tier = 2GB/month)

### View Analytics

The schema includes a pre-built view `trade_performance` that aggregates daily performance by strategy. Query it:

```sql
SELECT * FROM trade_performance
WHERE paper_trading = true
ORDER BY trade_date DESC
LIMIT 30;
```

This shows:
- Trades per day by strategy
- Win/loss counts
- Average return %
- Total P&L
- Average hold time
- Average confidence scores

## How It Works (Technical Details)

### Non-Blocking Architecture

```
Trade Execution
  ↓
Alpaca order placed successfully
  ↓
Trade queued for DB write (non-blocking, <1ms)
  ↓
Background thread writes to Supabase
  ↓
If DB write fails: log error, continue trading
```

The bot **never waits** for database writes. If Supabase is down, the bot continues trading normally and just logs errors.

### Async Writer

The `SupabaseClient` class uses:
- **Queue-based writes:** Trades are queued in memory (max 1000)
- **Background thread:** Separate thread processes the queue
- **Graceful failure:** DB errors don't affect trading
- **Auto-reconnect:** Automatically reconnects if network fails

### Database Client Lifecycle

```python
# In engine.py __init__:
self.supabase = get_supabase_client(url, key)

# After successful trade:
self.supabase.log_trade_entry(
    symbol=symbol,
    side=side,
    entry_price=price,
    quantity=qty,
    # ... all trade details
)

# On bot shutdown:
self.supabase.stop()  # Waits up to 10s for queue to empty
```

## Troubleshooting

### "Supabase initialization failed"

**Cause:** Invalid credentials or network issue

**Fix:**
1. Double-check `SUPABASE_URL` and `SUPABASE_KEY` in `.env`
2. Ensure no extra spaces or quotes around values
3. Test internet connection to `supabase.co`

### "Table 'trades' does not exist"

**Cause:** Schema not created

**Fix:**
1. Go to SQL Editor in Supabase
2. Run the `src/database/schema.sql` script again

### "/analytics shows 'Analytics Not Available'"

**Cause:** Bot started without Supabase configured

**Fix:**
1. Add `SUPABASE_URL` and `SUPABASE_KEY` to `.env`
2. Restart the bot

### No trades appearing in database

**Possible causes:**
1. Bot hasn't executed any trades yet (check logs)
2. DB write failed (check `logs/trading.log` for Supabase errors)
3. Queue is backed up (check `SupabaseClient` stats)

**Debug:**
```python
# Add to bot code temporarily:
if self.supabase:
    stats = self.supabase.get_stats()
    print(f"Supabase stats: {stats}")
```

## Cost & Limits

### Supabase Free Tier

- **Database:** 500MB (thousands of trades)
- **Bandwidth:** 2GB/month
- **API requests:** Unlimited
- **Rows:** 100,000 (more than enough)

### Estimated Usage

Assuming 20 trades/day:
- **Rows per month:** ~600 trades
- **Database size:** ~100KB/month (0.02% of limit)
- **Bandwidth:** ~50MB/month (2.5% of limit)

You'll be **well within free tier** limits for years!

### If You Hit Limits

Unlikely, but if you somehow fill 500MB:

**Option 1: Delete old data**
```sql
-- Delete trades older than 1 year
DELETE FROM trades
WHERE entry_time < NOW() - INTERVAL '1 year';
```

**Option 2: Upgrade**
- $25/month for 8GB database (overkill for trading bot)

## Backups

Supabase automatically backs up your database:
- **Free tier:** Daily backups, 7-day retention
- **Pro tier:** Point-in-time recovery

To manually export:
1. Go to **Database** → **Backups**
2. Click "Export database"
3. Download SQL dump

## Advanced: Custom Queries

You have full SQL access. Example queries:

### Best performing strategies
```sql
SELECT
  strategy,
  COUNT(*) as trades,
  AVG(profit_loss_pct) as avg_return,
  SUM(profit_loss) as total_pl
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY strategy
ORDER BY avg_return DESC;
```

### Win rate by hour of day
```sql
SELECT
  EXTRACT(HOUR FROM entry_time) as hour,
  COUNT(*) as trades,
  SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as win_rate
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY hour
ORDER BY hour;
```

### Consecutive wins/losses analysis
```sql
-- This is more complex, use the trade_performance view for quick insights
SELECT * FROM trade_performance
WHERE paper_trading = false
ORDER BY trade_date DESC;
```

## Security Notes

- ✅ **anon/public key** is safe to use in your `.env` (it has Row Level Security)
- ✅ RLS (Row Level Security) should be enabled on `trades` table (Supabase does this by default)
- ✅ Your credentials are filtered from logs by `SensitiveDataFilter`
- ✅ `.env` is in `.gitignore` - credentials won't be committed

**Do NOT share your service_role key** - only use the anon/public key!

## Next Steps

Once Supabase is working:

1. **Monitor performance:** Use `/analytics` daily to track win rate
2. **Analyze patterns:** Which strategies work best? What times?
3. **Optimize:** Disable underperforming strategies
4. **Set goals:** Track progress toward profitability targets

Your trade history is now stored forever for analysis! 📊📈

---

**Need help?** Check the logs:
- `logs/trading.log` - Supabase connection and write logs
- `logs/errors.log` - Database errors
- Supabase Dashboard → Logs - SQL query logs
