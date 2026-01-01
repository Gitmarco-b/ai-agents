# 🐳 Docker Setup Guide

This guide explains how to run the Moon Dev AI Trading Agents using Docker with or without local Ollama models.

---

## 📋 Prerequisites

- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (usually included with Docker Desktop)
- `.env` file configured with your API keys (see `.env_example`)

---

## 🚀 Quick Start

### Option 1: With Ollama (Local AI Models)

Run the trading app with local Ollama models for free AI inference:

```bash
# Build and start
docker-compose up --build trading-app-ollama

# Or run in background
docker-compose up -d trading-app-ollama
```

**First-time startup will:**
1. Install Ollama
2. Pull `deepseek-v3.1:671b` (recommended for trading)
3. Pull `llama3.2` (lightweight fallback)
4. Start the trading dashboard

**Note:** First build may take 10-30 minutes depending on your internet speed.

---

### Option 2: Without Ollama (Cloud AI Only)

Run the trading app using only cloud AI providers (Claude, GPT-4, DeepSeek API, etc.):

```bash
# Build and start
docker-compose up --build trading-app

# Or run in background
docker-compose up -d trading-app
```

**This version:**
- Smaller image size (~1GB vs ~8GB)
- Faster startup (~30 seconds)
- Lower memory usage (1-2GB vs 4-8GB)
- Requires cloud AI API keys

---

## 🔧 Configuration

### Using Ollama Models

Edit `src/config.py`:

```python
AI_MODEL_TYPE = 'ollama'              # Use local Ollama
AI_MODEL = "deepseek-v3.1:671b"       # Model to use
```

### Using Cloud AI Models

Edit `src/config.py`:

```python
AI_MODEL_TYPE = 'claude'              # or 'openai', 'deepseek', 'groq', etc.
AI_MODEL = "claude-sonnet-4-5-20250929"
```

Ensure you have the required API key in `.env`:
```bash
ANTHROPIC_KEY=your-key-here
# or
OPENAI_KEY=your-key-here
# or
DEEPSEEK_KEY=your-key-here
```

---

## 📊 Accessing the Dashboard

Once running, access the dashboard at:

**http://localhost:5000**

---

## 🛠️ Common Commands

### View Logs
```bash
# Ollama version
docker-compose logs -f trading-app-ollama

# No-Ollama version
docker-compose logs -f trading-app
```

### Stop Containers
```bash
docker-compose down
```

### Restart
```bash
# Restart without rebuilding
docker-compose restart trading-app-ollama

# Rebuild and restart
docker-compose up --build trading-app-ollama
```

### Access Container Shell
```bash
# Ollama version
docker-compose exec trading-app-ollama bash

# Check Ollama status inside container
docker-compose exec trading-app-ollama ollama list
```

---

## 💾 Data Persistence

Data is persisted in volumes:

- `./src/data` - Agent outputs, analysis results
- `./temp_data` - Temporary analysis files
- `ollama-models` - Downloaded Ollama models (Ollama version only)

Models are cached in the `ollama-models` volume, so they won't be re-downloaded on restart.

---

## 🎯 Resource Requirements

### With Ollama (trading-app-ollama)
- **Disk Space:** ~8-15GB (models are large)
- **RAM:** 4-8GB minimum (8GB+ recommended for large models)
- **CPU:** 4+ cores recommended
- **GPU:** Optional but highly recommended for faster inference

### Without Ollama (trading-app)
- **Disk Space:** ~1-2GB
- **RAM:** 1-2GB
- **CPU:** 2+ cores
- **GPU:** Not needed

---

## 🔥 GPU Support (Optional)

To use GPU acceleration with Ollama:

1. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

2. Uncomment GPU settings in `docker-compose.yml`:
```yaml
runtime: nvidia
environment:
  - NVIDIA_VISIBLE_DEVICES=all
```

3. Rebuild and start:
```bash
docker-compose up --build trading-app-ollama
```

---

## 🐛 Troubleshooting

### Ollama models not downloading

**Symptom:** Container starts but Ollama models fail to pull

**Solution:**
```bash
# Access container
docker-compose exec trading-app-ollama bash

# Manually pull models
ollama pull deepseek-v3.1:671b
ollama pull llama3.2

# Check status
ollama list
```

### Port already in use

**Symptom:** `Error: bind: address already in use`

**Solution:**
```bash
# Change ports in docker-compose.yml
ports:
  - "5001:5000"  # Use port 5001 instead
```

### Out of memory errors

**Symptom:** Container crashes with OOM errors

**Solution:**
1. Increase Docker memory limit (Docker Desktop → Settings → Resources)
2. Use smaller models: `llama3.2` instead of `deepseek-v3.1:671b`
3. Or use the no-Ollama version: `docker-compose up trading-app`

### Models deleted after restart

**Solution:**
Ensure the `ollama-models` volume persists:
```bash
# Check volumes
docker volume ls

# Should see: ai-agents_ollama-models

# If missing, recreate:
docker-compose down -v
docker-compose up --build trading-app-ollama
```

---

## 📝 Dockerfile Options

**`Dockerfile`** - Full version with Ollama
- Installs Ollama during build
- Auto-pulls recommended models on startup
- Larger image size (~8GB)

**`Dockerfile.no-ollama`** - Lightweight version
- No Ollama installation
- Cloud AI only
- Smaller image size (~1GB)

---

## 🔐 Security Notes

1. **Never commit `.env` with real API keys**
2. Bind to `127.0.0.1:5000` for local-only access
3. Use environment variables for secrets
4. Review firewall rules if exposing ports

---

## 📚 Additional Resources

- [Ollama Documentation](https://github.com/ollama/ollama/blob/main/docs/README.md)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [Project README](README.md)

---

## 🌙 Moon Dev

Built with love by Moon Dev 🚀

For issues or questions, see the [main repository](https://github.com/karmaworks-dev/ai-agents).
