"""
Moon Dev's Price Data Streaming
Real-time price updates from Hyperliquid WebSocket
Built with love by Moon Dev

Features:
- Real-time price updates for monitored tokens
- Event emission system for UI updates
- Internal state management with thread-safe access
- Automatic subscription to allMids channel
- 24h volume and change tracking
"""

import json
import time
import threading
import logging
from typing import Callable, Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict

from termcolor import cprint

# Configure module logger
logger = logging.getLogger(__name__)


@dataclass
class TickerData:
    """Ticker data structure for a single coin"""
    coin: str
    price: float
    bid: float = 0.0
    ask: float = 0.0
    volume24h: float = 0.0
    change24h: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        """Convert to dictionary format"""
        return {
            "channel": "ticker",
            "data": {
                "coin": self.coin,
                "price": self.price,
                "bid": self.bid,
                "ask": self.ask,
                "volume24h": self.volume24h,
                "change24h": self.change24h,
                "timestamp": self.last_update.isoformat()
            }
        }


class PriceFeed:
    """
    Real-time price feed manager for Hyperliquid

    Usage:
        from src.websocket import HyperliquidWebSocket
        from src.websocket.price_feed import PriceFeed

        ws = HyperliquidWebSocket()
        price_feed = PriceFeed(ws)

        # Add event listener
        price_feed.on_price_update = lambda data: print(data)

        # Start streaming
        price_feed.start(['BTC', 'ETH', 'SOL'])

        # Get current price
        price = price_feed.get_price('BTC')
    """

    def __init__(self, ws_client=None):
        """
        Initialize the price feed

        Args:
            ws_client: HyperliquidWebSocket instance (optional, will create if not provided)
        """
        self._ws = ws_client
        self._owns_ws = ws_client is None

        # Price state storage
        self._prices: Dict[str, TickerData] = {}
        self._price_history: Dict[str, List[float]] = defaultdict(list)
        self._lock = threading.RLock()

        # Event callbacks
        self._on_price_update_callbacks: List[Callable[[Dict], None]] = []
        self._on_all_prices_update_callbacks: List[Callable[[Dict[str, TickerData]], None]] = []

        # Monitored coins
        self._monitored_coins: Set[str] = set()

        # State tracking
        self._is_running = False
        self._last_all_mids_update: Optional[datetime] = None

        logger.info("PriceFeed initialized")

    @property
    def on_price_update(self) -> Optional[Callable]:
        """Get first price update callback"""
        return self._on_price_update_callbacks[0] if self._on_price_update_callbacks else None

    @on_price_update.setter
    def on_price_update(self, callback: Callable[[Dict], None]):
        """Set price update callback (replaces existing)"""
        self._on_price_update_callbacks = [callback] if callback else []

    def add_price_listener(self, callback: Callable[[Dict], None]):
        """Add a price update listener"""
        if callback not in self._on_price_update_callbacks:
            self._on_price_update_callbacks.append(callback)

    def remove_price_listener(self, callback: Callable[[Dict], None]):
        """Remove a price update listener"""
        if callback in self._on_price_update_callbacks:
            self._on_price_update_callbacks.remove(callback)

    def add_all_prices_listener(self, callback: Callable[[Dict[str, TickerData]], None]):
        """Add a listener for all prices batch update"""
        if callback not in self._on_all_prices_update_callbacks:
            self._on_all_prices_update_callbacks.append(callback)

    def start(self, coins: List[str] = None) -> bool:
        """
        Start the price feed

        Args:
            coins: List of coins to monitor (e.g., ['BTC', 'ETH', 'SOL'])
                   If None, will use HYPERLIQUID_SYMBOLS from config

        Returns:
            bool: True if started successfully
        """
        if self._is_running:
            cprint("Price feed already running", "yellow")
            return True

        # Get coins from config if not provided
        if coins is None:
            try:
                from src.config import HYPERLIQUID_SYMBOLS
                coins = HYPERLIQUID_SYMBOLS
            except ImportError:
                coins = ['BTC', 'ETH', 'SOL']

        self._monitored_coins = set(coins)
        cprint(f"Starting price feed for: {', '.join(coins)}", "cyan")
        logger.info(f"Starting price feed for {len(coins)} coins")

        # Create WebSocket if needed
        if self._owns_ws:
            from src.websocket.hyperliquid_ws import HyperliquidWebSocket
            self._ws = HyperliquidWebSocket(
                on_message=self._handle_ws_message,
                on_connect=self._handle_connect,
                on_disconnect=self._handle_disconnect,
                auto_reconnect=True
            )
            self._ws.connect()
        else:
            # Attach our message handler to existing WebSocket
            original_callback = self._ws._on_message_callback

            def combined_handler(data):
                self._handle_ws_message(data)
                if original_callback:
                    original_callback(data)

            self._ws._on_message_callback = combined_handler

        # Wait for connection
        timeout = 10
        start = time.time()
        while not self._ws.is_connected and (time.time() - start) < timeout:
            time.sleep(0.1)

        if not self._ws.is_connected:
            cprint("Failed to connect WebSocket", "red")
            return False

        # Subscribe to allMids for price updates
        self._ws.subscribe_all_mids()

        # Subscribe to L2 book for bid/ask data for each coin
        for coin in coins:
            self._ws.subscribe_l2_book(coin)

        self._is_running = True
        cprint("Price feed started successfully", "green")
        return True

    def stop(self):
        """Stop the price feed"""
        if not self._is_running:
            return

        logger.info("Stopping price feed")
        self._is_running = False

        # Unsubscribe from channels
        if self._ws and self._ws.is_connected:
            self._ws.unsubscribe_all_mids()
            for coin in self._monitored_coins:
                self._ws.unsubscribe_l2_book(coin)

        # Close WebSocket if we own it
        if self._owns_ws and self._ws:
            self._ws.close()

        cprint("Price feed stopped", "yellow")

    def _handle_connect(self):
        """Handle WebSocket connection"""
        cprint("Price feed connected", "green")

    def _handle_disconnect(self, was_clean: bool):
        """Handle WebSocket disconnection"""
        if not was_clean:
            cprint("Price feed disconnected unexpectedly", "red")

    def _handle_ws_message(self, data: Dict):
        """Handle incoming WebSocket messages"""
        channel = data.get("channel", "")

        if channel == "allMids":
            self._process_all_mids(data.get("data", {}))
        elif channel == "l2Book":
            self._process_l2_book(data.get("data", {}))

    def _process_all_mids(self, data: Dict):
        """Process allMids message for mid prices"""
        mids = data.get("mids", {})
        if not mids:
            return

        self._last_all_mids_update = datetime.now()
        updated_coins = []

        with self._lock:
            for coin, price_str in mids.items():
                try:
                    price = float(price_str)

                    # Only track monitored coins or create entry for all
                    if coin in self._prices:
                        # Update existing
                        old_price = self._prices[coin].price
                        self._prices[coin].price = price
                        self._prices[coin].last_update = datetime.now()

                        # Track price history for change calculation
                        self._price_history[coin].append(price)
                        # Keep only last 1440 prices (~24h at 1 update/min)
                        if len(self._price_history[coin]) > 1440:
                            self._price_history[coin] = self._price_history[coin][-1440:]

                        # Calculate 24h change if we have history
                        if len(self._price_history[coin]) >= 2:
                            first_price = self._price_history[coin][0]
                            if first_price > 0:
                                self._prices[coin].change24h = ((price - first_price) / first_price) * 100

                        updated_coins.append(coin)
                    elif coin in self._monitored_coins or not self._monitored_coins:
                        # Create new entry
                        self._prices[coin] = TickerData(
                            coin=coin,
                            price=price,
                            last_update=datetime.now()
                        )
                        self._price_history[coin].append(price)
                        updated_coins.append(coin)

                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse price for {coin}: {e}")

        # Emit events for updated coins
        for coin in updated_coins:
            self._emit_price_update(coin)

        # Emit batch update
        if updated_coins and self._on_all_prices_update_callbacks:
            prices_copy = self.get_all_prices()
            for callback in self._on_all_prices_update_callbacks:
                try:
                    callback(prices_copy)
                except Exception as e:
                    logger.error(f"Error in all_prices callback: {e}")

    def _process_l2_book(self, data: Dict):
        """Process L2 book message for bid/ask"""
        coin = data.get("coin", "")
        levels = data.get("levels", [[], []])

        if not coin or len(levels) < 2:
            return

        bids = levels[0]  # First element is bids
        asks = levels[1]  # Second element is asks

        with self._lock:
            if coin in self._prices:
                if bids:
                    self._prices[coin].bid = float(bids[0].get("px", 0))
                if asks:
                    self._prices[coin].ask = float(asks[0].get("px", 0))
                self._prices[coin].last_update = datetime.now()

                # If we have bid/ask, recalculate mid price
                if self._prices[coin].bid > 0 and self._prices[coin].ask > 0:
                    mid = (self._prices[coin].bid + self._prices[coin].ask) / 2
                    self._prices[coin].price = mid

        self._emit_price_update(coin)

    def _emit_price_update(self, coin: str):
        """Emit price update event"""
        if coin not in self._prices:
            return

        with self._lock:
            ticker_data = self._prices[coin].to_dict()

        for callback in self._on_price_update_callbacks:
            try:
                callback(ticker_data)
            except Exception as e:
                logger.error(f"Error in price_update callback: {e}")

    # ========================================================================
    # PUBLIC API - Get Price Data
    # ========================================================================

    def get_price(self, coin: str) -> Optional[float]:
        """
        Get current price for a coin

        Args:
            coin: Trading pair symbol (e.g., 'BTC')

        Returns:
            Current mid price or None if not available
        """
        with self._lock:
            if coin in self._prices:
                return self._prices[coin].price
        return None

    def get_bid(self, coin: str) -> Optional[float]:
        """Get current bid price for a coin"""
        with self._lock:
            if coin in self._prices:
                return self._prices[coin].bid
        return None

    def get_ask(self, coin: str) -> Optional[float]:
        """Get current ask price for a coin"""
        with self._lock:
            if coin in self._prices:
                return self._prices[coin].ask
        return None

    def get_bid_ask(self, coin: str) -> tuple:
        """
        Get current bid and ask for a coin

        Returns:
            Tuple of (bid, ask) or (None, None) if not available
        """
        with self._lock:
            if coin in self._prices:
                return (self._prices[coin].bid, self._prices[coin].ask)
        return (None, None)

    def get_ticker(self, coin: str) -> Optional[TickerData]:
        """Get full ticker data for a coin"""
        with self._lock:
            if coin in self._prices:
                return self._prices[coin]
        return None

    def get_all_prices(self) -> Dict[str, TickerData]:
        """Get all current prices"""
        with self._lock:
            return {coin: ticker for coin, ticker in self._prices.items()}

    def get_monitored_coins(self) -> List[str]:
        """Get list of monitored coins"""
        return list(self._monitored_coins)

    def is_price_stale(self, coin: str, max_age_seconds: float = 60.0) -> bool:
        """
        Check if price data is stale

        Args:
            coin: Trading pair symbol
            max_age_seconds: Maximum age in seconds before considered stale

        Returns:
            True if price is stale or not available
        """
        with self._lock:
            if coin not in self._prices:
                return True
            age = (datetime.now() - self._prices[coin].last_update).total_seconds()
            return age > max_age_seconds

    def get_price_age(self, coin: str) -> Optional[float]:
        """Get age of price data in seconds"""
        with self._lock:
            if coin in self._prices:
                return (datetime.now() - self._prices[coin].last_update).total_seconds()
        return None


