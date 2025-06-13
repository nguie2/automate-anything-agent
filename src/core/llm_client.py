"""LLM client abstraction supporting multiple providers."""

import json
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import httpx
from openai import AsyncOpenAI

from ..config import settings
from ..utils.logging import get_logger

logger = get_logger(__name__)


class LLMResponse:
    """Standardized LLM response format."""
    
    def __init__(self, content: str, function_calls: Optional[List[Dict]] = None, usage: Optional[Dict] = None):
        self.content = content
        self.function_calls = function_calls or []
        self.usage = usage or {}
    
    @property
    def has_function_calls(self) -> bool:
        return len(self.function_calls) > 0


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""
    
    def __init__(self, api_key: str, base_url: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        functions: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """Generate chat completion with optional function calling."""
        pass
    
    @abstractmethod
    def supports_function_calling(self) -> bool:
        """Return whether this provider supports function calling."""
        pass


class GenericOpenAIClient(BaseLLMClient):
    """Generic OpenAI-compatible API client (for OpenAI, DeepSeek, Qwen, etc.)."""
    
    def __init__(self, api_key: str, base_url: str, model: str):
        super().__init__(api_key, base_url, model)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        functions: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> LLMResponse:
        """Generate chat completion with OpenAI-compatible API."""
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Try function calling if supported
            if functions:
                try:
                    kwargs["functions"] = functions
                    kwargs["function_call"] = "auto"
                except Exception:
                    # Fall back to prompt engineering for models without native function calling
                    function_prompt = self._format_functions_as_prompt(functions)
                    if messages and messages[-1]["role"] == "user":
                        messages[-1]["content"] += f"\n\n{function_prompt}"
            
            response = await self.client.chat.completions.create(**kwargs)
            
            message = response.choices[0].message
            content = message.content or ""
            
            function_calls = []
            if hasattr(message, 'function_call') and message.function_call:
                function_calls = [{
                    "name": message.function_call.name,
                    "arguments": json.loads(message.function_call.arguments)
                }]
            elif functions and "FUNCTION_CALL:" in content:
                # Parse simulated function calls
                function_calls = self._parse_function_calls_from_content(content)
                if function_calls:
                    content = content.split("FUNCTION_CALL:")[0].strip()
            
            usage = {}
            if hasattr(response, 'usage') and response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            
            return LLMResponse(content, function_calls, usage)
            
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            raise
    
    def _format_functions_as_prompt(self, functions: List[Dict]) -> str:
        """Format functions as prompt for models without native function calling."""
        prompt = "Available functions (respond with FUNCTION_CALL: {json} to call):\n"
        for func in functions:
            prompt += f"- {func['name']}: {func['description']}\n"
        return prompt
    
    def _parse_function_calls_from_content(self, content: str) -> List[Dict]:
        """Parse function calls from content."""
        function_calls = []
        if "FUNCTION_CALL:" in content:
            try:
                call_start = content.find("FUNCTION_CALL:")
                call_content = content[call_start + 14:].strip()
                if call_content.startswith("{"):
                    end_brace = call_content.find("}")
                    if end_brace != -1:
                        call_json = call_content[:end_brace + 1]
                        parsed = json.loads(call_json)
                        function_calls = [parsed]
            except json.JSONDecodeError:
                pass
        return function_calls
    
    def supports_function_calling(self) -> bool:
        return True


class LLMClientFactory:
    """Factory for creating LLM clients based on provider."""
    
    @staticmethod
    def create_client() -> BaseLLMClient:
        """Create LLM client based on settings."""
        provider = settings.llm_provider.lower()
        
        # Default endpoints for known providers
        if not settings.llm_base_url:
            base_urls = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "groq": "https://api.groq.com/openai/v1",
                "together": "https://api.together.xyz/v1",
                "perplexity": "https://api.perplexity.ai",
                "openrouter": "https://openrouter.ai/api/v1",
                "ollama": "http://localhost:11434/v1",
                "anthropic": "https://api.anthropic.com/v1",
                "local": "http://localhost:8000/v1"
            }
            base_url = base_urls.get(provider, "http://localhost:8000/v1")
        else:
            base_url = settings.llm_base_url
        
        return GenericOpenAIClient(
            api_key=settings.llm_api_key,
            base_url=base_url,
            model=settings.llm_model
        )


# Global LLM client instance
def get_llm_client() -> BaseLLMClient:
    """Get the configured LLM client."""
    return LLMClientFactory.create_client() 