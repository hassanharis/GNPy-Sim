"""
Local LLM configuration for the GNPy agent.

The agent is model-agnostic and designed for local / air-gapped deployments.
Two providers are supported out of the box:

  * ``ollama``  - talks to a local Ollama server (default http://localhost:11434)
  * ``openai``  - any OpenAI-compatible endpoint (vLLM, llama.cpp server,
                  LM Studio, ...). Point ``base_url`` at your server.

Everything is driven by environment variables so no secrets or hostnames are
hardcoded. Nothing here imports the manual apps.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


# Reasonable local defaults. Override via environment variables.
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODELS = {
    # A capable tool-calling model is required for the agent loop.
    "ollama": "qwen2.5:14b-instruct",
    "openai": "Qwen/Qwen2.5-14B-Instruct",
}
DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434",
    "openai": "http://localhost:8000/v1",  # typical vLLM OpenAI-compatible port
}


@dataclass
class AgentModelConfig:
    """Resolved model settings for the agent."""

    provider: str = DEFAULT_PROVIDER
    model: str = ""
    base_url: str = ""
    api_key: str = "not-needed"  # local servers usually ignore this
    temperature: float = 0.1
    num_ctx: int = 8192  # context window hint (Ollama)

    def __post_init__(self) -> None:
        self.provider = (self.provider or DEFAULT_PROVIDER).lower().strip()
        if self.provider not in ("ollama", "openai"):
            raise ValueError(
                f"Unsupported provider '{self.provider}'. Use 'ollama' or 'openai'."
            )
        if not self.model:
            self.model = DEFAULT_MODELS[self.provider]
        if not self.base_url:
            self.base_url = DEFAULT_BASE_URLS[self.provider]


def config_from_env() -> AgentModelConfig:
    """Build a config from GNPY_AGENT_* environment variables."""
    return AgentModelConfig(
        provider=os.getenv("GNPY_AGENT_PROVIDER", DEFAULT_PROVIDER),
        model=os.getenv("GNPY_AGENT_MODEL", ""),
        base_url=os.getenv("GNPY_AGENT_BASE_URL", ""),
        api_key=os.getenv("GNPY_AGENT_API_KEY", "not-needed"),
        temperature=float(os.getenv("GNPY_AGENT_TEMPERATURE", "0.1")),
        num_ctx=int(os.getenv("GNPY_AGENT_NUM_CTX", "8192")),
    )


def build_chat_model(cfg: AgentModelConfig | None = None):
    """Instantiate a LangChain chat model for the given config.

    Imports are done lazily so the rest of the package (and the manual apps)
    never depend on langchain being installed.
    """
    cfg = cfg or config_from_env()

    if cfg.provider == "ollama":
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "langchain-ollama is not installed. Run "
                "`pip install -r requirements-agent.txt` and ensure an Ollama "
                "server is running (https://ollama.com)."
            ) from exc
        return ChatOllama(
            model=cfg.model,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            num_ctx=cfg.num_ctx,
        )

    # provider == "openai" (OpenAI-compatible local server, e.g. vLLM)
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "langchain-openai is not installed. Run "
            "`pip install -r requirements-agent.txt`."
        ) from exc
    return ChatOpenAI(
        model=cfg.model,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        temperature=cfg.temperature,
    )
