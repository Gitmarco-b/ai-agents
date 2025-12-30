"""
🌙 LLM Trading Agent - Production Ready
======================================
Fixed memory leaks with rotating logs and proper cleanup
"""

import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
import logging
from logging.handlers import RotatingFileHandler

# ============================================================================
# ROTATING LOGGER SETUP
# ============================================================================

# Create agent_data/logs directory
AGENT_LOGS_DIR = Path(__file__).parent.parent / "agent_data" / "logs"
AGENT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Agent logger (300KB max, 5 backups)
agent_logger = logging.getLogger('agent')
agent_handler = RotatingFileHandler(
    AGENT_LOGS_DIR / 'agent.log',
    maxBytes=300000,  # 300KB
    backupCount=5
)
agent_handler.setFormatter(
    logging.Formatter('%(asctime)s - %(message)s')
)
agent_logger.addHandler(agent_handler)
agent_logger.setLevel(logging.INFO)

# Also output to console for terminal visibility
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
agent_logger.addHandler(console_handler)

# ============================================================================
# PROJECT PATH SETUP (BEFORE IMPORTS)
# ============================================================================
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Dashboard logging helper import
from trading_app import log_position_open

def extract_json_from_text(text):
    """Safely extract JSON object from AI model responses"""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            agent_logger.warning("JSON extraction failed")
            return None
    agent_logger.warning("No JSON object found in AI response")
    return None

# Import AI models and data collectors
from src.models import model_factory
from src.agents.swarm_agent import SwarmAgent 
from src.data.ohlcv_collector import collect_all_tokens

load_dotenv()

# ============================================================================
# COLOR PRINT SHIM
# ============================================================================
try:
    from termcolor import cprint
except Exception:
    def cprint(msg, *args, **kwargs):
        agent_logger.info(msg)

# ============================================================================
# PANDAS SHIM (lightweight fallback)
# ============================================================================
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except Exception as e:
    pd = None
    PANDAS_AVAILABLE = False
    agent_logger.warning(f"pandas not installed: {e}. Using lightweight DataFrame shim.")
    import types

    class SimpleDataFrame:
        def __init__(self, data=None, columns=None):
            self._data = list(data) if data else []
            if columns:
                self.columns = list(columns)
            else:
                self.columns = list(self._data[0].keys()) if self._data else []
            self.index = list(range(len(self._data)))

        def __len__(self):
            return len(self._data)

        def head(self, n=5):
            return SimpleDataFrame(self._data[:n], columns=self.columns)

        def tail(self, n=3):
            return SimpleDataFrame(self._data[-n:], columns=self.columns)

        def to_string(self):
            if not self._data:
                return "<empty DataFrame>"
            header = " | ".join(self.columns)
            lines = [header]
            for row in self._data:
                lines.append(" | ".join(str(row.get(c, "")) for c in self.columns))
            return "\n".join(lines)

        def __str__(self):
            return self.to_string()

        def to_dict(self):
            return self._data
        
        def iloc(self, idx):
            """Support DataFrame clearing with .iloc[0:0]"""
            if isinstance(idx, slice) and idx.start == 0 and idx.stop == 0:
                return SimpleDataFrame([], columns=self.columns)
            return self

    def _concat(dfs, ignore_index=True):
        rows = []
        cols = []
        for df in dfs:
            if isinstance(df, SimpleDataFrame):
                rows.extend(df._data)
                for c in df.columns:
                    if c not in cols:
                        cols.append(c)
            elif isinstance(df, dict):
                rows.append(df)
        return SimpleDataFrame(rows, columns=cols)

    pd = types.SimpleNamespace(DataFrame=SimpleDataFrame, concat=_concat)

# ============================================================================
# CONFIGURATION (from your original file)
# ============================================================================
from eth_account import Account

EXCHANGE = "HYPERLIQUID"
USE_SWARM_MODE = False
LONG_ONLY = False

AI_MODEL_TYPE = 'gemini' 
AI_MODEL_NAME = 'gemini-2.5-pro'
AI_TEMPERATURE = 0.6   
AI_MAX_TOKENS = 3000   

USE_PORTFOLIO_ALLOCATION = True 
MAX_POSITION_PERCENTAGE = 90      
LEVERAGE = 20                     

