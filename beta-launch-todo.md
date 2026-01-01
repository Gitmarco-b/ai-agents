# Beta Launch TODO

This document tracks tasks for the AI Trading Dashboard beta launch.

## Completed

### AI Model Integration Fixes
- [x] **A1**: Fixed `/api/ai-models` to include `ollamafreeapi` provider
- [x] **A2**: Added Ollama auto-install script (`scripts/setup_ollama.sh`)
- [x] Fixed xAI environment variable mismatch (`XAI_KEY`)
- [x] Fixed `self.max_tokens` undefined in openrouter_model.py and groq_model.py
- [x] Removed prompt corruption from base_model.py (nonce/timestamp injection)
- [x] Standardized Claude model names with date suffixes
- [x] Changed Groq default to production model (`mixtral-8x7b-32768`)
- [x] Created OllamaFreeAPIModel for free cloud AI access

### Tier System
- [x] **B1**: Designed tier data model (`src/utils/tier_manager.py`)
  - Based (Free): 5 tokens, 5min cycle, Single AI, Ollama only
  - Trader ($5/mo): 10 tokens, 5min cycle, BYOK, All providers
  - Pro ($20/mo): Unlimited, Any cycle, Swarm mode, 6 AI models
- [x] **B2**: Created tier selection UI in Account modal (PLAN tab)
- [x] **B3**: Implemented tier enforcement with UI locking
  - Swarm mode toggle locked for non-Pro users
  - BYOK section shows warning for Based tier
  - Token limit badges displayed
  - Provider dropdown disables non-free options for Based tier
- [x] **B4**: Added tier upgrade prompts when saving settings that exceed limits

### Exchange Configuration
- [x] **C1**: Frontend shows HYPERLIQUID only (hardcoded)
- [x] **C2**: Backend supports future exchanges via `EXCHANGE` constant

## Pending

### Testing
- [ ] **A3**: Test full flow validation
  - [ ] Test OllamaFreeAPI with deepseek-coder model
  - [ ] Test BYOK with OpenAI/Claude/Gemini
  - [ ] Test tier switching for admin user (KW-Trader)
  - [ ] Test tier enforcement blocking for non-admin users
  - [ ] Test swarm mode with multiple AI models

### Pre-Launch
- [ ] Add payment integration for tier upgrades (Stripe?)
- [ ] Add email verification for new accounts
- [ ] Add password reset functionality
- [ ] Create user onboarding flow
- [ ] Add analytics/telemetry for monitoring

### Documentation
- [ ] Update README with tier system info
- [ ] Create user guide for BYOK setup
- [ ] Document rate limits per provider
- [ ] Create troubleshooting guide

### Future Features
- [ ] Add more exchanges (Binance, Coinbase, etc.)
- [ ] Add backtesting integration
- [ ] Add strategy marketplace
- [ ] Add mobile responsive improvements
- [ ] Add dark/light theme toggle

## Admin Users (Full Tier Access)
For testing purposes, these users can switch between all tiers:
- KW-Trader
- admin
- moondev

## Rate Limits by Provider

| Provider | Requests | Notes |
|----------|----------|-------|
| OllamaFreeAPI | 100/hour | Free, no API key needed |
| Local Ollama | Unlimited | Requires local install |
| Gemini | 10-15 RPM | Free tier available |
| DeepSeek | No hard limits | Pay per token |
| Groq | ~14,400/day | Fast inference |
| OpenAI | Varies by tier | Pay per token |
| Anthropic | Varies by tier | Pay per token |

## Tech Stack
- Backend: Flask (Python)
- Frontend: Vanilla JS + CSS
- AI: Multi-provider via ModelFactory
- Exchange: HyperLiquid API
- Auth: Session-based with Flask-Login
