"""
Polymarket API Client
Handles all interactions with Polymarket CLOB API
"""
from typing import Dict, List, Optional, Any
from loguru import logger
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs
from py_clob_client.order_builder.constants import BUY, SELL
from config.settings import get_settings


class PolymarketClient:
    """Client for interacting with Polymarket API"""

    def __init__(self):
        """Initialize Polymarket client"""
        self.settings = get_settings()
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize the CLOB client"""
        try:
            # Initialize client with credentials
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                key=self.settings.polymarket_api_key,
                chain_id=137,  # Polygon mainnet
                signature_type=2,
                funder=self.settings.wallet_address,
            )

            logger.info("Polymarket client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Polymarket client: {e}")
            raise

    def get_markets(self, limit: int = 100) -> List[Dict]:
        """
        Get active markets from Polymarket

        Args:
            limit: Maximum number of markets to fetch

        Returns:
            List of market dictionaries
        """
        try:
            markets = self.client.get_markets(limit=limit)
            logger.debug(f"Fetched {len(markets)} markets")
            return markets

        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    def get_market(self, condition_id: str) -> Optional[Dict]:
        """
        Get specific market details

        Args:
            condition_id: Market condition ID

        Returns:
            Market dictionary or None
        """
        try:
            market = self.client.get_market(condition_id)
            return market

        except Exception as e:
            logger.error(f"Error fetching market {condition_id}: {e}")
            return None

    def get_order_book(self, token_id: str) -> Optional[Dict]:
        """
        Get order book for a specific token

        Args:
            token_id: Token ID

        Returns:
            Order book data or None
        """
        try:
            order_book = self.client.get_order_book(token_id)
            return order_book

        except Exception as e:
            logger.error(f"Error fetching order book for {token_id}: {e}")
            return None

    def get_midpoint_price(self, token_id: str) -> Optional[float]:
        """
        Get midpoint price for a token

        Args:
            token_id: Token ID

        Returns:
            Midpoint price or None
        """
        try:
            order_book = self.get_order_book(token_id)
            if not order_book:
                return None

            bids = order_book.get('bids', [])
            asks = order_book.get('asks', [])

            if not bids or not asks:
                return None

            best_bid = float(bids[0]['price'])
            best_ask = float(asks[0]['price'])

            midpoint = (best_bid + best_ask) / 2
            return midpoint

        except Exception as e:
            logger.error(f"Error calculating midpoint price: {e}")
            return None

    def place_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        price: float,
        paper_trading: bool = True
    ) -> Optional[Dict]:
        """
        Place an order on Polymarket

        Args:
            token_id: Token ID to trade
            side: BUY or SELL
            amount: Amount to trade
            price: Limit price
            paper_trading: If True, simulate order without execution

        Returns:
            Order result or None
        """
        try:
            if paper_trading:
                logger.info(
                    f"[PAPER TRADE] {side} {amount} of {token_id} at ${price}"
                )
                return {
                    "order_id": f"paper_{token_id}_{side}",
                    "status": "simulated",
                    "side": side,
                    "amount": amount,
                    "price": price
                }

            # Real order execution
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=amount,
                side=BUY if side.upper() == "BUY" else SELL,
            )

            result = self.client.create_order(order_args)
            logger.info(f"Order placed: {result}")

            return result

        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def place_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        paper_trading: bool = True
    ) -> Optional[Dict]:
        """
        Place a market order on Polymarket

        Args:
            token_id: Token ID to trade
            side: BUY or SELL
            amount: Amount to trade
            paper_trading: If True, simulate order without execution

        Returns:
            Order result or None
        """
        try:
            if paper_trading:
                logger.info(
                    f"[PAPER TRADE] MARKET {side} {amount} of {token_id}"
                )
                return {
                    "order_id": f"paper_market_{token_id}_{side}",
                    "status": "simulated",
                    "side": side,
                    "amount": amount,
                }

            # Real market order execution
            market_order_args = MarketOrderArgs(
                token_id=token_id,
                amount=amount,
                side=BUY if side.upper() == "BUY" else SELL,
            )

            result = self.client.create_market_order(market_order_args)
            logger.info(f"Market order placed: {result}")

            return result

        except Exception as e:
            logger.error(f"Error placing market order: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an existing order

        Args:
            order_id: Order ID to cancel

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.cancel(order_id)
            logger.info(f"Order {order_id} cancelled")
            return True

        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def get_balance(self) -> Optional[Dict[str, float]]:
        """
        Get account balance

        Returns:
            Dictionary with balance information
        """
        try:
            # Get USDC balance on Polygon
            balance = self.client.get_balance()

            return {
                "usdc": float(balance) if balance else 0.0,
                "total": float(balance) if balance else 0.0
            }

        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return None

    def get_open_orders(self) -> List[Dict]:
        """
        Get all open orders

        Returns:
            List of open orders
        """
        try:
            orders = self.client.get_orders()
            return orders

        except Exception as e:
            logger.error(f"Error fetching open orders: {e}")
            return []

    def get_positions(self) -> List[Dict]:
        """
        Get current positions

        Returns:
            List of positions
        """
        try:
            # Note: Polymarket doesn't have a direct positions endpoint
            # We need to track positions ourselves or query balance per token
            positions = []

            # This is a placeholder - implement based on your tracking needs
            logger.debug("Fetching positions...")

            return positions

        except Exception as e:
            logger.error(f"Error fetching positions: {e}")
            return []

    def get_trade_history(self, limit: int = 100) -> List[Dict]:
        """
        Get trade history

        Args:
            limit: Maximum number of trades to fetch

        Returns:
            List of trades
        """
        try:
            trades = self.client.get_trades(limit=limit)
            return trades

        except Exception as e:
            logger.error(f"Error fetching trade history: {e}")
            return []
