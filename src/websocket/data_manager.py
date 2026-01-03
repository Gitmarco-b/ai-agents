"""
Moon Dev's WebSocket Data Manager
Unified interface for real-time market data that replaces API polling
Built with love by Moon Dev

DATA SOURCE ARCHITECTURE:
========================
| Data Type        | Source    | Reason                              |
|------------------|-----------|-------------------------------------|
| Current Price    | WebSocket | Real-time updates, no polling       |
| Bid/Ask          | WebSocket | Real-time order book                |
| L2 Order Book    | WebSocket | Real-time depth, 100ms updates      |
| Positions        | WebSocket | Real-time position updates          |
| Fills/Orders     | WebSocket | Real-time trade notifications       |
| Account State    | WebSocket | Real-time balance/equity updates    |
| OHLC/Candles     | API       | Historical data, batch fetching     |
| Funding Rates    | API       | Periodic data, not real-time        |

This module provides drop-in replacement functions that:
1. Use WebSocket data when available and fresh
2. Fall back to API polling when WebSocket is unavailable
3. Maintain backward compatibility with existing code
4. Always use API for historical/OHLC data (WebSocket only provides current candle)

Usage:
    # Replace imports in your code:
    # Before: from src.nice_funcs_hyperliquid import ask_bid, get_current_price
    # After:  from src.websocket.data_manager import ask_bid, get_current_price

    # Or use the smart functions that auto-select data source:
    from src.websocket.data_manager import get_price, get_bid_ask, get_ohlcv_data
"""

import time
import threading
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from termcolor import cprint

# Configure module logger
logger = logging.getLogger(__name__)


