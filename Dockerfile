# Use the specific Python version used during development [1]
FROM python:3.10-slim

# Install system dependencies
# Fixed: Comments moved outside the RUN command to prevent syntax errors
# Added: curl for Ollama installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    llvm \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Optimization: Keep python quiet and unbuffered for real-time dashboard logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Optimization: Install dependencies with no cache to save disk space
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full repository
COPY . .

# Critical: Create the exact directory the code expects for persistent data [2, 3]
# Also create temp_data for agent analysis cycles [4]
RUN mkdir -p /app/src/data /app/temp_data

# ===== OLLAMA INSTALLATION (Optional - Remove if not using local models) =====
# Note: Ollama requires ~4GB disk space and GPU is recommended for large models
# Install Ollama for local AI model support
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Create startup script for Ollama
RUN echo '#!/bin/bash\n\
echo "🌙 Starting Ollama server..."\n\
ollama serve &\n\
OLLAMA_PID=$!\n\
echo "⏳ Waiting for Ollama to be ready..."\n\
sleep 5\n\
\n\
# Pull recommended models for trading (only if not already installed)\n\
echo "📦 Pulling DeepSeek V3.1 671B model (this may take several minutes)..."\n\
ollama pull deepseek-v3.1:671b || echo "⚠️  Failed to pull deepseek-v3.1:671b"\n\
\n\
echo "📦 Pulling lightweight fallback model (llama3.2)..."\n\
ollama pull llama3.2 || echo "⚠️  Failed to pull llama3.2"\n\
\n\
echo "✅ Ollama setup complete!"\n\
ollama list\n\
\n\
# Start the trading app\n\
echo "🚀 Starting trading dashboard..."\n\
exec python trading_app.py\n\
' > /app/start.sh && chmod +x /app/start.sh

# Expose the dashboard port (default 5000) [5, 6]
EXPOSE 5000

# Expose Ollama API port (for debugging/external access)
EXPOSE 11434

# Start with our custom startup script
CMD ["/app/start.sh"]