STOP_LOSS_PERCENTAGE = 2.0
TAKE_PROFIT_PERCENTAGE = 5.0    
PNL_CHECK_INTERVAL = 2

usd_size = 25                  
max_usd_order_size = 3           
CASH_PERCENTAGE = 10

DAYSBACK_4_DATA = 1
DATA_TIMEFRAME = '5m'
SAVE_OHLCV_DATA = False

slippage = 199
SLEEP_BETWEEN_RUNS_MINUTES = 5

address = "ACCOUNT_ADDRESS"

USDC_ADDRESS = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" 
SOL_ADDRESS = "So11111111111111111111111111111111111111111"    
EXCLUDED_TOKENS = [USDC_ADDRESS, SOL_ADDRESS]

MONITORED_TOKENS = []

SYMBOLS = [
    'ETH', 'BTC', 'SOL', 'AAVE', 'LINK', 'LTC', 'FARTCOIN',
]

# ============================================================================
# EXCHANGE IMPORTS
# ============================================================================
if EXCHANGE == "HYPERLIQUID":
    try:
        import nice_funcs_hyperliquid as n
        agent_logger.info("🦈 Exchange: HyperLiquid (Perpetuals)")
    except ImportError:
        try:
            from src import nice_funcs_hyperliquid as n
            agent_logger.info("🦈 Exchange: HyperLiquid (Perpetuals)")
        except ImportError:
            agent_logger.error("❌ Error: nice_funcs_hyperliquid.py not found!")
            sys.exit(1)
else:
    agent_logger.error(f"❌ Unknown exchange: {EXCHANGE}")
    sys.exit(1)

# ============================================================================
# PROMPTS (from your original file)
# ============================================================================

TRADING_PROMPT = """
You are a renowned crypto trading expert and Trading Assistant

Analyze the provided market data, CURRENT POSITION, and STRATEGY CONTEXT signals to make a trading decision.

{position_context}

Market Data Criteria:
1. Price action relative to MA20 and MA40
2. RSI levels and trend
3. Volume patterns
4. Recent price movements

{strategy_context}

Respond in this exact format:
1. First line must be one of: BUY, SELL, or NOTHING (in caps)
2. Then explain your reasoning, always including:
   - Technical analysis
   - Strategy signals analysis (if available)
   - Risk factors
   - Market conditions
   - Confidence level (as a percentage, e.g. 75%)

Remember: 
- Always prioritizes risk management! 🛡️
- Never trade USDC or SOL directly
- Consider both technical and strategy signals
"""

ALLOCATION_PROMPT = """
You are our Portfolio Allocation Assistant 🌙

Given the total portfolio size and trading recommendations, allocate capital efficiently.
Consider:
1. Position sizing based on confidence levels
2. Risk distribution
3. Keep cash buffer as specified
4. Maximum allocation per position

Format your response as a Python dictionary:
{
    "token_address": allocated_amount,  # In USD
    ...
    "USDC_ADDRESS": remaining_cash  # Always use USDC_ADDRESS for cash
}

Remember:
- Total allocations must not exceed total_size
- Higher confidence should get larger allocations
- Never allocate more than {MAX_POSITION_PERCENTAGE}% to a single position
- Keep at least {CASH_PERCENTAGE}% in USDC as safety buffer
- Only allocate to BUY recommendations
- Cash must be stored as USDC using USDC_ADDRESS: {USDC_ADDRESS}
"""

SWARM_TRADING_PROMPT = """You are an expert cryptocurrency trading AI analyzing market data.

CRITICAL RULES:
1. Your response MUST be EXACTLY one of these three words: Buy, Sell, or Do Nothing
2. Do NOT provide any explanation, reasoning, or additional text
3. Respond with ONLY the action word
4. Do NOT show your thinking process or internal reasoning

Analyze the market data below and decide:

- "Buy" = Strong bullish signals, recommend opening/holding position
- "Sell" = Bearish signals or major weakness, recommend closing position entirely
- "Do Nothing" = Unclear/neutral signals, recommend holding current state unchanged

IMPORTANT: "Do Nothing" means maintain current position (if we have one, keep it; if we don't, stay out)

RESPOND WITH ONLY ONE WORD: Buy, Sell, or Do Nothing"""