# ============================================================================
# SINGLETON INSTANCE FOR GLOBAL ACCESS
# ============================================================================

_global_price_feed: Optional[PriceFeed] = None
_global_lock = threading.Lock()


def get_price_feed() -> PriceFeed:
    """Get the global PriceFeed instance (creates if needed)"""
    global _global_price_feed
    with _global_lock:
        if _global_price_feed is None:
            _global_price_feed = PriceFeed()
        return _global_price_feed


def get_current_price_ws(coin: str) -> Optional[float]:
    """
    Get current price from WebSocket feed (drop-in replacement for API polling)

    Args:
        coin: Trading pair symbol (e.g., 'BTC')

    Returns:
        Current price or None
    """
    feed = get_price_feed()
    if not feed._is_running:
        return None
    return feed.get_price(coin)


def get_ask_bid_ws(coin: str) -> tuple:
    """
    Get ask and bid from WebSocket feed (drop-in replacement for API polling)

    Args:
        coin: Trading pair symbol

    Returns:
        Tuple of (ask, bid, None) matching the API format, or raises exception
    """
    feed = get_price_feed()
    if not feed._is_running:
        raise Exception("WebSocket price feed not running")

    ticker = feed.get_ticker(coin)
    if ticker is None or ticker.ask == 0 or ticker.bid == 0:
        raise Exception(f"No bid/ask data available for {coin}")

    return (ticker.ask, ticker.bid, None)
