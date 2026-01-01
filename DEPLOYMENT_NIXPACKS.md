# 🚀 Nixpacks Deployment Guide

This guide covers deploying Moon Dev's AI Trading Agents to platforms that use **nixpacks** (Railway, Render, etc.).

---

## 🔑 Important Notes

### Ollama Not Supported in Nixpacks
**Nixpacks deployments do NOT support local Ollama models** due to platform limitations.

**For Ollama support, use:**
- Docker with `docker-compose up trading-app-ollama` (see `DOCKER_SETUP.md`)
- Local development with `ollama serve`

**For nixpacks deployments, use cloud AI providers:**
- Claude (Anthropic)
- OpenAI (GPT-4)
- DeepSeek API
- Groq
- Gemini
- OllamaFreeAPI (free cloud service)

---

## 🌐 Platform-Specific Guides

### Railway

1. **Create New Project**
   ```bash
   # Install Railway CLI
   npm install -g @railway/cli

   # Login
   railway login

   # Create project
   railway init
   ```

2. **Configure Environment Variables**

   Go to your Railway project → Variables → Add all from `.env_example`:

   ```bash
   # Required
   ANTHROPIC_KEY=your-key-here
   # or
   OPENAI_KEY=your-key-here
   # or
   DEEPSEEK_KEY=your-key-here

   # Trading APIs
   BIRDEYE_API_KEY=your-key
   MOONDEV_API_KEY=your-key

   # Exchange keys (if trading)
   HYPERLIQUID_ETH_PRIVATE_KEY=your-key
   RPC_ENDPOINT=your-rpc-url
   ```

3. **Deploy**
   ```bash
   railway up
   ```

4. **Monitor**
   ```bash
   railway logs
   ```

---

### Render

1. **Create New Web Service**
   - Connect your GitHub repository
   - Select branch: `main` or your working branch

2. **Configure Build Settings**
   - **Build Command:** (leave empty, nixpacks handles it)
   - **Start Command:** `python trading_app.py`
   - **Environment:** Python 3

3. **Add Environment Variables**

   Same as Railway - add all required keys from `.env_example`

4. **Deploy**

   Render will auto-deploy on git push

---

### Heroku

1. **Create App**
   ```bash
   heroku create your-app-name
   ```

2. **Set Environment Variables**
   ```bash
   heroku config:set ANTHROPIC_KEY=your-key
   heroku config:set BIRDEYE_API_KEY=your-key
   # ... etc
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

4. **View Logs**
   ```bash
   heroku logs --tail
   ```

---

## ⚙️ Configuration

### AI Model Selection

Edit `src/config.py` to use cloud AI providers:

```python
# Use cloud providers only (no Ollama)
AI_MODEL_TYPE = 'claude'              # or 'openai', 'deepseek', 'groq'
AI_MODEL = "claude-sonnet-4-5-20250929"

# Alternative free option (no API key required)
AI_MODEL_TYPE = 'ollamafreeapi'       # FREE cloud service
AI_MODEL = "deepseek-v3.1:671b"
```

### Port Configuration

Most platforms set the `PORT` environment variable automatically. The app will detect this.

If needed, set manually:
```bash
PORT=5000  # or whatever port your platform assigns
```

---

## 🐛 Troubleshooting

### Build Fails with "numpy" Error

**Symptom:** Build fails during pip install with numpy compilation errors

**Solution:** The requirements.txt has been fixed to use compatible versions:
- numpy==1.26.4 (compatible with Python 3.10)
- numba==0.60.0
- pandas==2.2.2

If still failing, the platform may need additional system packages.

### Build Fails with "TA-Lib" Error

**Symptom:** `TA-Lib-Precompiled` fails to install

**Solution 1 - Remove TA-Lib (if not using backtesting):**

Edit `requirements.txt` and comment out:
```python
# TA-Lib-Precompiled==0.4.25  # Only needed for backtesting
```

**Solution 2 - Use platform with TA-Lib support:**

Add to `nixpacks.toml`:
```toml
[phases.setup]
nixPkgs = [
  "python310",
  "gcc",
  "pkg-config",
  "zlib",
  "ta-lib"  # Add TA-Lib system package
]
```

### Ollama Model Selected But Not Available

**Symptom:** App crashes with "Could not connect to Ollama API"

**Solution:** Edit `src/config.py`:
```python
# Change from:
AI_MODEL_TYPE = 'ollama'  # ❌ Not supported in nixpacks

