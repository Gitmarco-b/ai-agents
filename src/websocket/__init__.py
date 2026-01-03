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
| OHLC/Candles     | API       | Historical data, batch fetching     |
| User State       | API       | Account data, positions             |
| Funding Rates    | API       | Periodic data, not real-time        |

Usage:
    # Start WebSocket feeds at app startup
    from src.websocket import start_websocket_feeds
    start_websocket_feeds()

    # Real-time data (WebSocket)
    from src.websocket import get_current_price, ask_bid
    price = get_current_price('BTC')
    ask, bid, _ = ask_bid('ETH')

    # Historical data (API - always)
    from src.websocket import get_ohlcv_data
    df = get_ohlcv_data('BTC', timeframe='15m', bars=100)
"""

from src.websocket.hyperliquid_ws import HyperliquidWebSocket
from src.websocket.price_feed import PriceFeed, get_price_feed, get_current_price_ws, get_ask_bid_ws
from src.websocket.orderbook_feed import OrderBookFeed, get_orderbook_feed, get_l2_book_ws
from src.websocket.data_manager import (
    WebSocketDataManager,
    get_data_manager,
    start_websocket_feeds,
    stop_websocket_feeds,
    # Real-time data (WebSocket with API fallback)
    get_current_price,
    ask_bid,
    get_market_info,
    # Historical/Account data (API only)
    get_ohlcv_data,
    get_funding_rates,
    get_position,
    get_account_value,
    get_balance,
    get_all_positions,
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
    # Data manager (recommended for most use cases)
    'WebSocketDataManager',
    'get_data_manager',
    'start_websocket_feeds',
    'stop_websocket_feeds',
    # Real-time data (WebSocket with API fallback)
    'get_current_price',
    'ask_bid',
    'get_market_info',
    # Historical/Account data (API only)
    'get_ohlcv_data',
    'get_funding_rates',
    'get_position',
    'get_account_value',
    'get_balance',
    'get_all_positions',
    # Utility functions
    'is_websocket_enabled',
    'is_websocket_connected',
    'get_data_source',
]
