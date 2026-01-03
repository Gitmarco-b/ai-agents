"""
Moon Dev's Order Book Data Feed
Real-time Level 2 orderbook data from Hyperliquid WebSocket
Built with love by Moon Dev

Features:
- Real-time L2 order book updates
- Bid/ask level parsing with depth calculation
- Configurable depth levels (default top 20)
- Update throttling (100ms default)
- Spread and imbalance calculations
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
class OrderLevel:
    """Single price level in the order book"""
    price: float
    size: float
    count: int = 1  # Number of orders at this level

    def to_dict(self) -> Dict:
        return {"price": self.price, "size": self.size, "count": self.count}


@dataclass
class OrderBook:
    """Complete order book for a single coin"""
    coin: str
    bids: List[OrderLevel] = field(default_factory=list)
    asks: List[OrderLevel] = field(default_factory=list)
    last_update: datetime = field(default_factory=datetime.now)
    sequence: int = 0

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price"""
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price"""
        return self.asks[0].price if self.asks else None

    @property
    def mid_price(self) -> Optional[float]:
        """Get mid price"""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        return None

    @property
    def spread(self) -> Optional[float]:
        """Get absolute spread"""
        if self.best_bid and self.best_ask:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_percent(self) -> Optional[float]:
        """Get spread as percentage of mid price"""
        if self.spread and self.mid_price:
            return (self.spread / self.mid_price) * 100
        return None

    @property
    def bid_depth(self) -> float:
        """Total bid depth (sum of all bid sizes)"""
        return sum(level.size for level in self.bids)

    @property
    def ask_depth(self) -> float:
        """Total ask depth (sum of all ask sizes)"""
        return sum(level.size for level in self.asks)

    @property
    def imbalance(self) -> float:
        """
        Order book imbalance: positive = more bids, negative = more asks
        Range: -1 to 1
        """
        total = self.bid_depth + self.ask_depth
        if total == 0:
            return 0
        return (self.bid_depth - self.ask_depth) / total

    def get_depth_at_price(self, price: float, side: str = "bid") -> float:
        """Get cumulative depth up to a price level"""
        levels = self.bids if side == "bid" else self.asks
        depth = 0
        for level in levels:
            if side == "bid" and level.price >= price:
                depth += level.size
            elif side == "ask" and level.price <= price:
                depth += level.size
        return depth

    def to_dict(self) -> Dict:
        """Convert to dictionary format"""
        return {
            "coin": self.coin,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "best_bid": self.best_bid,
            "best_ask": self.best_ask,
            "mid_price": self.mid_price,
            "spread": self.spread,
            "spread_percent": self.spread_percent,
            "bid_depth": self.bid_depth,
            "ask_depth": self.ask_depth,
            "imbalance": self.imbalance,
            "last_update": self.last_update.isoformat(),
            "sequence": self.sequence
        }


class OrderBookFeed:
    """
    Real-time order book feed manager for Hyperliquid

    Usage:
        from src.websocket import HyperliquidWebSocket
        from src.websocket.orderbook_feed import OrderBookFeed

        ws = HyperliquidWebSocket()
        ob_feed = OrderBookFeed(ws)

        # Add event listener
        ob_feed.on_orderbook_update = lambda data: print(data)

        # Start streaming
        ob_feed.start(['BTC', 'ETH'])

        # Get current orderbook
        book = ob_feed.get_orderbook('BTC')
        print(f"Best bid: {book.best_bid}, Best ask: {book.best_ask}")
    """

    # Default settings
    DEFAULT_DEPTH_LEVELS = 20  # Top 20 levels
    UPDATE_THROTTLE_MS = 100  # Minimum ms between updates per coin

    def __init__(
        self,
        ws_client=None,
        depth_levels: int = DEFAULT_DEPTH_LEVELS,
        update_throttle_ms: int = UPDATE_THROTTLE_MS
    ):
        """
        Initialize the order book feed

        Args:
            ws_client: HyperliquidWebSocket instance (optional)
            depth_levels: Number of levels to track (default 20)
            update_throttle_ms: Minimum ms between emitted updates (default 100)
        """
        self._ws = ws_client
        self._owns_ws = ws_client is None
        self._depth_levels = depth_levels
        self._update_throttle_ms = update_throttle_ms

        # Order book state storage
        self._orderbooks: Dict[str, OrderBook] = {}
        self._lock = threading.RLock()

        # Update throttling
        self._last_emit_time: Dict[str, float] = defaultdict(float)

        # Event callbacks
        self._on_orderbook_update_callbacks: List[Callable[[Dict], None]] = []

        # Monitored coins
        self._monitored_coins: Set[str] = set()

        # State tracking
        self._is_running = False

        logger.info(f"OrderBookFeed initialized (depth={depth_levels}, throttle={update_throttle_ms}ms)")

    @property
    def on_orderbook_update(self) -> Optional[Callable]:
        """Get first orderbook update callback"""
        return self._on_orderbook_update_callbacks[0] if self._on_orderbook_update_callbacks else None

    @on_orderbook_update.setter
    def on_orderbook_update(self, callback: Callable[[Dict], None]):
        """Set orderbook update callback (replaces existing)"""
        self._on_orderbook_update_callbacks = [callback] if callback else []

    def add_orderbook_listener(self, callback: Callable[[Dict], None]):
        """Add an orderbook update listener"""
        if callback not in self._on_orderbook_update_callbacks:
            self._on_orderbook_update_callbacks.append(callback)

    def remove_orderbook_listener(self, callback: Callable[[Dict], None]):
        """Remove an orderbook update listener"""
        if callback in self._on_orderbook_update_callbacks:
            self._on_orderbook_update_callbacks.remove(callback)

    def start(self, coins: List[str] = None) -> bool:
        """
        Start the order book feed

        Args:
            coins: List of coins to monitor (e.g., ['BTC', 'ETH'])
                   If None, will use HYPERLIQUID_SYMBOLS from config

        Returns:
            bool: True if started successfully
        """
        if self._is_running:
            cprint("Order book feed already running", "yellow")
            return True

        # Get coins from config if not provided
        if coins is None:
            try:
                from src.config import HYPERLIQUID_SYMBOLS
                coins = HYPERLIQUID_SYMBOLS
            except ImportError:
                coins = ['BTC', 'ETH', 'SOL']

        self._monitored_coins = set(coins)
        cprint(f"Starting order book feed for: {', '.join(coins)}", "cyan")
        logger.info(f"Starting order book feed for {len(coins)} coins")

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

        # Subscribe to L2 book for each coin
        for coin in coins:
            self._ws.subscribe_l2_book(coin)
            # Initialize empty orderbook
            with self._lock:
                self._orderbooks[coin] = OrderBook(coin=coin)

        self._is_running = True
        cprint("Order book feed started successfully", "green")
        return True

    def stop(self):
        """Stop the order book feed"""
        if not self._is_running:
            return

        logger.info("Stopping order book feed")
        self._is_running = False

        # Unsubscribe from channels
        if self._ws and self._ws.is_connected:
            for coin in self._monitored_coins:
                self._ws.unsubscribe_l2_book(coin)

        # Close WebSocket if we own it
        if self._owns_ws and self._ws:
            self._ws.close()

        cprint("Order book feed stopped", "yellow")

    def _handle_connect(self):
        """Handle WebSocket connection"""
        cprint("Order book feed connected", "green")

    def _handle_disconnect(self, was_clean: bool):
        """Handle WebSocket disconnection"""
        if not was_clean:
            cprint("Order book feed disconnected unexpectedly", "red")

    def _handle_ws_message(self, data: Dict):
        """Handle incoming WebSocket messages"""
        channel = data.get("channel", "")

        if channel == "l2Book":
            self._process_l2_book(data.get("data", {}))

    def _process_l2_book(self, data: Dict):
        """Process L2 book message"""
        coin = data.get("coin", "")
        levels = data.get("levels", [[], []])
        time_ms = data.get("time", 0)

        if not coin or len(levels) < 2:
            return

        raw_bids = levels[0]  # First element is bids
        raw_asks = levels[1]  # Second element is asks

        with self._lock:
            # Parse bid levels (sorted highest to lowest)
            bids = []
            for level in raw_bids[:self._depth_levels]:
                try:
                    bids.append(OrderLevel(
                        price=float(level.get("px", 0)),
                        size=float(level.get("sz", 0)),
                        count=int(level.get("n", 1))
                    ))
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse bid level: {e}")

            # Parse ask levels (sorted lowest to highest)
            asks = []
            for level in raw_asks[:self._depth_levels]:
                try:
                    asks.append(OrderLevel(
                        price=float(level.get("px", 0)),
                        size=float(level.get("sz", 0)),
                        count=int(level.get("n", 1))
                    ))
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse ask level: {e}")

            # Update or create orderbook
            if coin not in self._orderbooks:
                self._orderbooks[coin] = OrderBook(coin=coin)

            self._orderbooks[coin].bids = bids
            self._orderbooks[coin].asks = asks
            self._orderbooks[coin].last_update = datetime.now()
            self._orderbooks[coin].sequence += 1

        # Emit update with throttling
        self._maybe_emit_update(coin)

    def _maybe_emit_update(self, coin: str):
        """Emit update if throttle period has passed"""
        now = time.time() * 1000  # ms
        last_emit = self._last_emit_time[coin]

        if now - last_emit >= self._update_throttle_ms:
            self._last_emit_time[coin] = now
            self._emit_orderbook_update(coin)

    def _emit_orderbook_update(self, coin: str):
        """Emit orderbook update event"""
        if coin not in self._orderbooks:
            return

        with self._lock:
            book_data = self._orderbooks[coin].to_dict()

        for callback in self._on_orderbook_update_callbacks:
            try:
                callback(book_data)
            except Exception as e:
                logger.error(f"Error in orderbook_update callback: {e}")

    # ========================================================================
    # PUBLIC API - Get Order Book Data
    # ========================================================================

    def get_orderbook(self, coin: str) -> Optional[OrderBook]:
        """
        Get current order book for a coin

        Args:
            coin: Trading pair symbol (e.g., 'BTC')

        Returns:
            OrderBook object or None if not available
        """
        with self._lock:
            return self._orderbooks.get(coin)

    def get_best_bid(self, coin: str) -> Optional[float]:
        """Get best bid price for a coin"""
        with self._lock:
            if coin in self._orderbooks:
                return self._orderbooks[coin].best_bid
        return None

    def get_best_ask(self, coin: str) -> Optional[float]:
        """Get best ask price for a coin"""
        with self._lock:
            if coin in self._orderbooks:
                return self._orderbooks[coin].best_ask
        return None

    def get_spread(self, coin: str) -> Optional[float]:
        """Get spread for a coin"""
        with self._lock:
            if coin in self._orderbooks:
                return self._orderbooks[coin].spread
        return None

    def get_depth(self, coin: str) -> Dict[str, float]:
        """
        Get order book depth for a coin

        Returns:
            Dict with 'bid_depth' and 'ask_depth' keys
        """
        with self._lock:
            if coin in self._orderbooks:
                book = self._orderbooks[coin]
                return {
                    "bid_depth": book.bid_depth,
                    "ask_depth": book.ask_depth,
                    "imbalance": book.imbalance
                }
        return {"bid_depth": 0, "ask_depth": 0, "imbalance": 0}

    def get_imbalance(self, coin: str) -> float:
        """
        Get order book imbalance for a coin

        Returns:
            Imbalance value between -1 and 1
            Positive = more bids (bullish), Negative = more asks (bearish)
        """
        with self._lock:
            if coin in self._orderbooks:
                return self._orderbooks[coin].imbalance
        return 0

    def get_levels(self, coin: str, side: str = "both", limit: int = None) -> Dict:
        """
        Get order book levels for a coin

        Args:
            coin: Trading pair symbol
            side: 'bid', 'ask', or 'both'
            limit: Number of levels to return (None = all)

        Returns:
            Dict with 'bids' and/or 'asks' lists
        """
        result = {}
        limit = limit or self._depth_levels

        with self._lock:
            if coin not in self._orderbooks:
                return {"bids": [], "asks": []}

            book = self._orderbooks[coin]

            if side in ["bid", "both"]:
                result["bids"] = [level.to_dict() for level in book.bids[:limit]]

            if side in ["ask", "both"]:
                result["asks"] = [level.to_dict() for level in book.asks[:limit]]

        return result

    def get_all_orderbooks(self) -> Dict[str, OrderBook]:
        """Get all current order books"""
        with self._lock:
            return {coin: book for coin, book in self._orderbooks.items()}

    def is_orderbook_stale(self, coin: str, max_age_seconds: float = 5.0) -> bool:
        """
        Check if order book data is stale

        Args:
            coin: Trading pair symbol
            max_age_seconds: Maximum age in seconds before considered stale

        Returns:
            True if order book is stale or not available
        """
        with self._lock:
            if coin not in self._orderbooks:
                return True
            age = (datetime.now() - self._orderbooks[coin].last_update).total_seconds()
            return age > max_age_seconds


# ============================================================================
# SINGLETON INSTANCE FOR GLOBAL ACCESS
# ============================================================================

_global_orderbook_feed: Optional[OrderBookFeed] = None
_global_lock = threading.Lock()


def get_orderbook_feed() -> OrderBookFeed:
    """Get the global OrderBookFeed instance (creates if needed)"""
    global _global_orderbook_feed
    with _global_lock:
        if _global_orderbook_feed is None:
            _global_orderbook_feed = OrderBookFeed()
        return _global_orderbook_feed


def get_l2_book_ws(coin: str) -> Dict:
    """
    Get L2 order book from WebSocket feed (drop-in replacement for API polling)

    Args:
        coin: Trading pair symbol

    Returns:
        Dict with order book data or raises exception
    """
    feed = get_orderbook_feed()
    if not feed._is_running:
        raise Exception("WebSocket order book feed not running")

    book = feed.get_orderbook(coin)
    if book is None:
        raise Exception(f"No order book data available for {coin}")

    return book.to_dict()