class WebSocketDataManager:
    """
    Unified data manager that provides real-time market data
    with automatic fallback to API polling

    This is the main interface for replacing API polling with WebSocket data.
    """

    # Data staleness thresholds
    PRICE_STALE_THRESHOLD_SEC = 5.0  # Consider price stale after 5 seconds
    ORDERBOOK_STALE_THRESHOLD_SEC = 2.0  # Consider orderbook stale after 2 seconds

    def __init__(self, auto_start: bool = False, coins: List[str] = None):
        """
        Initialize the data manager

        Args:
            auto_start: Automatically start WebSocket feeds
            coins: List of coins to monitor (uses config if not provided)
        """
        self._price_feed = None
        self._orderbook_feed = None
        self._user_state_feed = None
        self._ws_client = None
        self._is_initialized = False
        self._lock = threading.Lock()

        # Get config
        try:
            from src.config import USE_WEBSOCKET_FEEDS, WEBSOCKET_FALLBACK_TO_API
            self._use_websocket = USE_WEBSOCKET_FEEDS
            self._fallback_to_api = WEBSOCKET_FALLBACK_TO_API
        except ImportError:
            self._use_websocket = True
            self._fallback_to_api = True

        if auto_start:
            self.start(coins)

    def start(self, coins: List[str] = None) -> bool:
        """
        Start the WebSocket data feeds

        Args:
            coins: List of coins to monitor

        Returns:
            bool: True if started successfully
        """
        if self._is_initialized:
            return True

        if not self._use_websocket:
            logger.info("WebSocket feeds disabled by config")
            return False

        with self._lock:
            try:
                from src.websocket.hyperliquid_ws import HyperliquidWebSocket
                from src.websocket.price_feed import PriceFeed
                from src.websocket.orderbook_feed import OrderBookFeed
                from src.websocket.user_state_feed import UserStateFeed

                # Create shared WebSocket client
                self._ws_client = HyperliquidWebSocket(auto_reconnect=True)
                self._ws_client.connect()

                # Wait for connection
                timeout = 10
                start = time.time()
                while not self._ws_client.is_connected and (time.time() - start) < timeout:
                    time.sleep(0.1)

                if not self._ws_client.is_connected:
                    logger.error("Failed to connect WebSocket")
                    return False

                # Get coins from config if not provided
                if coins is None:
                    try:
                        from src.config import HYPERLIQUID_SYMBOLS
                        coins = HYPERLIQUID_SYMBOLS
                    except ImportError:
                        coins = ['BTC', 'ETH', 'SOL']

                # Create price feed with shared WebSocket
                self._price_feed = PriceFeed(ws_client=self._ws_client)
                self._price_feed.start(coins)

                # Create orderbook feed with shared WebSocket
                self._orderbook_feed = OrderBookFeed(ws_client=self._ws_client)
                self._orderbook_feed.start(coins)

                # Create user state feed with shared WebSocket
                self._user_state_feed = UserStateFeed(ws_client=self._ws_client)
                self._user_state_feed.start()

                self._is_initialized = True
                cprint("WebSocket data manager started", "green")
                logger.info(f"Data manager initialized for {len(coins)} coins + user state")
                return True

            except Exception as e:
                logger.error(f"Failed to start data manager: {e}")
                cprint(f"Failed to start WebSocket data manager: {e}", "red")
                return False

    def stop(self):
        """Stop all WebSocket feeds"""
        with self._lock:
            if self._price_feed:
                self._price_feed.stop()
            if self._orderbook_feed:
                self._orderbook_feed.stop()
            if self._user_state_feed:
                self._user_state_feed.stop()
            if self._ws_client:
                self._ws_client.close()
            self._is_initialized = False
            cprint("WebSocket data manager stopped", "yellow")

    def is_running(self) -> bool:
        """Check if data manager is running"""
        return self._is_initialized and self._ws_client and self._ws_client.is_connected

    # ========================================================================
    # PRICE DATA METHODS
    # ========================================================================

    def get_current_price(self, symbol: str) -> float:
        """
        Get current price for a symbol

        Uses WebSocket data if available, falls back to API polling

        Args:
            symbol: Trading pair symbol (e.g., 'BTC')

        Returns:
            Current mid price
        """
        # Try WebSocket first
        if self._is_initialized and self._price_feed:
            price = self._price_feed.get_price(symbol)
            if price is not None and not self._price_feed.is_price_stale(symbol, self.PRICE_STALE_THRESHOLD_SEC):
                return price

        # Fall back to API
        if self._fallback_to_api:
            return self._api_get_current_price(symbol)

        raise Exception(f"No price data available for {symbol}")

    def get_ask_bid(self, symbol: str) -> Tuple[float, float, None]:
        """
        Get ask and bid prices for a symbol

        Returns tuple matching the API format: (ask, bid, levels)

        Args:
            symbol: Trading pair symbol

        Returns:
            Tuple of (ask, bid, None)
        """
        # Try WebSocket first
        if self._is_initialized and self._price_feed:
            ticker = self._price_feed.get_ticker(symbol)
            if ticker and ticker.ask > 0 and ticker.bid > 0:
                if not self._price_feed.is_price_stale(symbol, self.PRICE_STALE_THRESHOLD_SEC):
                    return (ticker.ask, ticker.bid, None)

        # Try orderbook for more accurate bid/ask
        if self._is_initialized and self._orderbook_feed:
            book = self._orderbook_feed.get_orderbook(symbol)
            if book and book.best_ask and book.best_bid:
                if not self._orderbook_feed.is_orderbook_stale(symbol, self.ORDERBOOK_STALE_THRESHOLD_SEC):
                    return (book.best_ask, book.best_bid, None)

        # Fall back to API
        if self._fallback_to_api:
            return self._api_ask_bid(symbol)

        raise Exception(f"No bid/ask data available for {symbol}")

    # ========================================================================
    # ORDERBOOK DATA METHODS
    # ========================================================================

    def get_orderbook(self, symbol: str) -> Dict:
        """
        Get order book for a symbol

        Args:
            symbol: Trading pair symbol

        Returns:
            Dict with bids, asks, and depth info
        """
        # Try WebSocket first
        if self._is_initialized and self._orderbook_feed:
            book = self._orderbook_feed.get_orderbook(symbol)
            if book and not self._orderbook_feed.is_orderbook_stale(symbol, self.ORDERBOOK_STALE_THRESHOLD_SEC):
                return book.to_dict()

        # Fall back to API
        if self._fallback_to_api:
            return self._api_get_orderbook(symbol)

        raise Exception(f"No orderbook data available for {symbol}")

    def get_depth(self, symbol: str) -> Dict[str, float]:
        """Get order book depth for a symbol"""
        if self._is_initialized and self._orderbook_feed:
            return self._orderbook_feed.get_depth(symbol)
        return {"bid_depth": 0, "ask_depth": 0, "imbalance": 0}

    def get_spread(self, symbol: str) -> Optional[float]:
        """Get spread for a symbol"""
        if self._is_initialized and self._orderbook_feed:
            return self._orderbook_feed.get_spread(symbol)
        return None

    # ========================================================================
    # OHLCV DATA METHODS (Always use API - historical data)
    # ========================================================================

    def get_ohlcv_data(
        self,
        symbol: str,
        timeframe: str = '15m',
        bars: int = 100,
        add_indicators: bool = True
    ):
        """
        Get OHLCV (candlestick) data for a symbol

        NOTE: This always uses API polling because:
        - Historical candles require batch fetching
        - WebSocket only provides updates to current candle
        - Analysis/backtesting needs complete historical data

        Args:
            symbol: Trading pair symbol (e.g., 'BTC')
            timeframe: Candle timeframe (e.g., '1m', '5m', '15m', '1h', '4h', '1d')
            bars: Number of bars to fetch (max 5000)
            add_indicators: Whether to add technical indicators

        Returns:
            pd.DataFrame with columns: timestamp, open, high, low, close, volume
        """
        from src.nice_funcs_hyperliquid import get_data
        return get_data(symbol, timeframe=timeframe, bars=bars, add_indicators=add_indicators)

    def get_funding_rates(self, symbol: str) -> Optional[Dict]:
        """
        Get funding rates for a symbol (always uses API)

        Args:
            symbol: Trading pair symbol

        Returns:
            Dict with funding_rate, mark_price, open_interest
        """
        from src.nice_funcs_hyperliquid import get_funding_rates
        return get_funding_rates(symbol)

    def get_position(self, symbol: str, account=None) -> tuple:
        """
        Get current position for a symbol

        Uses WebSocket data if available and fresh, falls back to API.

        Args:
            symbol: Trading pair symbol
            account: Optional account object

        Returns:
            Tuple: (positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, is_long)
        """
        # Try WebSocket first
        if self._is_initialized and self._user_state_feed:
            pos = self._user_state_feed.get_position(symbol)
            if pos and not self._user_state_feed.is_position_stale(symbol, 30.0):
                # Convert to API format
                return (
                    [pos.to_dict()],  # positions list
                    True,  # im_in_pos
                    pos.size,  # pos_size
                    pos.coin,  # pos_sym
                    pos.entry_price,  # entry_px
                    pos.pnl_percent,  # pnl_perc
                    pos.is_long  # is_long
                )
            elif not self._user_state_feed.has_position(symbol):
                # No position - return empty
                return ([], False, 0, symbol, 0, 0, True)

        # Fall back to API
        if self._fallback_to_api:
            from src.nice_funcs_hyperliquid import get_position as hl_get_position
            return hl_get_position(symbol, account)

        return ([], False, 0, symbol, 0, 0, True)

    def get_account_value(self, address=None) -> float:
        """
        Get total account value

        Uses WebSocket data if available, falls back to API.

        Args:
            address: Wallet address or Account object (optional if using WebSocket)

        Returns:
            Total account value in USD
        """
        # Try WebSocket first
        if self._is_initialized and self._user_state_feed:
            account_state = self._user_state_feed.get_account_state()
            if account_state.account_value > 0:
                return account_state.account_value

        # Fall back to API
        if self._fallback_to_api and address:
            from src.nice_funcs_hyperliquid import get_account_value as hl_get_account_value
            return hl_get_account_value(address)

        return 0.0

    def get_balance(self, address=None) -> float:
        """
        Get available balance

        Uses WebSocket data if available, falls back to API.

        Args:
            address: Wallet address or Account object (optional if using WebSocket)

        Returns:
            Available balance in USD
        """
        # Try WebSocket first
        if self._is_initialized and self._user_state_feed:
            account_state = self._user_state_feed.get_account_state()
            if account_state.withdrawable > 0:
                return account_state.withdrawable

        # Fall back to API
        if self._fallback_to_api and address:
            from src.nice_funcs_hyperliquid import get_balance as hl_get_balance
            return hl_get_balance(address)

        return 0.0

    def get_all_positions(self, address=None) -> list:
        """
        Get all open positions

        Uses WebSocket data if available, falls back to API.

        Args:
            address: Wallet address or Account object (optional if using WebSocket)

        Returns:
            List of position dictionaries
        """
        # Try WebSocket first
        if self._is_initialized and self._user_state_feed:
            positions = self._user_state_feed.get_positions_list()
            if positions or self._user_state_feed._initial_state_loaded:
                return positions

        # Fall back to API
        if self._fallback_to_api and address:
            from src.nice_funcs_hyperliquid import get_all_positions as hl_get_all_positions
            return hl_get_all_positions(address)

        return []

    def get_recent_fills(self, limit: int = 10) -> list:
        """
        Get recent trade fills from WebSocket

        Args:
            limit: Maximum number of fills to return

        Returns:
            List of fill dictionaries
        """
        if self._is_initialized and self._user_state_feed:
            return self._user_state_feed.get_recent_fills(limit)
        return []

    def add_position_listener(self, callback) -> None:
        """Add a callback for real-time position updates"""
        if self._user_state_feed:
            self._user_state_feed.add_position_listener(callback)

    def add_fill_listener(self, callback) -> None:
        """Add a callback for real-time fill notifications"""
        if self._user_state_feed:
            self._user_state_feed.add_fill_listener(callback)

    def add_account_listener(self, callback) -> None:
        """Add a callback for real-time account updates"""
        if self._user_state_feed:
            self._user_state_feed.add_account_listener(callback)

    # ========================================================================
    # API FALLBACK METHODS
    # ========================================================================

    def _api_get_current_price(self, symbol: str) -> float:
        """Get price via API (fallback)"""
        from src.nice_funcs_hyperliquid import get_current_price as hl_get_price
        return hl_get_price(symbol)

    def _api_ask_bid(self, symbol: str) -> Tuple[float, float, any]:
        """Get ask/bid via API (fallback)"""
        from src.nice_funcs_hyperliquid import ask_bid as hl_ask_bid
        return hl_ask_bid(symbol)

    def _api_get_orderbook(self, symbol: str) -> Dict:
        """Get orderbook via API (fallback)"""
        ask, bid, levels = self._api_ask_bid(symbol)

        # Parse levels into structured format
        bids = []
        asks = []

        if levels and len(levels) >= 2:
            for level in levels[0][:20]:  # Top 20 bids
                bids.append({
                    "price": float(level.get("px", 0)),
                    "size": float(level.get("sz", 0))
                })
            for level in levels[1][:20]:  # Top 20 asks
                asks.append({
                    "price": float(level.get("px", 0)),
                    "size": float(level.get("sz", 0))
                })

        return {
            "coin": symbol,
            "bids": bids,
            "asks": asks,
            "best_bid": bid,
            "best_ask": ask
        }


