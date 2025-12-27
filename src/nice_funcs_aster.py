"""
🌙 Moon Dev's Aster DEX Functions (fixed)
Built with love by Moon Dev 🚀

Notes:
- This version normalizes API responses (tuple/dict) so `.get()` won't raise
  "'tuple' object has no attribute 'get'".
"""

import os
import sys
import time
from termcolor import cprint
from dotenv import load_dotenv

# Add Aster Dex Trading Bots to path
aster_bots_path = '/Users/md/Dropbox/dev/github/Aster-Dex-Trading-Bots'
if aster_bots_path not in sys.path:
    sys.path.insert(0, aster_bots_path)

# Try importing Aster modules
ASTER_AVAILABLE = True
try:
    from aster_api import AsterAPI  # type: ignore
    from aster_funcs import AsterFuncs  # type: ignore
except ImportError as e:
    cprint(f"⚠️ Aster modules not available: {e}", "yellow")
    cprint(f"Skipping Aster functionality. Make sure Aster-Dex-Trading-Bots exists at: {aster_bots_path}", "yellow")
    ASTER_AVAILABLE = False

if ASTER_AVAILABLE:
    # Load environment variables
    load_dotenv()

    # Get API keys
    ASTER_API_KEY = os.getenv('ASTER_API_KEY')
    ASTER_API_SECRET = os.getenv('ASTER_API_SECRET')

    # Verify API keys
    if not ASTER_API_KEY or not ASTER_API_SECRET:
        cprint("❌ ASTER API keys not found in .env file!", "red")
        cprint("Please add ASTER_API_KEY and ASTER_API_SECRET to your .env file", "yellow")
        ASTER_AVAILABLE = False
    else:
        # Initialize API (global instance)
        api = AsterAPI(ASTER_API_KEY, ASTER_API_SECRET)
        funcs = AsterFuncs(api)

# ============================================================================
# CONFIGURATION
# ============================================================================
DEFAULT_LEVERAGE = 5  # Change this to adjust leverage globally (1-125x)
DEFAULT_SYMBOL_SUFFIX = 'USDT'  # Aster uses BTCUSDT, ETHUSDT, etc.

# Precision cache
SYMBOL_PRECISION_CACHE = {}

# -------------------------
# Response normalization
# -------------------------
def normalize_response(resp, kind=None):
    """
    Convert various API return shapes into a dictionary form used by this script.

    Heuristics:
    - If resp already a dict -> return as is.
    - If resp is a list/tuple and contains at least one dict -> return the first dict.
    - If resp is a list/tuple and no dict is inside -> attempt to map common
      structures for known kinds (order, position, account, orderbook, exchange_info).
    - Otherwise return empty dict.
    """
    # Already a dict (common)
    if isinstance(resp, dict):
        return resp

    # If tuple/list, try to find a dict inside
    if isinstance(resp, (list, tuple)):
        for item in resp:
            if isinstance(item, dict):
                return item

        # Heuristics by kind
        if kind == 'order':
            return {
                'orderId': resp[0] if len(resp) > 0 else None,
                'status': resp[1] if len(resp) > 1 else None,
                'filled_qty': resp[2] if len(resp) > 2 else None
            }
        if kind == 'position':
            # expected (position_amount, entry_price, mark_price, pnl, pnl_percentage, is_long)
            return {
                'position_amount': float(resp[0]) if len(resp) > 0 else 0.0,
                'entry_price': float(resp[1]) if len(resp) > 1 else 0.0,
                'mark_price': float(resp[2]) if len(resp) > 2 else 0.0,
                'pnl': float(resp[3]) if len(resp) > 3 else 0.0,
                'pnl_percentage': float(resp[4]) if len(resp) > 4 else 0.0,
                'is_long': bool(resp[5]) if len(resp) > 5 else (float(resp[0]) > 0 if len(resp) > 0 else False)
            }
        if kind == 'account':
            return {
                'availableBalance': float(resp[0]) if len(resp) > 0 else 0.0,
                'totalPositionInitialMargin': float(resp[1]) if len(resp) > 1 else 0.0,
                'totalUnrealizedProfit': float(resp[2]) if len(resp) > 2 else 0.0
            }
        if kind == 'orderbook':
            # assume (bids, asks) or similar
            bids = resp[0] if len(resp) > 0 else []
            asks = resp[1] if len(resp) > 1 else []
            # if inner elements are strings/tuples, return as-is
            return {'bids': bids, 'asks': asks}
        if kind == 'exchange_info':
            # If first element is dict, return that, else default
            if len(resp) > 0 and isinstance(resp[0], dict):
                return resp[0]
            return {'symbols': []}

    # Fallback
    return {}

