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

from agent.config import AgentModelConfig

st.set_page_config(page_title="GNPy Input Assistant", page_icon="🤖", layout="wide")


# =============================================================================
# Sidebar: local model configuration
# =============================================================================
def sidebar_config() -> AgentModelConfig:
    st.sidebar.title("🤖 GNPy Input Assistant")
    st.sidebar.caption("Local LLM agent for building GNPy inputs. Separate from the manual apps.")

    provider = st.sidebar.selectbox(
        "Provider", ["ollama", "openai"],
        help="ollama = local Ollama server. openai = any OpenAI-compatible "
             "endpoint (vLLM, llama.cpp, LM Studio).",
    )
    default_model = "qwen2.5:14b-instruct" if provider == "ollama" else "Qwen/Qwen2.5-14B-Instruct"
    default_url = "http://localhost:11434" if provider == "ollama" else "http://localhost:8000/v1"

    model = st.sidebar.text_input("Model", value=default_model)
    base_url = st.sidebar.text_input("Base URL", value=default_url)
    temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.1, 0.05)

    cfg = AgentModelConfig(
        provider=provider, model=model, base_url=base_url, temperature=temperature
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
def get_agent(provider: str, model: str, base_url: str, temperature: float):
    from agent.agent import build_agent

    cfg = AgentModelConfig(
        provider=provider, model=model, base_url=base_url, temperature=temperature
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
        agent = get_agent(cfg.provider, cfg.model, cfg.base_url, cfg.temperature)
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
