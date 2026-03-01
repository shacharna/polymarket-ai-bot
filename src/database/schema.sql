-- Trading Bot Database Schema for Supabase
-- Stores trade history for performance analytics

-- Trades table: Stores all executed trades with entry/exit details
CREATE TABLE IF NOT EXISTS trades (
  id BIGSERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Trade identification
  symbol VARCHAR(10) NOT NULL,
  side VARCHAR(4) NOT NULL CHECK (side IN ('buy', 'sell')),
  alpaca_order_id VARCHAR(50), -- Alpaca order ID for reference

  -- Entry details
  entry_price DECIMAL(10, 2) NOT NULL,
  entry_time TIMESTAMPTZ NOT NULL,
  quantity INTEGER NOT NULL,
  position_value DECIMAL(12, 2) NOT NULL,

  -- Exit details (NULL if position still open)
  exit_price DECIMAL(10, 2),
  exit_time TIMESTAMPTZ,
  exit_reason VARCHAR(50), -- 'take_profit', 'stop_loss', 'trailing_stop', 'manual', 'end_of_day'

  -- Performance metrics
  profit_loss DECIMAL(10, 2),
  profit_loss_pct DECIMAL(6, 3),
  hold_duration_minutes INTEGER,

  -- Strategy & AI scores
  strategy VARCHAR(50) NOT NULL, -- 'momentum', 'mean_reversion', 'breakout', 'gap'
  confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
  ai_setup_score INTEGER CHECK (ai_setup_score >= 1 AND ai_setup_score <= 10),
  ai_risk_score INTEGER CHECK (ai_risk_score >= 1 AND ai_risk_score <= 10),
  ai_reasoning TEXT,

  -- Technical indicators at entry
  rsi_14 DECIMAL(5, 2),
  sma_20 DECIMAL(10, 2),
  sma_50 DECIMAL(10, 2),
  macd DECIMAL(10, 4),
  macd_signal DECIMAL(10, 4),
  volume_avg BIGINT,
  volume_current BIGINT,

  -- Metadata
  paper_trading BOOLEAN DEFAULT true,
  bot_version VARCHAR(20),

  -- Timestamps
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RLS: Disable for this bot (single-user service, not multi-tenant)
-- The anon key is used by the trading bot; RLS would block all writes.
ALTER TABLE trades DISABLE ROW LEVEL SECURITY;

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_paper_trading ON trades(paper_trading);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason) WHERE exit_reason IS NOT NULL;

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to call the function on UPDATE
CREATE TRIGGER update_trades_updated_at
  BEFORE UPDATE ON trades
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

-- View for quick analytics
CREATE OR REPLACE VIEW trade_performance AS
SELECT
  DATE_TRUNC('day', entry_time) as trade_date,
  strategy,
  paper_trading,
  COUNT(*) as total_trades,
  SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
  SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
  ROUND(AVG(profit_loss_pct)::numeric, 2) as avg_return_pct,
  ROUND(SUM(profit_loss)::numeric, 2) as total_profit_loss,
  ROUND(AVG(hold_duration_minutes)::numeric, 0) as avg_hold_minutes,
  ROUND(AVG(confidence)::numeric, 1) as avg_confidence,
  ROUND(AVG(ai_setup_score)::numeric, 1) as avg_setup_score
FROM trades
WHERE exit_time IS NOT NULL
GROUP BY trade_date, strategy, paper_trading
ORDER BY trade_date DESC, strategy;

-- Comments for documentation
COMMENT ON TABLE trades IS 'Historical trade data for performance analytics';
COMMENT ON COLUMN trades.alpaca_order_id IS 'Alpaca broker order ID for cross-reference';
COMMENT ON COLUMN trades.exit_reason IS 'Why the trade was closed: take_profit, stop_loss, trailing_stop, manual, end_of_day';
COMMENT ON COLUMN trades.confidence IS 'Strategy confidence score (0-100)';
COMMENT ON COLUMN trades.ai_setup_score IS 'AI setup quality score (1-10), higher is better';
COMMENT ON COLUMN trades.ai_risk_score IS 'AI risk assessment (1-10), higher is riskier';
COMMENT ON VIEW trade_performance IS 'Aggregated daily performance metrics by strategy';