# Convenience wrapper specifically for orders
def normalize_order(order):
    return normalize_response(order, kind='order')

# Convenience wrapper for positions
def normalize_position(position):
    return normalize_response(position, kind='position')

# Convenience wrapper for account info
def normalize_account(account_info):
    return normalize_response(account_info, kind='account')

# Convenience wrapper for orderbook
def normalize_orderbook(orderbook):
    return normalize_response(orderbook, kind='orderbook')

# Convenience wrapper for exchange info
def normalize_exchange_info(exchange_info):
    return normalize_response(exchange_info, kind='exchange_info')

# ============================================================================
# Utilities
# ============================================================================
def get_symbol_precision(symbol):
    """Get price and quantity precision for a symbol

    Returns:
        tuple: (price_precision, quantity_precision) as number of decimal places
    """
    if symbol in SYMBOL_PRECISION_CACHE:
        return SYMBOL_PRECISION_CACHE[symbol]

    try:
        exchange_info_raw = api.get_exchange_info()
        exchange_info = normalize_exchange_info(exchange_info_raw)

        for sym_info in exchange_info.get('symbols', []):
            if sym_info.get('symbol') == symbol:
                price_precision = 2
                quantity_precision = 3

                for filter_info in sym_info.get('filters', []):
                    if filter_info.get('filterType') == 'PRICE_FILTER':
                        tick_size = filter_info.get('tickSize', '0.01')
                        price_precision = len(tick_size.rstrip('0').split('.')[-1]) if '.' in tick_size else 0

                    if filter_info.get('filterType') == 'LOT_SIZE':
                        step_size = filter_info.get('stepSize', '0.001')
                        quantity_precision = len(step_size.rstrip('0').split('.')[-1]) if '.' in step_size else 0

                SYMBOL_PRECISION_CACHE[symbol] = (price_precision, quantity_precision)
                return price_precision, quantity_precision

        # Default if not found
        SYMBOL_PRECISION_CACHE[symbol] = (2, 3)
        return 2, 3

    except Exception as e:
        cprint(f"❌ Error getting precision: {e}", "red")
        return 2, 3

def format_symbol(token):
    """Convert token address/symbol to Aster format"""
    if not token.endswith(DEFAULT_SYMBOL_SUFFIX):
        return f"{token}{DEFAULT_SYMBOL_SUFFIX}"
    return token

def token_price(address):
    """Get current token price from bid/ask midpoint"""
    try:
        symbol = format_symbol(address)
        # api.get_ask_bid might return a tuple (ask, bid, something) or a dict
        res = api.get_ask_bid(symbol)

        ask = bid = 0.0

        if isinstance(res, (list, tuple)):
            # try standard unpack
            try:
                ask, bid, _ = res
            except Exception:
                # fallback: try to find dict inside
                res2 = normalize_response(res)
                ask = float(res2.get('ask', 0) or 0)
                bid = float(res2.get('bid', 0) or 0)
        elif isinstance(res, dict):
            ask = float(res.get('ask', 0) or 0)
            bid = float(res.get('bid', 0) or 0)
        else:
            res2 = normalize_response(res)
            ask = float(res2.get('ask', 0) or 0)
            bid = float(res2.get('bid', 0) or 0)

        if ask == 0 or bid == 0:
            return 0.0

        midpoint = (float(ask) + float(bid)) / 2
        return midpoint
    except Exception as e:
        cprint(f"❌ Error getting price for {address}: {e}", "red")
        return 0.0

