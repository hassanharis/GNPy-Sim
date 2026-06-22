"""
GNPy Input Assistant - standalone AI agent app.

This is a SEPARATE app from the manual tools. It does not import or modify
app_2.py or app_CustomInputGenerator_v2.py. The manual apps keep working with
no extra dependencies; this one additionally needs requirements-agent.txt and a
local LLM (Ollama or an OpenAI-compatible server such as vLLM).

Run with:
    streamlit run app_agent.py
"""

from __future__ import annotations

import streamlit as st

from agent.config import (
    DEFAULT_BASE_URLS,
    DEFAULT_MODELS,
    MODELS_DIR,
    SUPPORTED_PROVIDERS,
    AgentModelConfig,
)
from agent.models import detect_models

st.set_page_config(page_title="GNPy Input Assistant", page_icon="🤖", layout="wide")

_CUSTOM = "(enter manually)"


@st.cache_data(show_spinner=False, ttl=30)
def _cached_detect(provider: str, base_url: str, api_key: str, models_dir: str) -> list[str]:
    return detect_models(provider, base_url=base_url, api_key=api_key, models_dir=models_dir)


def _model_picker(provider: str, base_url: str, api_key: str, models_dir: str, default_model: str) -> str:
    """Show detected models as a dropdown, with a manual-entry fallback."""
    detected = _cached_detect(provider, base_url, api_key, models_dir)
    if detected:
        options = detected + [_CUSTOM]
        default_idx = detected.index(default_model) if default_model in detected else 0
        choice = st.sidebar.selectbox(
            f"Model ({len(detected)} detected)", options, index=default_idx,
            help="Auto-detected local models. Choose one or pick manual entry.",
        )
        if choice != _CUSTOM:
            return choice
        return st.sidebar.text_input("Model (manual)", value=default_model)
    st.sidebar.caption("No models auto-detected - enter one manually.")
    return st.sidebar.text_input("Model", value=default_model)


