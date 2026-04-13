"""
Polygon.io Technical Indicators Client
Provides SMA, RSI, MACD, and other indicators with intelligent caching
to stay within rate limits (< 100 req/hour for Pi optimization)
"""
from typing import Dict, List, Optional, Any
from polygon import RESTClient
from datetime import datetime, timedelta
from loguru import logger
from config.settings import get_settings
import time


class PolygonIndicatorClient:
    """
    Cached client for Polygon.io technical indicators.

    Rate limit strategy:
    - Cache indicators for 5 minutes
    - Batch requests when possible
    - Prioritize most important indicators (RSI, SMA50, SMA200)
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = RESTClient(self.settings.polygon_api_key)

        # Cache: {symbol: {indicator_name: {data, timestamp}}}
        self.cache = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]
        self.cache_ttl = 300  # 5 minutes cache

        # Rate limiting
        self.request_count = 0
        self.request_window_start = datetime.now()
        self.max_requests_per_hour = 90  # Stay under 100 limit

        logger.info(f"Polygon.io client initialized (max {self.max_requests_per_hour} req/hour)")

    def _check_rate_limit(self):
        # type: () -> bool
        """Check if we can make another request without hitting rate limit"""
        now = datetime.now()
        elapsed_hours = (now - self.request_window_start).total_seconds() / 3600

        if elapsed_hours >= 1.0:
            # Reset counter after 1 hour
            self.request_count = 0
            self.request_window_start = now
            return True

        if self.request_count >= self.max_requests_per_hour:
            logger.warning(
                f"Polygon rate limit reached ({self.request_count}/{self.max_requests_per_hour}). "
                f"Using cached data only."
            )
            return False

        return True

    def _get_cached(self, symbol, indicator_name):
        # type: (str, str) -> Optional[Any]
        """Get cached indicator if still valid"""
        if symbol not in self.cache:
            return None

        if indicator_name not in self.cache[symbol]:
            return None

        cached = self.cache[symbol][indicator_name]
        age = (datetime.now() - cached["timestamp"]).total_seconds()

        if age > self.cache_ttl:
            return None  # Expired

        logger.debug(f"Cache hit: {symbol} {indicator_name} (age: {age:.0f}s)")
        return cached["data"]

    def _set_cache(self, symbol, indicator_name, data):
        # type: (str, str, Any) -> None
        """Store indicator in cache"""
        if symbol not in self.cache:
            self.cache[symbol] = {}

        self.cache[symbol][indicator_name] = {
            "data": data,
            "timestamp": datetime.now()
        }

    def get_rsi(self, symbol, window=14, limit=10):
        # type: (str, int, int) -> Optional[List[Dict[str, Any]]]
        """Get RSI indicator (14-period standard)"""
        cache_key = f"rsi_{window}"
        cached = self._get_cached(symbol, cache_key)
        if cached is not None:
            return cached

        if not self._check_rate_limit():
            return None

        try:
            result = self.client.get_rsi(
                ticker=symbol,
                timespan="day",
                adjusted="true",
                window=str(window),
                series_type="close",
                order="desc",
                limit=str(limit),
            )

            self.request_count += 1
            data = list(result.values) if result and result.values else []
            self._set_cache(symbol, cache_key, data)

            logger.debug(f"Polygon API: RSI({window}) for {symbol} - {len(data)} points")
            return data

        except Exception as e:
            logger.error(f"Error fetching RSI for {symbol}: {e}")
            return None

    def get_sma(self, symbol, window=50, limit=10):
        # type: (str, int, int) -> Optional[List[Dict[str, Any]]]
        """Get Simple Moving Average"""
        cache_key = f"sma_{window}"
        cached = self._get_cached(symbol, cache_key)
        if cached is not None:
            return cached

        if not self._check_rate_limit():
            return None

        try:
            result = self.client.get_sma(
                ticker=symbol,
                timespan="day",
                adjusted="true",
                window=str(window),
                series_type="close",
                order="desc",
                limit=str(limit),
            )

            self.request_count += 1
            data = list(result.values) if result and result.values else []
            self._set_cache(symbol, cache_key, data)

            logger.debug(f"Polygon API: SMA({window}) for {symbol} - {len(data)} points")
            return data

        except Exception as e:
            logger.error(f"Error fetching SMA for {symbol}: {e}")
            return None

    def get_macd(self, symbol, limit=10):
        # type: (str, int) -> Optional[List[Dict[str, Any]]]
        """Get MACD indicator"""
        cache_key = "macd"
        cached = self._get_cached(symbol, cache_key)
        if cached is not None:
            return cached

        if not self._check_rate_limit():
            return None

        try:
            result = self.client.get_macd(
                ticker=symbol,
                timespan="day",
                adjusted="true",
                short_window="12",
                long_window="26",
                signal_window="9",
                series_type="close",
                order="desc",
                limit=str(limit),
            )

            self.request_count += 1
            data = list(result.values) if result and result.values else []
            self._set_cache(symbol, cache_key, data)

            logger.debug(f"Polygon API: MACD for {symbol} - {len(data)} points")
            return data

        except Exception as e:
            logger.error(f"Error fetching MACD for {symbol}: {e}")
            return None

    def get_indicators_bundle(self, symbol):
        # type: (str) -> Dict[str, Any]
        """
        Get essential indicators for a stock in one call.
        Returns: {rsi, sma50, sma200, macd, price_vs_sma50, price_vs_sma200}

        This is the main method strategies should call.
        """
        bundle = {
            "symbol": symbol,
            "rsi_14": None,
            "sma_50": None,
            "sma_200": None,
            "macd": None,
            "price_vs_sma50": None,  # "above" or "below"
            "price_vs_sma200": None,
        }

        # Fetch indicators
        rsi_data = self.get_rsi(symbol, window=14, limit=1)
        if rsi_data and len(rsi_data) > 0:
            bundle["rsi_14"] = rsi_data[0].value

        sma50_data = self.get_sma(symbol, window=50, limit=1)
        if sma50_data and len(sma50_data) > 0:
            bundle["sma_50"] = sma50_data[0].value

        sma200_data = self.get_sma(symbol, window=200, limit=1)
        if sma200_data and len(sma200_data) > 0:
            bundle["sma_200"] = sma200_data[0].value

        macd_data = self.get_macd(symbol, limit=1)
        if macd_data and len(macd_data) > 0:
            bundle["macd"] = {
                "value": macd_data[0].value,
                "signal": macd_data[0].signal,
                "histogram": macd_data[0].histogram,
            }

        return bundle

    def get_rate_limit_status(self):
        # type: () -> Dict[str, Any]
        """Get current rate limit status for monitoring"""
        elapsed_hours = (datetime.now() - self.request_window_start).total_seconds() / 3600
        return {
            "requests_used": self.request_count,
            "requests_remaining": max(0, self.max_requests_per_hour - self.request_count),
            "max_per_hour": self.max_requests_per_hour,
            "window_elapsed_hours": round(elapsed_hours, 2),
            "cache_size": len(self.cache),
        }