def get_best_bid_ask(symbol):
    """Get best bid and ask prices from order book"""
    try:
        orderbook_raw = api.get_orderbook(symbol, limit=5)
        orderbook = normalize_orderbook(orderbook_raw)

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return None, None

        # bids/asks might be lists of [price, qty] tuples or strings
        try:
            best_bid = float(bids[0][0])
        except Exception:
            best_bid = float(bids[0]) if bids else None

        try:
            best_ask = float(asks[0][0])
        except Exception:
            best_ask = float(asks[0]) if asks else None

        return best_bid, best_ask

    except Exception as e:
        cprint(f"❌ Error getting order book for {symbol}: {e}", "red")
        return None, None

def place_limit_order_with_chase(symbol, side, quantity, leverage, max_attempts=20, check_interval=0.5):
    """Place limit order at best bid/ask and chase until filled"""
    try:
        # Set leverage first
        api.change_leverage(symbol, leverage)

        current_order_id = None
        last_price = None
        attempts = 0

        while attempts < max_attempts:
            attempts += 1

            # Get best bid/ask
            best_bid, best_ask = get_best_bid_ask(symbol)
            if best_bid is None or best_ask is None:
                cprint(f"❌ Could not get order book", "red")
                time.sleep(check_interval)
                continue

            target_price = best_bid if side == 'BUY' else best_ask

            # Round price to proper precision
            price_precision, _ = get_symbol_precision(symbol)
            target_price = round(target_price, price_precision)

            # If we have an existing order and price hasn't changed, check status
            if current_order_id and target_price == last_price:
                order_status_raw = api.get_order(symbol, order_id=current_order_id)
                order_status = normalize_order(order_status_raw)
                status = order_status.get('status', '')

                if status == 'FILLED':
                    cprint(f"✅ Order FILLED! Order ID: {current_order_id}", "green", attrs=['bold'])
                    return order_status

                # Order still open, wait and continue
                time.sleep(check_interval)
                continue

            # Price changed or first order - cancel old order if exists
            if current_order_id:
                try:
                    cprint(f"🔄 Best {side} price changed: ${last_price:.2f} → ${target_price:.2f}", "yellow")
                    api.cancel_order(symbol, order_id=current_order_id)
                    cprint(f"❌ Cancelled order {current_order_id}", "yellow")
                    time.sleep(0.2)  # Brief delay after cancel
                except Exception as e:
                    # Order might have filled during cancel
                    cprint(f"   Could not cancel order {current_order_id}: {e}", "yellow")

            # Place new limit order at best bid/ask
            cprint(f"📝 Placing LIMIT {side}: {quantity} {symbol} @ ${target_price:.2f}", "cyan")
            order_raw = api.place_order(
                symbol=symbol,
                side=side,
                order_type='LIMIT',
                quantity=quantity,
                price=target_price,
                time_in_force='GTC'
            )

            order = normalize_order(order_raw)
            current_order_id = order.get('orderId')
            last_price = target_price
            cprint(f"   Order placed: ID {current_order_id}", "cyan")

            time.sleep(check_interval)

        # Max attempts reached
        if current_order_id:
            cprint(f"⚠️  Max attempts reached, cancelling order {current_order_id}", "yellow")
            try:
                api.cancel_order(symbol, order_id=current_order_id)
            except Exception:
                pass

        return None

    except Exception as e:
        cprint(f"❌ Error in limit order chase: {e}", "red")
        return None

def get_position(token_mint_address):
    """Get current position for a token"""
    try:
        symbol = format_symbol(token_mint_address)
        position_raw = api.get_position(symbol)
        position = normalize_position(position_raw)
        return position
    except Exception as e:
        cprint(f"❌ Error getting position for {token_mint_address}: {e}", "red")
        return None

