"""
LLM Provider Abstraction Layer

Supports multiple backends:
- Ollama (local inference)
- Groq (cloud inference, OpenAI-compatible)
"""

import os
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Generator
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Dict:
        pass

    @abstractmethod
    def check_connection(self) -> bool:
        pass

    @abstractmethod
    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Generator[str, None, None]:
        pass


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self.chat_url = f"{self.base_url}/api/chat"
        self.tags_url = f"{self.base_url}/api/tags"

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Dict:
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        response = requests.post(self.chat_url, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        return {
            "content": result["message"]["content"].strip(),
            "tokens": result.get("eval_count", 0),
            "total_duration": result.get("total_duration", 0),
        }

    def check_connection(self) -> bool:
        try:
            response = requests.get(self.tags_url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.ConnectionError:
            return False

    def get_available_models(self) -> List[str]:
        try:
            response = requests.get(self.tags_url, timeout=5)
            if response.status_code == 200:
                return [m["name"] for m in response.json().get("models", [])]
        except Exception:
            pass
        return []

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Generator[str, None, None]:
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        with requests.post(
            self.chat_url, json=payload, stream=True, timeout=120
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data:
                        token = data["message"].get("content", "")
                        if token:
                            yield token
                    if data.get("done", False):
                        break


class GroqProvider(LLMProvider):
    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODELS_URL = "https://api.groq.com/openai/v1/models"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Groq API key required. "
                "Set GROQ_API_KEY env var or pass api_key parameter."
            )

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Dict:
        payload = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        response = requests.post(
            self.BASE_URL, headers=self._headers(), json=payload, timeout=30
        )
        response.raise_for_status()
        result = response.json()

        choice = result["choices"][0]
        usage = result.get("usage", {})

        return {
            "content": choice["message"]["content"].strip(),
            "tokens": usage.get("completion_tokens", 0),
            "total_duration": 0,
        }

    def check_connection(self) -> bool:
        try:
            response = requests.get(
                self.MODELS_URL, headers=self._headers(), timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> List[str]:
        try:
            response = requests.get(
                self.MODELS_URL, headers=self._headers(), timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception:
            pass
        return []

    def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.8,
        max_tokens: int = 500,
    ) -> Generator[str, None, None]:
        payload = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        with requests.post(
            self.BASE_URL,
            headers=self._headers(),
            json=payload,
            stream=True,
            timeout=30,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    line = line.decode("utf-8") if isinstance(line, bytes) else line
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue


def create_provider(
    backend: Optional[str] = None,
    api_key: Optional[str] = None,
    ollama_url: str = "http://localhost:11434",
) -> LLMProvider:
    backend = (backend or os.getenv("LLM_BACKEND", "ollama")).lower().strip()

    if backend == "groq":
        return GroqProvider(api_key=api_key)
    return OllamaProvider(base_url=ollama_url)


DEFAULT_MODELS = {
    "ollama": "llama3.2:1b",
    "groq": "llama-3.3-70b-versatile",
}
