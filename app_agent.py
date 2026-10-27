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
    KNOWN_GGUF_MODELS,
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


def render_download_section(models_dir: str) -> None:
    """GGUF download UI (llamacpp). Needs network + huggingface_hub."""
    with st.sidebar.expander("⬇️ Download a GGUF model"):
        labels = [f"{fn}  ({repo})" for repo, fn in KNOWN_GGUF_MODELS]
        choice = st.selectbox("Curated builds", labels + [_CUSTOM], key="dl_choice")
        if choice == _CUSTOM:
            repo_id = st.text_input("repo_id", key="dl_repo",
                                    placeholder="bartowski/Qwen3-14B-GGUF")
            filename = st.text_input("filename (.gguf)", key="dl_file",
                                     placeholder="Qwen3-14B-Q4_K_M.gguf")
        else:
            repo_id, filename = KNOWN_GGUF_MODELS[labels.index(choice)]
            st.caption(f"repo: `{repo_id}`")

        st.caption(f"Saves to: `{models_dir}`")
        if st.button("Download", key="dl_btn", use_container_width=True):
            if not repo_id or not filename:
                st.error("repo_id and filename are required.")
                return
            try:
                from agent.models import download_gguf_model
                with st.spinner(f"Downloading {filename} - watch the console for progress..."):
                    path = download_gguf_model(repo_id, filename, models_dir)
                st.success(f"Downloaded: {path}")
                _cached_detect.clear()
                st.rerun()
            except ImportError:
                st.error("huggingface_hub is not installed. Run "
                         "`pip install huggingface_hub`.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Download failed: {e}")


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
    verbose = False
    disable_thinking = True

    if provider in ("ollama", "openai"):
        base_url = st.sidebar.text_input("Base URL", value=base_url)
        if provider == "openai":
            api_key = st.sidebar.text_input("API key", value=api_key, type="password")
        model = _model_picker(provider, base_url, api_key, models_dir, default_model)
    else:  # llamacpp
        models_dir = st.sidebar.text_input("Models folder", value=models_dir)
        model = _model_picker(provider, base_url, api_key, models_dir, default_model)
        render_download_section(models_dir)
        with st.sidebar.expander("GGUF / GPU settings"):
            num_ctx = st.number_input("n_ctx (context)", 2048, 131072, 8192, step=2048)
            n_gpu_layers = st.number_input(
                "n_gpu_layers (-1 = all on GPU)", -1, 200, -1, step=1)
            max_tokens = st.number_input("max_tokens", 256, 8192, 2048, step=256)
            import os as _os
            n_threads = st.number_input(
                "n_threads", 1, 64, max(4, (_os.cpu_count() or 8) // 2), step=1)
            verbose = st.checkbox(
                "Verbose llama.cpp logs", value=False,
                help="Print the raw llama.cpp load/inference logs to the console "
                     "(run terminal). Use this to debug model load failures.")
            disable_thinking = not st.checkbox(
                "Enable model thinking/reasoning", value=False,
                help="Reasoning models emit a hidden <think> block before every "
                     "answer, which is slow even for trivial prompts. Leave OFF "
                     "for fast replies; turn ON for harder multi-step tasks. "
                     "Only affects models whose chat template supports it.")

    temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.1, 0.05)

    cfg = AgentModelConfig(
        provider=provider, model=model, base_url=base_url, api_key=api_key,
        temperature=temperature, num_ctx=int(num_ctx), n_gpu_layers=int(n_gpu_layers),
        n_threads=int(n_threads), max_tokens=int(max_tokens), verbose=verbose,
        disable_thinking=disable_thinking, models_dir=models_dir,
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
def _model_slot() -> dict:
    """Single-slot holder for the loaded model + agent.

    Persists across Streamlit reruns/sessions (one model per GPU) while letting
    us explicitly tear the old model down before loading a new one.
    """
    return {"sig": None, "model": None, "agent": None}


def _config_signature(cfg: AgentModelConfig) -> tuple:
    return (
        cfg.provider, cfg.model, cfg.base_url, cfg.api_key, cfg.temperature,
        cfg.num_ctx, cfg.n_gpu_layers, cfg.n_threads, cfg.max_tokens,
        cfg.verbose, cfg.disable_thinking, str(cfg.models_dir),
    )


def _release_model(slot: dict) -> None:
    """Free the currently loaded model so its VRAM is returned before reloading.

    llama.cpp holds the weights in the in-process ``Llama`` client; closing it
    releases the GPU/CPU buffers. Without this, switching models in the sidebar
    would briefly hold two models and OOM the GPU.
    """
    model = slot.get("model")
    slot["sig"] = None
    slot["model"] = None
    slot["agent"] = None
    if model is None:
        return
    try:
        client = getattr(model, "client", None)
        if client is not None and hasattr(client, "close"):
            client.close()
    except Exception:  # noqa: BLE001 - best-effort teardown
        pass
    del model
    import gc

    gc.collect()


def get_agent(cfg: AgentModelConfig):
    """Return a cached agent for ``cfg``, freeing the previous model on change."""
    slot = _model_slot()
    sig = _config_signature(cfg)
    if slot["sig"] == sig and slot["agent"] is not None:
        return slot["agent"]

    # Config changed (or first build): drop the old model before allocating.
    _release_model(slot)

    from agent.agent import build_agent
    from agent.config import build_chat_model

    model = build_chat_model(cfg)
    agent = build_agent(model=model)
    slot.update(sig=sig, model=model, agent=agent)
    return agent


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


def _chunk_text(content) -> str:
    """Coerce a message chunk's content (str or list of blocks) to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, str):
                out.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                out.append(block["text"])
        return "".join(out)
    return ""


def run_agent_turn(agent, user_text: str):
    """Stream one agent turn with live token output and persist the new state."""
    from langchain_core.messages import HumanMessage

    # Copy history so a mid-turn failure can't leave a dangling user message in
    # session state (which would be resent on the next turn).
    history = list(st.session_state.get("lc_messages", []))
    history.append(HumanMessage(content=user_text))

    inputs = {"messages": history}
    final_state = None
    with st.chat_message("assistant"):
        status = st.status("Thinking...", expanded=False)
        placeholder = st.empty()
        answer = ""
        try:
            # Two stream modes at once: "messages" gives token-level deltas for
            # live output; "values" gives full state snapshots so we can persist
            # the final message list.
            for mode, data in agent.stream(inputs, stream_mode=["values", "messages"]):
                if mode == "values":
                    final_state = data
                    continue
                # mode == "messages": data is (message_chunk, metadata)
                chunk, _meta = data
                if getattr(chunk, "type", None) == "tool":
                    status.write(f"✅ {getattr(chunk, 'name', 'tool')} returned")
                    continue
                tool_calls = getattr(chunk, "tool_call_chunks", None) or getattr(chunk, "tool_calls", None)
                if tool_calls:
                    for tc in tool_calls:
                        name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
                        if name:
                            status.update(label=f"Calling tool: {name}", state="running")
                text = _chunk_text(getattr(chunk, "content", ""))
                if text:
                    answer += text
                    placeholder.markdown(answer)
        except Exception as e:  # noqa: BLE001
            import traceback

            tb = traceback.format_exc()
            # Always dump the full traceback to the console (run terminal) so the
            # exact failing frame is visible, not just the exception message.
            traceback.print_exc()
            status.update(label="Error", state="error")
            st.error(f"Agent error: {e}")
            with st.expander("Show full traceback"):
                st.code(tb, language="text")
            return

        status.update(label="Done", state="complete")

        if final_state is not None:
            st.session_state.lc_messages = final_state["messages"]
            if not answer:
                # Fallback if nothing streamed (e.g. non-streaming model).
                for m in reversed(final_state["messages"]):
                    if getattr(m, "type", None) == "ai" and getattr(m, "content", ""):
                        answer = _chunk_text(m.content)
                        break
        placeholder.markdown(answer or "_(no text response)_")


# =============================================================================
# Main
# =============================================================================
def main():
    cfg = sidebar_config()

    st.title("GNPy Input Assistant")
    st.caption("Conversational + datasheet-driven builder for GNPy components, topologies and services.")

    # Build the agent; surface setup problems clearly without crashing.
    try:
        agent = get_agent(cfg)
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
