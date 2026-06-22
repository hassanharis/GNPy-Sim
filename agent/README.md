# GNPy Input Assistant (optional AI agent add-on)

A self-contained, **optional** LLM/agent assistant for building GNPy inputs
(equipment components, topologies, services) through conversation, guided
field-by-field help, and vendor datasheet parsing.

> The manual apps (`app_2.py`, `app_CustomInputGenerator_v2.py`) are **not**
> modified and do **not** depend on anything here. They keep working even if the
> packages below are not installed.

## What it does

- **Guided generation** – walks you through only the fields relevant to your
  choice (EDFA `type_def`, fiber dispersion model, ROADM equalization), with
  defaults and explanations.
- **Conversational generation** – e.g. *"Create a variable_gain EDFA, 25 dB
  gain, 5 dB NF, C-band"* → builds + validates a component for your approval.
- **Datasheet parsing** – reads a vendor PDF/CSV/XLSX/text datasheet, maps specs
  to GNPy fields (with explicit unit conversions), then previews + validates.

Every component is validated with the existing `gnpy_schema` rules and shown to
you **before** anything is written. The assistant only saves to
`inputs/library/` (or `inputs/topologies/`) after you explicitly confirm.

## Architecture

```
app_agent.py            # separate Streamlit chat app
agent/
  config.py             # local model config (Ollama / OpenAI-compatible / llama.cpp)
  models.py             # auto-detect installed local models
  tools.py              # wraps gnpy_schema build/validate/default + library I/O
  datasheet.py          # local PDF/CSV/XLSX/text extraction
  agent.py              # create_deep_agent factory + system prompt
```

The tools import and reuse `gnpy_schema.py` (the single source of truth shared
with the manual input generator). No business logic is duplicated.

## Setup

1. Install the optional dependencies:

   ```bash
   pip install -r requirements-agent.txt
   ```

2. Provide a **local** tool-calling model via one of:

   - **Ollama** (simplest):
     ```bash
     # install from https://ollama.com, then:
     ollama pull qwen2.5:14b-instruct
     ollama serve   # serves on http://localhost:11434
     ```
   - **vLLM / OpenAI-compatible server** (e.g.):
     ```bash
     vllm serve Qwen/Qwen2.5-14B-Instruct --port 8000
     # base URL: http://localhost:8000/v1
     ```
   - **llama.cpp GGUF on GPU** (Windows / RTX, in-process, no server):
     ```bash
     # CUDA-enabled wheel:
     pip install llama-cpp-python --extra-index-url \
       https://abetlen.github.io/llama-cpp-python/whl/cu124
     ```
     Drop a `.gguf` file into the models folder (default `./models/`), or set
     `GGUF_MODEL_PATH`. For an RTX 4090 24 GB, a 32B instruct GGUF at Q4_K_M with
     `n_ctx=8192` and `n_gpu_layers=-1` is a good target. You can download a
     curated build from `agent.models.download_gguf_model(repo_id, filename)`.

3. Run the app:

   ```bash
   streamlit run app_agent.py
   ```

   Pick the provider in the sidebar. **Installed models are auto-detected**
   (Ollama tags, OpenAI `/models`, or `*.gguf` files in the models folder) and
   shown in a dropdown; use "Re-detect models" to refresh, or enter one manually.

## Configuration (env vars, optional)

| Variable | Default | Notes |
| --- | --- | --- |
| `GNPY_AGENT_PROVIDER` | `ollama` | `ollama`, `openai` or `llamacpp` |
| `GNPY_AGENT_MODEL` | provider default | model name / id, or `.gguf` filename |
| `GNPY_AGENT_BASE_URL` | provider default | server URL (ollama/openai) |
| `GNPY_AGENT_API_KEY` | `not-needed` | for OpenAI-compatible servers |
| `GNPY_AGENT_TEMPERATURE` | `0.1` | sampling temperature |
| `GNPY_AGENT_NUM_CTX` | `8192` | context window (Ollama / llama.cpp `n_ctx`) |
| `GNPY_AGENT_N_GPU_LAYERS` | `-1` | llama.cpp GPU offload (-1 = all) |
| `GNPY_AGENT_MAX_TOKENS` | `2048` | llama.cpp max output tokens |
| `GNPY_AGENT_MODELS_DIR` | `./models` | folder scanned for `.gguf` files |
| `GGUF_MODEL_PATH` | — | explicit path to a `.gguf` (overrides model) |

## Model choice

The agent loop needs **reliable tool/function calling**. Prefer a capable
instruct model (Qwen2.5 14B+/Qwen3, Llama 3.3 70B class). Very small models
(≤8B) often fail multi-step tool loops. If your hardware is limited, keep to the
read/guidance use cases rather than autonomous building.

## Notes / current limitations

- Human-in-the-loop is enforced via the preview→confirm→save flow and the system
  prompt. A future iteration can use deepagents' interrupt-based approvals.
- Datasheet parsing is text-based; scanned (image-only) PDFs need a local vision
  model and are not handled yet.
- This add-on builds **inputs**. Running simulations stays in the main app.