def get_token_balance_usd(token_mint_address):
    """Get USD value of current position"""
    try:
        position = get_position(token_mint_address)
        if not position:
            return 0.0

        position_amt = float(position.get('position_amount', 0) or 0)
        mark_price = float(position.get('mark_price', 0) or 0)

        return abs(position_amt * mark_price)
    except Exception as e:
        cprint(f"❌ Error getting balance for {token_mint_address}: {e}", "red")
        return 0.0

def market_buy(token, amount, slippage, leverage=DEFAULT_LEVERAGE):
    """Open or add to LONG position with MARKET order (immediate fill)"""
    try:
        symbol = format_symbol(token)

        # Set leverage
        cprint(f"⚙️  Setting leverage to {leverage}x for {symbol}", "yellow")
        api.change_leverage(symbol, leverage)

        # Get current price and calculate quantity
        current_price = token_price(token)
        if current_price == 0:
            cprint(f"❌ Could not get price for {symbol}", "red")
            return None

        # Calculate quantity based on NOTIONAL value
        quantity = amount / current_price

        # Round to proper precision
        _, quantity_precision = get_symbol_precision(symbol)
        quantity = round(quantity, quantity_precision)

        # Check if quantity is too small
        min_notional = 5.0
        actual_notional = quantity * current_price

        if quantity <= 0 or actual_notional < min_notional:
            cprint(f"❌ Position size too small for {symbol}!", "red")
            cprint(f"   Calculated Quantity: {quantity} {symbol}", "red")
            cprint(f"   Actual Notional: ${actual_notional:.2f} (minimum: ${min_notional:.2f})", "red")
            cprint(f"   💡 Need at least ${min_notional:.2f} position size", "yellow")
            return None

        # Calculate required margin for logging
        required_margin = amount / leverage

        cprint(f"🚀 MARKET BUY: {quantity} {symbol} @ ~${current_price:.2f}", "green")
        cprint(f"💰 Notional Position: ${amount:.2f} | Margin Required: ${required_margin:.2f} ({leverage}x)", "cyan")

        # Place market buy order
        order_raw = api.place_order(
            symbol=symbol,
            side='BUY',
            order_type='MARKET',
            quantity=quantity
        )
        order = normalize_order(order_raw)

        cprint(f"✅ Market buy order placed! Order ID: {order.get('orderId')}", "green")
        return order

    except Exception as e:
        cprint(f"❌ Error placing market buy: {e}", "red")
        return None

def limit_buy(token, amount, slippage, leverage=DEFAULT_LEVERAGE):
    """Open or add to LONG position with LIMIT order at best bid (chase until filled)"""
    try:
        symbol = format_symbol(token)

        # Get current price and calculate quantity
        current_price = token_price(token)
        if current_price == 0:
            cprint(f"❌ Could not get price for {symbol}", "red")
            return None

        # Calculate quantity based on NOTIONAL value
        quantity = amount / current_price

        # Round to proper precision
        _, quantity_precision = get_symbol_precision(symbol)
        quantity = round(quantity, quantity_precision)

        # Check if quantity is too small
        min_notional = 5.0
        actual_notional = quantity * current_price

        if quantity <= 0 or actual_notional < min_notional:
            cprint(f"❌ Position size too small for {symbol}!", "red")
            cprint(f"   Calculated Quantity: {quantity} {symbol}", "red")
            cprint(f"   Actual Notional: ${actual_notional:.2f} (minimum: ${min_notional:.2f})", "red")
            cprint(f"   💡 Need at least ${min_notional:.2f} position size", "yellow")
            return None

        # Calculate required margin for logging
        required_margin = amount / leverage

        cprint(f"🚀 LIMIT BUY: {quantity} {symbol} (chasing best bid)", "green")
        cprint(f"💰 Notional Position: ${amount:.2f} | Margin Required: ${required_margin:.2f} ({leverage}x)", "cyan")

        # Place limit order at best bid and chase until filled
        order = place_limit_order_with_chase(
            symbol=symbol,
            side='BUY',
            quantity=quantity,
            leverage=leverage,
            max_attempts=20,
            check_interval=0.5
        )

        if order:
            return order
        else:
            cprint(f"❌ Failed to fill buy order after chasing", "red")
            return None

    except Exception as e:
        cprint(f"❌ Error placing limit buy: {e}", "red")
        return None

