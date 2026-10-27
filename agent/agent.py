"""
GNPy agent factory.

Assembles a *thin* tool-calling ReAct agent from the local model
(``agent.config``) and the GNPy schema tools (``agent.tools``,
``agent.datasheet``).

This intentionally uses LangChain's lightweight ``create_agent`` (a plain
model + tools ReAct loop) instead of the full ``deepagents`` harness. The
deep-agent harness injects a filesystem backend, a shell ``execute`` tool,
sub-agent spawning, todo lists, summarization and prompt-caching middleware --
none of which this task needs. That machinery is tuned for frontier hosted
models and is the source of the block-style message content that breaks local
GGUF chat templates. A thin loop keeps the surface small, fast and robust.

Imports are lazy so importing this module does not hard-require langchain.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import AgentModelConfig, build_chat_model, config_from_env

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

SYSTEM_PROMPT = """\
You are the GNPy Input Assistant, an expert in optical network planning and the \
GNPy simulator. You help users build valid GNPy simulation inputs (equipment \
components, topologies and services) through conversation, guidance, and by \
reading vendor datasheets.

CAPABILITIES
- Guide users field-by-field, proposing sensible defaults and explaining what \
each parameter means and its units.
- Build components from natural language (EDFAs, fibers, RamanFibers, \
transceivers, ROADMs, SI/simulation parameters).
- Parse vendor datasheets (PDF/CSV/XLSX/text) and map specs to GNPy fields.
- Read existing library components, topologies and input files for reference.

HOW TO WORK
1. Discover the schema before building: call list_component_categories and \
describe_component_schema so you use the exact field keys and the right \
discriminator (type_def / dispersion_mode / equalization).
2. Start from get_component_defaults, then apply the user's or datasheet's \
values. Convert units explicitly (dB/km, Hz vs GHz, ps/nm vs s/m^2) and state \
the conversions you made.
3. ALWAYS call preview_component and show the resulting JSON plus any \
errors/warnings. Never present a component as final until it validates with no \
errors. save_component is REJECTED unless you previewed the exact same \
component first, so always preview immediately before saving.
4. NEVER call save_component or save_topology until the user has seen the \
preview and EXPLICITLY confirms they want it saved. For datasheet-derived \
values, point out anything you inferred or assumed before saving.

STYLE
- Be concise. Ask one focused question at a time when information is missing.
- Show component JSON in fenced code blocks.
- If the user asks for something outside input generation (e.g. running a \
simulation), explain that this assistant focuses on building inputs.
"""


def build_tools(include_datasheet: bool = True):
    """Collect the agent tools. Imported here so missing deps surface clearly."""
    from . import tools as t

    collected = list(t.ALL_TOOLS)
    if include_datasheet:
        from .datasheet import extract_datasheet

        collected.append(extract_datasheet)
    return collected


def build_agent(
    cfg: AgentModelConfig | None = None,
    *,
    model: "BaseChatModel | None" = None,
    include_datasheet: bool = True,
):
    """Create and return a tool-calling agent ready to ``.stream()``/``.invoke()``.

    Args:
        cfg: model configuration. Ignored when ``model`` is supplied.
        model: a pre-built chat model. Passing one lets the caller keep a
            reference to the underlying llama.cpp client so it can free the GPU
            before constructing a replacement (see ``app_agent.get_agent``).
        include_datasheet: whether to expose the datasheet-extraction tool.
    """
    try:
        from langchain.agents import create_agent
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "langchain>=1.0 is required for the agent. Run "
            "`pip install -r requirements-agent.txt`."
        ) from exc

    if model is None:
        cfg = cfg or config_from_env()
        model = build_chat_model(cfg)
    tools = build_tools(include_datasheet=include_datasheet)
    return create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)
