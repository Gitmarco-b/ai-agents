"""
Moon Dev's User State Feed
Real-time user state updates from Hyperliquid WebSocket
Built with love by Moon Dev

Features:
- Real-time position updates
- Trade fill notifications
- Order status updates
- Account balance tracking
- Event emission for frontend updates
"""

import os
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
class Position:
    """Position data structure"""
    coin: str
    size: float  # Positive = long, negative = short
    entry_price: float
    unrealized_pnl: float
    return_on_equity: float  # PnL percentage
    leverage: float
    liquidation_price: Optional[float] = None
    margin_used: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

    @property
    def is_long(self) -> bool:
        return self.size > 0

    @property
    def side(self) -> str:
        return "LONG" if self.is_long else "SHORT"

    @property
    def pnl_percent(self) -> float:
        return self.return_on_equity * 100

    def to_dict(self) -> Dict:
        return {
            "coin": self.coin,
            "size": self.size,
            "entry_price": self.entry_price,
            "unrealized_pnl": self.unrealized_pnl,
            "pnl_percent": self.pnl_percent,
            "leverage": self.leverage,
            "liquidation_price": self.liquidation_price,
            "margin_used": self.margin_used,
            "is_long": self.is_long,
            "side": self.side,
            "last_update": self.last_update.isoformat()
        }


@dataclass
class Fill:
    """Trade fill data structure"""
    coin: str
    side: str  # "B" for buy, "A" for sell
    size: float
    price: float
    time: datetime
    fee: float = 0.0
    order_id: Optional[str] = None
    closed_pnl: float = 0.0

    @property
    def is_buy(self) -> bool:
        return self.side == "B"

    def to_dict(self) -> Dict:
        return {
            "coin": self.coin,
            "side": "BUY" if self.is_buy else "SELL",
            "size": self.size,
            "price": self.price,
            "time": self.time.isoformat(),
            "fee": self.fee,
            "order_id": self.order_id,
            "closed_pnl": self.closed_pnl
        }


@dataclass
class AccountState:
    """Account state data structure"""
    account_value: float = 0.0
    withdrawable: float = 0.0
    total_margin_used: float = 0.0
    total_unrealized_pnl: float = 0.0
    last_update: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            "account_value": self.account_value,
            "withdrawable": self.withdrawable,
            "total_margin_used": self.total_margin_used,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "last_update": self.last_update.isoformat()
        }