def market_sell(token, amount, slippage, leverage=DEFAULT_LEVERAGE):
    """Close LONG or open SHORT position with MARKET order (immediate fill)"""
    try:
        symbol = format_symbol(token)

        # Check current position
        position = get_position(token)

        # Get current price and calculate quantity
        current_price = token_price(token)
        if current_price == 0:
            cprint(f"❌ Could not get price for {symbol}", "red")
            return None

        # Calculate quantity based on NOTIONAL value
        quantity = amount / current_price

        # Round to proper precision
        _, quantity_precision = get_symbol_precision(symbol)
        quantity = round(quantity, quantity_precision)

        if position and float(position.get('position_amount', 0)) > 0:
            # We have a long position - close it (reduce_only)
            cprint(f"📉 Closing LONG: {quantity} {symbol} @ MARKET", "red")
            cprint(f"💰 Closing ${amount:.2f} notional position", "cyan")

            order_raw = api.place_order(
                symbol=symbol,
                side='SELL',
                order_type='MARKET',
                quantity=quantity,
                reduce_only=True
            )
            order = normalize_order(order_raw)

            cprint(f"✅ Market sell order placed! Order ID: {order.get('orderId')}", "green")
            return order
        else:
            # No long position - open short
            # Check if quantity is too small
            min_notional = 5.0
            actual_notional = quantity * current_price

            if quantity <= 0 or actual_notional < min_notional:
                cprint(f"❌ Position size too small for {symbol}!", "red")
                cprint(f"   Calculated Quantity: {quantity} {symbol}", "red")
                cprint(f"   Actual Notional: ${actual_notional:.2f} (minimum: ${min_notional:.2f})", "red")
                cprint(f"   💡 Need at least ${min_notional:.2f} position size", "yellow")
                return None

            cprint(f"⚙️  Setting leverage to {leverage}x for {symbol}", "yellow")
            api.change_leverage(symbol, leverage)

            required_margin = amount / leverage
            cprint(f"📉 MARKET SELL (SHORT): {quantity} {symbol} @ ~${current_price:.2f}", "red")
            cprint(f"💰 Notional Position: ${amount:.2f} | Margin Required: ${required_margin:.2f} ({leverage}x)", "cyan")

            order_raw = api.place_order(
                symbol=symbol,
                side='SELL',
                order_type='MARKET',
                quantity=quantity
            )
            order = normalize_order(order_raw)

            cprint(f"✅ Market sell order placed! Order ID: {order.get('orderId')}", "green")
            return order

    except Exception as e:
        cprint(f"❌ Error placing market sell: {e}", "red")
        return None

