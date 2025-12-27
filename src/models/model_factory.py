"""
🌙 Moon Dev's Model Factory
Built with love by Moon Dev 🚀

This module manages all available AI models and provides a unified interface.
"""

import os
from typing import Dict, Optional, Type
from termcolor import cprint
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return None
from pathlib import Path
from .base_model import BaseModel

# Try importing optional model adapters; set to None if not available
ClaudeModel = None
GroqModel = None
OpenAIModel = None
GeminiModel = None
DeepSeekModel = None
OllamaModel = None
XAIModel = None
OpenRouterModel = None

try:
    from .claude_model import ClaudeModel
except Exception as e:
    cprint(f"⚠️ claude_model not available: {e}", "yellow")

try:
    from .groq_model import GroqModel
except Exception as e:
    cprint(f"⚠️ groq_model not available: {e}", "yellow")

try:
    from .openai_model import OpenAIModel
except Exception as e:
    cprint(f"⚠️ openai_model not available: {e}", "yellow")

try:
    from .gemini_model import GeminiModel
except Exception as e:
    cprint(f"⚠️ gemini_model not available: {e}", "yellow")

try:
    from .deepseek_model import DeepSeekModel
except Exception as e:
    cprint(f"⚠️ deepseek_model not available: {e}", "yellow")

try:
    from .ollama_model import OllamaModel
except Exception as e:
    cprint(f"⚠️ ollama_model not available: {e}", "yellow")

try:
    from .xai_model import XAIModel
except Exception as e:
    cprint(f"⚠️ xai_model not available: {e}", "yellow")

try:
    from .openrouter_model import OpenRouterModel
except Exception as e:
    cprint(f"⚠️ openrouter_model not available: {e}", "yellow")
import random

class ModelFactory:
    """Factory for creating and managing AI models"""
    
    # Map model types to their implementations
    # Build the implementations mapping only with adapters that are actually imported
    MODEL_IMPLEMENTATIONS = {}
    if ClaudeModel is not None:
        MODEL_IMPLEMENTATIONS["claude"] = ClaudeModel
    if GroqModel is not None:
        MODEL_IMPLEMENTATIONS["groq"] = GroqModel
    if OpenAIModel is not None:
        MODEL_IMPLEMENTATIONS["openai"] = OpenAIModel
    if GeminiModel is not None:
        MODEL_IMPLEMENTATIONS["gemini"] = GeminiModel
    if DeepSeekModel is not None:
        MODEL_IMPLEMENTATIONS["deepseek"] = DeepSeekModel
    if OllamaModel is not None:
        MODEL_IMPLEMENTATIONS["ollama"] = OllamaModel
    if XAIModel is not None:
        MODEL_IMPLEMENTATIONS["xai"] = XAIModel
    if OpenRouterModel is not None:
        MODEL_IMPLEMENTATIONS["openrouter"] = OpenRouterModel
    
    # Default models for each type
    DEFAULT_MODELS = {
        "claude": "claude-3-5-haiku-latest",  # Latest fast Claude model
        "groq": "mixtral-8x7b-32768",        # Fast Mixtral model
        "openai": "gpt-4o",                  # Latest GPT-4 Optimized
        "gemini": "gemini-2.5-flash",        # Fast Gemini 2.5 model
        "deepseek": "deepseek-reasoner",     # Enhanced reasoning model
        "ollama": "llama3.2",                # Meta's Llama 3.2 - balanced performance
        "xai": "grok-4-fast-reasoning",      # xAI's Grok 4 Fast with reasoning (best value: 2M context, cheap!)
        "openrouter": "google/gemini-2.5-flash"  # 🌙 Moon Dev: OpenRouter default - fast & cheap Gemini!
    }
    
    def __init__(self):
        # Load environment variables (noop if python-dotenv not installed)
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / '.env'
        try:
            load_dotenv(dotenv_path=env_path)
        except Exception:
            pass

        self._models: Dict[str, BaseModel] = {}
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize all available models"""
        # Try to initialize each model type silently
        for model_type, key_name in self._get_api_key_mapping().items():
            if api_key := os.getenv(key_name):
                try:
                    if model_type in self.MODEL_IMPLEMENTATIONS:
                        model_class = self.MODEL_IMPLEMENTATIONS[model_type]
                        model_instance = model_class(api_key)

                        if model_instance.is_available():
                            self._models[model_type] = model_instance
                            # Just show the ready message
                            cprint(f"✅ {model_instance.model_name} ready", "green")
                except:
                    pass  # Silently skip failed models

        # Initialize Ollama separately (no API key needed)
        try:
            model_class = self.MODEL_IMPLEMENTATIONS["ollama"]
            model_instance = model_class(model_name=self.DEFAULT_MODELS["ollama"])

            if model_instance.is_available():
                self._models["ollama"] = model_instance
                cprint(f"✅ {model_instance.model_name} ready", "green")
        except:
            pass  # Silently skip if Ollama not available

        if not self._models:
            cprint("⚠️ No AI models available - check API keys in .env", "yellow")
    
    def get_model(self, model_type: str, model_name: Optional[str] = None) -> Optional[BaseModel]:
        """Get a specific model instance"""
        if model_type not in self.MODEL_IMPLEMENTATIONS or model_type not in self._models:
            return None

        model = self._models[model_type]
        if model_name and model.model_name != model_name:
            try:
                # Special handling for Ollama models
                if model_type == "ollama":
                    model = self.MODEL_IMPLEMENTATIONS[model_type](model_name=model_name)
                else:
                    # For API-based models that need a key
                    if api_key := os.getenv(self._get_api_key_mapping()[model_type]):
                        model = self.MODEL_IMPLEMENTATIONS[model_type](api_key, model_name=model_name)
                    else:
                        return None

                self._models[model_type] = model
            except:
                return None

        return model
    
    def _get_api_key_mapping(self) -> Dict[str, str]:
        """Get mapping of model types to their API key environment variable names"""
        return {
            "claude": "ANTHROPIC_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_KEY",
            "gemini": "GEMINI_KEY",  # Re-enabled with Gemini 2.5 models
            "deepseek": "DEEPSEEK_KEY",
            "xai": "GROK_API_KEY",  # Grok/xAI uses GROK_API_KEY
            "openrouter": "OPENROUTER_API_KEY",  # 🌙 Moon Dev: OpenRouter - 200+ models!
            # Ollama doesn't need an API key as it runs locally
        }
    
    @property
    def available_models(self) -> Dict[str, list]:
        """Get all available models and their configurations"""
        return {
            model_type: model.AVAILABLE_MODELS
            for model_type, model in self._models.items()
        }
    
    def is_model_available(self, model_type: str) -> bool:
        """Check if a specific model type is available"""
        return model_type in self._models and self._models[model_type].is_available()

    def generate_response(self, system_prompt, user_content, temperature=0.7, max_tokens=None):
        """Generate a response from the model with no caching"""
        try:
            # Add random nonce to prevent caching
            nonce = f"_{random.randint(1, 1000000)}"
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{user_content}{nonce}"}  # Add nonce to force new response
                ],
                temperature=temperature,
                max_tokens=max_tokens if max_tokens else self.max_tokens
            )
            
            return response.choices[0].message
            
        except Exception as e:
            if "503" in str(e):
                raise e  # Let the retry logic handle 503s
            cprint(f"❌ Model error: {str(e)}", "red")
            return None

# Create a singleton instance
model_factory = ModelFactory() 