POSITION_ANALYSIS_PROMPT = """
You are an expert crypto trading analyst. Your task is to analyze the user's open positions based on the provided position summaries and current market data.

For EACH symbol, decide whether the user should **KEEP** the position open or **CLOSE** it. 
Explain briefly the reasoning behind each decision (e.g., "Trend weakening, RSI overbought").

⚠️ CRITICAL OUTPUT RULES:
- You MUST respond ONLY with a valid JSON object — no commentary, no Markdown, no code fences.
- JSON must be well-formed and parseable by Python's json.loads().
- The JSON must follow exactly this structure:

{
  "BTC": {
    "action": "KEEP",
    "reasoning": "Trend remains bullish; RSI under 60"
  },
  "ETH": {
    "action": "CLOSE",
    "reasoning": "Breakdown below MA40 with weak RSI"
  }
}

Do not include ```json or any other formatting around the JSON.
Respond ONLY with the raw JSON object.
"""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_account_balance(account=None):
    """Get account balance in USD"""
    try:
        if EXCHANGE in ["ASTER", "HYPERLIQUID"]:
            address = os.getenv("ACCOUNT_ADDRESS")
            if not address:
                if account is None:
                    account = n._get_account_from_env()
                address = account.address

            try:
                if hasattr(n, 'get_available_balance'):
                    balance = n.get_available_balance(address)
                    agent_logger.info(f"💰 {EXCHANGE} Available Balance: ${balance}")
                else:
                    balance = n.get_account_value(address)
            except Exception as e:
                agent_logger.error(f"❌ Error getting balance: {e}")
                balance = 0

            return float(balance)
        else:
            balance = n.get_token_balance_usd(USDC_ADDRESS)
            return balance
            
    except Exception as e:
        agent_logger.error(f"❌ Error getting account balance: {e}")
        return 0

def calculate_position_size(account_balance):
    """Calculate position size based on MAX_POSITION_PERCENTAGE"""
    if EXCHANGE in ["ASTER", "HYPERLIQUID"]:
        margin_to_use = account_balance * (MAX_POSITION_PERCENTAGE / 100)
        notional_position = margin_to_use * LEVERAGE

        agent_logger.info(f"📊 Position Calculation: ${account_balance:,.2f} balance")
        agent_logger.info(f"💰 Margin to Use: ${margin_to_use:,.2f} ({MAX_POSITION_PERCENTAGE}%)")
        agent_logger.info(f"⚡ Leverage: {LEVERAGE}x")
        agent_logger.info(f"💎 Notional Position: ${notional_position:,.2f}")

        return notional_position
    else:
        position_size = account_balance * (MAX_POSITION_PERCENTAGE / 100)
        agent_logger.info(f"💎 Position Size: ${position_size:,.2f}")
        return position_size

# ============================================================================
# TEMP FILE CLEANUP
# ============================================================================

