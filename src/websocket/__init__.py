"""
Moon Dev's WebSocket Module
Real-time data feeds for trading agents

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

Usage:
    # Start WebSocket feeds at app startup
    from src.websocket import start_websocket_feeds
    start_websocket_feeds()

    # Real-time data (WebSocket)
    from src.websocket import get_current_price, ask_bid
    price = get_current_price('BTC')
    ask, bid, _ = ask_bid('ETH')

    # Real-time user state (WebSocket)
    from src.websocket import get_all_positions, add_position_listener
    positions = get_all_positions()
    add_position_listener(lambda pos: print(f"Position update: {pos}"))

    # Historical data (API - always)
    from src.websocket import get_ohlcv_data
    df = get_ohlcv_data('BTC', timeframe='15m', bars=100)
"""

from src.websocket.hyperliquid_ws import HyperliquidWebSocket
from src.websocket.price_feed import PriceFeed, get_price_feed, get_current_price_ws, get_ask_bid_ws
from src.websocket.orderbook_feed import OrderBookFeed, get_orderbook_feed, get_l2_book_ws
from src.websocket.user_state_feed import (
    UserStateFeed,
    get_user_state_feed,
    get_positions_realtime,
    get_position_realtime,
    Position,
    Fill,
    AccountState,
)
from src.websocket.data_manager import (
    WebSocketDataManager,
    get_data_manager,
    start_websocket_feeds,
    stop_websocket_feeds,
    # Real-time data (WebSocket with API fallback)
    get_current_price,
    ask_bid,
    get_market_info,
    # Real-time user state (WebSocket with API fallback)
    get_position,
    get_account_value,
    get_balance,
    get_all_positions,
    get_recent_fills,
    add_position_listener,
    add_fill_listener,
    add_account_listener,
    # Historical data (API only)
    get_ohlcv_data,
    get_funding_rates,
    # Utility functions
    is_websocket_enabled,
    is_websocket_connected,
    get_data_source,
)

__all__ = [
    # Low-level WebSocket client
    'HyperliquidWebSocket',
    # Price feed
    'PriceFeed',
    'get_price_feed',
    'get_current_price_ws',
    'get_ask_bid_ws',
    # Order book feed
    'OrderBookFeed',
    'get_orderbook_feed',
    'get_l2_book_ws',
    # User state feed
    'UserStateFeed',
    'get_user_state_feed',
    'get_positions_realtime',
    'get_position_realtime',
    'Position',
    'Fill',
    'AccountState',
    # Data manager (recommended for most use cases)
    'WebSocketDataManager',
    'get_data_manager',
    'start_websocket_feeds',
    'stop_websocket_feeds',
    # Real-time data (WebSocket with API fallback)
    'get_current_price',
    'ask_bid',
    'get_market_info',
    # Real-time user state (WebSocket with API fallback)
    'get_position',
    'get_account_value',
    'get_balance',
    'get_all_positions',
    'get_recent_fills',
    'add_position_listener',
    'add_fill_listener',
    'add_account_listener',
    # Historical data (API only)
    'get_ohlcv_data',
    'get_funding_rates',
    # Utility functions
    'is_websocket_enabled',
    'is_websocket_connected',
    'get_data_source',
]
