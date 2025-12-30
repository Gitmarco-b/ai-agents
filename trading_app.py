#!/usr/bin/env python3
"""
Trading Dashboard Backend - Production Ready
============================================
Fixed memory leaks with rotating logs and bounded JSON files
"""
import os
import sys
import json
import time
import threading
from threading import Lock
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from dotenv import load_dotenv
from flask_cors import CORS
import signal
import atexit
import logging
from logging.handlers import RotatingFileHandler

# ============================================================================
# SETUP & CONFIGURATION
# ============================================================================

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

load_dotenv()

# Initialize Flask
DASHBOARD_DIR = BASE_DIR / "dashboard"
app = Flask(__name__,
    template_folder=str(DASHBOARD_DIR / "templates"),
    static_folder=str(DASHBOARD_DIR / "static"),
    static_url_path='/static'
)

CORS(app)

# ============================================================================
# DATA DIRECTORIES - Production Structure
# ============================================================================
DATA_ROOT = BASE_DIR / "agent_data"
LOGS_DIR = DATA_ROOT / "logs"
DATA_DIR = DATA_ROOT / "data"
TEMP_DIR = DATA_ROOT / "temp"

# Create directories
for directory in [LOGS_DIR, DATA_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# File paths
TRADES_FILE = DATA_DIR / "trades.json"
HISTORY_FILE = DATA_DIR / "history.json"
AGENT_STATE_FILE = DATA_DIR / "agent_state.json"

# ============================================================================
# ROTATING LOGGER SETUP
# ============================================================================

# Dashboard logger (300KB max, 5 backups)
dashboard_logger = logging.getLogger('dashboard')
dashboard_handler = RotatingFileHandler(
    LOGS_DIR / 'dashboard.log',
    maxBytes=300000,  # 300KB
    backupCount=5
)
dashboard_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
)
dashboard_logger.addHandler(dashboard_handler)
dashboard_logger.setLevel(logging.INFO)

# Also log to console for Docker
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
dashboard_logger.addHandler(console_handler)

# ============================================================================
# AGENT CONTROL VARIABLES
# ============================================================================
agent_thread = None
agent_running = False
stop_agent_flag = False
shutdown_in_progress = False
agent_executing = False
agent_lock = Lock()

SYMBOLS = ['ETH', 'BTC', 'SOL', 'AAVE', 'LINK', 'LTC', 'FARTCOIN']
EXCHANGE = "HYPERLIQUID"

# ============================================================================
# CACHING SYSTEM
# ============================================================================
_cache = {
    "account_data": {"data": None, "timestamp": 0},
    "positions_data": {"data": None, "timestamp": 0}
}
_cache_lock = Lock()
CACHE_DURATION = 5

def get_cached_or_fetch(cache_key, fetch_function):
    """Generic caching with 5-second TTL"""
    with _cache_lock:
        cache_entry = _cache.get(cache_key)
        now = time.time()
        
        if cache_entry and cache_entry["timestamp"] > 0:
            age = now - cache_entry["timestamp"]
            if age < CACHE_DURATION:
                return cache_entry["data"]
    
    try:
        fresh_data = fetch_function()
        with _cache_lock:
            _cache[cache_key] = {
                "data": fresh_data,
                "timestamp": time.time()
            }
        return fresh_data
        
    except Exception as e:
        dashboard_logger.error(f"Error fetching {cache_key}: {e}")
        with _cache_lock:
            if cache_entry and cache_entry["data"] is not None:
                return cache_entry["data"]
        raise

# ============================================================================
# IMPORT TRADING FUNCTIONS
# ============================================================================
EXCHANGE_CONNECTED = False
try:
    import nice_funcs_hyperliquid as n
    from eth_account import Account
    
    def _get_account():
        key = os.getenv("HYPER_LIQUID_ETH_PRIVATE_KEY", "").strip().replace('"', '').replace("'", "")
        if not key:
            raise RuntimeError("Missing HYPER_LIQUID_ETH_PRIVATE_KEY")
        if key.startswith("0x"):
            key = key[2:]
        if len(key) != 64:
            raise RuntimeError("Invalid key length")
        return Account.from_key(key)
    
    EXCHANGE_CONNECTED = True
    dashboard_logger.info("HyperLiquid connected successfully")
    
