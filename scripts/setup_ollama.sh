#!/bin/bash
# ============================================================================
# Moon Dev's Ollama Setup Script
# Installs Ollama and pulls recommended models for AI Trading
# ============================================================================

set -e

echo "🌙 Moon Dev's Ollama Setup Script"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if Ollama is already installed
if command -v ollama &> /dev/null; then
    echo -e "${GREEN}✅ Ollama is already installed${NC}"
    ollama --version
else
    echo -e "${YELLOW}📦 Installing Ollama...${NC}"

    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -fsSL https://ollama.ai/install.sh | sh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ollama
        else
            curl -fsSL https://ollama.ai/install.sh | sh
        fi
    else
        echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
        echo "Please install Ollama manually from: https://ollama.ai"
        exit 1
    fi

    echo -e "${GREEN}✅ Ollama installed successfully${NC}"
fi

echo ""
echo -e "${CYAN}🚀 Starting Ollama server...${NC}"

# Check if Ollama server is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Ollama server is already running${NC}"
else
    echo -e "${YELLOW}Starting Ollama server in background...${NC}"
    ollama serve &
    sleep 3

    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ollama server started${NC}"
    else
        echo -e "${RED}❌ Failed to start Ollama server${NC}"
        echo "Try running 'ollama serve' manually"
        exit 1
    fi
fi

echo ""
echo -e "${CYAN}📥 Pulling recommended models...${NC}"
echo "This may take a while depending on your internet connection."
echo ""

# Recommended models for trading
MODELS=(
    "deepseek-coder:6.7b"    # STEM/coding expert - recommended default
    "llama3.2"               # General purpose, balanced
    "mistral"                # Fast general purpose
)

for model in "${MODELS[@]}"; do
    echo -e "${YELLOW}Pulling $model...${NC}"
    if ollama pull "$model"; then
        echo -e "${GREEN}✅ $model ready${NC}"
    else
        echo -e "${RED}⚠️ Failed to pull $model - skipping${NC}"
    fi
    echo ""
done

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}🎉 Ollama setup complete!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "Available models:"
ollama list
echo ""
echo -e "${CYAN}To use in the trading app:${NC}"
echo "1. Select 'Ollama (Local)' as your AI Provider"
echo "2. Choose 'deepseek-coder' for STEM/math tasks"
echo "3. Or 'llama3.2' for general trading analysis"
echo ""
echo -e "${YELLOW}Note: Keep 'ollama serve' running in the background${NC}"
echo ""
