"""
GNPy AI agent add-on (optional).

A self-contained package that adds an LLM/agent assistant for building GNPy
inputs. It reuses gnpy_schema and the inputs/ layout but never imports the
manual Streamlit apps, so app_2.py and app_CustomInputGenerator_v2.py remain
fully independent and work without these dependencies installed.

Public entry point: agent.agent.build_agent()
"""

from .config import AgentModelConfig, config_from_env

__all__ = ["AgentModelConfig", "config_from_env", "build_agent"]


def build_agent(*args, **kwargs):
    """Lazy proxy to agent.agent.build_agent (avoids importing deepagents at
    package import time)."""
    from .agent import build_agent as _build_agent

    return _build_agent(*args, **kwargs)