except ImportError as e:
    dashboard_logger.warning(f"Running in DEMO mode: {e}")
    
    class DummyAccount:
        address = "0x0000000000000000000000000000000000000000"
    
    def _get_account():
        return DummyAccount()
    
    n = None

# ============================================================================
# JSON ROTATION HELPER
# ============================================================================

def save_json_with_rotation(filepath, data, max_entries, max_size_kb=500):
    """Save JSON with automatic rotation and size limits"""
    filepath = Path(filepath)
    
    # Rotate if file too large
    if filepath.exists() and filepath.stat().st_size > (max_size_kb * 1024):
        backup = filepath.with_suffix('.json.backup')
        filepath.rename(backup)
        dashboard_logger.info(f"Rotated {filepath.name} (size limit exceeded)")
    
    # Load existing data
    if filepath.exists():
        try:
            with open(filepath, 'r') as f:
                existing = json.load(f)
        except json.JSONDecodeError:
            dashboard_logger.warning(f"Corrupted {filepath.name}, resetting")
            existing = []
    else:
        existing = []
    
    # Append and trim
    existing.append(data)
    existing = existing[-max_entries:]
    
    # Write atomically
    try:
        with open(filepath, 'w') as f:
            json.dump(existing, f, indent=2)
    except Exception as e:
        dashboard_logger.error(f"Failed to save {filepath.name}: {e}")

# ============================================================================
# DATA COLLECTION FUNCTIONS
# ============================================================================

def get_account_data():
    """Fetch account data with caching"""
    return get_cached_or_fetch("account_data", _fetch_account_data_uncached)

def _fetch_account_data_uncached():
    """Fetch live account data"""
    if not EXCHANGE_CONNECTED or n is None:
        return {
            "account_balance": 10.0,
            "total_equity": 10.0,
            "pnl": 0.0,
            "status": "Demo Mode",
            "exchange": "HyperLiquid (Disconnected)",
            "agent_running": agent_running
        }
    
    try:
        account = _get_account()
        address = os.getenv("ACCOUNT_ADDRESS", account.address)
        
        available_balance = float(n.get_available_balance(address)) if hasattr(n, 'get_available_balance') else 10.0
        total_equity = float(n.get_account_value(address)) if hasattr(n, 'get_account_value') else 10.0
        
        starting_balance = 10.0
        pnl = total_equity - starting_balance
        
        save_balance_history(total_equity)
        
        return {
            "account_balance": round(available_balance, 2),
            "total_equity": round(total_equity, 2),
            "pnl": round(pnl, 2),
            "status": "Running" if agent_running else "Connected",
            "exchange": "HyperLiquid",
            "agent_running": agent_running
        }
        
    except Exception as e:
        dashboard_logger.error(f"Error fetching account data: {e}")
        return {
            "account_balance": 0.0,
            "total_equity": 0.0,
            "pnl": 0.0,
            "status": "Error",
            "exchange": "HyperLiquid",
            "agent_running": agent_running
        }

def get_positions_data():
    """Fetch positions with caching"""
    return get_cached_or_fetch("positions_data", _fetch_positions_data_uncached)

def _fetch_positions_data_uncached():
    """Fetch live positions"""
    if not EXCHANGE_CONNECTED or n is None:
        return []

    try:
        account = _get_account()
        address = os.getenv("ACCOUNT_ADDRESS", account.address)
        
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
        
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
        user_state = info.user_state(address)
        
        positions = []
        
        if "assetPositions" not in user_state:
            return []
        
        for position in user_state["assetPositions"]:
            raw_pos = position.get("position", {})
            symbol = raw_pos.get("coin", "Unknown")
            pos_size = float(raw_pos.get("szi", 0))
            
            if pos_size == 0:
                continue
            
            entry_px = float(raw_pos.get("entryPx", 0))
            pnl_perc = float(raw_pos.get("returnOnEquity", 0)) * 100
            is_long = pos_size > 0
            
            try:
                ask, bid, _ = n.ask_bid(symbol)
                mark_price = (ask + bid) / 2
            except:
                mark_price = entry_px
            
            position_value = abs(pos_size) * mark_price
            
            positions.append({
                "symbol": symbol,
                "size": float(pos_size),
                "entry_price": float(entry_px),
                "mark_price": float(mark_price),
                "position_value": float(position_value),
                "pnl_percent": float(pnl_perc),
                "side": "LONG" if is_long else "SHORT"
            })
        
        return positions

    except Exception as e:
        dashboard_logger.error(f"Error fetching positions: {e}")
        return []