# ============================================================================
# GLOBAL INSTANCE AND DROP-IN REPLACEMENT FUNCTIONS
# ============================================================================

_global_data_manager: Optional[WebSocketDataManager] = None
_global_lock = threading.Lock()


def get_data_manager() -> WebSocketDataManager:
    """Get the global WebSocketDataManager instance"""
    global _global_data_manager
    with _global_lock:
        if _global_data_manager is None:
            _global_data_manager = WebSocketDataManager()
        return _global_data_manager


def start_websocket_feeds(coins: List[str] = None) -> bool:
    """
    Start WebSocket data feeds

    Call this once at application startup to enable WebSocket data.

    Args:
        coins: List of coins to monitor

    Returns:
        bool: True if started successfully
    """
    manager = get_data_manager()
    return manager.start(coins)


def stop_websocket_feeds():
    """Stop WebSocket data feeds"""
    manager = get_data_manager()
    manager.stop()


# ============================================================================
# DROP-IN REPLACEMENT FUNCTIONS
# These can replace the API polling functions from nice_funcs_hyperliquid
# ============================================================================

def get_current_price(symbol: str) -> float:
    """
    Get current price for a symbol (drop-in replacement)

    This function automatically uses WebSocket data if available,
    otherwise falls back to API polling.

    Args:
        symbol: Trading pair symbol (e.g., 'BTC')

    Returns:
        Current mid price
    """
    manager = get_data_manager()
    return manager.get_current_price(symbol)


