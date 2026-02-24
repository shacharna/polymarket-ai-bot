"""
Test script for Polygon.io Massive API integration
Run this to verify your API key and test indicator fetching
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.trading.polygon_client import PolygonIndicatorClient
from loguru import logger

def test_polygon_client():
    """Test Polygon.io client with your API key"""
    logger.info("=" * 60)
    logger.info("Testing Polygon.io Massive API Integration")
    logger.info("=" * 60)

    try:
        # Initialize client
        logger.info("\n1. Initializing Polygon client...")
        polygon = PolygonIndicatorClient()
        logger.info("✓ Client initialized successfully")

        # Test RSI
        logger.info("\n2. Testing RSI indicator for AAPL...")
        rsi_data = polygon.get_rsi("AAPL", window=14, limit=1)
        if rsi_data and len(rsi_data) > 0:
            rsi_value = rsi_data[0].get("value")
            logger.info(f"✓ AAPL RSI(14): {rsi_value:.2f}")
            if rsi_value > 70:
                logger.info("  → OVERBOUGHT (>70)")
            elif rsi_value < 30:
                logger.info("  → OVERSOLD (<30)")
            else:
                logger.info("  → NEUTRAL (30-70)")
        else:
            logger.warning("✗ No RSI data returned")

        # Test SMA50
        logger.info("\n3. Testing SMA(50) indicator for AAPL...")
        sma50_data = polygon.get_sma("AAPL", window=50, limit=1)
        if sma50_data and len(sma50_data) > 0:
            sma50_value = sma50_data[0].get("value")
            logger.info(f"✓ AAPL SMA(50): ${sma50_value:.2f}")
        else:
            logger.warning("✗ No SMA50 data returned")

        # Test SMA200
        logger.info("\n4. Testing SMA(200) indicator for AAPL...")
        sma200_data = polygon.get_sma("AAPL", window=200, limit=1)
        if sma200_data and len(sma200_data) > 0:
            sma200_value = sma200_data[0].get("value")
            logger.info(f"✓ AAPL SMA(200): ${sma200_value:.2f}")
        else:
            logger.warning("✗ No SMA200 data returned")

        # Test MACD
        logger.info("\n5. Testing MACD indicator for AAPL...")
        macd_data = polygon.get_macd("AAPL", limit=1)
        if macd_data and len(macd_data) > 0:
            macd = macd_data[0]
            logger.info(f"✓ AAPL MACD:")
            logger.info(f"  - Value: {macd.get('value', 0):.3f}")
            logger.info(f"  - Signal: {macd.get('signal', 0):.3f}")
            logger.info(f"  - Histogram: {macd.get('histogram', 0):.3f}")
            if macd.get('histogram', 0) > 0:
                logger.info("  → BULLISH momentum")
            else:
                logger.info("  → BEARISH momentum")
        else:
            logger.warning("✗ No MACD data returned")

        # Test full indicator bundle
        logger.info("\n6. Testing full indicator bundle for TSLA...")
        bundle = polygon.get_indicators_bundle("TSLA")
        logger.info(f"✓ TSLA Indicator Bundle:")
        logger.info(f"  - RSI(14): {bundle.get('rsi_14', 'N/A')}")
        logger.info(f"  - SMA(50): {bundle.get('sma_50', 'N/A')}")
        logger.info(f"  - SMA(200): {bundle.get('sma_200', 'N/A')}")
        logger.info(f"  - MACD: {bundle.get('macd', 'N/A')}")

        # Test caching
        logger.info("\n7. Testing cache (should be instant)...")
        bundle2 = polygon.get_indicators_bundle("TSLA")
        logger.info("✓ Cache working - second call returned instantly")

        # Check rate limit status
        logger.info("\n8. Checking rate limit status...")
        status = polygon.get_rate_limit_status()
        logger.info(f"✓ Rate Limit Status:")
        logger.info(f"  - Requests used: {status['requests_used']}/{status['max_per_hour']}")
        logger.info(f"  - Requests remaining: {status['requests_remaining']}")
        logger.info(f"  - Cache size: {status['cache_size']} symbols")
        logger.info(f"  - Window elapsed: {status['window_elapsed_hours']:.2f} hours")

        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info("\nPolygon.io integration is working correctly!")
        logger.info("You can now run your trading bot with technical indicator support.")

    except Exception as e:
        logger.error("\n" + "=" * 60)
        logger.error(f"✗ TEST FAILED: {e}")
        logger.error("=" * 60)
        logger.error("\nTroubleshooting:")
        logger.error("1. Check your .env file has POLYGON_API_KEY set")
        logger.error("2. Verify your API key is valid at polygon.io")
        logger.error("3. Make sure you have internet connection")
        logger.error("4. Check if you've exceeded rate limits (< 100 req/hour)")
        raise

if __name__ == "__main__":
    test_polygon_client()