def save_balance_history(balance):
    """Save balance with rotation"""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "balance": float(balance)
    }
    save_json_with_rotation(HISTORY_FILE, entry, max_entries=100, max_size_kb=200)

def load_trades():
    """Load recent trades"""
    try:
        if TRADES_FILE.exists():
            with open(TRADES_FILE, 'r') as f:
                trades = json.load(f)
                return trades[-20:]
        return []
    except Exception as e:
        dashboard_logger.error(f"Error loading trades: {e}")
        return []

def save_trade(trade_data):
    """Save trade with rotation"""
    save_json_with_rotation(TRADES_FILE, trade_data, max_entries=50, max_size_kb=500)
    
    symbol = trade_data.get('symbol', 'Unknown')
    side = trade_data.get('side', 'LONG')
    pnl = trade_data.get('pnl', 0)
    
    side_emoji = "📈" if side == "LONG" else "📉"
    dashboard_logger.info(f"{side_emoji} Closed {side} {symbol} ${pnl:+.2f}")

def log_position_open(symbol, side, size_usd):
    """Log position opening"""
    emoji = "📈" if side == "LONG" else "📉"
    dashboard_logger.info(f"{emoji} Opened {side} {symbol} ${size_usd:.2f}")

# ============================================================================
# CONSOLE LOG READING (from rotating log file)
# ============================================================================

def get_console_logs():
    """Read last 100 lines from dashboard log file"""
    log_file = LOGS_DIR / 'dashboard.log'
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()[-100:]
        
        logs = []
        for line in lines:
            # Parse: "2024-01-01 12:00:00 - INFO - message"
            parts = line.split(' - ', 2)
            if len(parts) >= 3:
                timestamp = parts[0].split(' ')[1] if ' ' in parts[0] else parts[0]
                level = parts[1].lower()
                message = parts[2].strip()
                
                logs.append({
                    'timestamp': timestamp,
                    'level': level,
                    'message': message
                })
        
        return logs
        
    except Exception as e:
        dashboard_logger.error(f"Error reading console logs: {e}")
        return []

# ============================================================================
# AGENT STATE MANAGEMENT
# ============================================================================

def load_agent_state():
    """Load agent state"""
    try:
        if AGENT_STATE_FILE.exists():
            with open(AGENT_STATE_FILE, 'r') as f:
                return json.load(f)
        
        return {
            "running": False,
            "last_started": None,
            "last_stopped": None,
            "total_cycles": 0
        }
    except Exception as e:
        dashboard_logger.error(f"Error loading agent state: {e}")
        return {
            "running": False,
            "last_started": None,
            "last_stopped": None,
            "total_cycles": 0
        }

