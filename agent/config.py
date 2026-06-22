"""
Local LLM configuration for the GNPy agent.

The agent is model-agnostic and designed for local / air-gapped deployments.
Three providers are supported out of the box:

  * ``ollama``    - talks to a local Ollama server (default http://localhost:11434)
  * ``openai``    - any OpenAI-compatible endpoint (vLLM, llama.cpp server,
                    LM Studio, ...). Point ``base_url`` at your server.
  * ``llamacpp``  - in-process GGUF inference via llama-cpp-python with CUDA
                    (Windows-friendly, e.g. an RTX 4090). No server needed.

Everything is driven by environment variables so no secrets or hostnames are
hardcoded. Nothing here imports the manual apps.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Where GGUF model files live (for the llamacpp provider / auto-detection).
MODELS_DIR = Path(os.environ.get("GNPY_AGENT_MODELS_DIR", str(BASE_DIR / "models")))

SUPPORTED_PROVIDERS = ("ollama", "openai", "llamacpp")

# Reasonable local defaults. Override via environment variables / the sidebar.
DEFAULT_PROVIDER = "ollama"
DEFAULT_MODELS = {
    # A capable tool-calling model is required for the agent loop.
    "ollama": "qwen2.5:14b-instruct",
    "openai": "Qwen/Qwen2.5-14B-Instruct",
    "llamacpp": "nvidia_Nemotron-Cascade-14B-Thinking-Q8_0.gguf",
}
DEFAULT_BASE_URLS = {
    "ollama": "http://localhost:11434",
    "openai": "http://localhost:8000/v1",  # typical vLLM OpenAI-compatible port
    "llamacpp": "",  # not used (in-process)
}

# Curated GGUF builds (repo_id, filename) usable for optional downloads.
# Mirrors common Windows/RTX targets; tune to your VRAM.
KNOWN_GGUF_MODELS = [
    ("bartowski/Qwen2.5-32B-Instruct-GGUF", "Qwen2.5-32B-Instruct-Q4_K_M.gguf"),
    ("bartowski/Qwen3-32B-GGUF", "Qwen3-32B-Q4_K_M.gguf"),
    ("bartowski/Qwen3-14B-GGUF", "Qwen3-14B-Q4_K_M.gguf"),
    ("bartowski/nvidia_Nemotron-Cascade-14B-Thinking-GGUF",
     "nvidia_Nemotron-Cascade-14B-Thinking-Q8_0.gguf"),
    ("bartowski/Llama-3.1-Nemotron-70B-Instruct-HF-GGUF",
     "Llama-3.1-Nemotron-70B-Instruct-HF-Q4_K_M.gguf"),
    ("bartowski/gemma-3-27b-it-GGUF", "gemma-3-27b-it-Q4_K_M.gguf"),
    ("mradermacher/granite-3.2-8b-instruct-GGUF", "granite-3.2-8b-instruct.Q8_0.gguf"),
]


@dataclass
class AgentModelConfig:
    """Resolved model settings for the agent."""

    provider: str = DEFAULT_PROVIDER
    model: str = ""  # model name (ollama/openai) OR gguf filename/path (llamacpp)
    base_url: str = ""
    api_key: str = "not-needed"  # local servers usually ignore this
    temperature: float = 0.1
    num_ctx: int = 8192  # context window (Ollama / llama.cpp n_ctx)
    # llama.cpp-only knobs:
    n_gpu_layers: int = -1  # -1 = offload all layers to GPU
    n_threads: int = max(4, (os.cpu_count() or 8) // 2)
    max_tokens: int = 2048
    verbose: bool = False  # llama.cpp logs to console (useful for load errors)
    models_dir: Path = MODELS_DIR

    def __post_init__(self) -> None:
        self.provider = (self.provider or DEFAULT_PROVIDER).lower().strip()
        if self.provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported provider '{self.provider}'. Use one of {SUPPORTED_PROVIDERS}."
            )
        if not self.model:
            self.model = DEFAULT_MODELS[self.provider]
        if not self.base_url:
            self.base_url = DEFAULT_BASE_URLS[self.provider]
        self.models_dir = Path(self.models_dir)

    def resolve_model_path(self) -> Path:
        """For llamacpp: turn ``model`` (a path or bare filename) into a path."""
        env_path = os.environ.get("GGUF_MODEL_PATH")
        if env_path:
            return Path(env_path)
        candidate = Path(self.model)
        if candidate.is_absolute() or candidate.parent != Path("."):
            return candidate
        return self.models_dir / self.model


def config_from_env() -> AgentModelConfig:
    """Build a config from GNPY_AGENT_* environment variables."""
    return AgentModelConfig(
        provider=os.getenv("GNPY_AGENT_PROVIDER", DEFAULT_PROVIDER),
        model=os.getenv("GNPY_AGENT_MODEL", ""),
        base_url=os.getenv("GNPY_AGENT_BASE_URL", ""),
        api_key=os.getenv("GNPY_AGENT_API_KEY", "not-needed"),
        temperature=float(os.getenv("GNPY_AGENT_TEMPERATURE", "0.1")),
        num_ctx=int(os.getenv("GNPY_AGENT_NUM_CTX", "8192")),
        n_gpu_layers=int(os.getenv("GNPY_AGENT_N_GPU_LAYERS", "-1")),
        max_tokens=int(os.getenv("GNPY_AGENT_MAX_TOKENS", "2048")),
        verbose=os.getenv("GNPY_AGENT_VERBOSE", "").lower() in ("1", "true", "yes"),
    )


# =============================================================================
# Windows + CUDA: make llama.cpp / CUDA DLLs discoverable before import.
# =============================================================================
_dll_directory_handles: list = []


def add_windows_llama_dll_dirs() -> None:
    """Register llama.cpp/CUDA DLL directories on Windows so llama_cpp imports.

    No-op on non-Windows platforms.
    """
    if os.name != "nt":
        return

    import site
    import sysconfig

    roots = {Path(sysconfig.get_paths().get("purelib", ""))}
    roots.update(Path(p) for p in site.getsitepackages())
    if site.getusersitepackages():
        roots.add(Path(site.getusersitepackages()))

    relative_dirs = [
        Path("bin"),
        Path("llama_cpp/lib"),
        Path("nvidia/cuda_runtime/bin"),
        Path("nvidia/cublas/bin"),
        Path("nvidia/cuda_nvrtc/bin"),
        Path("torch/lib"),
    ]

    for root in roots:
        for relative_dir in relative_dirs:
            dll_dir = root / relative_dir
            if not dll_dir.exists():
                continue
            dll_dir_str = str(dll_dir)
            try:
                _dll_directory_handles.append(os.add_dll_directory(dll_dir_str))
            except (FileNotFoundError, OSError):
                pass
            if dll_dir_str not in os.environ.get("PATH", ""):
                os.environ["PATH"] = dll_dir_str + os.pathsep + os.environ.get("PATH", "")


# =============================================================================
# Chat model factory
# =============================================================================
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

    if cfg.provider == "llamacpp":
        add_windows_llama_dll_dirs()
        try:
            from langchain_community.chat_models import ChatLlamaCpp
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError(
                "langchain-community and llama-cpp-python are required for the "
                "llamacpp provider. See requirements-agent.txt (install a "
                "CUDA-enabled llama-cpp-python build for GPU)."
            ) from exc
        model_path = cfg.resolve_model_path()
        if not model_path.exists():
            raise FileNotFoundError(
                f"GGUF model not found: {model_path}\n"
                "Put a .gguf file in your models folder, set GGUF_MODEL_PATH, or "
                "download one (see agent/models.download_gguf_model)."
            )
        # Catch incomplete downloads early (real GGUFs are tens to thousands of MB).
        size_mb = model_path.stat().st_size / (1024 * 1024)
        if size_mb < 5:
            raise RuntimeError(
                f"GGUF file looks incomplete ({size_mb:.1f} MB): {model_path}. "
                "Re-download the model; the file is likely truncated."
            )
        try:
            return ChatLlamaCpp(
                model_path=str(model_path),
                n_ctx=cfg.num_ctx,
                n_gpu_layers=cfg.n_gpu_layers,
                n_threads=cfg.n_threads,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
                verbose=cfg.verbose,
            )
        except Exception as exc:  # noqa: BLE001 - turn into an actionable message
            raise RuntimeError(
                f"llama.cpp could not load the model ({size_mb:.0f} MB):\n"
                f"  {model_path}\n\n"
                "Common causes and fixes:\n"
                f"  - Not enough VRAM with n_gpu_layers={cfg.n_gpu_layers}. Lower "
                "n_gpu_layers in the sidebar (e.g. 20), or set it to 0 for CPU.\n"
                f"  - n_ctx={cfg.num_ctx} too large for available memory. Try 8192.\n"
                "  - llama-cpp-python too old for this model architecture. Upgrade:\n"
                "      pip install -U llama-cpp-python\n"
                "  - CPU-only wheel installed but GPU offload requested. Reinstall a\n"
                "    CUDA wheel (see requirements-agent.txt) or set n_gpu_layers=0.\n"
                "  - Corrupt/incomplete download. Re-download the .gguf.\n\n"
                "Enable 'Verbose llama.cpp logs' in the sidebar to see the raw "
                f"llama.cpp error in the console.\n\nOriginal error: {exc}"
            ) from exc

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
