from openai import OpenAI
from config.settings import OPENROUTER_API_KEY, get_default_config, get_agent_config
from typing import List, Dict, Any, Optional


class LLMClient:
    def __init__(
        self,
        agent_name: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        base_url: Optional[str] = None
    ):
        defaults = get_default_config()
        
        if agent_name:
            agent_cfg = get_agent_config(agent_name)
            self.model = model or agent_cfg.get("model")
            self.temperature = temperature if temperature is not None else agent_cfg.get("temperature", 0.7)
            self.max_tokens = max_tokens or agent_cfg.get("max_tokens", 4000)
        else:
            self.model = model or defaults.get("fallback_model", "qwen/qwen2.5-72b-instruct")
            self.temperature = temperature if temperature is not None else 0.7
            self.max_tokens = max_tokens or 4000
        
        self.base_url = base_url or defaults.get("base_url", "https://openrouter.ai/api/v1")
        
        self.client = OpenAI(
            api_key=api_key or OPENROUTER_API_KEY,
            base_url=self.base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/iqbalbaharum/forward-agent",
                "X-Title": "Forward Agent"
            }
        )

    def chat(self, messages: List[Dict[str, str]], temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens or self.max_tokens
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temp,
            max_tokens=tokens
        )
        return response.choices[0].message.content

    def chat_with_json(self, messages: List[Dict[str, str]], temperature: Optional[float] = None) -> Dict[str, Any]:
        temp = temperature if temperature is not None else self.temperature
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temp,
            max_tokens=self.max_tokens,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        import json
        return json.loads(content)