# =============================================================================
# Sidebar: local model configuration
# =============================================================================
def sidebar_config() -> AgentModelConfig:
    st.sidebar.title("🤖 GNPy Input Assistant")
    st.sidebar.caption("Local LLM agent for building GNPy inputs. Separate from the manual apps.")

    provider = st.sidebar.selectbox(
        "Provider", list(SUPPORTED_PROVIDERS),
        help="ollama = local Ollama server. openai = OpenAI-compatible endpoint "
             "(vLLM, LM Studio). llamacpp = in-process GGUF on GPU (Windows/CUDA).",
    )

    if st.sidebar.button("🔍 Re-detect models", use_container_width=True):
        _cached_detect.clear()

    default_model = DEFAULT_MODELS[provider]
    base_url = DEFAULT_BASE_URLS[provider]
    api_key = "not-needed"
    models_dir = str(MODELS_DIR)

    # llamacpp-specific knobs
    n_gpu_layers, n_threads, max_tokens = -1, max(4, 4), 2048
    num_ctx = 8192

    if provider in ("ollama", "openai"):
        base_url = st.sidebar.text_input("Base URL", value=base_url)
        if provider == "openai":
            api_key = st.sidebar.text_input("API key", value=api_key, type="password")
        model = _model_picker(provider, base_url, api_key, models_dir, default_model)
    else:  # llamacpp
        models_dir = st.sidebar.text_input("Models folder", value=models_dir)
        model = _model_picker(provider, base_url, api_key, models_dir, default_model)
        with st.sidebar.expander("GGUF / GPU settings"):
            num_ctx = st.number_input("n_ctx (context)", 2048, 131072, 8192, step=2048)
            n_gpu_layers = st.number_input(
                "n_gpu_layers (-1 = all on GPU)", -1, 200, -1, step=1)
            max_tokens = st.number_input("max_tokens", 256, 8192, 2048, step=256)
            import os as _os
            n_threads = st.number_input(
                "n_threads", 1, 64, max(4, (_os.cpu_count() or 8) // 2), step=1)

    temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.1, 0.05)

    cfg = AgentModelConfig(
        provider=provider, model=model, base_url=base_url, api_key=api_key,
        temperature=temperature, num_ctx=int(num_ctx), n_gpu_layers=int(n_gpu_layers),
        n_threads=int(n_threads), max_tokens=int(max_tokens), models_dir=models_dir,
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Reset conversation", use_container_width=True):
        st.session_state.pop("lc_messages", None)
        st.rerun()

    with st.sidebar.expander("Tips"):
        st.markdown(
            "- *Create a variable_gain EDFA, 25 dB gain, 5 dB NF, C-band.*\n"
            "- *Walk me through building an SSMF fiber type.*\n"
            "- *Parse this datasheet:* `inputs/datasheets/edfa.pdf`\n"
            "- *Show me the schema for a ROADM.*\n\n"
            "The assistant always previews + validates before anything is saved, "
            "and asks for your confirmation first."
        )
    return cfg


# =============================================================================
# Agent lifecycle (rebuilt when config changes)
# =============================================================================
@st.cache_resource(show_spinner=False)
def get_agent(provider: str, model: str, base_url: str, api_key: str, temperature: float,
              num_ctx: int, n_gpu_layers: int, n_threads: int, max_tokens: int, models_dir: str):
    from agent.agent import build_agent

    cfg = AgentModelConfig(
        provider=provider, model=model, base_url=base_url, api_key=api_key,
        temperature=temperature, num_ctx=num_ctx, n_gpu_layers=n_gpu_layers,
        n_threads=n_threads, max_tokens=max_tokens, models_dir=models_dir,
    )
    return build_agent(cfg)


def render_history():
    """Render prior user/assistant turns from stored LangChain messages."""
    for msg in st.session_state.get("lc_messages", []):
        mtype = getattr(msg, "type", None)
        content = getattr(msg, "content", "")
        if mtype == "human":
            with st.chat_message("user"):
                st.markdown(content)
        elif mtype == "ai" and content:
            with st.chat_message("assistant"):
                st.markdown(content)


def run_agent_turn(agent, user_text: str):
    """Stream one agent turn, showing tool activity, and persist the new state."""
    from langchain_core.messages import HumanMessage

    history = st.session_state.get("lc_messages", [])
    history.append(HumanMessage(content=user_text))

    inputs = {"messages": history}
    final_state = None
    with st.chat_message("assistant"):
        status = st.status("Thinking...", expanded=False)
        try:
            for chunk in agent.stream(inputs, stream_mode="values"):
                final_state = chunk
                msgs = chunk.get("messages", [])
                if not msgs:
                    continue
                last = msgs[-1]
                tool_calls = getattr(last, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        status.update(label=f"Calling tool: {tc.get('name', '?')}", state="running")
                elif getattr(last, "type", None) == "tool":
                    status.write(f"✅ {getattr(last, 'name', 'tool')} returned")
        except Exception as e:  # noqa: BLE001
            status.update(label="Error", state="error")
            st.error(f"Agent error: {e}")
            return

        status.update(label="Done", state="complete")

        if final_state is not None:
            st.session_state.lc_messages = final_state["messages"]
            answer = ""
            for m in reversed(final_state["messages"]):
                if getattr(m, "type", None) == "ai" and getattr(m, "content", ""):
                    answer = m.content
                    break
            st.markdown(answer or "_(no text response)_")


# =============================================================================
# Main
# =============================================================================
def main():
    cfg = sidebar_config()

    st.title("GNPy Input Assistant")
    st.caption("Conversational + datasheet-driven builder for GNPy components, topologies and services.")

    # Build the agent; surface setup problems clearly without crashing.
    try:
        agent = get_agent(
            cfg.provider, cfg.model, cfg.base_url, cfg.api_key, cfg.temperature,
            cfg.num_ctx, cfg.n_gpu_layers, cfg.n_threads, cfg.max_tokens, str(cfg.models_dir),
        )
    except ImportError as e:
        st.warning(
            "The agent dependencies are not installed.\n\n"
            "Install them with `pip install -r requirements-agent.txt` and start "
            "a local model server (Ollama or an OpenAI-compatible endpoint)."
        )
        st.caption(f"Details: {e}")
        st.stop()
    except Exception as e:  # noqa: BLE001
        st.error(f"Could not initialize the agent: {e}")
        st.caption(
            "Check that your local model server is running and the Base URL / "
            "model name are correct."
        )
        st.stop()

    if "lc_messages" not in st.session_state:
        st.session_state.lc_messages = []

    render_history()

    if user_text := st.chat_input("Describe the component you want to build, or point me at a datasheet..."):
        with st.chat_message("user"):
            st.markdown(user_text)
        run_agent_turn(agent, user_text)


if __name__ == "__main__":
    main()