class UserStateFeed:
    """
    Real-time user state feed for Hyperliquid

    Subscribes to:
    - userFills: Trade executions
    - orderUpdates: Order status changes
    - userEvents: General user events including position updates

    Usage:
        from src.websocket import HyperliquidWebSocket
        from src.websocket.user_state_feed import UserStateFeed

        ws = HyperliquidWebSocket()
        user_feed = UserStateFeed(ws, user_address="0x...")

        # Add event listeners
        user_feed.on_position_update = lambda pos: print(f"Position: {pos}")
        user_feed.on_fill = lambda fill: print(f"Fill: {fill}")

        # Start streaming
        user_feed.start()

        # Get current positions
        positions = user_feed.get_all_positions()
    """

    def __init__(self, ws_client=None, user_address: str = None):
        """
        Initialize the user state feed

        Args:
            ws_client: HyperliquidWebSocket instance (optional)
            user_address: User's wallet address (uses ACCOUNT_ADDRESS from env if not provided)
        """
        self._ws = ws_client
        self._owns_ws = ws_client is None

        # Get user address
        if user_address:
            self._user_address = user_address
        else:
            self._user_address = os.getenv("ACCOUNT_ADDRESS", "")

        if not self._user_address:
            logger.warning("No user address provided - user state feed will not work")

        # State storage
        self._positions: Dict[str, Position] = {}
        self._recent_fills: List[Fill] = []
        self._account_state = AccountState()
        self._lock = threading.RLock()

        # Keep last N fills
        self._max_fills = 100

        # Event callbacks
        self._on_position_update_callbacks: List[Callable[[Dict], None]] = []
        self._on_fill_callbacks: List[Callable[[Dict], None]] = []
        self._on_account_update_callbacks: List[Callable[[Dict], None]] = []
        self._on_order_update_callbacks: List[Callable[[Dict], None]] = []

        # State tracking
        self._is_running = False
        self._initial_state_loaded = False

        logger.info(f"UserStateFeed initialized for {self._user_address[:8]}..." if self._user_address else "UserStateFeed initialized (no address)")

    @property
    def user_address(self) -> str:
        return self._user_address

    @property
    def on_position_update(self) -> Optional[Callable]:
        return self._on_position_update_callbacks[0] if self._on_position_update_callbacks else None

    @on_position_update.setter
    def on_position_update(self, callback: Callable[[Dict], None]):
        self._on_position_update_callbacks = [callback] if callback else []

    @property
    def on_fill(self) -> Optional[Callable]:
        return self._on_fill_callbacks[0] if self._on_fill_callbacks else None

    @on_fill.setter
    def on_fill(self, callback: Callable[[Dict], None]):
        self._on_fill_callbacks = [callback] if callback else []

    @property
    def on_account_update(self) -> Optional[Callable]:
        return self._on_account_update_callbacks[0] if self._on_account_update_callbacks else None

    @on_account_update.setter
    def on_account_update(self, callback: Callable[[Dict], None]):
        self._on_account_update_callbacks = [callback] if callback else []

    def add_position_listener(self, callback: Callable[[Dict], None]):
        """Add a position update listener"""
        if callback not in self._on_position_update_callbacks:
            self._on_position_update_callbacks.append(callback)

    def add_fill_listener(self, callback: Callable[[Dict], None]):
        """Add a fill listener"""
        if callback not in self._on_fill_callbacks:
            self._on_fill_callbacks.append(callback)

    def add_account_listener(self, callback: Callable[[Dict], None]):
        """Add an account update listener"""
        if callback not in self._on_account_update_callbacks:
            self._on_account_update_callbacks.append(callback)

    def add_order_listener(self, callback: Callable[[Dict], None]):
        """Add an order update listener"""
        if callback not in self._on_order_update_callbacks:
            self._on_order_update_callbacks.append(callback)

    def start(self) -> bool:
        """
        Start the user state feed

        Returns:
            bool: True if started successfully
        """
        if self._is_running:
            cprint("User state feed already running", "yellow")
            return True

        if not self._user_address:
            cprint("Cannot start user state feed: no user address", "red")
            return False

        cprint(f"Starting user state feed for {self._user_address[:8]}...", "cyan")
        logger.info(f"Starting user state feed for {self._user_address}")

        # Load initial state from API
        self._load_initial_state()

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

        # Subscribe to user channels
        self._ws.subscribe_user_fills(self._user_address)
        self._ws.subscribe_order_updates(self._user_address)
        self._ws.subscribe_user_events(self._user_address)

        self._is_running = True
        cprint("User state feed started successfully", "green")
        return True

    def stop(self):
        """Stop the user state feed"""
        if not self._is_running:
            return

        logger.info("Stopping user state feed")
        self._is_running = False

        # Unsubscribe from channels
        if self._ws and self._ws.is_connected and self._user_address:
            self._ws.unsubscribe_user_fills(self._user_address)
            self._ws.unsubscribe_order_updates(self._user_address)
            self._ws.unsubscribe_user_events(self._user_address)

        # Close WebSocket if we own it
        if self._owns_ws and self._ws:
            self._ws.close()

        cprint("User state feed stopped", "yellow")

    def _load_initial_state(self):
        """Load initial state from API"""
        try:
            from src.nice_funcs_hyperliquid import get_all_positions, get_account_value, get_balance

            # Load positions
            positions = get_all_positions(self._user_address)
            with self._lock:
                for pos in positions:
                    coin = pos.get('symbol', '')
                    self._positions[coin] = Position(
                        coin=coin,
                        size=pos.get('size', 0),
                        entry_price=pos.get('entry_price', 0),
                        unrealized_pnl=0,
                        return_on_equity=pos.get('pnl_percent', 0) / 100,
                        leverage=1,
                        last_update=datetime.now()
                    )

            # Load account state
            account_value = get_account_value(self._user_address)
            balance = get_balance(self._user_address)

            with self._lock:
                self._account_state.account_value = account_value
                self._account_state.withdrawable = balance
                self._account_state.last_update = datetime.now()

            self._initial_state_loaded = True
            cprint(f"Loaded {len(self._positions)} positions from API", "cyan")

        except Exception as e:
            logger.error(f"Failed to load initial state: {e}")
            cprint(f"Warning: Could not load initial state: {e}", "yellow")

    def _handle_connect(self):
        """Handle WebSocket connection"""
        cprint("User state feed connected", "green")

    def _handle_disconnect(self, was_clean: bool):
        """Handle WebSocket disconnection"""
        if not was_clean:
            cprint("User state feed disconnected unexpectedly", "red")

    def _handle_ws_message(self, data: Dict):
        """Handle incoming WebSocket messages"""
        channel = data.get("channel", "")

        if channel == "userFills":
            self._process_fills(data.get("data", []))
        elif channel == "orderUpdates":
            self._process_order_updates(data.get("data", []))
        elif channel == "userEvents":
            self._process_user_events(data.get("data", {}))

    def _process_fills(self, fills_data: List):
        """Process user fills message"""
        if not fills_data:
            return

        for fill_data in fills_data:
            try:
                fill = Fill(
                    coin=fill_data.get("coin", ""),
                    side=fill_data.get("side", ""),
                    size=float(fill_data.get("sz", 0)),
                    price=float(fill_data.get("px", 0)),
                    time=datetime.now(),
                    fee=float(fill_data.get("fee", 0)),
                    order_id=str(fill_data.get("oid", "")),
                    closed_pnl=float(fill_data.get("closedPnl", 0))
                )

                with self._lock:
                    self._recent_fills.insert(0, fill)
                    # Trim to max fills
                    if len(self._recent_fills) > self._max_fills:
                        self._recent_fills = self._recent_fills[:self._max_fills]

                # Emit fill event
                self._emit_fill(fill)

                logger.info(f"Fill: {fill.side} {fill.size} {fill.coin} @ {fill.price}")

            except Exception as e:
                logger.error(f"Error processing fill: {e}")

    def _process_order_updates(self, updates_data: List):
        """Process order updates message"""
        if not updates_data:
            return

        for update in updates_data:
            try:
                order_data = {
                    "order_id": str(update.get("order", {}).get("oid", "")),
                    "coin": update.get("order", {}).get("coin", ""),
                    "side": update.get("order", {}).get("side", ""),
                    "size": float(update.get("order", {}).get("sz", 0)),
                    "price": float(update.get("order", {}).get("limitPx", 0)),
                    "status": update.get("status", ""),
                    "filled": float(update.get("order", {}).get("filled", 0)),
                }

                # Emit order update event
                for callback in self._on_order_update_callbacks:
                    try:
                        callback(order_data)
                    except Exception as e:
                        logger.error(f"Error in order_update callback: {e}")

            except Exception as e:
                logger.error(f"Error processing order update: {e}")

    def _process_user_events(self, events_data: Dict):
        """Process user events message (includes position updates)"""
        # Check for position updates
        if "assetPositions" in events_data:
            self._update_positions(events_data.get("assetPositions", []))

        # Check for margin summary
        if "marginSummary" in events_data:
            self._update_account_state(events_data.get("marginSummary", {}))

    def _update_positions(self, positions_data: List):
        """Update positions from user events"""
        updated_coins = []

        with self._lock:
            # Track which coins we've seen
            seen_coins = set()

            for pos_data in positions_data:
                try:
                    raw_pos = pos_data.get("position", {})
                    coin = raw_pos.get("coin", "")
                    size = float(raw_pos.get("szi", 0))

                    seen_coins.add(coin)

                    if size != 0:
                        # Update or create position
                        self._positions[coin] = Position(
                            coin=coin,
                            size=size,
                            entry_price=float(raw_pos.get("entryPx", 0)),
                            unrealized_pnl=float(raw_pos.get("unrealizedPnl", 0)),
                            return_on_equity=float(raw_pos.get("returnOnEquity", 0)),
                            leverage=float(raw_pos.get("leverage", {}).get("value", 1)),
                            liquidation_price=float(raw_pos.get("liquidationPx", 0)) if raw_pos.get("liquidationPx") else None,
                            margin_used=float(raw_pos.get("marginUsed", 0)),
                            last_update=datetime.now()
                        )
                        updated_coins.append(coin)
                    elif coin in self._positions:
                        # Position closed
                        del self._positions[coin]
                        updated_coins.append(coin)

                except Exception as e:
                    logger.error(f"Error updating position: {e}")

        # Emit position updates
        for coin in updated_coins:
            self._emit_position_update(coin)

    def _update_account_state(self, margin_data: Dict):
        """Update account state from margin summary"""
        with self._lock:
            self._account_state.account_value = float(margin_data.get("accountValue", 0))
            self._account_state.withdrawable = float(margin_data.get("withdrawable", 0))
            self._account_state.total_margin_used = float(margin_data.get("totalMarginUsed", 0))
            self._account_state.total_unrealized_pnl = float(margin_data.get("totalNtlPos", 0))
            self._account_state.last_update = datetime.now()

        # Emit account update
        for callback in self._on_account_update_callbacks:
            try:
                callback(self._account_state.to_dict())
            except Exception as e:
                logger.error(f"Error in account_update callback: {e}")

    def _emit_position_update(self, coin: str):
        """Emit position update event"""
        with self._lock:
            if coin in self._positions:
                pos_data = self._positions[coin].to_dict()
            else:
                # Position closed
                pos_data = {"coin": coin, "size": 0, "closed": True}

        for callback in self._on_position_update_callbacks:
            try:
                callback(pos_data)
            except Exception as e:
                logger.error(f"Error in position_update callback: {e}")

    def _emit_fill(self, fill: Fill):
        """Emit fill event"""
        fill_data = fill.to_dict()

        for callback in self._on_fill_callbacks:
            try:
                callback(fill_data)
            except Exception as e:
                logger.error(f"Error in fill callback: {e}")

    # ========================================================================
    # PUBLIC API - Get User State Data
    # ========================================================================

    def get_position(self, coin: str) -> Optional[Position]:
        """Get position for a specific coin"""
        with self._lock:
            return self._positions.get(coin)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all current positions"""
        with self._lock:
            return {coin: pos for coin, pos in self._positions.items()}

    def get_positions_list(self) -> List[Dict]:
        """Get all positions as a list of dictionaries"""
        with self._lock:
            return [pos.to_dict() for pos in self._positions.values()]

    def get_account_state(self) -> AccountState:
        """Get current account state"""
        with self._lock:
            return self._account_state

    def get_recent_fills(self, limit: int = 10) -> List[Dict]:
        """Get recent fills"""
        with self._lock:
            return [fill.to_dict() for fill in self._recent_fills[:limit]]

    def has_position(self, coin: str) -> bool:
        """Check if there's an open position for a coin"""
        with self._lock:
            return coin in self._positions and self._positions[coin].size != 0

    def get_position_size(self, coin: str) -> float:
        """Get position size for a coin (0 if no position)"""
        with self._lock:
            if coin in self._positions:
                return self._positions[coin].size
            return 0.0

    def get_total_pnl(self) -> float:
        """Get total unrealized PnL across all positions"""
        with self._lock:
            return sum(pos.unrealized_pnl for pos in self._positions.values())

    def is_position_stale(self, coin: str, max_age_seconds: float = 30.0) -> bool:
        """Check if position data is stale"""
        with self._lock:
            if coin not in self._positions:
                return True
            age = (datetime.now() - self._positions[coin].last_update).total_seconds()
            return age > max_age_seconds


# ============================================================================
# SINGLETON INSTANCE FOR GLOBAL ACCESS
# ============================================================================

_global_user_feed: Optional[UserStateFeed] = None
_global_lock = threading.Lock()


def get_user_state_feed(user_address: str = None) -> UserStateFeed:
    """Get the global UserStateFeed instance (creates if needed)"""
    global _global_user_feed
    with _global_lock:
        if _global_user_feed is None:
            _global_user_feed = UserStateFeed(user_address=user_address)
        return _global_user_feed


def get_positions_realtime() -> List[Dict]:
    """
    Get all positions from WebSocket feed (real-time)

    Returns:
        List of position dictionaries
    """
    feed = get_user_state_feed()
    if not feed._is_running:
        return []
    return feed.get_positions_list()


def get_position_realtime(coin: str) -> Optional[Dict]:
    """
    Get position for a coin from WebSocket feed (real-time)

    Returns:
        Position dictionary or None
    """
    feed = get_user_state_feed()
    if not feed._is_running:
        return None
    pos = feed.get_position(coin)
    return pos.to_dict() if pos else None
