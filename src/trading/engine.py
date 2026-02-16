"""
Trading Engine
Main engine that coordinates all trading activities
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from datetime import datetime, timedelta
import time
import asyncio
from threading import Thread

from src.trading.polymarket_client import PolymarketClient
from src.agents.ai_agent import AITradingAgent
from src.trading.risk_manager import RiskManager
from src.trading.strategies import StrategyManager
from src.monitoring.logger import log_trade
from config.settings import get_settings


class TradingEngine:
    """Main trading engine coordinating all components"""

    def __init__(self):
        """Initialize trading engine"""
        self.settings = get_settings()

        # Initialize components
        self.polymarket = PolymarketClient()
        self.ai_agent = AITradingAgent()
        self.risk_manager = RiskManager()
        self.strategy_manager = StrategyManager()

        # State
        self.is_running = False
        self.is_paused = False
        self.positions = []
        self.trades = []
        self.start_time = datetime.now()

        # Performance tracking
        self.initial_balance = self.settings.initial_balance
        self.current_balance = self.initial_balance

        logger.info("Trading Engine initialized")

    def start(self):
        """Start the trading engine"""
        logger.info("Starting trading engine...")
        self.is_running = True
        self.is_paused = False

        # Main trading loop
        self.run_trading_loop()

    def stop(self):
        """Stop the trading engine"""
        logger.info("Stopping trading engine...")
        self.is_running = False

    def pause(self):
        """Pause trading"""
        logger.info("Pausing trading...")
        self.is_paused = True

    def resume(self):
        """Resume trading"""
        logger.info("Resuming trading...")
        self.is_paused = False

    def run_trading_loop(self):
        """Main trading loop"""
        loop_count = 0

        while self.is_running:
            try:
                loop_count += 1
                logger.debug(f"Trading loop iteration {loop_count}")

                # Check if paused
                if self.is_paused:
                    logger.debug("Trading paused, skipping iteration")
                    time.sleep(30)
                    continue

                # 1. Update balance
                self.update_balance()

                # 2. Check risk limits
                can_trade, reason = self.risk_manager.can_trade()
                if not can_trade:
                    logger.warning(f"Cannot trade: {reason}")
                    time.sleep(60)
                    continue

                # 3. Scan markets
                markets = self.scan_markets()

                # 4. Analyze markets with strategies
                opportunities = self.find_opportunities(markets)

                # 5. Execute trades
                if opportunities:
                    self.execute_opportunities(opportunities)

                # 6. Manage existing positions
                self.manage_positions()

                # Sleep between iterations (every 5 minutes)
                logger.debug("Sleeping for 5 minutes...")
                time.sleep(300)

            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                self.stop()
                break

            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                time.sleep(60)

        logger.info("Trading engine stopped")

    def update_balance(self):
        """Update current balance"""
        try:
            if self.settings.paper_trading:
                # In paper trading, track balance ourselves
                # Start with initial balance, adjust for P&L
                total_pnl = sum(trade.get('pnl', 0) for trade in self.trades)
                self.current_balance = self.initial_balance + total_pnl
            else:
                # Get real balance from Polymarket
                balance_info = self.polymarket.get_balance()
                if balance_info:
                    self.current_balance = balance_info.get('total', 0)

            logger.debug(f"Current balance: ${self.current_balance:.2f}")

        except Exception as e:
            logger.error(f"Error updating balance: {e}")

    def scan_markets(self) -> List[Dict]:
        """
        Scan available markets

        Returns:
            List of market data
        """
        try:
            # Get active markets from Polymarket
            markets = self.polymarket.get_markets(limit=50)

            logger.info(f"Scanned {len(markets)} markets")

            return markets

        except Exception as e:
            logger.error(f"Error scanning markets: {e}")
            return []

    def find_opportunities(self, markets: List[Dict]) -> List[Dict]:
        """
        Find trading opportunities using strategies and AI

        Args:
            markets: List of markets to analyze

        Returns:
            List of opportunities
        """
        opportunities = []

        for market in markets[:10]:  # Analyze top 10 markets
            try:
                # Prepare market data
                market_data = self.prepare_market_data(market)

                # Run strategy analysis
                strategy_signals = self.strategy_manager.analyze_market(market_data)

                if strategy_signals:
                    # Get best signal from strategies
                    best_signal = self.strategy_manager.get_best_signal(strategy_signals)

                    # Validate with AI
                    ai_analysis = self.ai_agent.analyze_market(market_data)

                    # Combine strategy and AI signals
                    if self.should_trade(best_signal, ai_analysis):
                        opportunity = {
                            **market_data,
                            'signal': best_signal,
                            'ai_analysis': ai_analysis,
                            'timestamp': datetime.now()
                        }
                        opportunities.append(opportunity)

                        logger.info(
                            f"Found opportunity: {market_data.get('question', 'Unknown')[:50]}"
                        )

            except Exception as e:
                logger.error(f"Error analyzing market: {e}")
                continue

        logger.info(f"Found {len(opportunities)} trading opportunities")
        return opportunities

    def prepare_market_data(self, market: Dict) -> Dict:
        """
        Prepare market data for analysis

        Args:
            market: Raw market data from API

        Returns:
            Prepared market data
        """
        # Extract relevant information
        # Note: Adjust field names based on actual Polymarket API response

        return {
            'question': market.get('question', ''),
            'description': market.get('description', ''),
            'price': market.get('outcome_prices', [0.5])[0],
            'volume': market.get('volume', 0),
            'liquidity': market.get('liquidity', 0),
            'end_date': market.get('end_date_iso', ''),
            'market_id': market.get('id', ''),
            'token_id': market.get('tokens', [{}])[0].get('token_id', ''),
        }

    def should_trade(self, strategy_signal: Dict, ai_analysis: Dict) -> bool:
        """
        Decide if we should execute trade based on signals

        Args:
            strategy_signal: Signal from strategy
            ai_analysis: Analysis from AI

        Returns:
            True if should trade
        """
        # Both must agree on direction
        if strategy_signal.get('action') != ai_analysis.get('action'):
            logger.debug("Strategy and AI disagree on action")
            return False

        # Require minimum confidence from AI
        if ai_analysis.get('confidence', 0) < 70:
            logger.debug(f"AI confidence too low: {ai_analysis.get('confidence')}%")
            return False

        return True

    def execute_opportunities(self, opportunities: List[Dict]):
        """
        Execute trading opportunities

        Args:
            opportunities: List of opportunities to execute
        """
        # Execute top opportunity (most confident)
        opportunities_sorted = sorted(
            opportunities,
            key=lambda x: x['ai_analysis'].get('confidence', 0),
            reverse=True
        )

        for opp in opportunities_sorted[:1]:  # Execute only 1 at a time
            self.execute_trade(opp)

    def execute_trade(self, opportunity: Dict):
        """
        Execute a single trade

        Args:
            opportunity: Opportunity data
        """
        try:
            ai_analysis = opportunity['ai_analysis']
            action = ai_analysis.get('action')
            confidence = ai_analysis.get('confidence', 0)

            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                confidence=confidence,
                current_balance=self.current_balance,
                ai_suggested_size=ai_analysis.get('position_size', 5)
            )

            # Validate position size
            is_valid, adjusted_size, reason = self.risk_manager.validate_position_size(
                position_size,
                self.current_balance
            )

            if not is_valid:
                logger.warning(f"Invalid position size: {reason}")
                return

            position_size = adjusted_size

            # Execute order
            token_id = opportunity.get('token_id')
            price = opportunity.get('price', 0.5)

            result = self.polymarket.place_order(
                token_id=token_id,
                side=action,
                amount=position_size,
                price=price,
                paper_trading=self.settings.paper_trading
            )

            if result:
                # Record trade
                trade = {
                    'market': opportunity.get('question', 'Unknown'),
                    'action': action,
                    'price': price,
                    'size': position_size,
                    'timestamp': datetime.now(),
                    'strategy': opportunity['signal'].get('strategy', 'Unknown'),
                    'confidence': confidence,
                    'reasoning': ai_analysis.get('reasoning', ''),
                    'order_id': result.get('order_id'),
                    'pnl': 0  # Will be calculated on exit
                }

                self.trades.append(trade)
                self.positions.append({
                    **trade,
                    'entry_price': price,
                    'current_price': price
                })

                # Log trade
                log_trade(
                    action=action,
                    market=trade['market'],
                    price=price,
                    size=position_size,
                    confidence=confidence
                )

                logger.info(
                    f"✅ Executed {action}: {trade['market'][:50]} @ ${price:.4f} | ${position_size:.2f}"
                )

                # Update balance for paper trading
                if self.settings.paper_trading:
                    self.current_balance -= position_size

        except Exception as e:
            logger.error(f"Error executing trade: {e}")

    def manage_positions(self):
        """Monitor and manage open positions"""
        for position in self.positions[:]:
            try:
                # Get current price
                token_id = position.get('token_id')
                if token_id:
                    current_price = self.polymarket.get_midpoint_price(token_id)
                    if current_price:
                        position['current_price'] = current_price

                # Check stop loss
                should_stop, reason = self.risk_manager.should_stop_loss(
                    entry_price=position['entry_price'],
                    current_price=position['current_price'],
                    position_type=position['action']
                )

                if should_stop:
                    logger.warning(f"Stop loss triggered: {reason}")
                    self.close_position(position, reason="Stop Loss")
                    continue

                # Check take profit
                should_exit, reason = self.risk_manager.should_take_profit(
                    entry_price=position['entry_price'],
                    current_price=position['current_price'],
                    position_type=position['action']
                )

                if should_exit:
                    logger.info(f"Take profit triggered: {reason}")
                    self.close_position(position, reason="Take Profit")
                    continue

            except Exception as e:
                logger.error(f"Error managing position: {e}")

    def close_position(self, position: Dict, reason: str = "Manual"):
        """
        Close an open position

        Args:
            position: Position to close
            reason: Reason for closing
        """
        try:
            # Calculate P&L
            entry_price = position['entry_price']
            exit_price = position['current_price']
            size = position['size']

            if position['action'] == 'BUY':
                pnl = (exit_price - entry_price) * size / entry_price
            else:
                pnl = (entry_price - exit_price) * size / entry_price

            # Update trade record
            for trade in self.trades:
                if trade.get('order_id') == position.get('order_id'):
                    trade['pnl'] = pnl
                    trade['exit_price'] = exit_price
                    trade['exit_time'] = datetime.now()
                    trade['exit_reason'] = reason

            # Record with risk manager
            self.risk_manager.record_trade(pnl)

            # Remove from positions
            self.positions.remove(position)

            # Update balance (paper trading)
            if self.settings.paper_trading:
                self.current_balance += (size + pnl)

            logger.info(
                f"Closed position: {position['market'][:50]} | "
                f"P&L: ${pnl:+.2f} | Reason: {reason}"
            )

        except Exception as e:
            logger.error(f"Error closing position: {e}")

    # API methods for Telegram bot

    def get_status(self) -> Dict:
        """Get bot status"""
        return {
            'status': 'Running' if self.is_running and not self.is_paused else 'Paused' if self.is_paused else 'Stopped',
            'balance': self.current_balance,
            'daily_pnl': self.risk_manager.daily_loss,
            'open_positions': len(self.positions),
            'trades_today': self.risk_manager.daily_trades,
            'mode': 'PAPER TRADING' if self.settings.paper_trading else 'LIVE TRADING',
            'last_update': datetime.now().isoformat()
        }

    def get_balance(self) -> Dict:
        """Get balance info"""
        in_positions = sum(p.get('size', 0) for p in self.positions)
        total_pnl = sum(t.get('pnl', 0) for t in self.trades)

        return {
            'usdc': self.current_balance,
            'in_positions': in_positions,
            'available': self.current_balance - in_positions,
            'total': self.current_balance + in_positions,
            'pnl': total_pnl,
            'pnl_pct': (total_pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0
        }

    def get_positions(self) -> List[Dict]:
        """Get open positions"""
        return self.positions

    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades"""
        return sorted(
            self.trades,
            key=lambda x: x.get('timestamp', datetime.min),
            reverse=True
        )[:limit]

    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        completed_trades = [t for t in self.trades if 'exit_time' in t]
        winning_trades = [t for t in completed_trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in completed_trades if t.get('pnl', 0) < 0]

        return {
            'total_trades': len(completed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': (len(winning_trades) / len(completed_trades) * 100) if completed_trades else 0,
            'total_pnl': sum(t.get('pnl', 0) for t in completed_trades),
            'avg_win': sum(t.get('pnl', 0) for t in winning_trades) / len(winning_trades) if winning_trades else 0,
            'avg_loss': sum(t.get('pnl', 0) for t in losing_trades) / len(losing_trades) if losing_trades else 0,
            'best_trade': max([t.get('pnl', 0) for t in completed_trades]) if completed_trades else 0,
            'worst_trade': min([t.get('pnl', 0) for t in completed_trades]) if completed_trades else 0,
            'trades_today': self.risk_manager.daily_trades,
            'pnl_today': self.risk_manager.daily_loss,
            'win_rate_today': 0  # TODO: Calculate
        }

    def get_strategies(self) -> Dict[str, bool]:
        """Get enabled strategies"""
        strategies = {}
        for name, strategy in self.strategy_manager.strategies.items():
            strategies[name] = strategy.enabled
        return strategies

    def get_risk_metrics(self) -> Dict:
        """Get risk metrics"""
        return self.risk_manager.get_risk_metrics()
