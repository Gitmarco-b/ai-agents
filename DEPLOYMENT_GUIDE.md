# Trading Dashboard Deployment Guide
**Branch:** `claude-ai-trader-ready-deploy-TDYdX`
**Status:** ✅ DEPLOYMENT READY
**Date:** 2025-12-30

---

## 🎉 All Critical Issues Fixed!

All security vulnerabilities and bugs identified in `DEPLOYMENT_ANALYSIS.md` have been resolved:

✅ **Fixed:** Hardcoded credentials moved to environment variables
✅ **Fixed:** Strong Flask secret key validation
✅ **Fixed:** Circular import between trading_app.py and trading_agent.py
✅ **Fixed:** Broken `add_console_log()` function
✅ **Updated:** .env_example with dashboard credentials

---

## 📋 Required Files for Deployment

This branch contains a complete trading dashboard system. Below are the essential files:

### Core Application
```
trading_app.py              # Main Flask application (PORT: 5000)
requirements.txt            # Python dependencies (Flask, HyperLiquid SDK, AI models)
.env_example               # Environment variable template
```

### Dashboard UI
```
dashboard/
├── static/
│   ├── app.js             # Frontend JavaScript (real-time updates, charts)
│   └── style.css          # Dashboard styling
└── templates/
    ├── index.html         # Main dashboard interface
    └── login.html         # Login page
```

### Trading System
```
src/
├── agents/
│   ├── trading_agent.py   # Main AI trading agent
│   └── swarm_agent.py     # Multi-model consensus voting
├── data/
│   └── ohlcv_collector.py # Market data collection
├── models/                # LLM provider abstraction
│   ├── __init__.py
│   ├── base_model.py
│   ├── model_factory.py
│   ├── claude_model.py
│   ├── openai_model.py
│   ├── deepseek_model.py
│   ├── groq_model.py
│   ├── gemini_model.py
│   ├── ollama_model.py
│   ├── openrouter_model.py
│   └── xai_model.py
├── utils/                 # Shared utilities
│   ├── __init__.py
│   └── logging_utils.py   # Shared logging (prevents circular imports)
├── nice_funcs_hyperliquid.py  # HyperLiquid trading functions
└── config.py              # Trading configuration
```

---

## 🚀 Quick Start Deployment

### 1. Clone Repository
```bash
git clone <repository-url>
cd ai-agents
git checkout claude-ai-trader-ready-deploy-TDYdX
```

### 2. Create Virtual Environment
```bash
# Use existing conda environment (recommended)
conda activate tflow

# OR create new virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy `.env_example` to `.env`:
```bash
cp .env_example .env
```

Edit `.env` and configure:

#### Dashboard Credentials (REQUIRED)
```bash
# Generate strong secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
FLASK_SECRET_KEY=<generated_key_from_above>
DASHBOARD_USERNAME=your_username
DASHBOARD_EMAIL=your_email@example.com
DASHBOARD_PASSWORD=your_secure_password
```

#### HyperLiquid (REQUIRED)
```bash
HYPER_LIQUID_ETH_PRIVATE_KEY=0x...  # Your Ethereum private key
```

#### AI Model Keys (At least ONE required)
```bash
ANTHROPIC_KEY=sk-ant-...     # Claude models
OPENAI_KEY=sk-...            # GPT models
DEEPSEEK_KEY=...             # DeepSeek models
GROQ_API_KEY=...             # Groq (fast inference)
GEMINI_KEY=...               # Google Gemini (default)
```

#### Optional Trading APIs
```bash
BIRDEYE_API_KEY=...          # Solana token data
MOONDEV_API_KEY=...          # Custom signals
COINGECKO_API_KEY=...        # Token metadata
RPC_ENDPOINT=...             # Helius RPC (for Solana)
```

### 5. Run the Application
```bash
python trading_app.py
```

The dashboard will be available at:
- **Local:** http://localhost:5000
- **Network:** http://0.0.0.0:5000

### 6. Login
Navigate to the dashboard URL and login with the credentials you set in `.env`:
- **Username or Email:** (as configured)
- **Password:** (as configured)

---

## 🔧 Configuration

### Trading Settings
Edit `src/config.py` to customize:
- **Exchange:** `EXCHANGE = 'hyperliquid'` (or 'solana', 'aster')
- **Symbols:** `HYPERLIQUID_SYMBOLS = ['SOL', 'BTC', 'ETH']`
- **Leverage:** `HYPERLIQUID_LEVERAGE = 5`
- **Position Size:** `usd_size = 12` (minimum $10 for HyperLiquid)
- **Risk Limits:** `MAX_LOSS_USD`, `MAX_GAIN_USD`, `MINIMUM_BALANCE_USD`
- **AI Model:** `AI_MODEL = "gemini-2.5-flash"` (default)
- **Run Frequency:** `SLEEP_BETWEEN_RUNS_MINUTES = 1`

### AI Model Selection
The system supports multiple AI models:
- **Gemini 2.5 Flash** (default) - Fast, cost-effective
- **Claude 3 Haiku** - Fast reasoning
- **Claude 3 Sonnet** - Balanced performance
- **GPT-4** - OpenAI models
- **DeepSeek** - Cost-effective reasoning
- **Groq** - Ultra-fast inference

Configure in `src/config.py` or use swarm mode for consensus voting.

---

## 📊 Dashboard Features

- **Real-time Account Balance** - Live updates from HyperLiquid
- **Position Monitoring** - View all open positions with PnL
- **Trade History** - Last 20 completed trades
- **Console Logs** - Live agent activity and decisions
- **Balance Chart** - Historical account value
- **Agent Control** - Start/Stop trading agent
- **Session Management** - Secure login/logout

---

## 🔒 Security Best Practices

### Production Deployment
1. ✅ **HTTPS Only** - Use reverse proxy (nginx, Caddy)
2. ✅ **Strong Secret Key** - 64+ character random string
3. ✅ **Secure Passwords** - Complex dashboard password
4. ✅ **Environment Variables** - Never commit `.env` file
5. ✅ **Firewall** - Restrict access to trusted IPs
6. ✅ **Session Timeout** - Configure in Flask settings
7. ✅ **Rate Limiting** - Add to login endpoint
8. ✅ **CORS Restrictions** - Limit to specific domains (edit `trading_app.py`)

### API Key Safety
- Never print API keys in logs
- Never share `.env` file
- Rotate keys if exposed
- Use separate keys for testing/production

---

## 🐳 Docker Deployment (Optional)

Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "trading_app.py"]
```

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  trading-dashboard:
    build: .
    ports:
      - "5000:5000"
    env_file:
      - .env
    volumes:
      - ./src/data:/app/src/data
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d
```

---

## 📈 Production Servers

### Option 1: EasyPanel (Recommended)
1. Create new app from GitHub
2. Select this branch
3. Add environment variables
4. Deploy

### Option 2: Railway
1. Connect GitHub repository
2. Select branch
3. Configure environment variables
4. Deploy

### Option 3: DigitalOcean App Platform
1. Create new app
2. Link repository
3. Configure build command: `pip install -r requirements.txt`
4. Configure run command: `python trading_app.py`
5. Add environment variables

### Option 4: AWS/GCP/Azure
Use Docker deployment method above with your preferred container service.

---

## 🧪 Testing

### Test Locally
```bash
# Start the application
python trading_app.py

