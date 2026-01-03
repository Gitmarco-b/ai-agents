"""
🌙 Moon Dev's OpenRouter Model Implementation
Built with love by Moon Dev 🚀

OpenRouter provides unified access to all major AI models through a single API.
"""

from openai import OpenAI
from termcolor import cprint
from .base_model import BaseModel, ModelResponse
import time

class OpenRouterModel(BaseModel):
    """Implementation for OpenRouter's model routing"""

    AVAILABLE_MODELS = {
        # ============================================================================
        # 🆓 FREE MODELS (No cost - recommended for testing)
        # ============================================================================
        "deepseek/deepseek-chat-v3.1:free": {
            "description": "(FREE) DeepSeek V3.1 - 671B hybrid reasoning - 128k context",
            "input_price": "FREE",
            "output_price": "FREE"
        },
        "google/gemini-2.0-flash-exp:free": {
            "description": "(FREE) Gemini 2.0 Flash - Fast multimodal - 1M context",
            "input_price": "FREE",
            "output_price": "FREE"
        },
        "nvidia/nemotron-nano-9b-v2:free": {
            "description": "(FREE) Nemotron Nano 9B - Compact reasoning model - 32k context",
            "input_price": "FREE",
            "output_price": "FREE"
        },

        # ============================================================================
        # 🚀 XAI GROK MODELS
        # ============================================================================
        "x-ai/grok-4.1-fast": {
            "description": "Grok 4.1 Fast - Best agentic tool calling - 2M context",
            "input_price": "$0.20/1M tokens",
            "output_price": "$0.50/1M tokens"
        },

        # ============================================================================
        # 🧮 DEEPSEEK MODELS
        # ============================================================================
        "deepseek/deepseek-chat-v3.1": {
            "description": "DeepSeek V3.1 - 671B hybrid reasoning - 128k context",
            "input_price": "$0.20/1M tokens",
            "output_price": "$0.80/1M tokens"
        },
        "deepseek/deepseek-reasoner": {
            "description": "DeepSeek Reasoner - Advanced reasoning model - 64k context",
            "input_price": "$0.55/1M tokens",
            "output_price": "$2.19/1M tokens"
        },

        # ============================================================================
        # 🔮 QWEN MODELS
        # ============================================================================
        "qwen/qwen3-max": {
            "description": "Qwen 3 Max - Flagship model - 256k context",
            "input_price": "$1.20/1M tokens",
            "output_price": "$6.00/1M tokens"
        },
        "qwen/qwen-plus": {
            "description": "Qwen Plus - Balanced performance - 131k context",
            "input_price": "$0.40/1M tokens",
            "output_price": "$1.20/1M tokens"
        },

        # ============================================================================
        # 🌐 GOOGLE GEMINI MODELS
        # ============================================================================
        "google/gemini-2.5-pro": {
            "description": "Gemini 2.5 Pro - Advanced reasoning - 128k context",
            "input_price": "$1.25/1M tokens",
            "output_price": "$5.00/1M tokens"
        },
        "google/gemini-2.5-flash": {
            "description": "Gemini 2.5 Flash - Fast multimodal - 1M context",
            "input_price": "$0.10/1M tokens",
            "output_price": "$0.40/1M tokens"
        },

        # ============================================================================
        # 🤖 ANTHROPIC CLAUDE MODELS
        # ============================================================================
        "anthropic/claude-sonnet-4": {
            "description": "Claude Sonnet 4 - Balanced performance - 200k context",
            "input_price": "$3.00/1M tokens",
            "output_price": "$15.00/1M tokens"
        },
        "anthropic/claude-haiku-3.5": {
            "description": "Claude Haiku 3.5 - Fast & efficient - 200k context",
            "input_price": "$0.80/1M tokens",
            "output_price": "$4.00/1M tokens"
        },

        # ============================================================================
        # 🔥 OPENAI MODELS
        # ============================================================================
        "openai/gpt-4o": {
            "description": "GPT-4o - OpenAI flagship multimodal - 128k context",
            "input_price": "$2.50/1M tokens",
            "output_price": "$10.00/1M tokens"
        },
        "openai/gpt-4o-mini": {
            "description": "GPT-4o Mini - Fast & cheap - 128k context",
            "input_price": "$0.15/1M tokens",
            "output_price": "$0.60/1M tokens"
        },
    }

    def __init__(self, api_key: str, model_name: str = "deepseek/deepseek-chat-v3.1:free", **kwargs):
        # Validate API key
        if not api_key or len(api_key.strip()) == 0:
            raise ValueError("API key is empty or None")

        self.model_name = model_name
        self.max_tokens = kwargs.get('max_tokens', 2000)  # Default max tokens
        super().__init__(api_key, **kwargs)

    def initialize_client(self, **kwargs) -> None:
        """Initialize the OpenRouter client (uses OpenAI SDK)"""
        # OpenRouter uses OpenAI-compatible API
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://openrouter.ai/api/v1"
        )

        # Test the connection
        test_response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=50
        )

        cprint(f"✨ Initialized {self.model_name}", "green")

    def generate_response(self, system_prompt, user_content, temperature=0.7, max_tokens=None):
        """Generate response with no caching"""
        try:
            # Force unique request every time
            timestamp = int(time.time() * 1000)  # Millisecond precision

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{user_content}_{timestamp}"}  # Make each request unique
                ],
                temperature=temperature,
                max_tokens=max_tokens if max_tokens else self.max_tokens,
                stream=False  # Disable streaming to prevent caching
            )

            # Extract content and filter out thinking tags
            raw_content = response.choices[0].message.content

            # Remove <think>...</think> tags and their content (for reasoning models)
            import re

            # First, try to remove complete <think>...</think> blocks
            filtered_content = re.sub(r'<think>.*?</think>', '', raw_content, flags=re.DOTALL).strip()

            # If <think> tag exists but wasn't removed (unclosed tag due to token limit),
            # remove everything from <think> onwards
            if '<think>' in filtered_content:
                filtered_content = filtered_content.split('<think>')[0].strip()

            # If filtering removed everything, return the original
            final_content = filtered_content if filtered_content else raw_content

            return ModelResponse(
                content=final_content,
                raw_response=response,
                model_name=self.model_name,
                usage=response.usage
            )

        except Exception as e:
            error_str = str(e)

            # Handle rate limit errors (429)
            if "429" in error_str or "rate_limit" in error_str:
                cprint(f"⚠️  OpenRouter rate limit exceeded", "yellow")
                cprint(f"   Model: {self.model_name}", "yellow")
                cprint(f"   💡 Skipping this model for this request...", "cyan")
                return None

            # Handle quota errors (402)
            if "402" in error_str or "insufficient" in error_str:
                cprint(f"⚠️  OpenRouter credits insufficient", "yellow")
                cprint(f"   Model: {self.model_name}", "yellow")
                cprint(f"   💡 Add credits at: https://openrouter.ai/credits", "cyan")
                return None

            # Raise 503 errors (service unavailable)
            if "503" in error_str:
                raise e

            # Log other errors
            cprint(f"❌ OpenRouter error: {error_str}", "red")
            return None

    def is_available(self) -> bool:
        """Check if OpenRouter is available"""
        return self.client is not None

    @property
    def model_type(self) -> str:
        return "openrouter"