def limit_sell(token, amount, slippage, leverage=DEFAULT_LEVERAGE):
    """Close LONG or open SHORT position with LIMIT order at best ask (chase until filled)"""
    try:
        symbol = format_symbol(token)

        # Check current position
        position = get_position(token)

        # Get current price and calculate quantity
        current_price = token_price(token)
        if current_price == 0:
            cprint(f"❌ Could not get price for {symbol}", "red")
            return None

        # Calculate quantity based on NOTIONAL value
        quantity = amount / current_price

        # Round to proper precision
        _, quantity_precision = get_symbol_precision(symbol)
        quantity = round(quantity, quantity_precision)

        if position and float(position.get('position_amount', 0)) > 0:
            # We have a long position - close it (reduce_only)
            # Use market order for immediate exit when closing
            cprint(f"📉 Closing LONG: {quantity} {symbol} @ MARKET (immediate exit)", "red")
            cprint(f"💰 Closing ${amount:.2f} notional position", "cyan")

            order_raw = api.place_order(
                symbol=symbol,
                side='SELL',
                order_type='MARKET',
                quantity=quantity,
                reduce_only=True
            )
            order = normalize_order(order_raw)

            cprint(f"✅ Market sell order placed! Order ID: {order.get('orderId')}", "green")
            return order
        else:
            # No long position - open short using limit order chase
            # Check if quantity is too small
            min_notional = 5.0
            actual_notional = quantity * current_price

            if quantity <= 0 or actual_notional < min_notional:
                cprint(f"❌ Position size too small for {symbol}!", "red")
                cprint(f"   Calculated Quantity: {quantity} {symbol}", "red")
                cprint(f"   Actual Notional: ${actual_notional:.2f} (minimum: ${min_notional:.2f})", "red")
                cprint(f"   💡 Need at least ${min_notional:.2f} position size", "yellow")
                return None

            required_margin = amount / leverage
            cprint(f"🚀 LIMIT SELL (SHORT): {quantity} {symbol} (chasing best ask)", "red")
            cprint(f"💰 Notional Position: ${amount:.2f} | Margin Required: ${required_margin:.2f} ({leverage}x)", "cyan")

            # Place limit order at best ask and chase until filled
            order = place_limit_order_with_chase(
                symbol=symbol,
                side='SELL',
                quantity=quantity,
                leverage=leverage,
                max_attempts=20,
                check_interval=0.5
            )

            if order:
                return order
            else:
                cprint(f"❌ Failed to fill sell order after chasing", "red")
                return None

    except Exception as e:
        cprint(f"❌ Error placing limit sell: {e}", "red")
        return None

def chunk_kill(token_mint_address, max_usd_order_size, slippage):
    """Close entire position in chunks"""
    try:
        symbol = format_symbol(token_mint_address)
        position = get_position(token_mint_address)

        if not position:
            cprint(f"⚠️  No position to close for {symbol}", "yellow")
            return True

        position_amt = float(position.get('position_amount', 0) or 0)
        is_long = bool(position.get('is_long', position_amt > 0))

        cprint(f"🔄 Closing position: {position_amt} {symbol} ({'LONG' if is_long else 'SHORT'})", "cyan")

        # Determine close side (opposite of position)
        close_side = 'SELL' if is_long else 'BUY'

        # Get total position value
        total_value = abs(position_amt * float(position.get('mark_price', 0) or 0))

        # Calculate number of chunks needed
        num_chunks = int(total_value / max_usd_order_size) + 1
        chunk_size_tokens = abs(position_amt) / num_chunks

        # Round to proper precision
        _, quantity_precision = get_symbol_precision(symbol)
        chunk_size_tokens = round(chunk_size_tokens, quantity_precision)

        cprint(f"📊 Closing in {num_chunks} chunks of ~{chunk_size_tokens} tokens", "yellow")

        for i in range(num_chunks):
            # Check remaining position
            current_position = get_position(token_mint_address)
            if not current_position or abs(float(current_position.get('position_amount', 0) or 0)) < 0.0001:
                cprint(f"✅ Position fully closed after {i} chunks!", "green")
                break

            # Calculate chunk size (use remaining position for last chunk)
            remaining = abs(float(current_position.get('position_amount', 0) or 0))
            chunk = min(chunk_size_tokens, remaining)
            chunk = round(chunk, quantity_precision)

            cprint(f"🔄 Chunk {i+1}/{num_chunks}: Closing {chunk} {symbol}", "cyan")

            # Place market order to close chunk
            order_raw = api.place_order(
                symbol=symbol,
                side=close_side,
                order_type='MARKET',
                quantity=chunk,
                reduce_only=True
            )
            order = normalize_order(order_raw)

            cprint(f"✅ Chunk order placed! Order ID: {order.get('orderId')}", "green")
            time.sleep(1)  # Small delay between chunks

        # Verify position closed
        final_position = get_position(token_mint_address)
        if not final_position or abs(float(final_position.get('position_amount', 0) or 0)) < 0.0001:
            cprint(f"✅ Position closed successfully!", "green", attrs=['bold'])
            return True
        else:
            cprint(f"⚠️  Position still has {final_position.get('position_amount')} remaining", "yellow")
            return False

    except Exception as e:
        cprint(f"❌ Error in chunk_kill: {e}", "red")
        return False

