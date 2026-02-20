"""
Aggressive Stock Trading Strategies
Implements momentum, mean reversion, breakout, and gap strategies
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from datetime import datetime


class TradingStrategy:
    """Base class for trading strategies"""

    def __init__(self, name: str):
        self.name = name
        self.enabled = True

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze stock data and return trading signal

        Args:
            snapshot: Current market snapshot (price, volume, change)
            bars: Historical OHLCV bars (15-min intervals)

        Returns:
            None or signal dict with action, confidence, reasoning, position_size
        """
        raise NotImplementedError


class MomentumStrategy(TradingStrategy):
    """
    Aggressive momentum/trend-following strategy.
    Rides strong directional moves confirmed by volume.
    """

    def __init__(self):
        super().__init__("Momentum")
        self.min_intraday_change_pct = 2.0
        self.min_volume_ratio = 1.5

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            change_pct = snapshot.get("intraday_change_pct", 0)
            day_volume = snapshot.get("day_volume", 0)
            symbol = snapshot.get("symbol", "?")

            if not bars or day_volume == 0:
                return None

            # Calculate average volume from bars
            volumes = [b["volume"] for b in bars if b.get("volume", 0) > 0]
            avg_volume = sum(volumes) / len(volumes) if volumes else day_volume
            volume_ratio = day_volume / avg_volume if avg_volume > 0 else 1.0

            # Check for recent price acceleration (last 4 bars trending)
            recent_bars = bars[-4:] if len(bars) >= 4 else bars
            price_trending = self._check_trend(recent_bars)

            # Strong upward momentum
            if (
                change_pct >= self.min_intraday_change_pct
                and volume_ratio >= self.min_volume_ratio
                and price_trending == "up"
            ):
                confidence = min(85, 55 + int(change_pct * 5) + int(volume_ratio * 3))
                return {
                    "action": "BUY",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} momentum BUY: {change_pct:+.1f}% intraday, "
                        f"{volume_ratio:.1f}x avg volume, uptrend confirmed"
                    ),
                    "position_size": 8,
                    "strategy_type": "momentum_long",
                }

            # Strong downward momentum (potential short via inverse ETF or avoid)
            if (
                change_pct <= -self.min_intraday_change_pct
                and volume_ratio >= self.min_volume_ratio
                and price_trending == "down"
            ):
                confidence = min(80, 50 + int(abs(change_pct) * 5) + int(volume_ratio * 3))
                return {
                    "action": "SELL",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} momentum SELL: {change_pct:+.1f}% intraday, "
                        f"{volume_ratio:.1f}x avg volume, downtrend confirmed"
                    ),
                    "position_size": 7,
                    "strategy_type": "momentum_short",
                }

            return None
        except Exception as e:
            logger.error(f"Error in momentum analysis: {e}")
            return None

    def _check_trend(self, bars: List[Dict[str, Any]]) -> str:
        """Check if recent bars show a clear trend"""
        if len(bars) < 2:
            return "none"
        closes = [b["close"] for b in bars]
        ups = sum(1 for i in range(1, len(closes)) if closes[i] > closes[i - 1])
        downs = sum(1 for i in range(1, len(closes)) if closes[i] < closes[i - 1])
        total = len(closes) - 1
        if ups >= total * 0.7:
            return "up"
        if downs >= total * 0.7:
            return "down"
        return "none"