# In another terminal, test the health endpoint
curl http://localhost:5000/health
```

### Test Trading Agent (Standalone)
```bash
cd src/agents
python trading_agent.py
```

### Test API Endpoints
```bash
# Health check
curl http://localhost:5000/health

# Login (get session cookie)
curl -X POST http://localhost:5000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username":"your_username","password":"your_password"}'
```

---

## 📝 Monitoring & Logs

### Application Logs
- **Console Output:** Real-time logs in terminal
- **Dashboard Console:** View in dashboard UI
- **Persistent Logs:** `src/data/agent_data/logs/app_YYYY-MM-DD.log`

### Trading Data
- **Trades:** `src/data/trades.json`
- **Balance History:** `src/data/balance_history.json`
- **Agent State:** `src/data/agent_state.json`

### Set Up Monitoring (Optional)
- **Sentry:** Error tracking
- **DataDog:** Performance monitoring
- **Prometheus + Grafana:** Metrics and dashboards

---

## 🛠️ Troubleshooting

### "Module not found" errors
```bash
# Ensure you're in the project root
pwd  # Should show /path/to/ai-agents

# Reinstall dependencies
pip install -r requirements.txt
```

### "FLASK_SECRET_KEY not set" warning
```bash
# Generate secret key
python -c "import secrets; print(secrets.token_hex(32))"

# Add to .env
echo "FLASK_SECRET_KEY=<generated_key>" >> .env
```

### "Dashboard credentials not configured"
```bash
# Add to .env
echo "DASHBOARD_USERNAME=admin" >> .env
echo "DASHBOARD_EMAIL=admin@example.com" >> .env
echo "DASHBOARD_PASSWORD=secure_password" >> .env
```

### HyperLiquid connection issues
```bash
# Verify private key format (should start with 0x)
# Verify key has permissions
# Check network connectivity
```

### Agent won't start
- Check `src/config.py` for valid configuration
- Verify AI model API key is set
- Check console logs for errors

---

## 🎯 Next Steps

1. ✅ Deploy to production server
2. ✅ Configure monitoring and alerts
3. ✅ Set up automated backups of `src/data/`
4. ✅ Test trading strategy with small position sizes
5. ✅ Monitor performance and adjust `src/config.py` as needed
6. ✅ Join Discord for community support

---

## 📚 Additional Resources

- **Main Repository:** [GitHub](https://github.com/your-repo)
- **YouTube Channel:** Moon Dev tutorials
- **Discord Community:** Get support
- **Documentation:** Full agent documentation in `src/agents/README.md`

---

## ⚠️ Disclaimer

This is an experimental AI trading system. Trading cryptocurrencies carries substantial risk of loss. Use at your own risk. Start with small position sizes and never trade with funds you cannot afford to lose.

**Not financial advice. For educational purposes only.**

---

## 📞 Support

- **Issues:** Open GitHub issue
- **Discord:** Moon Dev community
- **Email:** Support contact

---

**Happy Trading! 🚀🌙**