def ask_bid(symbol: str) -> Tuple[float, float, any]:
    """
    Get ask and bid prices for a symbol (drop-in replacement)

    Returns tuple matching the API format: (ask, bid, levels)

    Args:
        symbol: Trading pair symbol

    Returns:
        Tuple of (ask, bid, levels)
    """
    manager = get_data_manager()
    return manager.get_ask_bid(symbol)


def get_market_info() -> Dict:
    """
    Get current market info for all coins (drop-in replacement)

    Returns:
        Dict mapping coin symbols to mid prices
    """
    manager = get_data_manager()

    if manager.is_running() and manager._price_feed:
        prices = manager._price_feed.get_all_prices()
        return {coin: str(ticker.price) for coin, ticker in prices.items()}

    # Fall back to API
    from src.nice_funcs_hyperliquid import get_market_info as hl_get_market_info
    return hl_get_market_info()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def is_websocket_enabled() -> bool:
    """Check if WebSocket feeds are enabled"""
    try:
        from src.config import USE_WEBSOCKET_FEEDS
        return USE_WEBSOCKET_FEEDS
    except ImportError:
        return True


def is_websocket_connected() -> bool:
    """Check if WebSocket is connected and running"""
    manager = get_data_manager()
    return manager.is_running()


def get_data_source(symbol: str) -> str:
    """
    Get the current data source for a symbol

    Returns:
        'websocket' or 'api'
    """
    manager = get_data_manager()

    if manager.is_running() and manager._price_feed:
        if not manager._price_feed.is_price_stale(symbol, manager.PRICE_STALE_THRESHOLD_SEC):
            return 'websocket'

    return 'api'