def ai_entry(symbol, amount, max_chunk_size=None, leverage=DEFAULT_LEVERAGE, use_limit=True):
    """Smart entry with automatic chunking"""
    try:
        symbol = format_symbol(symbol)

        if max_chunk_size is None or amount <= max_chunk_size:
            # Single order
            if use_limit:
                result = limit_buy(symbol, amount, slippage=0, leverage=leverage)
            else:
                result = market_buy(symbol, amount, slippage=0, leverage=leverage)
            return result is not None

        # Multiple chunks
        num_chunks = int(amount / max_chunk_size) + 1
        chunk_size = amount / num_chunks

        order_type_str = "LIMIT" if use_limit else "MARKET"
        cprint(f"🎯 AI Entry: ${amount} in {num_chunks} {order_type_str} chunks of ${chunk_size:.2f}", "cyan")

        for i in range(num_chunks):
            cprint(f"🔄 Chunk {i+1}/{num_chunks}: ${chunk_size:.2f}", "cyan")

            if use_limit:
                result = limit_buy(symbol, chunk_size, slippage=0, leverage=leverage)
            else:
                result = market_buy(symbol, chunk_size, slippage=0, leverage=leverage)

            if not result:
                cprint(f"❌ Chunk {i+1} failed!", "red")
                return False

            time.sleep(1)  # Delay between chunks

        cprint(f"✅ AI Entry complete! ${amount} deployed across {num_chunks} {order_type_str} orders", "green")
        return True

    except Exception as e:
        cprint(f"❌ Error in ai_entry: {e}", "red")
        return False

def open_short(token, amount, slippage, leverage=DEFAULT_LEVERAGE):
    """Open SHORT position explicitly"""
    try:
        symbol = format_symbol(token)

        # Set leverage
        cprint(f"⚙️  Setting leverage to {leverage}x for {symbol}", "yellow")
        api.change_leverage(symbol, leverage)

        # Get current price and calculate quantity
        current_price = token_price(token)
        if current_price == 0:
            cprint(f"❌ Could not get price for {symbol}", "red")
            return None

        # Calculate quantity based on NOTIONAL value
        quantity = amount / current_price

        # Round to proper precision
        _, quantity_precision = get_symbol_precision(symbol)
        quantity = round(quantity, quantity_precision)

        # Calculate required margin
        required_margin = amount / leverage

        cprint(f"📉 Opening SHORT: {quantity} {symbol} @ ~${current_price:.2f}", "red")
        cprint(f"💰 Notional Position: ${amount:.2f} | Margin Required: ${required_margin:.2f} ({leverage}x)", "cyan")

        # Place market sell order to open short
        order_raw = api.place_order(
            symbol=symbol,
            side='SELL',
            order_type='MARKET',
            quantity=quantity
        )
        order = normalize_order(order_raw)

        cprint(f"✅ Short position opened! Order ID: {order.get('orderId')}", "green")
        return order

    except Exception as e:
        cprint(f"❌ Error opening short: {e}", "red")
        return None

def get_account_balance():
    """Get account balance information"""
    try:
        account_info_raw = api.get_account_info()
        account_info = normalize_account(account_info_raw)

        available = float(account_info.get('availableBalance', 0) or 0)
        position_margin = float(account_info.get('totalPositionInitialMargin', 0) or 0)
        unrealized_profit = float(account_info.get('totalUnrealizedProfit', 0) or 0)
        total_equity = available + position_margin + unrealized_profit

        return {
            'available': available,
            'total_equity': total_equity,
            'position_margin': position_margin,
            'unrealized_pnl': unrealized_profit
        }
    except Exception as e:
        cprint(f"❌ Error getting account balance: {e}", "red")
        return None

# Initialize on import
cprint("✨ Aster DEX functions loaded successfully (normalized)!", "green")
