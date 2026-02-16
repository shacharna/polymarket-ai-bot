"""
Trading Strategies
Implements different trading approaches for Polymarket
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from datetime import datetime, timedelta
import statistics


class TradingStrategy:
    """Base class for trading strategies"""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    def analyze(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analyze market and return trading signal

        Returns:
            None or {
                "action": "BUY|SELL|HOLD",
                "confidence": 0-100,
                "reasoning": str,
                "position_size": float
            }
        """
        raise NotImplementedError


class ArbitrageStrategy(TradingStrategy):
    """
    Low-risk arbitrage strategy
    Looks for price discrepancies and guaranteed profits
    """

    def __init__(self):
        super().__init__("Arbitrage")
        self.min_profit_pct = 2.0  # Minimum 2% profit to execute

    def analyze(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Look for arbitrage opportunities

        Checks if YES + NO prices != 1.0 (inefficiency)
        """
        try:
            yes_price = market_data.get('yes_price', 0)
            no_price = market_data.get('no_price', 0)

            if not yes_price or not no_price:
                return None

            # Check if prices don't sum to ~1.0
            price_sum = yes_price + no_price
            ideal_sum = 1.0

            # If sum < 1.0, there's potential arbitrage
            # (buy both sides, guaranteed profit at resolution)
            if price_sum < ideal_sum:
                potential_profit_pct = ((ideal_sum - price_sum) / price_sum) * 100

                if potential_profit_pct >= self.min_profit_pct:
                    return {
                        "action": "BUY",
                        "confidence": 85,
                        "reasoning": f"Arbitrage opportunity: prices sum to {price_sum:.4f}, "
                                   f"potential {potential_profit_pct:.2f}% profit",
                        "position_size": 8,  # High position size for low-risk arb
                        "target": "BOTH"  # Buy both YES and NO
                    }

            # Check for single-side arbitrage (price too low/high)
            if yes_price < 0.10 and market_data.get('implied_probability', 0.5) > 0.3:
                return {
                    "action": "BUY",
                    "confidence": 75,
                    "reasoning": f"YES underpriced at ${yes_price:.4f}",
                    "position_size": 6
                }

            if no_price < 0.10 and market_data.get('implied_probability', 0.5) < 0.7:
                return {
                    "action": "SELL",
                    "confidence": 75,
                    "reasoning": f"NO underpriced at ${no_price:.4f}",
                    "position_size": 6
                }

            return None

        except Exception as e:
            logger.error(f"Error in arbitrage analysis: {e}")
            return None


class HighFrequencyStrategy(TradingStrategy):
    """
    High-frequency strategy for markets near resolution
    Targets markets priced at 95c+ with imminent resolution
    """

    def __init__(self):
        super().__init__("HighFrequency")
        self.min_price = 0.95
        self.max_hours_to_resolution = 48

    def analyze(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Look for nearly-resolved markets with clear outcomes
        """
        try:
            current_price = market_data.get('price', 0)
            hours_to_resolution = market_data.get('hours_to_resolution', 9999)

            # Check if market is near resolution and highly priced
            if hours_to_resolution <= self.max_hours_to_resolution:
                if current_price >= self.min_price:
                    # High confidence in YES outcome
                    potential_profit = ((1.0 - current_price) / current_price) * 100

                    return {
                        "action": "BUY",
                        "confidence": 80,
                        "reasoning": f"Near resolution ({hours_to_resolution}h), "
                                   f"high probability at ${current_price:.4f}, "
                                   f"{potential_profit:.2f}% upside",
                        "position_size": 7
                    }

                elif current_price <= (1.0 - self.min_price):
                    # High confidence in NO outcome
                    return {
                        "action": "SELL",
                        "confidence": 80,
                        "reasoning": f"Near resolution ({hours_to_resolution}h), "
                                   f"low probability, high NO confidence",
                        "position_size": 7
                    }

            return None

        except Exception as e:
            logger.error(f"Error in high-frequency analysis: {e}")
            return None


class LiquidityStrategy(TradingStrategy):
    """
    Liquidity provision strategy
    Provides liquidity to new markets for spread profits
    """

    def __init__(self):
        super().__init__("Liquidity")
        self.max_market_age_hours = 24
        self.min_volume = 100

    def analyze(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Look for new markets with low liquidity
        """
        try:
            market_age_hours = market_data.get('age_hours', 9999)
            current_volume = market_data.get('volume', 0)
            spread = market_data.get('spread', 0)

            # Target new markets with low volume but decent spread
            if market_age_hours <= self.max_market_age_hours:
                if current_volume < 1000 and spread > 0.02:
                    return {
                        "action": "BUY",
                        "confidence": 60,
                        "reasoning": f"New market ({market_age_hours}h old), "
                                   f"low liquidity, {spread*100:.1f}% spread",
                        "position_size": 4,  # Medium-low size for new markets
                        "strategy_type": "market_making"
                    }

            return None

        except Exception as e:
            logger.error(f"Error in liquidity analysis: {e}")
            return None


class ValueStrategy(TradingStrategy):
    """
    Value investing strategy
    Looks for mispriced markets based on fundamental analysis
    """

    def __init__(self):
        super().__init__("Value")

    def analyze(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Compare current price to estimated fair value
        """
        try:
            current_price = market_data.get('price', 0)
            fair_value = market_data.get('fair_value_estimate', None)

            if not fair_value:
                # Can't analyze without fair value estimate
                return None

            # Calculate mispricing
            mispricing_pct = ((fair_value - current_price) / current_price) * 100

            # Require at least 15% mispricing for value play
            min_mispricing = 15.0

            if abs(mispricing_pct) >= min_mispricing:
                if mispricing_pct > 0:
                    # Underpriced - BUY
                    confidence = min(90, 60 + int(abs(mispricing_pct) / 5))

                    return {
                        "action": "BUY",
                        "confidence": confidence,
                        "reasoning": f"Underpriced by {mispricing_pct:.1f}% "
                                   f"(fair value: ${fair_value:.4f})",
                        "position_size": 6
                    }
                else:
                    # Overpriced - SELL
                    confidence = min(90, 60 + int(abs(mispricing_pct) / 5))

                    return {
                        "action": "SELL",
                        "confidence": confidence,
                        "reasoning": f"Overpriced by {abs(mispricing_pct):.1f}% "
                                   f"(fair value: ${fair_value:.4f})",
                        "position_size": 6
                    }

            return None

        except Exception as e:
            logger.error(f"Error in value analysis: {e}")
            return None


class StrategyManager:
    """Manages multiple trading strategies"""

    def __init__(self):
        """Initialize strategy manager with all strategies"""
        self.strategies = {
            "arbitrage": ArbitrageStrategy(),
            "high_frequency": HighFrequencyStrategy(),
            "liquidity": LiquidityStrategy(),
            "value": ValueStrategy()
        }

        logger.info(f"Strategy Manager initialized with {len(self.strategies)} strategies")

    def analyze_market(self, market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Run all enabled strategies on market data

        Args:
            market_data: Market information

        Returns:
            List of signals from all strategies
        """
        signals = []

        for strategy_name, strategy in self.strategies.items():
            if not strategy.enabled:
                continue

            try:
                signal = strategy.analyze(market_data)
                if signal:
                    signal['strategy'] = strategy_name
                    signals.append(signal)
                    logger.debug(f"{strategy_name} strategy generated signal: {signal['action']}")

            except Exception as e:
                logger.error(f"Error in {strategy_name} strategy: {e}")

        return signals

    def get_best_signal(self, signals: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select the best signal from multiple strategies

        Args:
            signals: List of signals

        Returns:
            Best signal or None
        """
        if not signals:
            return None

        # Sort by confidence
        signals_sorted = sorted(signals, key=lambda x: x.get('confidence', 0), reverse=True)

        # Return highest confidence signal
        best_signal = signals_sorted[0]

        logger.info(
            f"Best signal: {best_signal['strategy']} - {best_signal['action']} "
            f"with {best_signal['confidence']}% confidence"
        )

        return best_signal

    def enable_strategy(self, strategy_name: str):
        """Enable a specific strategy"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = True
            logger.info(f"Enabled {strategy_name} strategy")

    def disable_strategy(self, strategy_name: str):
        """Disable a specific strategy"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = False
            logger.info(f"Disabled {strategy_name} strategy")

    def get_enabled_strategies(self) -> List[str]:
        """Get list of enabled strategies"""
        return [
            name for name, strategy in self.strategies.items()
            if strategy.enabled
        ]