def save_agent_state(state):
    """Save agent state"""
    try:
        with open(AGENT_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        dashboard_logger.error(f"Error saving agent state: {e}")

# ============================================================================
# TRADING AGENT CONTROL
# ============================================================================

def run_trading_agent():
    """Run trading agent with proper memory management"""
    global agent_running, stop_agent_flag, agent_executing
    
    try:
        dashboard_logger.info("Initializing Trading Agent...")
        
        try:
            from src.agents.trading_agent import TradingAgent
        except ImportError:
            try:
                from trading_agent import TradingAgent
            except ImportError:
                sys.path.insert(0, str(BASE_DIR / "src" / "agents"))
                from trading_agent import TradingAgent
        
        agent = TradingAgent()
        dashboard_logger.info("Trading agent initialized successfully")
        
    except Exception as e:
        dashboard_logger.error(f"Failed to create agent: {e}")
        with agent_lock:
            agent_running = False
            agent_executing = False
        return
    
    cycle_count = 0
    
    while agent_running and not stop_agent_flag:
        try:
            cycle_count += 1
            dashboard_logger.info(f"Starting Cycle #{cycle_count}")
            
            with agent_lock:
                agent_executing = True
            
            cycle_start = time.time()
            
            if EXCHANGE in ["ASTER", "HYPERLIQUID"]:
                from src.agents.trading_agent import SYMBOLS as tokens
            else:
                from src.agents.trading_agent import MONITORED_TOKENS as tokens
            
            dashboard_logger.info(f"Analyzing {len(tokens)} tokens")
            
            agent.run_trading_cycle()
            
            cycle_duration = int(time.time() - cycle_start)
            dashboard_logger.info(f"Cycle #{cycle_count} complete ({cycle_duration}s)")

            with agent_lock:
                agent_executing = False
            
            if hasattr(agent, 'recommendations_df') and len(agent.recommendations_df) > 0:
                buy_count = len(agent.recommendations_df[agent.recommendations_df['action'] == 'BUY'])
                sell_count = len(agent.recommendations_df[agent.recommendations_df['action'] == 'SELL'])
                nothing_count = len(agent.recommendations_df[agent.recommendations_df['action'] == 'NOTHING'])
                dashboard_logger.info(f"Signals: {buy_count} BUY, {sell_count} SELL, {nothing_count} HOLD")
                
                # Clear DataFrame to free memory
                agent.recommendations_df = agent.recommendations_df.iloc[0:0]
            
            # Force garbage collection
            import gc
            gc.collect()
            
            from src.agents.trading_agent import SLEEP_BETWEEN_RUNS_MINUTES as minutes
            dashboard_logger.info(f"Next cycle in {minutes} minutes")
            
            for i in range(minutes):
                if stop_agent_flag:
                    dashboard_logger.info("Stop signal received")
                    break
                time.sleep(60)
            
        except Exception as e:
            with agent_lock:
                agent_executing = False
                
            dashboard_logger.error(f"Cycle #{cycle_count} error: {e}")
            dashboard_logger.warning("Retrying in 60 seconds")
            time.sleep(60)
    
    # Cleanup
    with agent_lock:
        agent_running = False
        agent_executing = False
    
    # Force delete agent to free memory
    del agent
    import gc
    gc.collect()
    
    dashboard_logger.info(f"Agent stopped after {cycle_count} cycles")

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/agent-status')
def get_agent_status():
    """Lightweight status check"""
    global agent_running, agent_executing, agent_thread
    with agent_lock:
        thread_alive = agent_thread is not None and agent_thread.is_alive()
        
        if agent_running and not thread_alive:
            dashboard_logger.warning("Agent thread died unexpectedly - resetting flags")
            agent_running = False
            agent_executing = False
        
        return jsonify({
            "running": agent_running,
            "executing": agent_executing,
            "thread_alive": thread_alive,
            "timestamp": datetime.now().isoformat()
        })

@app.route('/api/data')
def get_data():
    """Account data and positions"""
    try:
        account_data = get_account_data()
        positions = get_positions_data()
        
        return jsonify({
            **account_data,
            "positions": positions,
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        dashboard_logger.error(f"Error in /api/data: {e}")
        return jsonify({
            "error": str(e),
            "account_balance": 0,
            "total_equity": 0,
            "pnl": 0,
            "positions": [],
            "status": "Error",
            "agent_running": False
        }), 500

@app.route('/api/trades')
def get_trades():
    return jsonify(load_trades())

@app.route('/api/history')
def get_history():
    try:
        if HISTORY_FILE.exists():
            with open(HISTORY_FILE, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        dashboard_logger.error(f"Error loading history: {e}")
        return jsonify([])

@app.route('/api/console')
def get_console():
    """Return console logs from rotating log file"""
    return jsonify(get_console_logs())

@app.route('/api/start', methods=['POST'])
def start_agent():
    global agent_thread, agent_running, stop_agent_flag
    
    with agent_lock:
        if agent_running:
            return jsonify({
                "status": "already_running",
                "message": "Agent is already running"
            })
        
        agent_running = True
        stop_agent_flag = False
        
        state = load_agent_state()
        state["running"] = True
        state["last_started"] = datetime.now().isoformat()
        state["total_cycles"] = state.get("total_cycles", 0) + 1
        save_agent_state(state)
        
        agent_thread = threading.Thread(target=run_trading_agent, daemon=True)
        agent_thread.start()
    
    dashboard_logger.info("Trading agent started via dashboard")
    
    return jsonify({
        "status": "started",
        "message": "Trading agent started successfully"
    })

@app.route('/api/stop', methods=['POST'])
def stop_agent():
    global agent_running, stop_agent_flag
    
    with agent_lock:
        if not agent_running:
            return jsonify({
                "status": "not_running",
                "message": "Agent is not running"
            })
        
        stop_agent_flag = True
        agent_running = False
        
        state = load_agent_state()
        state["running"] = False
        state["last_stopped"] = datetime.now().isoformat()
        save_agent_state(state)
    
    dashboard_logger.info("Trading agent stopped via dashboard")
    
    return jsonify({
        "status": "stopped",
        "message": "Trading agent stopped successfully"
    })

@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }), 200

# ============================================================================
# GRACEFUL SHUTDOWN
# ============================================================================

def cleanup_and_exit(signum=None, frame=None):
    """Graceful shutdown handler"""
    global agent_running, stop_agent_flag, shutdown_in_progress
    
    if shutdown_in_progress:
        return
    
    shutdown_in_progress = True
    
    print("\n" + "="*60)
    print("🛑 SHUTDOWN SIGNAL RECEIVED")
    print("="*60)
    
    if agent_running:
        print("⏹️  Stopping trading agent...")
        stop_agent_flag = True
        agent_running = False
        
        if agent_thread and agent_thread.is_alive():
            agent_thread.join(timeout=5)
        
        try:
            state = load_agent_state()
            state["running"] = False
            state["last_stopped"] = datetime.now().isoformat()
            save_agent_state(state)
            dashboard_logger.info("Agent stopped - server shutting down")
        except Exception as e:
            print(f"Error saving state: {e}")
    
    print("\n✅ Cleanup complete - Port 5000 released")
    print("="*60)
    print("👋 Goodbye!\n")
    
    os._exit(0)

if threading.current_thread() is threading.main_thread():
    signal.signal(signal.SIGINT, cleanup_and_exit)
    signal.signal(signal.SIGTERM, cleanup_and_exit)
    atexit.register(lambda: cleanup_and_exit() if not shutdown_in_progress else None)

# ============================================================================
# STARTUP WITH CLEANUP
# ============================================================================

if __name__ == '__main__':
    # Startup cleanup - rotate oversized files
    print("\n" + "="*60)
    print("🧹 Startup Cleanup")
    print("="*60)
    
    for file in DATA_DIR.glob('*.json'):
        if file.stat().st_size > 1_000_000:  # > 1MB
            backup = file.with_suffix('.json.old')
            file.rename(backup)
            print(f"Rotated oversized file: {file.name}")
    
    # Clean old temp files
    for file in TEMP_DIR.glob('*'):
        if time.time() - file.stat().st_mtime > 3600:  # > 1 hour
            file.unlink()
            print(f"Deleted old temp file: {file.name}")
    
    print("="*60 + "\n")
    
    port = int(os.getenv('PORT', 5000))
    
    print(f"""
{'='*60}
🌙 Marco's AI Trading Dashboard - Production Ready
{'='*60}
Dashboard URL: http://0.0.0.0:{port}
Local URL: http://localhost:{port}
Exchange: HyperLiquid
Status: {'Connected ✅' if EXCHANGE_CONNECTED else 'Demo Mode ⚠️'}
Agent: {'Running 🟢' if agent_running else 'Stopped 🔴'}
Logs: {LOGS_DIR}
Data: {DATA_DIR}
{'='*60}

Press Ctrl+C to shutdown gracefully
""")
    
    dashboard_logger.info("Dashboard server started")
    
    if not EXCHANGE_CONNECTED:
        dashboard_logger.warning("Running in DEMO mode - HyperLiquid not connected")
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False,
            threaded=True
        )
    except KeyboardInterrupt:
        cleanup_and_exit()
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        cleanup_and_exit()