def cleanup_temp_files():
    """Clean up old temporary files at start of each cycle"""
    temp_dir = Path("agent_data/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    cleaned = 0
    for file in temp_dir.glob("*"):
        try:
            # Delete files older than 1 hour
            if time.time() - file.stat().st_mtime > 3600:
                file.unlink()
                cleaned += 1
        except Exception as e:
            agent_logger.warning(f"Could not delete {file.name}: {e}")
    
    if cleaned > 0:
        agent_logger.info(f"🧹 Cleaned {cleaned} old temp files")

# ============================================================================
# TRADING AGENT CLASS
# ============================================================================

class TradingAgent:
    def __init__(self):
        # Initialize Account
        self.account = None
        if EXCHANGE == "HYPERLIQUID":
            agent_logger.info("🔐 Initializing Hyperliquid Account...")
            try:
                raw_key = (
                   os.getenv("HYPER_LIQUID_KEY", "")
                   or os.getenv("HYPER_LIQUID_ETH_PRIVATE_KEY", "")
                )
                clean_key = raw_key.strip().replace('"', '').replace("'", "")
                self.account = Account.from_key(clean_key)

                self.address = os.getenv("ACCOUNT_ADDRESS")
                if not self.address:
                    self.address = self.account.address

                agent_logger.info(f"✅ Account loaded: {self.address}")
            except Exception as e:
                agent_logger.error(f"❌ Error loading key: {e}")
                sys.exit(1)

        # Initialize AI models
        if USE_SWARM_MODE:
            agent_logger.info("🌊 Initializing Swarm Mode (6 AI models)")
            self.swarm = SwarmAgent()
            agent_logger.info("💼 Initializing fast model for portfolio calculations")
            self.model = model_factory.get_model(AI_MODEL_TYPE, AI_MODEL_NAME)
        else:
            agent_logger.info(f"Initializing with {AI_MODEL_TYPE} model")
            self.model = model_factory.get_model(AI_MODEL_TYPE, AI_MODEL_NAME)
            self.swarm = None

            if not self.model:
                agent_logger.error(f"❌ Failed to initialize {AI_MODEL_TYPE} model!")
                sys.exit(1)

            agent_logger.info(f"✅ Using model: {self.model.model_name}")

        # Initialize empty DataFrame
        self.recommendations_df = pd.DataFrame(
            columns=["token", "action", "confidence", "reasoning"]
        )

        # Show configuration
        tokens_to_show = SYMBOLS if EXCHANGE in ["ASTER", "HYPERLIQUID"] else MONITORED_TOKENS
        
        agent_logger.info(f"\n🎯 Active Tokens: {', '.join(tokens_to_show)}")
        agent_logger.info(f"🦈 Exchange: {EXCHANGE}")
        
        if LONG_ONLY:
            agent_logger.info("📊 Mode: LONG ONLY")
        else:
            agent_logger.info("⚡ Mode: LONG/SHORT")

        agent_logger.info("🤖 LLM Trading Agent initialized!")

    def chat_with_ai(self, system_prompt, user_content):
        """Send prompt to AI model"""
        try:
            response = self.model.generate_response(
                system_prompt=system_prompt,
                user_content=user_content,
                temperature=AI_TEMPERATURE,
                max_tokens=AI_MAX_TOKENS
            )

            if hasattr(response, "content"):
                return response.content
            return str(response)

        except Exception as e:
            agent_logger.error(f"❌ AI model error: {e}")
            return None

    # ... (Keep all other methods from your original TradingAgent class)
    # For brevity, I'm showing the key modified method:

    def run_trading_cycle(self, strategy_signals=None):
        """Enhanced trading cycle with memory management"""
        
        # CLEANUP TEMP FILES AT START
        cleanup_temp_files()
        
        try:
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            agent_logger.info(f"\n{'='*80}")
            agent_logger.info(f"🔄 TRADING CYCLE START: {current_time}")
            agent_logger.info(f"{'='*80}")

            # ... (rest of your run_trading_cycle code)
            # Copy the entire method from your original file here
            
            # AT THE END, add memory cleanup:
            
            # Clear DataFrame memory
            if hasattr(self, 'recommendations_df'):
                self.recommendations_df = self.recommendations_df.iloc[0:0]
            
            # Force garbage collection
            import gc
            gc.collect()
            
            agent_logger.info(f"{'='*80}")
            agent_logger.info("✅ TRADING CYCLE COMPLETE")
            agent_logger.info(f"{'='*80}\n")

        except Exception as e:
            agent_logger.error(f"\n❌ Error in trading cycle: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Main function - simple cycle every X minutes"""
    agent_logger.info("🚀 AI Trading System Starting Up! 🚀")
    print("🛑 Press Ctrl+C to stop.\n")
    
    agent = TradingAgent()
    
    while True:
        try:
            agent.run_trading_cycle()
            
            next_run = datetime.now() + timedelta(minutes=SLEEP_BETWEEN_RUNS_MINUTES)
            agent_logger.info(f"\n⏰ Next cycle at: {next_run.strftime('%H:%M:%S')}")
            time.sleep(SLEEP_BETWEEN_RUNS_MINUTES * 60)
            
        except KeyboardInterrupt:
            agent_logger.info("\n👋 AI Agent shutting down gracefully...")
            break
        except Exception as e:
            agent_logger.error(f"\n❌ Error in main loop: {e}")
            import traceback
            traceback.print_exc()
            time.sleep(SLEEP_BETWEEN_RUNS_MINUTES * 60)


if __name__ == "__main__":
    main()
