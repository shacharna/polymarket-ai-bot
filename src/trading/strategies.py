"""
Stock Trading Strategies with Polygon.io Indicator Confirmation
Implements momentum, mean reversion, breakout, and gap strategies
Enhanced with RSI, SMA, and MACD confirmations for higher win rate
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from datetime import datetime


class TradingStrategy:
    """Base class for trading strategies"""

    def __init__(self, name: str, polygon_client=None):
        self.name = name
        self.enabled = True
        self.polygon = polygon_client  # Polygon.io client for indicators

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
    Momentum/trend-following strategy with RSI confirmation.
    Rides strong directional moves confirmed by volume + RSI filters.

    RSI Filter: Only enters momentum trades when RSI is 40-70
    - Avoids overbought (>70) situations that often reverse
    - Avoids deeply oversold (<40) which isn't true momentum
    """

    def __init__(self, polygon_client=None):
        super().__init__("Momentum", polygon_client)
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

            # Get RSI from Polygon for confirmation
            rsi = None
            if self.polygon:
                try:
                    indicators = self.polygon.get_indicators_bundle(symbol)
                    rsi = indicators.get("rsi_14")
                except Exception as e:
                    logger.debug(f"Could not fetch Polygon indicators for {symbol}: {e}")

            # Strong upward momentum
            if (
                change_pct >= self.min_intraday_change_pct
                and volume_ratio >= self.min_volume_ratio
                and price_trending == "up"
            ):
                base_confidence = min(85, 55 + int(change_pct * 5) + int(volume_ratio * 3))

                # RSI filter: Avoid overbought, prefer 40-70 range
                if rsi is not None:
                    if rsi > 70:
                        logger.info(
                            f"{symbol}: RSI overbought ({rsi:.1f}), skipping momentum trade"
                        )
                        return None
                    elif rsi < 40:
                        logger.info(
                            f"{symbol}: RSI too low ({rsi:.1f}), not strong momentum"
                        )
                        return None
                    elif 50 <= rsi <= 65:
                        # Sweet spot for momentum - boost confidence
                        base_confidence = min(95, base_confidence + 5)
                        logger.info(f"{symbol}: RSI {rsi:.1f} - ideal momentum zone")
                    else:
                        logger.info(f"{symbol}: RSI {rsi:.1f} - acceptable momentum range")
                else:
                    logger.debug(f"{symbol}: No RSI data, using price/volume only")

                return {
                    "action": "BUY",
                    "confidence": base_confidence,
                    "reasoning": (
                        f"{symbol} momentum BUY: {change_pct:+.1f}% intraday, "
                        f"{volume_ratio:.1f}x avg volume, uptrend confirmed"
                        f"{f', RSI {rsi:.1f}' if rsi else ''}"
                    ),
                    "position_size": 8,
                    "strategy_type": "momentum_long",
                }

            # Strong downward momentum short
            if (
                change_pct <= -self.min_intraday_change_pct
                and volume_ratio >= self.min_volume_ratio
                and price_trending == "down"
            ):
                base_confidence = min(82, 52 + int(abs(change_pct) * 5) + int(volume_ratio * 3))

                # RSI filter: only short when RSI is 30-60
                # - RSI > 60: strong downward momentum with room to fall
                # - RSI < 30: already oversold, likely to bounce — skip
                if rsi is not None:
                    if rsi < 30:
                        logger.info(
                            f"{symbol}: RSI oversold ({rsi:.1f}), skipping momentum short"
                        )
                        return None
                    elif rsi > 65:
                        logger.info(
                            f"{symbol}: RSI {rsi:.1f} too high for short momentum, skip"
                        )
                        return None
                    elif 40 <= rsi <= 55:
                        # Sweet spot: room to fall, confirmed downtrend
                        base_confidence = min(92, base_confidence + 5)
                        logger.info(f"{symbol}: RSI {rsi:.1f} - ideal short momentum zone")
                    else:
                        logger.info(f"{symbol}: RSI {rsi:.1f} - acceptable short range")
                else:
                    logger.debug(f"{symbol}: No RSI data, using price/volume only for short")

                return {
                    "action": "SELL",
                    "confidence": base_confidence,
                    "reasoning": (
                        f"{symbol} momentum SHORT: {change_pct:+.1f}% intraday, "
                        f"{volume_ratio:.1f}x avg volume, downtrend confirmed"
                        f"{f', RSI {rsi:.1f}' if rsi else ''}"
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
    Mean reversion strategy with RSI oversold confirmation.
    Catches genuine oversold bounces using Polygon RSI.

    RSI Confirmation: Only enters when RSI < 30-35 (truly oversold)
    - RSI < 25 = very oversold, higher confidence
    - RSI > 35 = not oversold enough, skip
    """

    def __init__(self, polygon_client=None):
        super().__init__("MeanReversion", polygon_client)
        self.oversold_threshold = -3.0  # Stock down 3%+ intraday

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            change_pct = snapshot.get("intraday_change_pct", 0)
            symbol = snapshot.get("symbol", "?")
            price = snapshot.get("price", 0)

            if not bars or len(bars) < 10:
                return None

            # Get RSI from Polygon (preferred) or calculate fallback
            rsi = None
            if self.polygon:
                try:
                    indicators = self.polygon.get_indicators_bundle(symbol)
                    rsi = indicators.get("rsi_14")
                except Exception as e:
                    logger.debug(f"Could not fetch Polygon RSI for {symbol}: {e}")

            # Fallback: calculate RSI if Polygon unavailable
            if rsi is None:
                rsi = self._calculate_rsi(bars, period=14)
                logger.debug(f"{symbol}: Using calculated RSI (Polygon unavailable)")

            # Oversold bounce opportunity (long)
            if change_pct <= self.oversold_threshold:
                if rsi is None:
                    logger.debug(f"{symbol}: No RSI data available, skipping")
                    return None

                if rsi > 35:
                    logger.info(
                        f"{symbol}: RSI {rsi:.1f} not oversold enough (need <35), skip"
                    )
                    return None

                # RSI confirms oversold - calculate confidence
                base_confidence = min(80, 55 + int(abs(change_pct) * 3))

                if rsi < 25:
                    # Very oversold = higher bounce probability
                    base_confidence = min(90, base_confidence + 10)
                    logger.info(f"{symbol}: RSI {rsi:.1f} VERY OVERSOLD - strong bounce setup!")
                else:
                    logger.info(f"{symbol}: RSI {rsi:.1f} oversold - mean reversion setup")

                return {
                    "action": "BUY",
                    "confidence": base_confidence,
                    "reasoning": (
                        f"{symbol} mean reversion: {change_pct:+.1f}% drop, "
                        f"RSI={rsi:.1f} oversold, expecting bounce"
                    ),
                    "position_size": 7,
                    "strategy_type": "mean_reversion_long",
                }

            # Overbought reversal opportunity (short)
            # Mirror of oversold bounce: stock up hard + RSI overbought = likely to revert down
            overbought_threshold = abs(self.oversold_threshold)  # +3.0%
            if change_pct >= overbought_threshold:
                if rsi is None:
                    logger.debug(f"{symbol}: No RSI data available, skipping overbought short")
                    return None

                if rsi < 65:
                    logger.info(
                        f"{symbol}: RSI {rsi:.1f} not overbought enough (need >65), skip short"
                    )
                    return None

                base_confidence = min(78, 52 + int(change_pct * 3))

                if rsi > 75:
                    # Very overbought = higher reversal probability
                    base_confidence = min(88, base_confidence + 10)
                    logger.info(f"{symbol}: RSI {rsi:.1f} VERY OVERBOUGHT - strong reversal short!")
                else:
                    logger.info(f"{symbol}: RSI {rsi:.1f} overbought - reversal short setup")

                return {
                    "action": "SELL",
                    "confidence": base_confidence,
                    "reasoning": (
                        f"{symbol} overbought reversal SHORT: {change_pct:+.1f}% up, "
                        f"RSI={rsi:.1f} overbought, expecting pullback"
                    ),
                    "position_size": 6,
                    "strategy_type": "overbought_reversal_short",
                }

            return None
        except Exception as e:
            logger.error(f"Error in mean reversion analysis: {e}")
            return None

    def _calculate_rsi(
        self, bars: List[Dict[str, Any]], period: int = 14
    ) -> Optional[float]:
        """Calculate RSI from bar data (fallback if Polygon unavailable)"""
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
    Breakout strategy with SMA trend confirmation.
    Only trades breakouts when price is above SMA50 (uptrend confirmed).

    SMA Confirmation:
    - Price > SMA50 > SMA200 = STRONG uptrend (+15 confidence)
    - Price > SMA50 = uptrend (+8 confidence)
    - Price < SMA50 = skip (avoid breakouts in downtrends)
    """

    def __init__(self, polygon_client=None):
        super().__init__("Breakout", polygon_client)
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
            volumes = [b["volume"] for b in lookback if b.get("volume", 0) > 0]

            recent_high = max(highs[:-1])  # Exclude current bar
            avg_volume = sum(volumes) / len(volumes) if volumes else 1

            current_bar = bars[-1]
            current_volume = current_bar.get("volume", 0)
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            # Check for bullish breakout
            if price > recent_high and volume_ratio >= self.min_volume_multiplier:
                breakout_pct = ((price - recent_high) / recent_high) * 100
                base_confidence = min(85, 60 + int(breakout_pct * 5) + int(volume_ratio * 3))

                # Get SMAs from Polygon for trend confirmation
                if self.polygon:
                    try:
                        indicators = self.polygon.get_indicators_bundle(symbol)
                        sma50 = indicators.get("sma_50")
                        sma200 = indicators.get("sma_200")

                        if sma50 and sma200:
                            if price > sma50 > sma200:
                                # Golden cross + price above both = STRONG uptrend
                                base_confidence = min(95, base_confidence + 15)
                                trend_text = f"STRONG UPTREND (${price:.2f} > SMA50 ${sma50:.2f} > SMA200 ${sma200:.2f})"
                                logger.info(f"{symbol}: Breakout with {trend_text}")
                            elif price > sma50:
                                # Price above SMA50 = uptrend confirmed
                                base_confidence = min(90, base_confidence + 8)
                                trend_text = f"uptrend (${price:.2f} > SMA50 ${sma50:.2f})"
                                logger.info(f"{symbol}: Breakout with {trend_text}")
                            else:
                                # Price below SMA50 = downtrend, skip breakout
                                logger.info(
                                    f"{symbol}: Breakout but price ${price:.2f} below SMA50 ${sma50:.2f}, skip"
                                )
                                return None
                        elif sma50:
                            if price > sma50:
                                base_confidence = min(88, base_confidence + 5)
                                trend_text = f"uptrend (${price:.2f} > SMA50 ${sma50:.2f})"
                                logger.info(f"{symbol}: Breakout with {trend_text}")
                            else:
                                logger.info(f"{symbol}: Breakout but price below SMA50, skip")
                                return None
                        else:
                            logger.debug(f"{symbol}: No SMA data for trend confirmation")
                            trend_text = "volume confirmed"
                    except Exception as e:
                        logger.debug(f"Could not fetch Polygon SMAs for {symbol}: {e}")
                        trend_text = "volume confirmed"
                else:
                    trend_text = "volume confirmed"

                return {
                    "action": "BUY",
                    "confidence": base_confidence,
                    "reasoning": (
                        f"{symbol} BREAKOUT: ${price:.2f} above ${recent_high:.2f} "
                        f"(+{breakout_pct:.1f}%), {volume_ratio:.1f}x volume, {trend_text}"
                    ),
                    "position_size": 8,
                    "strategy_type": "breakout_long",
                }

            return None
        except Exception as e:
            logger.error(f"Error in breakout analysis: {e}")
            return None


class GapStrategy(TradingStrategy):
    """
    Gap trading strategy - trades gap-ups and gap-downs at market open.
    Most effective in first 30-60 minutes of trading.
    (Indicators less relevant for gap plays - based on overnight price action)
    """

    def __init__(self, polygon_client=None):
        super().__init__("Gap", polygon_client)
        self.min_gap_pct = 2.0

    def analyze(
        self, snapshot: Dict[str, Any], bars: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            gap_pct = snapshot.get("gap_pct", 0)
            intraday_pct = snapshot.get("intraday_change_pct", 0)
            symbol = snapshot.get("symbol", "?")

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

            # Gap DOWN bounce (buying the dip)
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
    """Manages multiple trading strategies with Polygon.io integration"""

    def __init__(self, polygon_client=None):
        """Initialize strategy manager with all strategies"""
        self.polygon = polygon_client
        self.strategies = {
            "momentum": MomentumStrategy(polygon_client),
            "mean_reversion": MeanReversionStrategy(polygon_client),
            "breakout": BreakoutStrategy(polygon_client),
            "gap": GapStrategy(polygon_client),
        }
        logger.info(
            f"Strategy Manager initialized with {len(self.strategies)} strategies"
            + (f" (Polygon.io enabled)" if polygon_client else "")
        )

    def set_polygon_client(self, polygon_client):
        """Update Polygon client for all strategies"""
        self.polygon = polygon_client
        for strategy in self.strategies.values():
            strategy.polygon = polygon_client
        logger.info("Polygon client updated for all strategies")

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