# To:
AI_MODEL_TYPE = 'claude'  # ✅ Cloud provider
# or
AI_MODEL_TYPE = 'ollamafreeapi'  # ✅ Free cloud option
```

### Environment Variables Not Loading

**Symptom:** App starts but shows "No AI models available"

**Solution:**
1. Check platform environment variable settings
2. Ensure keys are set correctly (no quotes needed)
3. Restart the service after adding variables

---

## 📊 Resource Requirements

### Minimum
- **RAM:** 512MB (1GB recommended)
- **CPU:** 1 core (2 cores recommended)
- **Disk:** 1GB

### Recommended (for production)
- **RAM:** 2GB
- **CPU:** 2 cores
- **Disk:** 2GB

### Scaling
Most platforms auto-scale based on demand. Configure in platform settings.

---

## 🔒 Security Best Practices

1. **Never commit API keys** to git
   - Use environment variables
   - Add `.env` to `.gitignore` (already done)

2. **Use platform secrets/environment variables**
   - Railway: Project → Variables
   - Render: Environment → Environment Variables
   - Heroku: Settings → Config Vars

3. **Limit IP access** (if available on platform)
   - Configure firewall rules
   - Use platform's built-in security features

4. **Enable HTTPS**
   - Most platforms provide this automatically
   - Verify SSL certificate is active

---

## 💰 Cost Estimates

### Railway (Hobby Plan)
- $5/month base
- $0.000231/GB-hour for resources
- Free $5 credit monthly
- **Estimate:** Free tier may be sufficient for development

### Render (Free Tier)
- Free for web services
- Auto-sleeps after 15 min inactivity
- **Estimate:** Free for low-traffic development

### Heroku (Eco Plan)
- $5/month per dyno
- No auto-sleep
- **Estimate:** $5/month minimum

**Note:** AI API costs are separate and vary by provider.

---

## 📝 Files Used by Nixpacks

- `nixpacks.toml` - Build configuration
- `requirements.txt` - Python dependencies
- `runtime.txt` - Python version specification
- `Procfile` - Process definition (start command)
- `.nixpacks` - Provider hint file

---

## 🚫 What's NOT Supported in Nixpacks

1. **Local Ollama models** - Use Docker instead
2. **GPU acceleration** - Use Docker with NVIDIA runtime
3. **Large model downloads** during build - Use cloud providers
4. **System-level modifications** - Limited to nixPkgs

---

## ✅ Recommended Setup for Production

1. **Platform:** Railway or Render (easiest nixpacks support)
2. **AI Provider:** Claude or DeepSeek API (reliable, affordable)
3. **Configuration:**
   ```python
   AI_MODEL_TYPE = 'deepseek'
   AI_MODEL = 'deepseek-chat'
   AI_TEMPERATURE = 0.6
   AI_MAX_TOKENS = 8000
   ```
4. **Monitoring:** Use platform's built-in logs and metrics
5. **Backups:** Enable automatic database backups (if using)

---

## 🆘 Getting Help

- Check platform-specific documentation
- Review logs: `railway logs` or platform dashboard
- Test locally first: `python trading_app.py`
- See main README.md for general troubleshooting

---

## 🌙 Moon Dev

Built with love by Moon Dev 🚀

For issues or questions, see the [main repository](https://github.com/karmaworks-dev/ai-agents).
