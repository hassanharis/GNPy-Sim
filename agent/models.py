"""
Local model auto-detection.

Discovers which models are available for each provider so the UI can offer a
dropdown instead of a free-text field:

  * ``ollama``    - queries the local Ollama server (GET /api/tags)
  * ``openai``    - queries an OpenAI-compatible server (GET {base_url}/models)
  * ``llamacpp``  - scans the local models folder for *.gguf files

All network calls use the stdlib (no extra deps) and fail soft (return []), so
detection never crashes the app when a server is down or unreachable.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from .config import MODELS_DIR


def _http_get_json(url: str, timeout: float = 2.5) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - detection must never raise
        return None


def detect_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """Return installed Ollama model names, or [] if the server is unreachable."""
    data = _http_get_json(base_url.rstrip("/") + "/api/tags")
    if not data:
        return []
    return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))


def detect_openai_models(base_url: str = "http://localhost:8000/v1", api_key: str = "not-needed") -> list[str]:
    """Return model ids served by an OpenAI-compatible endpoint, or []."""
    url = base_url.rstrip("/") + "/models"
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return sorted(m.get("id", "") for m in data.get("data", []) if m.get("id"))


def detect_gguf_models(models_dir: Path | str | None = None) -> list[str]:
    """Return *.gguf filenames found in the local models folder, or []."""
    folder = Path(models_dir) if models_dir else MODELS_DIR
    if not folder.exists():
        return []
    return sorted(p.name for p in folder.glob("*.gguf"))


def detect_models(provider: str, base_url: str = "", api_key: str = "not-needed",
                  models_dir: Path | str | None = None) -> list[str]:
    """Dispatch detection by provider name."""
    provider = (provider or "").lower().strip()
    if provider == "ollama":
        return detect_ollama_models(base_url or "http://localhost:11434")
    if provider == "openai":
        return detect_openai_models(base_url or "http://localhost:8000/v1", api_key)
    if provider == "llamacpp":
        return detect_gguf_models(models_dir)
    return []


def download_gguf_model(repo_id: str, filename: str, models_dir: Path | str | None = None) -> Path:
    """Optionally fetch a GGUF build from Hugging Face into the models folder.

    Requires network access and huggingface_hub; not used in air-gapped setups.
    """
    from huggingface_hub import hf_hub_download

    folder = Path(models_dir) if models_dir else MODELS_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(folder),
        local_dir_use_symlinks=False,
    )
    return Path(path)