class MeanReversionStrategy(TradingStrategy):
    """
    Mean reversion strategy - catches oversold bounces.
    Uses price deviation and RSI-like logic.
    """

    def __init__(self):
        super().__init__("MeanReversion")
        self.oversold_threshold = -3.0  # Stock down 3%+ intraday
        self.overbought_threshold = 5.0  # Stock up 5%+ (fade the rally)

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            change_pct = snapshot.get("intraday_change_pct", 0)
            symbol = snapshot.get("symbol", "?")
            price = snapshot.get("price", 0)

            if not bars or len(bars) < 10:
                return None

            rsi = self._calculate_rsi(bars, period=14)

            # Oversold bounce opportunity
            if change_pct <= self.oversold_threshold and rsi is not None and rsi < 30:
                confidence = min(80, 55 + int(abs(change_pct) * 3) + int((30 - rsi) / 2))
                return {
                    "action": "BUY",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} mean reversion BUY: {change_pct:+.1f}% oversold, "
                        f"RSI={rsi:.0f}, expecting bounce"
                    ),
                    "position_size": 7,
                    "strategy_type": "mean_reversion_long",
                }

            # Overbought fade opportunity
            if change_pct >= self.overbought_threshold and rsi is not None and rsi > 75:
                confidence = min(75, 50 + int(change_pct * 2) + int((rsi - 75) / 2))
                return {
                    "action": "SELL",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} mean reversion SELL: {change_pct:+.1f}% overbought, "
                        f"RSI={rsi:.0f}, expecting pullback"
                    ),
                    "position_size": 6,
                    "strategy_type": "mean_reversion_short",
                }

            return None
        except Exception as e:
            logger.error(f"Error in mean reversion analysis: {e}")
            return None

    def _calculate_rsi(
        self, bars: List[Dict[str, Any]], period: int = 14
    ) -> Optional[float]:
        """Calculate RSI from bar data"""
        if len(bars) < period + 1:
            return None

        closes = [b["close"] for b in bars[-(period + 1) :]]
        gains = []
        losses = []

        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            if delta > 0:
                gains.append(delta)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(delta))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


class BreakoutStrategy(TradingStrategy):
    """
    Breakout strategy - detects price breaking above/below key levels.
    Targets strong volume confirmation on breakouts.
    """

    def __init__(self):
        super().__init__("Breakout")
        self.lookback_bars = 20
        self.min_volume_multiplier = 2.0

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            price = snapshot.get("price", 0)
            day_volume = snapshot.get("day_volume", 0)
            symbol = snapshot.get("symbol", "?")

            if not bars or len(bars) < self.lookback_bars:
                return None

            lookback = bars[-self.lookback_bars :]
            highs = [b["high"] for b in lookback]
            lows = [b["low"] for b in lookback]
            volumes = [b["volume"] for b in lookback if b.get("volume", 0) > 0]

            recent_high = max(highs[:-1])  # Exclude current bar
            recent_low = min(lows[:-1])
            avg_volume = sum(volumes) / len(volumes) if volumes else 1

            current_bar = bars[-1]
            current_volume = current_bar.get("volume", 0)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Bullish breakout above recent high with volume
            if price > recent_high and volume_ratio >= self.min_volume_multiplier:
                breakout_pct = ((price - recent_high) / recent_high) * 100
                confidence = min(85, 60 + int(breakout_pct * 5) + int(volume_ratio * 3))
                return {
                    "action": "BUY",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} BREAKOUT: price ${price:.2f} above "
                        f"${recent_high:.2f} resistance (+{breakout_pct:.1f}%), "
                        f"{volume_ratio:.1f}x volume"
                    ),
                    "position_size": 8,
                    "strategy_type": "breakout_long",
                }

            # Bearish breakdown below recent low with volume
            if price < recent_low and volume_ratio >= self.min_volume_multiplier:
                breakdown_pct = ((recent_low - price) / recent_low) * 100
                confidence = min(80, 55 + int(breakdown_pct * 5) + int(volume_ratio * 3))
                return {
                    "action": "SELL",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} BREAKDOWN: price ${price:.2f} below "
                        f"${recent_low:.2f} support (-{breakdown_pct:.1f}%), "
                        f"{volume_ratio:.1f}x volume"
                    ),
                    "position_size": 7,
                    "strategy_type": "breakout_short",
                }

            return None
        except Exception as e:
            logger.error(f"Error in breakout analysis: {e}")
            return None