# ============================================================================
# API-ONLY FUNCTIONS (Historical/Account data - always use API)
# ============================================================================

def get_ohlcv_data(
    symbol: str,
    timeframe: str = '15m',
    bars: int = 100,
    add_indicators: bool = True
):
    """
    Get OHLCV (candlestick) data for a symbol

    This always uses API because historical data requires batch fetching.
    WebSocket only provides updates to the current forming candle.

    Args:
        symbol: Trading pair symbol (e.g., 'BTC')
        timeframe: Candle timeframe (e.g., '1m', '5m', '15m', '1h', '4h', '1d')
        bars: Number of bars to fetch (max 5000)
        add_indicators: Whether to add technical indicators

    Returns:
        pd.DataFrame with columns: timestamp, open, high, low, close, volume
    """
    from src.nice_funcs_hyperliquid import get_data
    return get_data(symbol, timeframe=timeframe, bars=bars, add_indicators=add_indicators)


def get_funding_rates(symbol: str) -> Optional[Dict]:
    """
    Get funding rates for a symbol (always uses API)

    Args:
        symbol: Trading pair symbol

    Returns:
        Dict with funding_rate, mark_price, open_interest
    """
    from src.nice_funcs_hyperliquid import get_funding_rates as hl_get_funding
    return hl_get_funding(symbol)


def get_position(symbol: str, account=None) -> tuple:
    """
    Get current position for a symbol

    Uses WebSocket data if available, falls back to API.

    Args:
        symbol: Trading pair symbol
        account: Optional account object

    Returns:
        Tuple: (positions, im_in_pos, pos_size, pos_sym, entry_px, pnl_perc, is_long)
    """
    manager = get_data_manager()
    return manager.get_position(symbol, account)


def get_account_value(address=None) -> float:
    """
    Get total account value

    Uses WebSocket data if available, falls back to API.

    Args:
        address: Wallet address or Account object

    Returns:
        Total account value in USD
    """
    manager = get_data_manager()
    return manager.get_account_value(address)


def get_balance(address=None) -> float:
    """
    Get available balance

    Uses WebSocket data if available, falls back to API.

    Args:
        address: Wallet address or Account object

    Returns:
        Available balance in USD
    """
    manager = get_data_manager()
    return manager.get_balance(address)


def get_all_positions(address=None) -> list:
    """
    Get all open positions

    Uses WebSocket data if available, falls back to API.

    Args:
        address: Wallet address or Account object

    Returns:
        List of position dictionaries
    """
    manager = get_data_manager()
    return manager.get_all_positions(address)


def get_recent_fills(limit: int = 10) -> list:
    """
    Get recent trade fills from WebSocket

    Args:
        limit: Maximum number of fills to return

    Returns:
        List of fill dictionaries
    """
    manager = get_data_manager()
    return manager.get_recent_fills(limit)


def add_position_listener(callback) -> None:
    """
    Add a callback for real-time position updates

    Callback receives position dict when position changes.
    """
    manager = get_data_manager()
    manager.add_position_listener(callback)


def add_fill_listener(callback) -> None:
    """
    Add a callback for real-time fill notifications

    Callback receives fill dict when trade executes.
    """
    manager = get_data_manager()
    manager.add_fill_listener(callback)


def add_account_listener(callback) -> None:
    """
    Add a callback for real-time account updates

    Callback receives account state dict when balance/equity changes.
    """
    manager = get_data_manager()
    manager.add_account_listener(callback)