class GapStrategy(TradingStrategy):
    """
    Gap trading strategy - trades gap-ups and gap-downs at market open.
    Most effective in first 30 minutes of trading.
    """

    def __init__(self):
        super().__init__("Gap")
        self.min_gap_pct = 2.0
        self.max_minutes_after_open = 60  # Only active first hour

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            gap_pct = snapshot.get("gap_pct", 0)
            change_pct = snapshot.get("change_pct", 0)
            intraday_pct = snapshot.get("intraday_change_pct", 0)
            symbol = snapshot.get("symbol", "?")
            day_volume = snapshot.get("day_volume", 0)

            if abs(gap_pct) < self.min_gap_pct:
                return None

            # Gap UP with continuation (momentum gap)
            if gap_pct >= self.min_gap_pct and intraday_pct > 0:
                confidence = min(80, 55 + int(gap_pct * 3))
                return {
                    "action": "BUY",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} GAP UP: {gap_pct:+.1f}% gap with "
                        f"{intraday_pct:+.1f}% continuation, riding momentum"
                    ),
                    "position_size": 7,
                    "strategy_type": "gap_continuation",
                }

            # Gap UP fading (gap fill play)
            if gap_pct >= self.min_gap_pct * 1.5 and intraday_pct < -0.5:
                confidence = min(75, 50 + int(gap_pct * 2))
                return {
                    "action": "SELL",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} GAP FADE: {gap_pct:+.1f}% gap fading, "
                        f"intraday {intraday_pct:+.1f}%, expecting gap fill"
                    ),
                    "position_size": 6,
                    "strategy_type": "gap_fade",
                }

            # Gap DOWN bounce
            if gap_pct <= -self.min_gap_pct and intraday_pct > 0.5:
                confidence = min(75, 50 + int(abs(gap_pct) * 2))
                return {
                    "action": "BUY",
                    "confidence": confidence,
                    "reasoning": (
                        f"{symbol} GAP DOWN BOUNCE: {gap_pct:+.1f}% gap, "
                        f"bouncing {intraday_pct:+.1f}%, buying the dip"
                    ),
                    "position_size": 7,
                    "strategy_type": "gap_bounce",
                }

            return None
        except Exception as e:
            logger.error(f"Error in gap analysis: {e}")
            return None


class StrategyManager:
    """Manages multiple trading strategies"""

    def __init__(self):
        """Initialize strategy manager with all strategies"""
        self.strategies = {
            "momentum": MomentumStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "breakout": BreakoutStrategy(),
            "gap": GapStrategy(),
        }
        logger.info(
            f"Strategy Manager initialized with {len(self.strategies)} strategies"
        )

    def analyze_stock(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Run all enabled strategies on stock data

        Args:
            snapshot: Current market snapshot
            bars: Historical OHLCV bars

        Returns:
            List of signals from all strategies
        """
        signals = []

        for strategy_name, strategy in self.strategies.items():
            if not strategy.enabled:
                continue
            try:
                signal = strategy.analyze(snapshot, bars)
                if signal:
                    signal["strategy"] = strategy_name
                    signals.append(signal)
                    logger.debug(
                        f"{strategy_name} signal for {snapshot.get('symbol', '?')}: "
                        f"{signal['action']} ({signal['confidence']}%)"
                    )
            except Exception as e:
                logger.error(f"Error in {strategy_name} strategy: {e}")

        return signals

    def get_best_signal(
        self, signals: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Select the highest confidence signal"""
        if not signals:
            return None

        signals_sorted = sorted(
            signals, key=lambda x: x.get("confidence", 0), reverse=True
        )
        best = signals_sorted[0]

        logger.info(
            f"Best signal: {best['strategy']} - {best['action']} "
            f"with {best['confidence']}% confidence"
        )
        return best

    def enable_strategy(self, strategy_name: str):
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = True
            logger.info(f"Enabled {strategy_name} strategy")

    def disable_strategy(self, strategy_name: str):
        if strategy_name in self.strategies:
            self.strategies[strategy_name].enabled = False
            logger.info(f"Disabled {strategy_name} strategy")

    def get_enabled_strategies(self) -> List[str]:
        return [
            name
            for name, strategy in self.strategies.items()
            if strategy.enabled
        ]
